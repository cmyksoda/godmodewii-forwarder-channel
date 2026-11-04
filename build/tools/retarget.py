#!/usr/bin/env python3
"""Point an Empty Slot WAD at a different homebrew app.

    python retarget.py "Empty Slot - ESLT [cmyksoda].wad" /apps/wiixplorer/boot.dol WXPL

The forwarder looks on SD first, then USB, and falls back from boot.dol to
boot.elf. Needs pycryptodome (pip install pycryptodome).
"""

import hashlib
import re
import struct
import sys

from Crypto.Cipher import AES

COMMON_KEY = bytes.fromhex("ebe42a225e8593e448d9c5457381aaf7")
MARKER = b"FWDPATH="
FIELD = 256


def align(n, a=64):
    return (n + a - 1) // a * a


def patch_path(dol, path):
    """Rewrite the forwarder's path field; it is FIELD bytes long, marker included."""
    at = dol.find(MARKER)
    if at < 0:
        raise SystemExit("no FWDPATH= field: this isn't the Empty Slot forwarder")
    raw = path.encode("ascii")
    room = FIELD - len(MARKER) - 1
    if not raw.startswith(b"/") or len(raw) > room:
        raise SystemExit(f"path must start with / and be at most {room} characters")
    start = at + len(MARKER)
    return dol[:start] + raw.ljust(room + 1, b"\0") + dol[at + FIELD:]


def title_key(tik):
    iv = tik[0x1DC:0x1E4] + bytes(8)
    return AES.new(COMMON_KEY, AES.MODE_CBC, iv).decrypt(tik[0x1BF:0x1CF])


def fakesign(blob, brute_at):
    b = bytearray(blob)
    b[4:0x104] = bytes(256)
    for v in range(0x10000):
        struct.pack_into(">H", b, brute_at, v)
        if hashlib.sha1(b[0x140:]).digest()[0] == 0:
            return bytes(b)
    raise SystemExit("fakesigning failed")


def load(path):
    d = open(path, "rb").read()
    hdr, _, *sizes = struct.unpack(">8I", d[:32])
    o = align(hdr)
    parts = []
    for n in sizes[:4]:
        parts.append(d[o:o + n])
        o = align(o + n)
    certs, crl, tik, tmd = parts
    key = title_key(tik)
    contents = []
    for i in range(struct.unpack(">H", tmd[0x1DE:0x1E0])[0]):
        e = 0x1E4 + i * 36
        size = struct.unpack(">Q", tmd[e + 8:e + 16])[0]
        iv = tmd[e + 4:e + 6] + bytes(14)
        blob = d[o:o + align(size, 16)]
        contents.append(AES.new(key, AES.MODE_CBC, iv).decrypt(blob)[:size])
        o = align(o + align(size, 16))
    return certs, crl, tik, tmd, contents, d[o:o + sizes[5]]


def save(path, certs, crl, tik, tmd, contents, footer):
    tmd = bytearray(tmd)
    for i, c in enumerate(contents):
        e = 0x1E4 + i * 36
        struct.pack_into(">Q", tmd, e + 8, len(c))
        tmd[e + 16:e + 36] = hashlib.sha1(c).digest()
    tmd = fakesign(tmd, 0x1D4)
    tik = fakesign(tik, 0x262)
    key = title_key(tik)
    blobs = []
    for i, c in enumerate(contents):
        e = 0x1E4 + i * 36
        iv = tmd[e + 4:e + 6] + bytes(14)
        blobs.append(AES.new(key, AES.MODE_CBC, iv).encrypt(c.ljust(align(len(c), 16), b"\0")))
    data_size = sum(align(len(b)) for b in blobs[:-1]) + len(blobs[-1])
    head = struct.pack(">8I", 0x20, 0x49730000, len(certs), len(crl), len(tik), len(tmd),
                       data_size, len(footer))
    out = b"".join(p.ljust(align(len(p)), b"\0")
                   for p in (head, certs, crl, tik, tmd, *blobs, footer) if p)
    open(path, "wb").write(out)


def set_title_id(tik, tmd, code):
    key = title_key(tik)
    tid = tmd[0x18C:0x190] + code.encode("ascii")
    tmd = tmd[:0x18C] + tid + tmd[0x194:]
    tik = tik[:0x1DC] + tid + tik[0x1E4:]
    enc = AES.new(COMMON_KEY, AES.MODE_CBC, tid + bytes(8)).encrypt(key)
    return tik[:0x1BF] + enc + tik[0x1CF:], tmd


def main():
    if len(sys.argv) not in (4, 5):
        raise SystemExit(__doc__)
    src, path, code = sys.argv[1:4]
    if not re.fullmatch(r"[A-Z0-9]{4}", code):
        raise SystemExit("title ID must be 4 characters, A-Z or 0-9, e.g. WXPL")
    dst = sys.argv[4] if len(sys.argv) == 5 else f"Empty Slot - {code}.wad"

    certs, crl, tik, tmd, contents, footer = load(src)
    # The forwarder is the boot content on the Wii, but sits behind a NAND loader on the vWii.
    forwarder = next((i for i, c in enumerate(contents) if MARKER in c), None)
    if forwarder is None:
        raise SystemExit("no FWDPATH= field: this isn't an Empty Slot WAD")
    contents[forwarder] = patch_path(contents[forwarder], path)
    tik, tmd = set_title_id(tik, tmd, code)
    save(dst, certs, crl, tik, tmd, contents, footer)
    print(f"{dst}: boots {path} from SD or USB, title ID 00010001-{code}")


if __name__ == "__main__":
    main()
