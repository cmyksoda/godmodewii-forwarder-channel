"""Check both built WADs for the traps that only show up on a console. Based on Empty Slot's verify.py."""
import hashlib
import struct
import sys

import banner as B
import config as C
import icon as I
import layout
from retarget import MARKER
from wiilib import CONTENT_RECORD, U8, WAD, imd5_unwrap, imet_titles, imet_verify, unpack_lz77_imd5

IOS = 58
FRAME = 14
failures = []


def check(ok, msg):
    print(("  ok    " if ok else "  FAIL  ") + msg)
    if not ok:
        failures.append(msg)


def check_container(wad, donor, console):
    tmd = wad.tmd
    check(wad.title_id == bytes.fromhex("00010001") + C.TITLE_ID.encode(), f"title ID is 00010001/{C.TITLE_ID}")
    check(wad.tik[0x1DC:0x1E4] == wad.title_id, "ticket and TMD title IDs match")
    if console == "vwii":
        check(len(wad.contents) == 3, "three contents: banner, NAND loader, forwarder")
        check(hashlib.sha256(wad.contents[1]).hexdigest() == C.VWII_LOADER_SHA256,
              "boot content is FIX94's r2 vWii NAND loader")
    else:
        check(len(wad.contents) == 2, "two contents: banner, forwarder")
    check(tmd[0x184:0x18C] == struct.pack(">II", 1, IOS), f"runs on IOS{IOS}")
    check(tmd[0x1D8:0x1DC] == donor.tmd[0x1D8:0x1DC], "access rights kept from the donor")
    check(struct.unpack(">H", tmd[0x1E0:0x1E2])[0] == 1, "boots content 1")
    for i, c in enumerate(wad.contents):
        e = 0x1E4 + i * CONTENT_RECORD
        check(struct.unpack_from(">Q", tmd, e + 8)[0] == len(c) and tmd[e + 16:e + 36] == hashlib.sha1(c).digest(),
              f"content {i} size and SHA-1 match the TMD")
    check(hashlib.sha1(tmd[0x140:]).digest()[0] == 0, "TMD fakesigned")
    check(tmd[0x19A:0x19C] == bytes(2), "TMD 0x19A left zero")
    check(hashlib.sha1(wad.tik[0x140:]).digest()[0] == 0, "ticket fakesigned")
    check(MARKER + C.BOOT_PATH.encode() + b"\0" in wad.contents[-1], f"forwarder boots {C.BOOT_PATH}")


def tpl_filters(data):
    """(min, mag) filter of a single-image TPL."""
    head = struct.unpack(">I", data[0x0C:0x10])[0]
    return struct.unpack(">II", data[head + 0x14:head + 0x1C])


def pane_flags(brlyt, name):
    """Flag byte of a pane: bit 0 visible, bit 2 location adjust."""
    at = brlyt.index(b"pic1")
    while brlyt[at + 12:at + 28].rstrip(b"\0") != name.encode():
        at = brlyt.index(b"pic1", at + 4)
    return brlyt[at + 8]


def check_tile_layout(kind, arc, blyt, tiles, names, frame_names):
    brlyt = arc.get(f"arc/blyt/{blyt}")
    atlas = B.ATLAS if kind == "banner" else I.ATLAS
    ok = all(layout.material_bytes(brlyt, names(suffix)[1]) == layout.expected_tile_bytes(
        names(suffix)[1], layout.texture_index(brlyt, atlas), layout.texture_index(brlyt, frame_names[0]),
        cols, rows, (256, 32), (16, 32), window) for suffix, c0, r0, cols, rows, window in tiles)
    check(ok, f"{kind}: all {len(tiles)} tunnel tiles use the tested tile-mode bytes")
    check(all(cols * 16 <= 1024 and rows * 32 <= 1024 for _, _, _, cols, rows, _ in tiles),
          f"{kind}: every tile stays under 1,024 atlas texels (hardware loses larger coordinates)")
    adjusted = [names(s)[0] for s, *_ in tiles if pane_flags(brlyt, names(s)[0]) & 0x04]
    check(not adjusted, f"{kind}: no tunnel tile is location-adjusted (16:9 would spread the tiles apart)")
    nearest = all(tpl_filters(arc.get(f"arc/timg/{n}")) == (0, 0) for n in frame_names + [atlas])
    check(nearest, f"{kind}: atlas and all {len(frame_names)} index maps filter NEAREST (blended indices draw garbage)")


def check_meta(app, donor):
    check(app[:0x40] == donor.contents[0][:0x40], "build tag matches the donor's")
    check(imet_verify(app), "IMET MD5 valid")
    off = app.find(b"IMET")
    sizes = struct.unpack(">III", app[off + 0x0C:off + 0x18])
    meta = U8.load(app[app.find(U8.MAGIC):])
    icon = unpack_lz77_imd5(meta.get("meta/icon.bin"))
    banner = unpack_lz77_imd5(meta.get("meta/banner.bin"))
    for i, (kind, u8) in enumerate((("icon", icon), ("banner", banner))):
        check(sizes[i] == len(u8), f"IMET {kind} size matches ({len(u8):,})")
        check(not U8.load(u8).check_tree(), f"{kind} U8 tree sound")
    check(len(icon) <= I.ICON_CAP, f"icon.bin {len(icon):,} <= {I.ICON_CAP:,} (over it the Menu crashes at boot)")
    check(len(banner) <= B.BUDGET, f"banner.bin {len(banner):,} <= {B.BUDGET:,}")
    n_banner = int(C.TUNNEL_PERIOD * C.TUNNEL_FPS)
    check_tile_layout("banner", U8.load(banner), "banner.brlyt", B.TILES, B.tile_names,
                      [B.frame_name(i) for i in range(n_banner)])
    n_icon = int(C.ICON_PERIOD * I.TUNNEL_FPS)
    check_tile_layout("icon", U8.load(icon), "icon.brlyt", I.TILES, I.tile_names,
                      [I.frame_name(i) for i in range(n_icon)])
    bns = imd5_unwrap(meta.get("meta/sound.bin"))
    check(sizes[2] == len(bns), "IMET sound size matches")
    loop_start, total = struct.unpack(">II", bns[0x30:0x38])
    check(bns[:4] == b"BNS " and bns[0x29] == 1, "sound is a looping BNS")
    check(0 < loop_start < total and loop_start % FRAME == 0,
          f"loop starts on a frame boundary ({loop_start / 32000:.3f} s)")
    check(all(name == C.TITLE for name in imet_titles(app)[1]), f"all 10 names are {C.TITLE!r}")


def main():
    paths = sys.argv[1:] or [str(C.ROOT / name) for name in C.WAD_NAMES.values()]
    donor = WAD.load(C.DONOR)
    for path in paths:
        wad = WAD.load(path)
        console = "vwii" if len(wad.contents) == 3 else "wii"
        print(f"{path.rsplit('/', 1)[-1]} ({console}):")
        check_container(wad, donor, console)
        check_meta(wad.contents[0], donor)
    print(f"\n  {'all checks passed' if not failures else f'{len(failures)} FAILED'}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
