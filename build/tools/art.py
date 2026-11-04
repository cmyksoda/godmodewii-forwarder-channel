"""The channel's pictures, drawn in libogc's 8x16 console font: the banner logo and the icon's parts."""
from pathlib import Path

import numpy as np
from PIL import Image

from config import ROOT

FONT = (Path(__file__).resolve().parent / "console_font_8x16.bin").read_bytes()

# GodModeWii's own splash (source/ui.c, ui_splash).
LOGO = [
    "  ____           _ __  __           _      __        ___ _ ",
    " / ___| ___   __| |  \\/  | ___   __| | ___ \\ \\      / (_|_)",
    "| |  _ / _ \\ / _` | |\\/| |/ _ \\ / _` |/ _ \\ \\ \\ /\\ / /| | |",
    "| |_| | (_) | (_| | |  | | (_) | (_| |  __/  \\ V  V / | | |",
    " \\____|\\___/ \\__,_|_|  |_|\\___/ \\__,_|\\___|   \\_/\\_/  |_|_|",
]
CYAN = (25, 248, 248)
NAVY = (2, 0, 112)
TEAL = (12, 124, 123)
GRAY = (204, 204, 204)
WHITE = (255, 255, 255)
# No "[SEEP] seeprom:/": at 16 characters it fills all 128 px a 4:3 Menu shows of the icon.
DRIVES = ["[SD  ] sd:/", "[USB1] usb1:/", "[NAND] nand:/", "[DISC] disc:/", "[MCA ] mca:/", "[KEYS] keys:/"]

OUTLINE = 7
FILL_GAP = 12


def glyph_rows(ch):
    """One console-font character as 16 rows of 8 bits, the left pixel in bit 7."""
    return list(FONT[ord(ch) * 16:ord(ch) * 16 + 16])


def text_mask(lines):
    """True where the console font lights a pixel."""
    cols = max(len(line) for line in lines)
    mask = np.zeros((len(lines) * 16, cols * 8), bool)
    for row, line in enumerate(lines):
        for col, ch in enumerate(line):
            glyph = FONT[ord(ch) * 16:ord(ch) * 16 + 16]
            for y, bits in enumerate(glyph):
                for x in range(8):
                    mask[row * 16 + y, col * 8 + x] = bits >> (7 - x) & 1
    return mask


def _shift_or(mask, offsets):
    h, w = mask.shape
    out = np.zeros_like(mask)
    for dy, dx in offsets:
        out[max(0, dy):h + min(0, dy), max(0, dx):w + min(0, dx)] |= \
            mask[max(0, -dy):h - max(0, dy), max(0, -dx):w - max(0, dx)]
    return out


def _square(r):
    return [(dy, dx) for dy in range(-r, r + 1) for dx in range(-r, r + 1)]


def _cut(r):
    return [(dy, dx) for dy, dx in _square(r) if abs(dx) + abs(dy) <= r * 1.4]


def banner_logo():
    """The splash lettering filled black, with a 7 px cut-corner outline, as an RGBA image."""
    strokes = np.pad(text_mask(LOGO), FILL_GAP + OUTLINE)
    filled = ~_shift_or(~_shift_or(strokes, _square(FILL_GAP)), _square(FILL_GAP))
    backing = _shift_or(filled, _cut(OUTLINE))
    ys, xs = np.nonzero(backing)
    top, left = ys.min(), xs.min()
    backing = backing[top:ys.max() + 1, left:xs.max() + 1]
    strokes = strokes[top:ys.max() + 1, left:xs.max() + 1]
    rgba = np.zeros(backing.shape + (4,), np.uint8)
    rgba[backing] = (0, 0, 0, 255)
    rgba[strokes] = CYAN + (255,)
    return Image.fromarray(rgba), (FILL_GAP + OUTLINE - left, FILL_GAP + OUTLINE - top)


def hbc_lettering(scale=2):
    """The lettering from GodModeWii's Homebrew Channel icon, cut out of its black."""
    im = Image.open(ROOT / "icon/hbc-icon.png").convert("RGB").crop((1, 16, 127, 32))
    rgba = np.array(im.convert("RGBA"))
    rgba[rgba[..., 1] <= 40] = 0
    return Image.fromarray(rgba).resize((im.width * scale, im.height * scale), Image.NEAREST)


def text_image(lines, color):
    """Console text in one color on transparent."""
    mask = text_mask(lines)
    rgba = np.zeros(mask.shape + (4,), np.uint8)
    rgba[mask] = tuple(color) + (255,)
    return Image.fromarray(rgba)
