"""Desmonta um vídeo de referência em números antes de você compor qualquer coisa.

    python scripts/analyze_ref.py ref.mp4 --out ana/

Imprime: mapa de energia, % parado, cortes secos (e se vêm em rajada), durações dos planos,
velocidade típica dos movimentos. Salva folhas de contato (uma por plano) e um report.json.
"""
import argparse, json, subprocess, sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
import energy as E


def grab(path, t, w=480):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", path, "-frames:v", "1",
                          "-vf", f"scale={w}:-2", "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True).stdout
    from io import BytesIO
    return Image.open(BytesIO(raw)).convert("RGB") if raw else None


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--out", default="ana")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    A = E.analyse(a.video)
    fps, n = A["fps"], A["n"]
    dur = n / fps
    cuts = [i / fps for i in np.nonzero(A["cut"])[0]]
    shots = E.shots(A)
    still = float(E.still_mask(A).mean())
    gaps = np.diff(cuts) if len(cuts) > 1 else np.array([])
    bursts = int((gaps < 0.5).sum())
    moving = A["flow"][A["flow"] > 1]
    print(f"{a.video} · {dur:.2f}s · {fps:.0f} fps · {A['info']['w']}x{A['info']['h']}")
    print(f"mapa      [{E.energy_map(A)}]")
    print(f"parado    {still:.0%} do tempo")
    print(f"cortes    {len(cuts)}" + (f" ({bursts} em rajada, < 0.5s entre eles)" if bursts else "") +
          (": " + ", ".join(f"{c:.2f}" for c in cuts) if cuts else ""))
    if shots:
        print(f"planos    {len(shots)} · menor {min(shots):.2f}s · maior {max(shots):.2f}s · "
              f"razão {max(shots) / max(min(shots), 1e-3):.1f}x")
    if len(moving):
        print(f"movimento mediana {np.median(moving):.0f} px/frame · pico {moving.max():.0f} px/frame")

    # folha de contato: 6 quadros espalhados por plano
    idx = [0] + [int(c * fps) for c in cuts] + [n]
    for k, (s, e) in enumerate(zip(idx, idx[1:])):
        ts = np.linspace(s / fps, max(s / fps, (e - 1) / fps), 6)
        ims = [im for im in (grab(a.video, t) for t in ts) if im]
        if not ims:
            continue
        w, h = ims[0].size
        sheet = Image.new("RGB", (w * 3, h * 2), (20, 20, 20))
        for j, im in enumerate(ims):
            sheet.paste(im, ((j % 3) * w, (j // 3) * h))
        sheet.save(out / f"plano_{k:02d}.png")
    rep = {"dur": dur, "fps": fps, "still": still, "cuts": cuts, "shots": shots, "bursts": bursts,
           "motion_median": float(np.median(moving)) if len(moving) else 0, "map": E.energy_map(A)}
    (out / "report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"folhas e report.json em {out}/")


if __name__ == "__main__":
    main()
