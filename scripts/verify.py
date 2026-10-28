"""Oráculo: reprova o filme antes de um humano precisar assistir.

    python scripts/verify.py draft.mp4 --comp templates/comp.html
    python scripts/verify.py draft.mp4 --beats 0.9,1.6,3.6,4.4,6.0,6.6 --ref ref.mp4

Pernas (FAIL derruba o exit code; WARN só avisa):
  ritmo       planos/beats com durações parecidas demais (metrônomo) → FAIL
  repouso     menos de 12% do filme parado → FAIL (o descanso é o que faz o movimento bater)
  continuidade média de carry nas fronteiras < 0.5 → FAIL; alguma fronteira < 0.3 → WARN
  blur        movimento > 80 px/frame com cara de estroboscópio → WARN
  audio       pico > -1 dBFS (clip) → FAIL; nunca fica quieto → WARN
"""
import argparse, asyncio, json, sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import energy as E


async def comp_beats(comp):
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page()
        await pg.goto(Path(comp).resolve().as_uri())
        await pg.evaluate("window.__ready")
        meta = await pg.evaluate("window.__meta || {}")
        await b.close()
        return meta.get("beats") or []


def spread(durs):
    durs = [d for d in durs if d > 0.05]
    if len(durs) < 2:
        return None, None
    return max(durs) / min(durs), float(np.std(durs) / np.mean(durs))


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    ap.add_argument("--comp", help="lê as fronteiras de __meta.beats")
    ap.add_argument("--beats", help="fronteiras em segundos, separadas por vírgula")
    ap.add_argument("--ref", help="vídeo de referência: imprime o mapa dele ao lado")
    ap.add_argument("--json", help="salva o relatório em JSON")
    a = ap.parse_args()

    A = E.analyse(a.video)
    dur = A["n"] / A["fps"]
    beats = [float(x) for x in a.beats.split(",")] if a.beats else (asyncio.run(comp_beats(a.comp)) if a.comp else [])
    rep, fails, warns = {}, [], []

    def leg(name, ok, msg, warn=False):
        tag = "PASS" if ok else ("WARN" if warn else "FAIL")
        (warns if tag == "WARN" else fails if tag == "FAIL" else []).append(name)
        print(f"  {tag:4}  {name:12} {msg}")
        rep[name] = {"status": tag, "msg": msg}

    print(f"{a.video} · {dur:.2f}s · {A['fps']:.0f} fps")
    print(f"  mapa  [{E.energy_map(A)}]")
    if a.ref:
        R = E.analyse(a.ref)
        print(f"  ref   [{E.energy_map(R)}]  parado {E.still_mask(R).mean():.0%} · cortes {int(R['cut'].sum())}")

    # ritmo: usa os beats da comp; sem eles, os planos entre cortes
    durs = np.diff([0.0] + sorted(beats) + [dur]).tolist() if beats else E.shots(A)
    ratio, cv = spread(durs)
    if ratio is None:
        leg("ritmo", True, "um plano só (sem beats declarados): passe --comp ou --beats pra medir", warn=True)
    else:
        leg("ritmo", ratio >= 3 and cv >= 0.35, f"maior/menor = {ratio:.1f}x (quer ≥ 3x) · CV {cv:.2f} (quer ≥ 0.35) · "
            + ", ".join(f"{d:.2f}" for d in durs))

    still = E.still_mask(A).mean()
    leg("repouso", still >= 0.12, f"{still:.0%} do filme parado (quer ≥ 12%)")

    if beats:
        cs = [E.carry(A, t) for t in beats]
        mean = float(np.mean(cs))
        detail = " · ".join(f"{t:.2f}s→{c:.2f}" for t, c in zip(beats, cs))
        leg("continuidade", mean >= 0.5, f"carry médio {mean:.2f} (quer ≥ 0.5) · {detail}")
        weak = [t for t, c in zip(beats, cs) if c < 0.3]
        if weak and mean >= 0.5:
            leg("fronteira", False, "fronteiras que trocam em vez de carregar: " + ", ".join(f"{t:.2f}s" for t in weak), warn=True)
    else:
        leg("continuidade", True, "sem fronteiras declaradas; não medida", warn=True)

    fast = A["flow"] > 80
    leg("blur", not fast.any(), f"pico {A['flow'].max():.0f} px/frame" + (f" em {fast.sum()} frames: confirme o shutter" if fast.any() else ""), warn=True)

    au = E.audio(a.video)
    if au is None or not len(au):
        leg("audio", True, "sem trilha de áudio", warn=True)
    else:
        peak = 20 * np.log10(np.abs(au).max() + 1e-9)
        win = 4800
        rms = np.sqrt(np.mean(au[: len(au) // win * win].reshape(-1, win, 2) ** 2, axis=(1, 2)))
        quiet = (20 * np.log10(rms + 1e-9) < -45).mean()
        leg("audio", peak <= -1.0, f"pico {peak:.1f} dBFS (quer ≤ -1) · {quiet:.0%} em silêncio")
        if quiet == 0:
            leg("respiro", False, "o áudio nunca fica quieto", warn=True)

    verdict = "REPROVADO" if fails else "APROVADO"
    print(f"\n{verdict}" + (f" · falhou: {', '.join(fails)}" if fails else "") + (f" · avisos: {', '.join(warns)}" if warns else ""))
    if a.json:
        Path(a.json).write_text(json.dumps({"verdict": verdict, "legs": rep}, ensure_ascii=False, indent=2), encoding="utf-8")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
