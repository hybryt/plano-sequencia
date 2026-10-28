"""Folha de stills: congela a comp em vários tempos e monta uma grade. Olhe antes de renderizar.

    python scripts/stills.py templates/comp.html --times 0.5,1.2,2.8,4.0,5.5,7.5 --out stills.png
    python scripts/stills.py comp.html --every 1 --out stills.png
"""
import argparse, sys, asyncio, io, math
from pathlib import Path

from PIL import Image, ImageDraw


async def shoot(comp, times, w, h):
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": w, "height": h})
        await pg.goto(Path(comp).resolve().as_uri())
        await pg.evaluate("window.__ready")
        meta = await pg.evaluate("window.__meta || {}")
        if times is None:
            step = ARGS.every
            times = [round(k * step, 3) for k in range(int(meta.get("dur", 10) / step) + 1)]
        out = []
        for t in times:
            await pg.evaluate(f"window.__seek({t})")
            out.append((t, Image.open(io.BytesIO(await pg.screenshot(type="png"))).convert("RGB")))
        await b.close()
        return out


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    global ARGS
    ap = argparse.ArgumentParser()
    ap.add_argument("comp")
    ap.add_argument("--times", help="lista separada por vírgula, em segundos")
    ap.add_argument("--every", type=float, default=1.0)
    ap.add_argument("--cols", type=int, default=3)
    ap.add_argument("--thumb", type=int, default=640, help="largura de cada quadro na grade")
    ap.add_argument("--out", default="stills.png")
    ARGS = ap.parse_args()
    times = [float(x) for x in ARGS.times.split(",")] if ARGS.times else None
    shots = asyncio.run(shoot(ARGS.comp, times, 1920, 1080))
    tw = ARGS.thumb
    th = round(tw * 1080 / 1920)
    cols = min(ARGS.cols, len(shots))
    rows = math.ceil(len(shots) / cols)
    pad = 12
    sheet = Image.new("RGB", (cols * (tw + pad) + pad, rows * (th + pad + 22) + pad), (30, 30, 30))
    d = ImageDraw.Draw(sheet)
    for k, (t, im) in enumerate(shots):
        x, y = pad + (k % cols) * (tw + pad), pad + (k // cols) * (th + pad + 22)
        sheet.paste(im.resize((tw, th), Image.LANCZOS), (x, y + 22))
        d.text((x, y + 4), f"t = {t:.2f}s", fill=(230, 230, 230))
    sheet.save(ARGS.out)
    print(f"ok → {ARGS.out} ({len(shots)} quadros)")


if __name__ == "__main__":
    main()
