"""Renderiza uma comp HTML (contrato window.__seek / __ready / __meta) em MP4 com motion blur real.

Cada frame em movimento é a média de várias capturas espalhadas pelo obturador aberto (180° por
padrão = meio frame), somadas em luz linear. Frame parado custa uma captura só.

    python scripts/render.py templates/comp.html --out draft.mp4                 # 1920x1080 · 30 fps
    python scripts/render.py comp.html --out film.mp4 --final --sfx sfx.wav      # 3840x2160 · 60 fps
    python scripts/render.py comp.html --out test.mp4 --from 2 --to 4 --workers 2

Requer: playwright (chromium), numpy, Pillow, ffmpeg no PATH.
"""
import argparse, asyncio, io, math, os, shutil, subprocess, sys, tempfile, time
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from PIL import Image

# sRGB <-> linear por tabela (rápido em uint8)
_LUT = ((np.arange(256) / 255.0) ** 2.2).astype(np.float32)


def to_linear(img):
    return _LUT[img]


def to_srgb(lin):
    return (np.clip(lin, 0, 1) ** (1 / 2.2) * 255 + 0.5).astype(np.uint8)


async def _probe(comp):
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page()
        await pg.goto(Path(comp).resolve().as_uri())
        await pg.evaluate("window.__ready")
        info = await pg.evaluate("({meta: window.__meta || null, motion: typeof window.__motion === 'function'})")
        await b.close()
        return info


async def _work(job):
    from playwright.async_api import async_playwright
    comp, frames, o = job["comp"], job["frames"], job["opt"]
    stats = {"captures": 0, "frames": 0}
    async with async_playwright() as p:
        args = [] if o["gpu"] else ["--disable-gpu"]
        b = await p.chromium.launch(args=args)
        ctx = await b.new_context(viewport={"width": o["w"], "height": o["h"]}, device_scale_factor=o["scale"])
        pg = await ctx.new_page()
        await pg.goto(Path(comp).resolve().as_uri())
        await pg.evaluate("window.__ready")

        async def grab(t):
            await pg.evaluate(f"window.__seek({t:.6f})")
            stats["captures"] += 1
            png = await pg.screenshot(type="png")
            return np.asarray(Image.open(io.BytesIO(png)).convert("RGB"))

        for i in frames:
            t = o["t0"] + i / o["fps"]
            half = o["shutter"] / 360.0 / o["fps"] / 2
            a, z = max(t - half, 0.0), min(t + half, o["dur"] - 1e-4)
            if o["shutter"] <= 0:
                n = 1
            elif o["motion"]:
                px = await pg.evaluate(f"window.__motion({a:.6f}, {z:.6f})") * o["scale"]
                n = int(min(o["max_samples"], max(1, math.ceil(px / o["gap"]))))
            else:
                n = o["samples"]
            if n == 1:
                img = await grab(t)
            else:
                first = await grab(a)
                last = await grab(z)
                if np.array_equal(first, last):          # frame parado: sem blur
                    img = first
                else:
                    acc = to_linear(first) + to_linear(last)
                    for k in range(1, n - 1):
                        acc += to_linear(await grab(a + (z - a) * k / (n - 1)))
                    img = to_srgb(acc / n)
            Image.fromarray(img).save(os.path.join(o["dir"], f"{i:06d}.png"), compress_level=1)
            stats["frames"] += 1
        await b.close()
    return stats


def _run(job):
    return asyncio.run(_work(job))


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("comp")
    ap.add_argument("--out", required=True)
    ap.add_argument("--final", action="store_true", help="3840x2160 a 60 fps")
    ap.add_argument("--fps", type=int)
    ap.add_argument("--dur", type=float, help="se a comp não define __meta.dur")
    ap.add_argument("--from", dest="t0", type=float, default=0.0)
    ap.add_argument("--to", dest="t1", type=float)
    ap.add_argument("--shutter", type=float, default=180.0, help="ângulo do obturador; 0 desliga o blur")
    ap.add_argument("--samples", type=int, default=8, help="capturas por frame em movimento sem __motion")
    ap.add_argument("--gap", type=float, default=6.0, help="px entre cópias quando a comp tem __motion")
    ap.add_argument("--max-samples", type=int, default=32)
    ap.add_argument("--workers", type=int, default=max(1, min(8, (os.cpu_count() or 4) - 2)))
    ap.add_argument("--sfx", help="wav pra mixar no vídeo")
    ap.add_argument("--crf", type=int, default=16)
    ap.add_argument("--gpu", action="store_true", help="deixa o Chromium usar a GPU (comps WebGL)")
    ap.add_argument("--keep", action="store_true", help="mantém os PNGs dos frames")
    a = ap.parse_args()

    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg não encontrado no PATH")
    info = asyncio.run(_probe(a.comp))
    meta = info["meta"] or {}
    dur = meta.get("dur") or a.dur
    if not dur:
        sys.exit("a comp não define __meta.dur; passe --dur")
    w, h = meta.get("w", 1920), meta.get("h", 1080)
    fps = a.fps or (60 if a.final else meta.get("fps", 30))
    scale = 2 if a.final else 1
    t1 = min(a.t1 if a.t1 is not None else dur, dur)
    n = int(round((t1 - a.t0) * fps))
    tmp = tempfile.mkdtemp(prefix="ps_frames_")
    opt = dict(w=w, h=h, scale=scale, fps=fps, dur=dur, t0=a.t0, shutter=a.shutter, samples=a.samples,
               gap=a.gap, max_samples=a.max_samples, motion=info["motion"], dir=tmp, gpu=a.gpu)
    W = max(1, min(a.workers, n))
    # blocos contíguos: cada navegador anda pra frente no tempo
    size = math.ceil(n / W)
    jobs = [dict(comp=a.comp, frames=list(range(k * size, min(n, (k + 1) * size))), opt=opt) for k in range(W)]
    jobs = [j for j in jobs if j["frames"]]
    print(f"render {w * scale}x{h * scale} @ {fps} fps · {n} frames · {len(jobs)} workers · shutter {a.shutter}°"
          f"{' · __motion' if info['motion'] else ''}")
    t_start = time.time()
    with Pool(len(jobs)) as pool:
        res = pool.map(_run, jobs)
    caps = sum(r["captures"] for r in res)
    print(f"capturas: {caps} ({caps / max(n, 1):.1f}/frame) em {time.time() - t_start:.1f}s")

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-i", os.path.join(tmp, "%06d.png")]
    if a.sfx:
        cmd += ["-ss", str(a.t0), "-i", a.sfx, "-c:a", "aac", "-b:a", "256k", "-shortest"]
    cmd += ["-c:v", "libx264", "-preset", "slow", "-crf", str(a.crf), "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)]
    subprocess.run(cmd, check=True)
    if a.keep:
        print(f"frames em {tmp}")
    else:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"ok → {out}")


if __name__ == "__main__":
    main()
