"""The ASCII texture tunnel as per-cell states, ported from ascii-magic-art's tunnel.js (MIT, see tunnel.LICENSE).

Each cell gets one of 15 states: 0 is blank, then 1-7 are the shade glyphs on tone A and 8-14 on
tone B. A frame is a small index map, and a glyph atlas holds the pre-colored tile for each state.
"""
import numpy as np

PALETTE_A = ["#000004", "#02004a", "#020070", "#2a2ab8", "#7070f0"]
PALETTE_B = ["#000606", "#033a39", "#0c7c7b", "#19c8c8", "#a8ffff"]
LEVELS = 7


def _hex(h):
    return [int(h[i:i + 2], 16) for i in (1, 3, 5)]


def gradient(stops, n):
    c = np.array([_hex(s) for s in stops], float)
    p = np.linspace(0, len(c) - 1, n)
    j = np.minimum(len(c) - 2, p.astype(int))
    f = (p - j)[:, None]
    return np.round(c[j] + (c[j + 1] - c[j]) * f).astype(np.uint8)


def tone_colors():
    """Seven colors per tone: the page's 14-step gradient, two steps per glyph level."""
    a, b = gradient(PALETTE_A, 14), gradient(PALETTE_B, 14)
    return a[1::2], b[1::2]


def cells(cols, rows, t, cy_base, sx, sy, period):
    """State of every cell at time t. Sway and spin are tuned so the frame at t + period equals t."""
    w = 2 * np.pi / period
    cx = cols / 2 + np.sin(w * t) * cols * 0.12
    cy = cy_base + np.cos(w * t) * sy * 0.2
    y, x = np.mgrid[0:rows, 0:cols].astype(float)
    dx, dy = (x - cx) / sx, (y - cy) / sy
    r = np.sqrt(dx * dx + dy * dy) + 1e-4
    u = np.arctan2(dy, dx) / (2 * np.pi) * 24 + t * (2 / period) * round(1.2 * period / 2)
    v = 2.6 / r + t * (2 / period) * round(4 * period / 2)
    iu, iv = np.floor(u), np.floor(v)
    check = (iu + iv).astype(int) & 1
    fu, fv = u - iu, v - iv
    edge = np.where(np.minimum.reduce([fu, 1 - fu, fv, 1 - fv]) < 0.08, 0.75, 1.0)
    light = np.minimum(0.86, r ** 0.9 * 1.15) * edge * np.where(check, 1.0, 0.8) * (0.72 + 0.28 * np.sin(fv * np.pi))
    level = np.minimum(LEVELS - 1, np.floor(light * LEVELS)).astype(int)
    state = np.where(check, 1, 1 + LEVELS) + level
    return np.where((r < 0.06) | (level == 0), 0, state).astype(np.uint8)


# How much of a cell each shade lights.
DENSITY = [0.0, 0.06, 0.12, 0.25, 0.5, 0.75, 1.0]


def scan_glyphs(cw, ch):
    """The shades as whole lit rows: the Menu squeezes a 16:9 banner sideways, which turns 1-pixel
    dither into stripes, but rows survive."""
    out = []
    for level, d in enumerate(DENSITY):
        lit = 0 if level == 0 else max(1, round(d * ch))
        rows = {int((k + 0.5) * ch / lit) for k in range(lit)}
        out.append([(1 << cw) - 1 if r in rows else 0 for r in range(ch)])
    return out


def atlas(glyphs, cw, ch):
    """One pre-colored tile per state, left to right, on black."""
    tone_a, tone_b = tone_colors()
    tiles = np.zeros((ch, cw * (1 + 2 * LEVELS), 3), np.uint8)
    for state in range(1, 1 + 2 * LEVELS):
        level = (state - 1) % LEVELS
        color = (tone_a if state <= LEVELS else tone_b)[level]
        for row, bits in enumerate(glyphs[level]):
            for px in range(cw):
                if bits >> (cw - 1 - px) & 1:
                    tiles[row, state * cw + px] = color
    return tiles


def render(index, tiles, cw, ch):
    """What the indirect-texture material should draw: each cell's tile from the atlas."""
    rows, cols = index.shape
    y, x = np.mgrid[0:rows * ch, 0:cols * cw]
    return tiles[y % ch, index[y // ch, x // cw] * cw + x % cw]
