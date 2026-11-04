"""TPL texture encoder for the GX formats this project needs.

GX stores textures in tiles. Tile size depends on the format:
  RGB565 / RGB5A3 : 4x4, 2 bytes per pixel
  RGBA8           : 4x4, stored as two 32-byte halves (AR block, then GB block)
  CI8             : 8x4, 1 byte per pixel
  CI4             : 8x8, 4 bits per pixel
  I4 / I8 / IA4   : 8x8 / 8x4 / 8x4, raw intensity values (IA4 keeps alpha in the high nibble)
Palette entries are RGB5A3.
"""

import struct

MAGIC = 0x0020AF30
I4, I8, IA4, IA8, RGB565, RGB5A3, RGBA8, CI4, CI8 = 0, 1, 2, 3, 4, 5, 6, 8, 9
TILE = {RGB565: (4, 4), RGB5A3: (4, 4), RGBA8: (4, 4), CI8: (8, 4), CI4: (8, 8),
        I8: (8, 4), I4: (8, 8), IA8: (4, 4), IA4: (8, 4)}


def _enc_rgb565(r, g, b):
    return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)


def _enc_rgb5a3(r, g, b, a):
    if a >= 0xE0:                                   # opaque -> 1rrrrrgggggbbbbb
        return 0x8000 | ((r >> 3) << 10) | ((g >> 3) << 5) | (b >> 3)
    return ((a >> 5) << 12) | ((r >> 4) << 8) | ((g >> 4) << 4) | (b >> 4)


def _tiles(w, h, tw, th):
    for by in range(0, h, th):
        for bx in range(0, w, tw):
            yield bx, by


def encode(img, fmt, palette=None, size=None):
    """Return (texture_bytes, palette_bytes, num_palette_entries).

    For CI4/CI8, `img` is an index map (list of rows) and `size` is required,
    since a plain list has no .size attribute.
    """
    w, h = size if size is not None else img.size
    tw, th = TILE[fmt]
    if fmt in (CI4, CI8):
        assert palette is not None, "palettized formats need a palette"
        idx = img
        out = bytearray()
        for bx, by in _tiles(w, h, tw, th):
            if fmt == CI8:
                for y in range(by, by + th):
                    for x in range(bx, bx + tw):
                        out.append(idx[y][x] if y < h and x < w else 0)
            else:
                for y in range(by, by + th):
                    for x in range(bx, bx + tw, 2):
                        hi = idx[y][x] if y < h and x < w else 0
                        lo = idx[y][x + 1] if y < h and x + 1 < w else 0
                        out.append((hi << 4) | lo)
        pal = bytearray()
        for (r, g, b, a) in palette:
            pal += struct.pack(">H", _enc_rgb5a3(r, g, b, a))
        return bytes(out), bytes(pal), len(palette)

    if fmt in (I4, I8):
        # `img` is a list of rows of raw values, like the CI index maps.
        out = bytearray()
        for bx, by in _tiles(w, h, tw, th):
            vals = [img[y][x] if y < h and x < w else 0
                    for y in range(by, by + th) for x in range(bx, bx + tw)]
            out += bytes(vals) if fmt == I8 else bytes(vals[i] << 4 | vals[i + 1] for i in range(0, len(vals), 2))
        return bytes(out), b"", 0
    if fmt == IA4:
        px = img.convert("LA").load()
        out = bytearray()
        for bx, by in _tiles(w, h, tw, th):
            for y in range(by, by + th):
                for x in range(bx, bx + tw):
                    lum, a = px[x, y] if x < w and y < h else (0, 0)
                    out.append((a >> 4) << 4 | lum >> 4)
        return bytes(out), b"", 0

    px = img.convert("RGBA").load()
    out = bytearray()
    if fmt == RGBA8:
        for bx, by in _tiles(w, h, tw, th):
            ar, gb = bytearray(), bytearray()
            for y in range(by, by + 4):
                for x in range(bx, bx + 4):
                    r, g, b, a = (px[min(x, w - 1), min(y, h - 1)]
                                  if (x < w and y < h) else (0, 0, 0, 0))
                    ar += bytes((a, r))
                    gb += bytes((g, b))
            out += ar + gb
    else:
        for bx, by in _tiles(w, h, tw, th):
            for y in range(by, by + th):
                for x in range(bx, bx + tw):
                    if x < w and y < h:
                        r, g, b, a = px[x, y]
                    else:
                        r = g = b = a = 0
                    v = _enc_rgb565(r, g, b) if fmt == RGB565 else _enc_rgb5a3(r, g, b, a)
                    out += struct.pack(">H", v)
    return bytes(out), b"", 0


def build(textures):
    """textures: list of (image_or_indexmap, fmt, palette_or_None, size[, nearest]).

    Layout matches the stock TPLs: header, texture table, texture headers,
    palette headers, then palette data and texture data (32-byte aligned).
    """
    n = len(textures)
    hdr = struct.pack(">III", MAGIC, n, 12)
    table_off = 12
    texhdr_off = table_off + n * 8
    npal_tex = sum(1 for t in textures if t[1] in (CI4, CI8))
    palhdr_off = texhdr_off + n * 0x20
    cur = palhdr_off + npal_tex * 0x0C

    enc = []
    for img, fmt, pal, size, *rest in textures:
        e, p, np_ = encode(img, fmt, pal, size)
        enc.append((e, p, np_, fmt, size, bool(rest and rest[0])))

    def align(x, a=32):
        return (x + a - 1) // a * a

    pal_offs, tex_offs = [], []
    for e, p, np_, fmt, size, nearest in enc:
        if p:
            cur = align(cur)
            pal_offs.append(cur)
            cur += len(p)
        else:
            pal_offs.append(0)
    for e, p, np_, fmt, size, nearest in enc:
        cur = align(cur)
        tex_offs.append(cur)
        cur += len(e)

    out = bytearray(b"\0" * cur)
    out[0:12] = hdr
    pi = 0
    for i, (e, p, np_, fmt, size, nearest) in enumerate(enc):
        th = texhdr_off + i * 0x20
        ph = (palhdr_off + pi * 0x0C) if p else 0
        struct.pack_into(">II", out, table_off + i * 8, th, ph)
        w, h = size
        # wrap S/T clamp; min/mag filter 0 nearest, 1 linear
        filt = 0 if nearest else 1
        struct.pack_into(">HHIIIIIIfBBBB", out, th, h, w, fmt, tex_offs[i],
                         0, 0, filt, filt, 0.0, 0, 0, 0, 0)
        if p:
            struct.pack_into(">HHII", out, ph, np_, 0, 2, pal_offs[i])  # palette fmt 2 = RGB5A3
            out[pal_offs[i]:pal_offs[i] + len(p)] = p
            pi += 1
        out[tex_offs[i]:tex_offs[i] + len(e)] = e
    return bytes(out)
