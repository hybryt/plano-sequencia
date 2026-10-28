"""Efeitos sonoros sintetizados a partir dos eventos da comp, todos na mesma sala.

    python scripts/sfx.py templates/comp.html --out sfx.wav
    python scripts/sfx.py --events eventos.json --dur 8 --out sfx.wav --music trilha.wav

Cinco materiais (whoosh, tick, pop, thud, chime) feitos com numpy, um reverb só pra todos,
música opcional abaixada (ducking) debaixo dos impactos, pico final em -3 dBFS.
Nada é baixado: tudo é síntese, então não tem licença de terceiro pra checar.
"""
import argparse, sys, asyncio, json, wave
from pathlib import Path

import numpy as np

SR = 48000


def env(n, attack, decay):
    t = np.arange(n) / SR
    return np.minimum(t / max(attack, 1e-4), 1) * np.exp(-t / decay)


def noise(n, rng):
    return rng.standard_normal(n)


def lowpass(x, cutoff):
    a = np.exp(-2 * np.pi * cutoff / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i, v in enumerate(x):
        acc = (1 - a) * v + a * acc
        y[i] = acc
    return y


def whoosh(rng):
    n = int(0.45 * SR)
    t = np.arange(n) / SR
    shape = np.sin(np.pi * t / t[-1]) ** 2
    x = noise(n, rng)
    lo, hi = lowpass(x, 600), lowpass(x, 3500)
    sweep = np.clip(t / t[-1], 0, 1)
    return (lo * (1 - sweep) + (hi - lo) * sweep) * shape * 0.9


def tick(rng):
    n = int(0.03 * SR)
    t = np.arange(n) / SR
    return (np.sin(2 * np.pi * 3200 * t) * 0.4 + noise(n, rng) * 0.3) * env(n, 0.0005, 0.004)


def pop(rng):
    n = int(0.18 * SR)
    t = np.arange(n) / SR
    f = 900 * np.exp(-t * 18) + 220
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, 0.001, 0.05)


def thud(rng):
    n = int(0.6 * SR)
    t = np.arange(n) / SR
    f = 110 * np.exp(-t * 6) + 42
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, 0.002, 0.18)
    click = lowpass(noise(n, rng), 1800) * env(n, 0.0005, 0.012) * 2
    return body + click


def chime(rng):
    n = int(1.8 * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for f, a, d in [(880, 1, 0.9), (1320, 0.5, 0.6), (2217, 0.25, 0.35), (2640, 0.15, 0.25)]:
        out += a * np.sin(2 * np.pi * f * t) * env(n, 0.002, d)
    return out * 0.35


SYNTH = {"whoosh": whoosh, "tick": tick, "pop": pop, "thud": thud, "chime": chime}
GAIN = {"whoosh": 0.35, "tick": 0.25, "pop": 0.5, "thud": 0.9, "chime": 0.6}


def room(x, seconds=1.1, wet=0.18, seed=5):
    """Uma sala só: resposta ao impulso sintética (ruído com decaimento) por convolução FFT."""
    rng = np.random.default_rng(seed)
    n = int(seconds * SR)
    ir = rng.standard_normal((n, 2)) * np.exp(-np.arange(n) / SR * 6.5)[:, None]
    ir[:, 0], ir[:, 1] = lowpass(ir[:, 0], 5000), lowpass(ir[:, 1], 5000)
    ir /= np.sqrt((ir ** 2).sum(0))
    m = len(x) + n
    F = np.fft.rfft(x, m, axis=0) * np.fft.rfft(ir, m, axis=0)
    return x + wet * np.fft.irfft(F, m, axis=0)[: len(x)]


def read_wav(path):
    with wave.open(str(path)) as w:
        sr, ch, sw = w.getframerate(), w.getnchannels(), w.getsampwidth()
        data = np.frombuffer(w.readframes(w.getnframes()), {2: np.int16, 4: np.int32}[sw]).astype(np.float32)
        data /= float(2 ** (8 * sw - 1))
        data = data.reshape(-1, ch)
    if ch == 1:
        data = np.repeat(data, 2, 1)
    if sr != SR:
        idx = np.arange(0, len(data), sr / SR)
        data = np.stack([np.interp(idx, np.arange(len(data)), data[:, c]) for c in range(2)], 1)
    return data[:, :2]


def write_wav(path, x):
    x = np.clip(x, -1, 1)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((x * 32767).astype(np.int16).tobytes())


async def comp_events(comp):
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page()
        await pg.goto(Path(comp).resolve().as_uri())
        await pg.evaluate("window.__ready")
        ev = await pg.evaluate("typeof window.__events === 'function' ? window.__events() : []")
        dur = await pg.evaluate("(window.__meta && window.__meta.dur) || 0")
        await b.close()
        return ev, dur


def score(events, dur, music=None, seed=1):
    rng = np.random.default_rng(seed)
    n = int(dur * SR) + SR
    mix = np.zeros((n, 2))
    duck = np.ones(n)
    for e in sorted(events, key=lambda e: e["t"]):
        kind = e.get("kind", "tick")
        if kind not in SYNTH:
            continue
        s = SYNTH[kind](rng) * GAIN[kind] * e.get("gain", 1.0)
        pan = float(np.clip(e.get("pan", (e.get("x", 960) - 960) / 960 * 0.5), -1, 1))
        i = int(e["t"] * SR)
        j = min(n, i + len(s))
        if i >= n:
            continue
        mix[i:j, 0] += s[: j - i] * np.sqrt((1 - pan) / 2) * 1.414
        mix[i:j, 1] += s[: j - i] * np.sqrt((1 + pan) / 2) * 1.414
        if kind in ("thud", "whoosh", "chime"):
            k = min(n, i + int(0.5 * SR))
            duck[i:k] = np.minimum(duck[i:k], 0.45 + 0.55 * np.linspace(0, 1, k - i))
    mix = room(mix)
    if music is not None:
        m = read_wav(music)[:n]
        m = np.pad(m, ((0, n - len(m)), (0, 0)))
        fade = int(0.8 * SR)
        m[-fade:] *= np.linspace(1, 0, fade)[:, None]
        mix += m * 0.5 * duck[:, None]
    mix = mix[: int(dur * SR)]
    peak = np.abs(mix).max()
    if peak > 0:
        mix *= 10 ** (-3 / 20) / peak    # pico em -3 dBFS: sobra pro AAC não clipar
    return mix


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("comp", nargs="?", help="comp HTML com window.__events()")
    ap.add_argument("--events", help="JSON [{t, kind, x?, gain?}]")
    ap.add_argument("--dur", type=float)
    ap.add_argument("--music", help="wav de trilha livre de royalties (você escolhe e guarda a licença)")
    ap.add_argument("--out", default="sfx.wav")
    a = ap.parse_args()
    if a.comp:
        ev, dur = asyncio.run(comp_events(a.comp))
    else:
        ev, dur = json.loads(Path(a.events).read_text(encoding="utf-8")), 0
    dur = a.dur or dur or (max(e["t"] for e in ev) + 2)
    write_wav(a.out, score(ev, dur, a.music))
    print(f"ok → {a.out} ({len(ev)} eventos, {dur:.2f}s)")


if __name__ == "__main__":
    main()
