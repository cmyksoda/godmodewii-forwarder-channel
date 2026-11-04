"""Render a tracker module as an intro plus a seamless loop of whole orders.

The song plays from its first order, so speed, tempo and volume are what the song set up; the loop span is
then played twice more and the body cut from the first repeat, so notes ringing over the seam come from the
loop's own end.
"""
import argparse
import ctypes as C
import json
import struct
import wave
from pathlib import Path

import numpy as np

lib = C.CDLL("libopenmpt.so.0")
lib.openmpt_module_create_from_memory2.restype = C.c_void_p
lib.openmpt_module_create_from_memory2.argtypes = [C.c_void_p, C.c_size_t] + [C.c_void_p] * 7
for name, res, args in [
    ("openmpt_module_get_current_order", C.c_int32, [C.c_void_p]),
    ("openmpt_module_get_current_row", C.c_int32, [C.c_void_p]),
    ("openmpt_module_set_render_param", C.c_int, [C.c_void_p, C.c_int, C.c_int32]),
    ("openmpt_module_read_float_stereo", C.c_size_t,
     [C.c_void_p, C.c_int32, C.c_size_t, C.c_void_p, C.c_void_p]),
]:
    f = getattr(lib, name)
    f.restype, f.argtypes = res, args

RENDER_STEREOSEPARATION = 2
RENDER_INTERPOLATIONFILTER = 3


def patch_orders(data, orders):
    data = bytearray(data)
    if data[:17] == b"Extended Module: ":
        data[64:66] = struct.pack("<H", len(orders))
        data[66:68] = struct.pack("<H", 0)
        data[80:80 + 256] = bytes(orders) + bytes(256 - len(orders))
    else:
        # MOD has no pattern count: players take the highest entry in all 128 slots, so keep it.
        highest = max(data[952:952 + 128])
        data[950] = len(orders)
        data[951] = 127
        data[952:952 + 128] = bytes(orders) + bytes([highest] * (128 - len(orders)))
    return bytes(data)


def original_orders(data):
    if data[:17] == b"Extended Module: ":
        n = struct.unpack("<H", data[64:66])[0]
        return list(data[80:80 + n])
    return list(data[952:952 + data[950]])


def render(data, rate, separation, interp):
    m = lib.openmpt_module_create_from_memory2(data, len(data), None, None, None, None, None, None, None)
    lib.openmpt_module_set_render_param(m, RENDER_STEREOSEPARATION, separation)
    lib.openmpt_module_set_render_param(m, RENDER_INTERPOLATIONFILTER, interp)
    left, right = (C.c_float * 64)(), (C.c_float * 64)()
    chunks, starts, pos, last = [], [], 0, None
    while True:
        o = lib.openmpt_module_get_current_order(m)
        if o != last and lib.openmpt_module_get_current_row(m) == 0:
            starts.append((o, pos))
        last = o
        got = lib.openmpt_module_read_float_stereo(m, rate, 64, left, right)
        if got == 0:
            break
        chunks.append(np.stack([np.frombuffer(left, np.float32)[:got].copy(),
                                np.frombuffer(right, np.float32)[:got].copy()], 1))
        pos += got
    return np.concatenate(chunks), starts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("module")
    ap.add_argument("loop_from", type=int, help="first order of the loop")
    ap.add_argument("loop_to", type=int, help="order after the loop's last one")
    ap.add_argument("out")
    ap.add_argument("--intro-from", type=int, help="first order of the intro (default: no intro)")
    ap.add_argument("--rate", type=int, default=32000)
    ap.add_argument("--separation", type=int, default=60, help="stereo separation percent")
    ap.add_argument("--interp", type=int, default=4, help="1 none, 2 linear, 4 cubic, 8 sinc")
    a = ap.parse_args()

    data = open(a.module, "rb").read()
    song = original_orders(data)
    loop = song[a.loop_from:a.loop_to]
    audio, starts = render(patch_orders(data, song[:a.loop_to] + loop * 2), a.rate, a.separation, a.interp)

    def start_of(index):
        return next(p for o, p in starts if o == index)

    def align(ref, guess, n=8192, reach=256):
        # Order changes are only seen once per 64-sample read, so snap each cut to the waveform.
        errs = [np.abs(audio[ref:ref + n] - audio[guess + d:guess + d + n]).sum()
                for d in range(-reach, reach + 1)]
        return guess - reach + int(np.argmin(errs)), min(errs) / n

    first = start_of(a.loop_from)
    second, _ = align(first, start_of(a.loop_to))
    third, seam = align(second, start_of(a.loop_to + len(loop)))
    body = audio[second:third].copy()
    head = audio[start_of(a.intro_from):first].copy() if a.intro_from is not None else audio[:0]
    if len(head):
        fade = min(256, len(head))
        ramp = np.linspace(0, 1, fade, dtype=np.float32)[:, None]
        body[:fade] = body[:fade] * ramp + audio[first:first + fade] * (1 - ramp)
        head[:64] *= np.linspace(0, 1, 64, dtype=np.float32)[:, None]

    out = np.concatenate([head, body])
    peak = float(np.abs(out).max())
    pcm = (np.clip(out / max(peak, 1e-6) * 0.89, -1, 1) * 32767).astype("<i2")

    with wave.open(a.out, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(a.rate)
        w.writeframes(pcm.tobytes())
    Path(a.out).with_suffix(".json").write_text(json.dumps({"loop_start": len(head), "frames": len(out)}))
    print(f"{a.out}: intro {len(head) / a.rate:.2f}s, loop {len(body) / a.rate:.2f}s "
          f"(loop start sample {len(head)}, length {len(body)}), peak {peak:.2f}, seam error {seam:.1e}")


if __name__ == "__main__":
    main()
