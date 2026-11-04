"""Build banner.bin: the ASCII tunnel under the outlined GodModeWii logo.

Derived from Tantric's FCE Ultra GX banner (a hand-built layout once bricked the Menu). BackgroundPicture is
hidden and cloned into the tunnel tiles (TunnelNNPicture); LogoPicture is the logo. Every other pane is hidden
and each texture is shrunk to a stub that keeps its name.

    banner.py [--still]    --still: one tunnel frame and no flipbook, for the first Dolphin test
"""
import re
import sys

import numpy as np
from PIL import Image

import art
import brlan as A
import brlyt as L
import config as C
import layout
import tpl
import tunnel
from wiilib import U8, pack_lz77_imd5, unpack_lz77_imd5

DONOR = C.ROOT / "donor/FCE Ultra GX - FCEU [Tantric].wad"
TUNNEL_PANE, TUNNEL_MAT = "BackgroundPicture", "BackgroundMaterial"
TILES = layout.tunnel_tiles(C.TUNNEL_SPLIT, C.TUNNEL_COLS, C.TUNNEL_ROWS)


def tile_names(suffix):
    return f"Tunnel{suffix}Picture", f"Tunnel{suffix}Material"


LOGO_PANE, LOGO_PICTURE, LOGO_MAT = "LogoPane", "LogoPicture", "LogoMaterial"
ATLAS, LOGO = "gmw_atlas.tpl", "gmw_logo.tpl"
TILE = (16, 32)
BUDGET = 600_000


def frame_name(i):
    return f"gmw_t{i:03d}.tpl"


def glyphs():
    return [art.glyph_rows(c) for c in C.TUNNEL_RAMP]


def atlas_image():
    """Each 8x16 glyph blown up to a 16x32 tile (GX can't wrap tiles smaller than 16 texels)."""
    cw, ch = C.CELL
    small = tunnel.atlas(glyphs(), cw, ch)
    big = small.repeat(TILE[1] // ch, 0).repeat(TILE[0] // cw, 1)
    big = np.pad(big, ((0, 0), (0, 256 - big.shape[1]), (0, 0)))
    return Image.fromarray(big)


def index_frames(count):
    times = np.arange(count) / C.TUNNEL_FPS
    return [tunnel.cells(C.TUNNEL_COLS, C.TUNNEL_ROWS, t, C.TUNNEL_CENTER_ROW, *C.TUNNEL_SCALE, C.TUNNEL_PERIOD)
            for t in times]


def donor_banner():
    from wiilib import WAD
    c0 = WAD.load(DONOR).contents[0]
    outer = U8.load(c0[c0.find(U8.MAGIC):])
    return U8.load(unpack_lz77_imd5(outer.get("/meta/banner.bin")))


def ci4_tpl(img, nearest=False):
    """A palettized TPL for art with 16 colors or fewer (transparency included)."""
    rgba = np.array(img.convert("RGBA"))
    colors, idx = np.unique(rgba.reshape(-1, 4), axis=0, return_inverse=True)
    assert len(colors) <= 16, f"{len(colors)} colors won't fit CI4"
    rows = idx.reshape(rgba.shape[:2]).tolist()
    return tpl.build([(rows, tpl.CI4, [tuple(int(v) for v in c) for c in colors], img.size, nearest)])


def tunnel_animation(xml, frames):
    """Replace the donor's tracks with one flipbook of index maps on the tunnel material."""
    xml = re.sub(r"\s*<pane name=.*?</pane>", "", xml, flags=re.S)
    xml = re.sub(r'\s*<timg name="[^"]*" />', "", xml)
    step = 60 // C.TUNNEL_FPS
    names = "".join(f'\n\t\t\t\t<timg name="{frame_name(i)}" />' for i in range(frames))
    keys = "".join(f"<pair><data1>{i * step:.15f}</data1><data2>{i:04x}</data2><padding>0000</padding></pair>"
                   for i in range(frames))
    track = "".join(f'<pane name="{tile_names(t[0])[1]}" type="1"><tag type="RLTP">'
                    f'<entry type1="1" type2="PaletteZero">{keys}</entry></tag></pane>' for t in TILES)
    head = r'<pai1 framesize="\d+" flags="\d+">'
    assert len(re.findall(head, xml)) == 1
    return re.sub(head, lambda m: f'<pai1 framesize="{frames * step}" flags="01">{names}{track}', xml)


def stub_tpl():
    return tpl.build([(Image.new("RGB", (4, 4)), tpl.RGB565, None, (4, 4))])


def main():
    still = "--still" in sys.argv
    arc = donor_banner()
    frames = index_frames(1 if still else int(C.TUNNEL_PERIOD * C.TUNNEL_FPS))
    logo, _ = art.banner_logo()

    (layout.BENZIN / "b_src.brlyt").write_bytes(arc.get("/arc/blyt/banner.brlyt"))
    layout.benzin("r", "b_src.brlyt", "b_src.xmlyt")
    x = (layout.BENZIN / "b_src.xmlyt").read_text()
    x = layout.add_textures(x, [ATLAS, frame_name(0), LOGO])
    after = TUNNEL_PANE
    tile_panes = {}
    for suffix, c0, r0, cols, rows, window in TILES:
        pic, mat = tile_names(suffix)
        x = layout.clone_pane(x, TUNNEL_PANE, TUNNEL_MAT, pic, mat, after)
        x = layout.replace_material(x, mat, layout.tile_material(
            mat, ATLAS, frame_name(0), cols, rows, (256, TILE[1]), TILE, window))
        w, h = cols * C.CELL[0], rows * C.CELL[1]
        tile_panes[pic] = {"translate": (-C.BANNER_W / 2 + c0 * C.CELL[0] + w / 2,
                                         C.BANNER_H / 2 - r0 * C.CELL[1] - h / 2), "size": (w, h)}
        after = pic
    x = layout.set_material_texture(x, LOGO_MAT, LOGO)
    x = L.identity_materials(x, {LOGO_MAT})
    x = L.edit_panes(x, {
        **tile_panes,
        LOGO_PANE: {"translate": (0.0, C.BANNER_H / 2 - (C.TUNNEL_CENTER_ROW * C.CELL[1] + 5))},
        LOGO_PICTURE: {"translate": (0.0, 0.0), "size": logo.size},
    })
    (layout.BENZIN / "b_new.xmlyt").write_text(x)
    layout.benzin("m", "b_new.xmlyt", "b_new.brlyt")
    brlyt = (layout.BENZIN / "b_new.brlyt").read_bytes()
    for suffix, c0, r0, cols, rows, window in TILES:
        mat = tile_names(suffix)[1]
        want = layout.expected_tile_bytes(mat, layout.texture_index(brlyt, ATLAS),
                                          layout.texture_index(brlyt, frame_name(0)),
                                          cols, rows, (256, TILE[1]), TILE, window)
        got = layout.material_bytes(brlyt, mat)
        assert got == want, f"{mat} differs from the reference:\n{got.hex()}\n{want.hex()}"
    arc.replace("/arc/blyt/banner.brlyt", brlyt)

    for name in ("banner_Start", "banner_Loop"):
        (layout.BENZIN / f"a_{name}.brlan").write_bytes(arc.get(f"/arc/anim/{name}.brlan"))
        layout.benzin("r", f"a_{name}.brlan", f"a_{name}.xmlan")
        a = (layout.BENZIN / f"a_{name}.xmlan").read_text()
        if still:
            a = A.drop_panes(a, {n for n in (TUNNEL_PANE, TUNNEL_MAT, LOGO_PANE, LOGO_PICTURE, LOGO_MAT)
                                 if f'<pane name="{n}"' in a})
        else:
            # Start and Loop are the same flipbook, so the hand-off between them can't jump.
            a = tunnel_animation(a, len(frames))
        (layout.BENZIN / f"a_{name}_new.xmlan").write_text(a)
        layout.benzin("m", f"a_{name}_new.xmlan", f"a_{name}_new.brlan")
        arc.replace(f"/arc/anim/{name}.brlan", (layout.BENZIN / f"a_{name}_new.brlan").read_bytes())

    for _, path in list(arc.paths()):
        if path.endswith(".tpl"):
            arc.replace(path, stub_tpl())
    a_img = atlas_image()
    layout.add_file(arc, "/arc/timg", ATLAS, ci4_tpl(a_img, nearest=True))
    layout.add_file(arc, "/arc/timg", LOGO, ci4_tpl(logo))
    for i, f in enumerate(frames):
        rows = f.tolist()
        layout.add_file(arc, "/arc/timg", frame_name(i),
                        tpl.build([(rows, tpl.I4, None, (C.TUNNEL_COLS, C.TUNNEL_ROWS), True)]))

    problems = arc.check_tree()
    assert not problems, problems
    raw = arc.to_bytes()
    C.OUT.mkdir(parents=True, exist_ok=True)
    (C.OUT / "banner.bin").write_bytes(pack_lz77_imd5(raw))
    Image.fromarray(tunnel.render(frames[0], np.array(a_img), *TILE)).resize(
        (C.BANNER_W, C.TUNNEL_ROWS * C.CELL[1]), Image.NEAREST).save(C.OUT / "banner-frame0.png")
    print(f"banner.bin: {len(frames)} tunnel frames, {len(raw):,} bytes uncompressed "
          f"({len(raw) / BUDGET:.0%} of the {BUDGET:,} share)")
    assert len(raw) <= BUDGET, "too much banner memory slows and then freezes the Wii Menu"
    export_layout({
        "b_new.brlyt": "banner.brlyt", "b_new.xmlyt": "banner.xmlyt",
        **{f"a_{n}_new.{e}": f"{n}.{e}"
           for n in ("banner_Start", "banner_Loop") for e in ("brlan", "xmlan")},
    })


def export_layout(names):
    """Keep the finished layouts and their Benzin XML in layout/, as the other channels do."""
    (C.ROOT / "layout").mkdir(exist_ok=True)
    for src, dst in names.items():
        (C.ROOT / "layout" / dst).write_bytes((layout.BENZIN / src).read_bytes())


if __name__ == "__main__":
    main()
