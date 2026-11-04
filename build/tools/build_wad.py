"""Assemble the Wii and vWii channel WADs from the pieces built by the other scripts.

Content 0 is the banner archive (IMET header + a U8 holding banner.bin, icon.bin and sound.bin). Content 1 is
the boot content: the forwarder DOL on the Wii, FIX94's NAND loader on the vWii (which boots the forwarder
from content 2).
"""

import hashlib
import struct

from config import BOOT_PATH, DONOR, FORWARDER_DOL, OUT, ROOT, TITLE, TITLE_ID, VWII_LOADER, WAD_NAMES
from retarget import patch_path
from wiilib import (CONTENT_RECORD, U8, WAD, imd5_unwrap, imet_set, imet_titles, imet_verify,
                    unpack_lz77_imd5)


def banner_content(donor_app):
    u8off = donor_app.find(U8.MAGIC)
    prefix, outer = donor_app[:u8off], U8.load(donor_app[u8off:])

    parts = {}
    for name in ("banner", "icon", "sound"):
        parts[name] = (OUT / f"{name}.bin").read_bytes()
        outer.replace(f"meta/{name}.bin", parts[name])

    problems = outer.check_tree()
    assert not problems, problems

    sizes = (len(unpack_lz77_imd5(parts["icon"])),
             len(unpack_lz77_imd5(parts["banner"])),
             len(imd5_unwrap(parts["sound"])))
    app = imet_set(prefix + outer.to_bytes(), TITLE, sizes)
    assert imet_verify(app), "IMET md5 failed"
    return app, sizes


def add_content(wad, data):
    """Append a normal content with the next ID and index to the TMD."""
    i = len(wad.contents)
    tmd = bytearray(wad.tmd[:0x1E4 + i * CONTENT_RECORD])
    tmd += struct.pack(">IHHQ20s", i, i, 1, len(data), hashlib.sha1(data).digest())
    struct.pack_into(">H", tmd, 0x1DE, i + 1)
    wad.tmd = bytes(tmd)
    wad.contents.append(data)


def build(console, banner, forwarder):
    wad = WAD.load(DONOR)
    wad.contents[0] = banner
    if console == "vwii":
        wad.contents[1] = open(VWII_LOADER, "rb").read()
        add_content(wad, forwarder)
    else:
        wad.contents[1] = forwarder
    wad.set_title_id(TITLE_ID)
    size = wad.save(str(ROOT / WAD_NAMES[console]))
    print(f"  {WAD_NAMES[console]}: {size:,} bytes")
    for i, c in enumerate(wad.contents):
        print(f"    content{i}  {len(c):,} bytes  sha1 {hashlib.sha1(c).hexdigest()[:16]}")


def main():
    banner, sizes = banner_content(WAD.load(DONOR).contents[0])
    forwarder = patch_path(open(FORWARDER_DOL, "rb").read(), BOOT_PATH)
    print(f"  title id {TITLE_ID}, name {imet_titles(banner)[1][1]!r}, IMET sizes "
          f"icon={sizes[0]:,} banner={sizes[1]:,} sound={sizes[2]:,}")
    for console in WAD_NAMES:
        build(console, banner, forwarder)


if __name__ == "__main__":
    main()
