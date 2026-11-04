"""Layout helpers beside brlyt.py and brlan.py: Benzin, adding files to the archive, cloning a picture into tunnel
tiles, and the indirect-texture material that draws the ASCII tunnel (see BUILDING.md)."""
import re
import struct
import subprocess
from pathlib import Path

from wiilib import U8Node

BENZIN = Path(__file__).resolve().parent / "benzin"


def benzin(*args):
    """Run Benzin under wine: 'r' rips a binary to XML, 'm' makes it back."""
    r = subprocess.run(["wine", "BENZIN.EXE", *args], cwd=BENZIN, capture_output=True, text=True)
    out = (r.stdout + r.stderr).strip()
    if r.returncode or "rror" in out:
        raise RuntimeError(f"benzin {args}: {out}")


def add_file(arc, directory, name, data):
    """Append a file at the end of `directory`, fixing every directory's range and parent index."""
    d = arc.find(directory)
    at = arc.nodes[d].last
    for i, nd in enumerate(arc.nodes):
        if not nd.is_dir:
            continue
        if i <= d and nd.last >= at:
            nd.last += 1
        elif i >= at:
            nd.last += 1
            if nd.parent >= at:
                nd.parent += 1
    arc.nodes.insert(at, U8Node(False, name, data))


def add_textures(xml, names):
    block = "".join(f"\n\t\t\t\t\t<name>{n}</name>" for n in names)
    return re.sub(r'(<tag type="txl1">\s*<entries>.*?)(\s*</entries>)', rf"\1{block}\2", xml, count=1, flags=re.S)


def _srt(tag, t):
    x, y, r, sx, sy = t
    return (f"<{tag}><XTrans>{x:.10f}</XTrans><YTrans>{y:.10f}</YTrans><Rotate>{r:.10f}</Rotate>"
            f"<XScale>{sx:.10f}</XScale><YScale>{sy:.10f}</YScale></{tag}>")


def _coordgen(matrix):
    return (f"<CoordGen><tgen_type>GX_TG_MTX2x4</tgen_type><tgen_src>GX_TG_TEX0</tgen_src>"
            f"<MatrixSource>GX_TEXMTX{matrix}</MatrixSource><padding>00</padding></CoordGen>")


# Benzin's labels for the TEV output register and clamp are swapped: "Clamp" holds the register
# (0 = PREV) and "RegisterID" holds the clamp flag.
TILE_STAGE = """<TevStage>
<TextureCoordinate>GX_TEXCOORD0</TextureCoordinate><TextureMap>GX_TEXMAP0</TextureMap>
<Color>GX_COLOR0A0</Color><Padding1>0</Padding1><RasSelect>GX_TEV_SWAP0</RasSelect><TexSelect>GX_TEV_SWAP0</TexSelect>
<TevColorCombinerA>f</TevColorCombinerA><TevColorCombinerB>8</TevColorCombinerB>
<TevColorCombinerC>a</TevColorCombinerC><TevColorCombinerD>f</TevColorCombinerD>
<TevColorScale>0</TevColorScale><TevColorBias>0</TevColorBias><TevColorOp>0</TevColorOp>
<TevColorClamp>0</TevColorClamp><TevColorRegisterID>1</TevColorRegisterID><TevKColorSelect>0c</TevKColorSelect>
<TevAlphaCombinerA>7</TevAlphaCombinerA><TevAlphaCombinerB>4</TevAlphaCombinerB>
<TevAlphaCombinerC>5</TevAlphaCombinerC><TevAlphaCombinerD>7</TevAlphaCombinerD>
<TevAlphaScale>0</TevAlphaScale><TevAlphaBias>0</TevAlphaBias><TevAlphaOp>0</TevAlphaOp>
<TevAlphaClamp>0</TevAlphaClamp><TevAlphaRegisterID>1</TevAlphaRegisterID><TevKAlphaSelect>1c</TevKAlphaSelect>
<IndirectTextureID>00</IndirectTextureID><IndirectTextureFormat>2</IndirectTextureFormat>
<IndirectTextureBias>0</IndirectTextureBias><IndirectTextureMatrixID>1</IndirectTextureMatrixID>
<IndirectTextureWrapS>5</IndirectTextureWrapS><IndirectTextureWrapT>4</IndirectTextureWrapT>
<IndirectTextureAddPrevious>0</IndirectTextureAddPrevious><IndirectTextureUTClod>1</IndirectTextureUTClod>
<IndirectTextureA>0</IndirectTextureA><Padding2>0</Padding2><Padding3>0</Padding3><Padding4>0</Padding4>
</TevStage>"""


def window_srt(c0, r0, cols, rows, map_cols, map_rows):
    """TexSRT that shows cells [c0, c0+cols) x [r0, r0+rows) of a map_cols x map_rows index map.
    NW4R scales about (0.5, 0.5) and then translates, so u' = sx * (u - 0.5) + 0.5 + tx."""
    sx, sy = cols / map_cols, rows / map_rows
    return (c0 / map_cols - 0.5 + 0.5 * sx, r0 / map_rows - 0.5 + 0.5 * sy, 0.0, sx, sy)


def tile_material(name, atlas, index, cols, rows, atlas_size, tile=(16, 32), window=(0.0, 0.0, 0.0, 1.0, 1.0)):
    """Each cell draws the atlas tile its index-map texel names (GX_SetTevIndTile, in layout form)."""
    sx, sy = cols * tile[0] / atlas_size[0], rows * tile[1] / atlas_size[1]
    return (f'<entries name="{name}">'
            '<colors><forecolor r="0" g="0" b="0" a="0" /><backcolor r="255" g="255" b="255" a="255" />'
            '<colorReg3 r="255" g="255" b="255" a="255" />'
            + "".join(f'<tev_k{i} r="ff" g="ff" b="ff" a="ff" />' for i in range(1, 5)) + "</colors>"
            f'<texture name="{atlas}"><wrap_s>GX_CLAMP</wrap_s><wrap_t>GX_CLAMP</wrap_t></texture>'
            f'<texture name="{index}"><wrap_s>GX_CLAMP</wrap_s><wrap_t>GX_CLAMP</wrap_t></texture>'
            + _srt("TextureSRT", (0.5 * (sx - 1), 0.5 * (sy - 1), 0.0, sx, sy))
            + _srt("TextureSRT", window)
            + _coordgen(0) + _coordgen(1)
            + "<ChanControl><ColorMatSource>GX_SRC_VTX</ColorMatSource><AlphaMatSource>GX_SRC_VTX</AlphaMatSource>"
              "<Padding1>00</Padding1><Padding2>00</Padding2></ChanControl>"
            + _srt("IndTextureSRT", (0.0, 0.0, 0.0, float(tile[0]), 0.0))
            + "<IndTextureOrder><TextureCoordinate>GX_TEXCOORD1</TextureCoordinate><TextureMap>GX_TEXMAP1</TextureMap>"
              "<ScaleS>GX_ITS_1</ScaleS><ScaleT>GX_ITS_1</ScaleT></IndTextureOrder>"
            + TILE_STAGE
            + "<AlphaCompare><comp0>GX_ALWAYS</comp0><comp1>GX_ALWAYS</comp1><aop>GX_AOP_AND</aop>"
              "<ref0>00</ref0><ref1>00</ref1></AlphaCompare>"
              "<BlendMode><type>GX_BM_BLEND</type><src_fact>GX_BL_SRCALPHA</src_fact>"
              "<dst_fact>GX_BL_INVSRCALPHA</dst_fact><op>GX_LO_COPY</op></BlendMode>"
            "</entries>")


def tunnel_tiles(split, map_cols, map_rows):
    """(name suffix, c0, r0, cols, rows, window SRT) for each tile of a split tunnel."""
    xs, ys = split
    out = []
    for j, (r0, r1) in enumerate(zip(ys, ys[1:])):
        for i, (c0, c1) in enumerate(zip(xs, xs[1:])):
            out.append((f"{j}{i}", c0, r0, c1 - c0, r1 - r0, window_srt(c0, r0, c1 - c0, r1 - r0, map_cols, map_rows)))
    return out


def clone_pane(x, picture, material, new_picture, new_material, after):
    """Copy a picture and its material under new names, drawn right after the pane `after`."""
    mat = re.search(rf'<entries name="{material}">.*?</entries>', x, re.S).group(0)
    x = x.replace(mat, mat + mat.replace(f'name="{material}"', f'name="{new_material}"'), 1)
    pic = re.search(rf'<tag type="pic1" name="{picture}".*?</tag>', x, re.S).group(0)
    new = pic.replace(f'name="{picture}"', f'name="{new_picture}"').replace(
        f'<material name="{material}" />', f'<material name="{new_material}" />')
    # Benzin's <flag> is NW4R's location-adjust bit: in 16:9 it spreads off-center panes apart.
    new = re.sub(r"<flag>\d+</flag>", "<flag>00</flag>", new, count=1)
    anchor = re.search(rf'<tag type="pic1" name="{after}".*?</tag>', x, re.S).group(0)
    return x.replace(anchor, anchor + "\n\t\t\t" + new, 1)


def replace_material(xml, name, new):
    pattern = rf'<entries name="{name}">.*?</entries>'
    assert len(re.findall(pattern, xml, re.S)) == 1, name
    return re.sub(pattern, lambda m: new, xml, count=1, flags=re.S)


def set_material_texture(xml, material, texture):
    def swap(m):
        return re.sub(r'<texture name="[^"]*">', f'<texture name="{texture}">', m.group(0), count=1)
    return re.sub(rf'<entries name="{material}">.*?</entries>', swap, xml, count=1, flags=re.S)


# What tile_material must come out as, byte for byte, built without Benzin as an independent check.
def expected_tile_bytes(name, atlas_idx, index_idx, cols, rows, atlas_size, tile=(16, 32),
                        window=(0.0, 0.0, 0.0, 1.0, 1.0)):
    sx, sy = cols * tile[0] / atlas_size[0], rows * tile[1] / atlas_size[1]
    out = bytearray(name.encode().ljust(20, b"\0"))
    out += struct.pack(">12h", 0, 0, 0, 0, 255, 255, 255, 255, 255, 255, 255, 255) + b"\xff" * 16
    out += struct.pack(">I", 0x0384A222)
    out += struct.pack(">HBB", atlas_idx, 0, 0) + struct.pack(">HBB", index_idx, 0, 0)
    out += struct.pack(">5f", 0.5 * (sx - 1), 0.5 * (sy - 1), 0.0, sx, sy) + struct.pack(">5f", *window)
    out += bytes([1, 4, 30, 0, 1, 4, 33, 0, 1, 1, 0, 0])
    out += struct.pack(">5f", 0, 0, 0, float(tile[0]), 0)
    out += bytes([1, 1, 0, 0])
    out += bytes.fromhex("000400008ffa0061477500e100" + "08" + "25" + "0a")
    out += bytes([0x77, 0, 0, 0, 1, 4, 5, 3])
    return bytes(out)


def material_bytes(brlyt, name):
    """The raw mat1 entry for `name` in a binary layout."""
    at = brlyt.index(b"mat1")
    count = struct.unpack(">H", brlyt[at + 8:at + 10])[0]
    offs = [struct.unpack(">I", brlyt[at + 12 + 4 * i:at + 16 + 4 * i])[0] for i in range(count)]
    size = struct.unpack(">I", brlyt[at + 4:at + 8])[0]
    ends = offs[1:] + [size]
    for o, e in zip(offs, ends):
        if brlyt[at + o:at + o + 20].rstrip(b"\0").decode() == name:
            return brlyt[at + o:at + e]
    raise KeyError(name)


def texture_index(brlyt, name):
    at = brlyt.index(b"txl1")
    count = struct.unpack(">H", brlyt[at + 8:at + 10])[0]
    base = at + 12
    for i in range(count):
        off = struct.unpack(">I", brlyt[base + 8 * i:base + 8 * i + 4])[0]
        end = brlyt.index(b"\0", base + off)
        if brlyt[base + off:end].decode() == name:
            return i
    raise KeyError(name)
