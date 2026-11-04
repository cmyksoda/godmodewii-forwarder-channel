"""Build sound.bin: the banner loop as a mono 32 kHz DSP-ADPCM BNS that plays the intro once.

The encoder is my Z-GX channel's (build/tools/build_sound.py there), with a loop start
and the loop's decoder context added.
"""
import json
import math
import struct
import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import ROOT
from wiilib import imd5_wrap

SRC = ROOT / "audio/kebab-loop.wav"
RATE = 32000
FRAME = 14


def read_wav(path):
    with wave.open(str(path), "rb") as w:
        ch, rate, n = w.getnchannels(), w.getframerate(), w.getnframes()
        assert w.getsampwidth() == 2 and rate == RATE, (w.getsampwidth(), rate)
        s = struct.unpack(f"<{n * ch}h", w.readframes(n))
    return [(s[i] + s[i + 1]) // 2 for i in range(0, len(s), 2)] if ch == 2 else list(s)


def lpc2(x):
    r0 = sum(v * v for v in x)
    r1 = sum(x[i] * x[i - 1] for i in range(1, len(x)))
    r2 = sum(x[i] * x[i - 2] for i in range(2, len(x)))
    det = r0 * r0 - r1 * r1
    if r0 == 0 or det == 0:
        return 2048, 0
    q = lambda v: max(-32768, min(32767, int(round(v * 2048))))
    return q((r1 * r0 - r2 * r1) / det), q((r0 * r2 - r1 * r1) / det)


def make_coefs(samples):
    seg = max(1, len(samples) // 8)
    coefs = []
    for i in range(8):
        coefs.extend(lpc2(samples[i * seg:(i + 1) * seg] or samples[-seg:]))
    return coefs


def clamp16(v):
    return -32768 if v < -32768 else (32767 if v > 32767 else v)


def encode_frame(targets, c1, c2, h1, h2, e):
    scale = (1 << e) * 2048
    err, nib = 0, []
    for t in targets:
        pred = c1 * h1 + c2 * h2
        n = max(-8, min(7, int(round(((t << 11) - pred - 1024) / scale))))
        s = clamp16((pred + scale * n + 1024) >> 11)
        err += (t - s) ** 2
        nib.append(n)
        h2, h1 = h1, s
    return err, nib, h1, h2


def encode(samples, coefs):
    out = bytearray()
    h1 = h2 = 0
    for f in range((len(samples) + FRAME - 1) // FRAME):
        targets = list(samples[f * FRAME:(f + 1) * FRAME])
        targets += [0] * (FRAME - len(targets))
        best = None
        for p in range(8):
            c1, c2 = coefs[p * 2], coefs[p * 2 + 1]
            maxd, s1, s2 = 0, h1, h2
            for t in targets:
                maxd = max(maxd, abs((t << 11) - (c1 * s1 + c2 * s2) - 1024))
                s2, s1 = s1, t
            e0 = 0
            while e0 < 15 and (1 << e0) * 2048 * 7 < maxd:
                e0 += 1
            for e in {max(0, e0 - 1), e0, min(15, e0 + 1)}:
                err, nib, nh1, nh2 = encode_frame(targets, c1, c2, h1, h2, e)
                if best is None or err < best[0]:
                    best = (err, p, e, nib, nh1, nh2)
        _, p, e, nib, h1, h2 = best
        out.append((p << 4) | e)
        for i in range(0, FRAME, 2):
            out.append(((nib[i] & 0xF) << 4) | (nib[i + 1] & 0xF))
    return bytes(out)


def decode(data, coefs, count):
    out, h1, h2 = [], 0, 0
    for o in range(0, len(data), 8):
        ps = data[o]
        scale = (1 << (ps & 0xF)) * 2048
        c1, c2 = coefs[(ps >> 4 & 7) * 2], coefs[(ps >> 4 & 7) * 2 + 1]
        for i in range(FRAME):
            n = data[o + 1 + i // 2] >> 4 if i % 2 == 0 else data[o + 1 + i // 2] & 0xF
            s = clamp16((c1 * h1 + c2 * h2 + scale * (n - 16 if n > 7 else n) + 1024) >> 11)
            h2, h1 = h1, s
            out.append(s)
    return out[:count]


def build_bns(adpcm, coefs, total, loop_start, decoded):
    info = bytearray(96)
    info[0:4] = b"INFO"
    struct.pack_into(">I", info, 4, 96)
    info[8], info[9], info[10] = 0, 1, 1
    struct.pack_into(">H", info, 12, RATE)
    struct.pack_into(">II", info, 16, loop_start, total)
    struct.pack_into(">I", info, 24, 0x18)
    struct.pack_into(">I", info, 32, 0x1C)
    struct.pack_into(">I", info, 40, 0x28)
    struct.pack_into(">16h", info, 48, *coefs)
    struct.pack_into(">H", info, 82, adpcm[0])
    # When the loop jumps back, the decoder resumes with this predictor and history.
    struct.pack_into(">Hhh", info, 88, adpcm[loop_start // FRAME * 8], decoded[loop_start - 1], decoded[loop_start - 2])
    data = b"DATA" + struct.pack(">I", len(adpcm) + 8) + adpcm
    head = bytearray(32)
    head[0:4] = b"BNS "
    head[4:8] = bytes.fromhex("feff0100")
    struct.pack_into(">I", head, 8, 32 + len(info) + len(data))
    struct.pack_into(">HH", head, 12, 32, 2)
    struct.pack_into(">IIII", head, 16, 32, len(info), 32 + len(info), len(data))
    return bytes(head) + bytes(info) + data


def main(out_dir):
    samples = read_wav(SRC)
    loop_start = json.loads(SRC.with_suffix(".json").read_text())["loop_start"]
    assert loop_start % FRAME == 0 and loop_start > 2, "the loop must start on a 14-sample frame"
    coefs = make_coefs(samples)
    adpcm = encode(samples, coefs)
    back = decode(adpcm, coefs, len(samples))
    noise = sum((a - b) ** 2 for a, b in zip(samples, back)) or 1
    snr = 10 * math.log10(sum(s * s for s in samples) / noise)
    bns = build_bns(adpcm, coefs, len(samples), loop_start, back)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "sound.bns").write_bytes(bns)
    (out / "sound.bin").write_bytes(imd5_wrap(bns))
    print(f"sound.bin: {len(samples) / RATE:.2f} s, loop from {loop_start / RATE:.3f} s, "
          f"{len(bns):,} bytes, round-trip SNR {snr:.1f} dB")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ROOT / "build/out")
