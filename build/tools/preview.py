"""Render the reference stills from the same frames and keyframes the WAD carries:
banner/banner.png, banner/logo.png, icon/icon.png and splash/splash.png. preview/ holds Dolphin captures instead.
"""
from PIL import Image

import art
import banner as B
import config as C
import icon as I
import tunnel


def smoothstep_keys(keys, f):
    """A Menu hermite track whose tangents are all zero."""
    for (f0, v0), (f1, v1) in zip(keys, keys[1:]):
        if f0 <= f <= f1:
            t = (f - f0) / (f1 - f0)
            return v0 + (v1 - v0) * t * t * (3 - 2 * t)
    return keys[-1][1]


def banner_frame(index, logo):
    tiles = tunnel.atlas(B.glyphs(), *C.CELL)
    im = Image.new("RGBA", (C.BANNER_W, C.BANNER_H), (0, 0, 0, 255))
    im.paste(Image.fromarray(tunnel.render(index, tiles, *C.CELL)).convert("RGBA"), (0, 0))
    center_y = C.TUNNEL_CENTER_ROW * C.CELL[1] + 5
    im.alpha_composite(logo, (round(C.BANNER_W / 2 - logo.width / 2), round(center_y - logo.height / 2)))
    return im


def icon_frame(f, frames, logo, lst, bars, head):
    cols = C.ICON_W // C.ICON_CELL[0]
    tiles = tunnel.atlas(tunnel.scan_glyphs(*C.ICON_CELL), *C.ICON_CELL)
    im = Image.fromarray(tunnel.render(frames[(f // 5) % len(frames)], tiles, *C.ICON_CELL)).convert("RGBA")
    assert im.width == cols * C.ICON_CELL[0]
    out_x = C.ICON_W / 2 + logo.width / 2
    x = out_x - 2 * out_x * min(1.0, f / I.MARQUEE_END)
    im.alpha_composite(logo, (round(C.ICON_W / 2 + x - logo.width / 2), round(C.ICON_H / 2 - logo.height / 2)))
    alpha = smoothstep_keys([(0, 0), (I.MARQUEE_END, 0), (I.DRIVES_START, 255), (I.DRIVES_END, 255),
                             (I.LOOP - 1, 0)], f)
    if alpha > 0:
        cursor = I.cursor_at(f)
        scroll = I.scroll_for(cursor)
        drives = Image.new("RGBA", im.size)
        drives.alpha_composite(lst, (0, I.HEAD_H - I.ROW * scroll))
        drives.alpha_composite(bars[cursor], (0, I.HEAD_H + I.ROW * (cursor - scroll)))
        drives.alpha_composite(head, (0, 0))
        drives.paste((0, 0, 0, 255), (0, I.FOOT_Y, C.ICON_W, C.ICON_H))
        drives.putalpha(drives.getchannel("A").point(lambda a: a * alpha // 255))
        im.alpha_composite(drives)
    return im




def main():
    root = C.ROOT
    logo, _ = art.banner_logo()
    still = banner_frame(B.index_frames(1)[0], logo).convert("RGB")
    still.save(root / "banner/banner.png")
    logo.save(root / "banner/logo.png")

    frames = I.tunnel_frames()
    parts = (I.logo_image(), I.list_image(), [I.strip(d, art.WHITE, art.TEAL) for d in art.DRIVES],
             I.strip("GodModeWii", art.WHITE, art.NAVY, I.HEAD_H, I.HEAD_TEXT_Y))
    icon_frame(I.MARQUEE_END // 2, frames, *parts).convert("RGB").save(root / "icon/icon.png")

    # GodModeWii's console on a 640x480 screen: 76x28 cells inside a 16 px margin, logo at row 8, column 7.
    splash = Image.new("RGBA", (640, 480), (0, 0, 0, 255))
    splash.alpha_composite(art.text_image(art.LOGO, art.CYAN), (16 + 7 * 8, 16 + 8 * 16))
    splash.convert("RGB").save(root / "splash/splash.png")


if __name__ == "__main__":
    main()
