"""Build icon.bin: the logo scrolls right to left over a little tunnel, then GodModeWii's drive list (six drives,
four rows shown) fades in and the cursor works down it, then it fades back to the tunnel. One 10 s loop.

Derived from Tantric's FCE Ultra GX icon. Its BackgroundPicture is cloned into the tunnel tiles and its other
pictures become the logo, drive list and cursor bar; a title bar and a black footer (hiding the next drive row)
are added on top. Drawn 176 wide so a 16:9 Menu sees no bars; everything readable stays in the middle 128.
"""
import re

import numpy as np
from PIL import Image

import art
import brlan as A
import brlyt as L
import config as C
import layout
import tpl
import tunnel
from banner import ci4_tpl, export_layout, stub_tpl
from wiilib import U8, WAD, pack_lz77_imd5, unpack_lz77_imd5

DONOR = C.ROOT / "donor/FCE Ultra GX - FCEU [Tantric].wad"
ICON_CAP = 0x19000
FPS = 60
LOOP = int(C.ICON_LOOP * FPS)
MARQUEE_END, FADE = 270, 30
DRIVES_START, DRIVES_END = MARQUEE_END + FADE, LOOP - FADE
CURSOR_STEP = 36
ROW = 16
# The Menu shows about rows 8 to 88 of the icon (a Wii U cut half of a 16-row title bar at the top and of the
# last drive row at the bottom), so the title bar's text sits at 8 and four drive rows fill 24 to 88.
HEAD_H, HEAD_TEXT_Y, VISIBLE_ROWS = 24, 8, 4
SIDE = (C.ICON_W - 128) // 2
# The text column, centered, so a 4:3 Menu shows it with a margin on both sides.
TEXT_X = (C.ICON_W - 8 * max(len(d) for d in art.DRIVES)) // 2
# Hides the top of the fifth drive row, which a Wii shows a pixel or two of under the fourth.
FOOT_Y = HEAD_H + ROW * VISIBLE_ROWS
TILE = (16, 32)
TUNNEL_FPS = 12

TUNNEL_PIC, TUNNEL_MAT = "BackgroundPicture", "BackgroundMaterial"
TILES = layout.tunnel_tiles(C.ICON_SPLIT, C.ICON_W // C.ICON_CELL[0], C.ICON_H // C.ICON_CELL[1])


def tile_names(suffix):
    return f"Tunnel{suffix}Picture", f"Tunnel{suffix}Material"


LOGO_PANE, LOGO_PIC, LOGO_MAT = "Goomba00Pane", "Goomba00Picture", "Goomba00Material"
LIST_PANE, LIST_PIC, LIST_MAT = "Mario00Pane", "Mario00Picture", "Mario00Material"
BAR_PANE, BAR_PIC, BAR_MAT = "Logo00Pane", "Logo00Picture", "Logo00Material"
HEAD_PIC, HEAD_MAT = "HeaderPicture", "HeaderMaterial"
FOOT_PIC, FOOT_MAT = "FooterPicture", "FooterMaterial"
ATLAS, LOGO, LIST, HEAD, FOOT = "gmw_iatlas.tpl", "gmw_ilogo.tpl", "gmw_ilist.tpl", "gmw_ihead.tpl", "gmw_ifoot.tpl"


def frame_name(i):
    return f"gmw_i{i:02d}.tpl"


def bar_name(i):
    return f"gmw_ibar{i}.tpl"


def tunnel_frames():
    count = int(C.ICON_PERIOD * TUNNEL_FPS)
    cols, rows = C.ICON_W // C.ICON_CELL[0], C.ICON_H // C.ICON_CELL[1]
    return [tunnel.cells(cols, rows, i / TUNNEL_FPS, rows / 2, 28, 14, C.ICON_PERIOD) for i in range(count)]


def atlas_image():
    cw, ch = C.ICON_CELL
    small = tunnel.atlas(tunnel.scan_glyphs(cw, ch), cw, ch)
    big = small.repeat(TILE[1] // ch, 0).repeat(TILE[0] // cw, 1)
    return Image.fromarray(np.pad(big, ((0, 0), (0, 256 - big.shape[1]), (0, 0))))


def strip(text, fg, bg, height=ROW, text_y=0):
    im = Image.new("RGBA", (C.ICON_W, height), bg + (255,))
    im.alpha_composite(art.text_image([text], fg), (TEXT_X, text_y))
    return im


def logo_image():
    lettering = art.hbc_lettering(2)
    box = Image.new("RGBA", (lettering.width + 8, lettering.height + 8), (0, 0, 0, 255))
    box.alpha_composite(lettering, (4, 4))
    rgba = np.array(box)
    lit = rgba[..., 1] >= 128
    rgba[..., :3] = np.where(lit[..., None], (0, 239, 255), (0, 0, 0))
    return Image.fromarray(rgba)


# One blank row under the last drive: scrolled to the end, the list would otherwise stop 8 px short
# of the icon's bottom edge and let the tunnel show through.
LIST_ROWS = len(art.DRIVES) + 1


def list_image():
    im = Image.new("RGBA", (C.ICON_W, ROW * LIST_ROWS), (0, 0, 0, 255))
    for i, d in enumerate(art.DRIVES):
        im.alpha_composite(art.text_image([d], art.GRAY), (TEXT_X, i * ROW))
    return im


# The first and last drives hold equally long; the moves between them stay CURSOR_STEP apart.
END_HOLD = (DRIVES_END - DRIVES_START - CURSOR_STEP * (len(art.DRIVES) - 2)) // 2


def cursor_at(frame):
    if frame < DRIVES_START + END_HOLD:
        return 0
    return min(len(art.DRIVES) - 1, 1 + (frame - DRIVES_START - END_HOLD) // CURSOR_STEP)


def scroll_for(cursor):
    return max(0, min(cursor - (VISIBLE_ROWS - 1), len(art.DRIVES) - VISIBLE_ROWS))


def layout_y(center_px):
    return C.ICON_H / 2 - center_px


def steps(values):
    """Hermite keys that jump between held values: (frame, value) changes, one frame per jump."""
    keys, last = [], None
    for f, v in values:
        if last is not None and v != last and f > 0:
            keys.append((f - 1, last, 0.0))
        if v != last:
            keys.append((f, v, 0.0))
        last = v
    return keys


def add_bar_copy(x, pic_name, mat_name):
    """A copy of the cursor bar's picture and material, drawn last."""
    mat = re.search(rf'<entries name="{BAR_MAT}">.*?</entries>', x, re.S).group(0)
    x = x.replace(mat, mat + mat.replace(f'name="{BAR_MAT}"', f'name="{mat_name}"'), 1)
    pic = re.search(rf'<tag type="pic1" name="{BAR_PIC}".*?</tag>', x, re.S).group(0)
    new = pic.replace(f'name="{BAR_PIC}"', f'name="{pic_name}"').replace(
        f'<material name="{BAR_MAT}" />', f'<material name="{mat_name}" />')
    closing = '<tag type="pae1" />\n\t\t\t<tag type="grp1"'
    assert x.count(closing) == 1
    return x.replace(closing, new + "\n\t\t\t" + closing)


def animation(logo_w, n_frames):
    out_x = C.ICON_W / 2 + logo_w / 2
    speed = -2 * out_x / MARQUEE_END
    logo = [(0, out_x, speed), (MARQUEE_END, -out_x, speed), (MARQUEE_END + 1, -out_x, 0.0), (LOOP - 1, -out_x, 0.0)]
    fade = A.smooth([(0, 0), (MARQUEE_END, 0), (DRIVES_START, 255), (DRIVES_END, 255), (LOOP - 1, 0)])

    cursor = [(f, cursor_at(f)) for f in range(LOOP)]
    list_y = steps([(f, layout_y(HEAD_H + ROW * LIST_ROWS / 2 - ROW * scroll_for(c))) for f, c in cursor])
    bar_y = steps([(f, layout_y(HEAD_H + ROW * (c - scroll_for(c)) + ROW / 2)) for f, c in cursor])

    step = FPS // TUNNEL_FPS
    tunnel_keys = "".join(f"<pair><data1>{f:.15f}</data1><data2>{(f // step) % n_frames:04x}</data2>"
                          f"<padding>0000</padding></pair>" for f in range(0, LOOP, step))
    names = [frame_name(i) for i in range(n_frames)] + [bar_name(i) for i in range(len(art.DRIVES))]
    moves = [0] + [f for f in range(1, LOOP) if cursor_at(f) != cursor_at(f - 1)]
    bar_keys = "".join(f"<pair><data1>{f:.15f}</data1><data2>{n_frames + cursor_at(f):04x}</data2>"
                       f"<padding>0000</padding></pair>" for f in moves)

    rltp = ("".join(f'\t\t\t\t<pane name="{tile_names(t[0])[1]}" type="1"><tag type="RLTP">'
                    f'<entry type1="1" type2="PaletteZero">{tunnel_keys}</entry></tag></pane>\n' for t in TILES)
            + f'\t\t\t\t<pane name="{BAR_MAT}" type="1"><tag type="RLTP"><entry type1="0" type2="PaletteZero">'
            f'{bar_keys}</entry></tag></pane>')

    panes = [
        A.pane(LOGO_PIC, [("RLPA", [(A.X_TRANS, logo)])]),
        A.pane(LIST_PIC, [("RLPA", [(A.Y_TRANS, list_y)]), ("RLVC", [(A.PANE_ALPHA, fade)])]),
        A.pane(BAR_PIC, [("RLPA", [(A.Y_TRANS, bar_y)]), ("RLVC", [(A.PANE_ALPHA, fade)])]),
        A.pane(HEAD_PIC, [("RLVC", [(A.PANE_ALPHA, fade)])]),
        A.pane(FOOT_PIC, [("RLVC", [(A.PANE_ALPHA, fade)])]),
        rltp,
    ]

    doc = A.document(LOOP, panes)
    timgs = "".join(f'\n\t\t\t\t<timg name="{n}" />' for n in names)
    return re.sub(r'(<pai1 framesize="\d+" flags="\d+">)', lambda m: m.group(1) + timgs, doc, count=1)


def donor_icon():
    c0 = WAD.load(DONOR).contents[0]
    outer = U8.load(c0[c0.find(U8.MAGIC):])
    return U8.load(unpack_lz77_imd5(outer.get("/meta/icon.bin")))


def main():
    arc = donor_icon()
    frames = tunnel_frames()
    logo, lst = logo_image(), list_image()
    bars = [strip(d, art.WHITE, art.TEAL) for d in art.DRIVES]
    head = strip("GodModeWii", art.WHITE, art.NAVY, HEAD_H, HEAD_TEXT_Y)
    foot = Image.new("RGBA", (C.ICON_W, C.ICON_H - FOOT_Y), (0, 0, 0, 255))

    (layout.BENZIN / "i_src.brlyt").write_bytes(arc.get("/arc/blyt/icon.brlyt"))
    layout.benzin("r", "i_src.brlyt", "i_src.xmlyt")
    x = (layout.BENZIN / "i_src.xmlyt").read_text()
    x = add_bar_copy(x, HEAD_PIC, HEAD_MAT)
    x = add_bar_copy(x, FOOT_PIC, FOOT_MAT)
    x = layout.add_textures(x, [ATLAS, frame_name(0), LOGO, LIST, bar_name(0), HEAD, FOOT])
    cols, rows = C.ICON_W // C.ICON_CELL[0], C.ICON_H // C.ICON_CELL[1]
    after, tile_panes = TUNNEL_PIC, {}
    for suffix, c0, r0, tc, tr, window in TILES:
        pic, mat = tile_names(suffix)
        x = layout.clone_pane(x, TUNNEL_PIC, TUNNEL_MAT, pic, mat, after)
        x = layout.replace_material(x, mat, layout.tile_material(
            mat, ATLAS, frame_name(0), tc, tr, (256, TILE[1]), TILE, window))
        w, h = tc * C.ICON_CELL[0], tr * C.ICON_CELL[1]
        tile_panes[pic] = {"translate": (-C.ICON_W / 2 + c0 * C.ICON_CELL[0] + w / 2,
                                         C.ICON_H / 2 - r0 * C.ICON_CELL[1] - h / 2), "size": (w, h)}
        after = pic
    for mat, tex in ((LOGO_MAT, LOGO), (LIST_MAT, LIST), (BAR_MAT, bar_name(0)), (HEAD_MAT, HEAD), (FOOT_MAT, FOOT)):
        x = layout.set_material_texture(x, mat, tex)
    x = L.identity_materials(x, {LOGO_MAT, LIST_MAT, BAR_MAT, HEAD_MAT, FOOT_MAT})
    centered = {"translate": (0.0, 0.0), "scale": (1.0, 1.0)}
    x = L.edit_panes(x, {
        **tile_panes,
        LOGO_PANE: centered, LIST_PANE: centered, BAR_PANE: centered,
        LOGO_PIC: {"translate": (C.ICON_W / 2 + logo.width / 2, 0.0), "size": logo.size},
        LIST_PIC: {"translate": (0.0, layout_y(HEAD_H + lst.height / 2)), "size": lst.size, "alpha": "00"},
        BAR_PIC: {"translate": (0.0, layout_y(HEAD_H + ROW / 2)), "size": bars[0].size, "alpha": "00"},
        HEAD_PIC: {"translate": (0.0, layout_y(HEAD_H / 2)), "size": head.size, "alpha": "00"},
        FOOT_PIC: {"translate": (0.0, layout_y((FOOT_Y + C.ICON_H) / 2)), "size": foot.size, "alpha": "00"},
    })
    (layout.BENZIN / "i_new.xmlyt").write_text(x)
    layout.benzin("m", "i_new.xmlyt", "i_new.brlyt")
    brlyt = (layout.BENZIN / "i_new.brlyt").read_bytes()
    for suffix, c0, r0, tc, tr, window in TILES:
        mat = tile_names(suffix)[1]
        want = layout.expected_tile_bytes(mat, layout.texture_index(brlyt, ATLAS),
                                          layout.texture_index(brlyt, frame_name(0)),
                                          tc, tr, (256, TILE[1]), TILE, window)
        assert layout.material_bytes(brlyt, mat) == want, f"icon {mat} differs from the reference"
    arc.replace("/arc/blyt/icon.brlyt", brlyt)

    (layout.BENZIN / "i_new.xmlan").write_text(animation(logo.width, len(frames)))
    layout.benzin("m", "i_new.xmlan", "i_new.brlan")
    arc.replace("/arc/anim/icon.brlan", (layout.BENZIN / "i_new.brlan").read_bytes())

    for _, path in list(arc.paths()):
        if path.endswith(".tpl"):
            arc.replace(path, stub_tpl())
    layout.add_file(arc, "/arc/timg", ATLAS, ci4_tpl(atlas_image(), nearest=True))
    for name, img in ((LOGO, logo), (LIST, lst), (HEAD, head), (FOOT, foot)):
        layout.add_file(arc, "/arc/timg", name, ci4_tpl(img))
    for i, b in enumerate(bars):
        layout.add_file(arc, "/arc/timg", bar_name(i), ci4_tpl(b))
    for i, f in enumerate(frames):
        layout.add_file(arc, "/arc/timg", frame_name(i), tpl.build([(f.tolist(), tpl.I4, None, (cols, rows), True)]))

    problems = arc.check_tree()
    assert not problems, problems
    raw = arc.to_bytes()
    (C.OUT / "icon.bin").write_bytes(pack_lz77_imd5(raw))
    print(f"icon.bin: {len(frames)} tunnel frames, {len(raw):,} bytes uncompressed "
          f"({len(raw) / ICON_CAP:.0%} of the {ICON_CAP:,}-byte cap)")
    assert len(raw) <= ICON_CAP, "an icon over the cap crashes the Wii Menu right after Health and Safety"
    export_layout({"i_new.brlyt": "icon.brlyt", "i_new.xmlyt": "icon.xmlyt",
                   "i_new.brlan": "icon.brlan", "i_new.xmlan": "icon.xmlan"})


if __name__ == "__main__":
    main()
