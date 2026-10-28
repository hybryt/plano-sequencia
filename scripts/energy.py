"""Medidas compartilhadas por analyze_ref.py e verify.py.

Lê o vídeo em baixa resolução (cinza) e calcula, por frame:
  diff      energia de mudança (média do |frame - anterior|, 0..255)
  cut       corte seco (pico de diff com histograma que muda de vez)
  flow      deslocamento máximo estimado (px/frame na largura original), fluxo óptico Farneback
  explained quanto da mudança o movimento explica (1 = tudo se move, 0 = troca/fade)
"""
import json, subprocess
import numpy as np
import cv2

AW, AH = 320, 180  # resolução de análise


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height,r_frame_rate:format=duration", "-of", "json", path],
                         capture_output=True, text=True, check=True).stdout
    j = json.loads(out)
    s = j["streams"][0]
    num, den = s["r_frame_rate"].split("/")
    return {"w": int(s["width"]), "h": int(s["height"]), "fps": float(num) / float(den),
            "dur": float(j["format"]["duration"])}


def frames(path, fps=None):
    vf = f"scale={AW}:{AH}:flags=area,format=gray"
    if fps:
        vf = f"fps={fps}," + vf
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vf", vf, "-f", "rawvideo", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, AH, AW)


def audio(path, sr=48000):
    p = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vn", "-ac", "2", "-ar", str(sr), "-f", "f32le", "-"],
                       capture_output=True)
    if p.returncode or not p.stdout:
        return None
    return np.frombuffer(p.stdout, np.float32).reshape(-1, 2)


def analyse(path, fps=None):
    info = probe(path)
    F = frames(path, fps)
    rate = fps or info["fps"]
    n = len(F)
    diff = np.zeros(n)
    flow = np.zeros(n)
    explained = np.ones(n)
    hist_jump = np.zeros(n)
    scale = info["w"] / AW
    prev_h = None
    for i in range(n):
        h = cv2.calcHist([F[i]], [0], None, [32], [0, 256]).ravel()
        h /= h.sum() + 1e-9
        if i:
            a, b = F[i - 1].astype(np.float32), F[i].astype(np.float32)
            d = np.abs(b - a)
            diff[i] = d.mean()
            hist_jump[i] = 0.5 * np.abs(h - prev_h).sum()
            if diff[i] > 0.15:
                fl = cv2.calcOpticalFlowFarneback(F[i - 1], F[i], None, 0.5, 3, 15, 3, 5, 1.2, 0)
                mag = np.hypot(fl[..., 0], fl[..., 1])
                # só onde tem textura: em área lisa o fluxo é chute (problema da abertura)
                grad = cv2.Sobel(F[i], cv2.CV_32F, 1, 0) ** 2 + cv2.Sobel(F[i], cv2.CV_32F, 0, 1) ** 2
                moving = (d > 6) & (grad > 400)
                flow[i] = (np.median(mag[moving]) if moving.sum() > 30 else 0) * scale
                # residual depois de compensar o movimento vs. residual cru
                gx, gy = np.meshgrid(np.arange(AW, dtype=np.float32), np.arange(AH, dtype=np.float32))
                # fluxo vai de a pra b: a(p) ≈ b(p + f), então puxar b pelo fluxo reconstrói a
                warped = cv2.remap(b, gx + fl[..., 0], gy + fl[..., 1], cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
                res = np.abs(a - warped).mean()
                explained[i] = float(np.clip(1 - res / (diff[i] + 1e-6), 0, 1))
        prev_h = h
    # corte: diff alto vs vizinhança e histograma muda bastante
    cut = np.zeros(n, bool)
    for i in range(1, n):
        lo, hi = max(1, i - 6), min(n, i + 7)
        neigh = np.median(np.r_[diff[lo:i], diff[i + 1:hi]]) if hi - lo > 1 else 0
        cut[i] = diff[i] > 12 and diff[i] > 4 * (neigh + 0.5) and (hist_jump[i] > 0.12 or explained[i] < 0.25)
    return {"info": info, "fps": rate, "n": n, "frames": F, "diff": diff, "flow": flow, "explained": explained, "cut": cut}


def still_mask(A, thr=0.35):
    """Frame parado: quase nada muda (com folga pra granulação e handheld leve)."""
    return A["diff"] < thr


def shots(A):
    """Durações dos planos entre cortes secos (s)."""
    idx = [0] + [i for i in np.nonzero(A["cut"])[0]] + [A["n"]]
    return [(b - a) / A["fps"] for a, b in zip(idx, idx[1:]) if b > a]


def ground(F):
    """Cor do fundo do filme todo: mediana das bordas de todos os frames.
    (Por frame não serve: num zoom em que o sujeito enche a tela, a borda vira o sujeito.)"""
    return int(np.median(np.concatenate([F[:, 0].ravel(), F[:, -1].ravel(), F[:, :, 0].ravel(), F[:, :, -1].ravel()])))


def foreground(f, bg):
    """Máscara do que não é fundo."""
    return np.abs(f.astype(np.int16) - bg) > 7


def carry(A, t, win=0.35, reach=4):
    """O que atravessa a fronteira t. 1 = o primeiro plano se transforma frame a frame, 0 = é trocado.

    A cada passo dentro da janela: o primeiro plano anterior cabe no novo (cresceu) ou o novo cabe
    no anterior (encolheu), com folga de reach px na resolução de análise. Um corte ou uma troca de cena derruba esse número
    num frame só; uma forma que cresce, encolhe ou anda mantém perto de 1. Vale o pior passo.
    """
    fps, F = A["fps"], A["frames"]
    a, b = max(1, int((t - win) * fps)), min(A["n"] - 1, int((t + win) * fps) + 1)
    if A["cut"][a:b + 1].any():
        return 0.0
    k = np.ones((2 * reach + 1, 2 * reach + 1), np.uint8)
    worst = 1.0
    bg = A.setdefault("ground", ground(F))
    prev = foreground(F[a - 1], bg)
    for i in range(a, b + 1):
        cur = foreground(F[i], bg)
        if prev.sum() > 20 and cur.sum() > 20:
            pd = cv2.dilate(prev.astype(np.uint8), k).astype(bool)
            cd = cv2.dilate(cur.astype(np.uint8), k).astype(bool)
            # cresce (o velho cabe no novo) ou encolhe (o novo cabe no velho): carregou. Troca: nenhum cabe.
            s = max((cur & pd).sum() / cur.sum(), (prev & cd).sum() / prev.sum())
            worst = min(worst, float(s))
        elif prev.sum() > 20 or cur.sum() > 20:
            worst = min(worst, 0.0 if A["diff"][i] > 3 else worst)   # algo sumiu/surgiu de uma vez
        prev = cur
    return worst


def energy_map(A, width=60):
    """Linha de texto: onde o filme se mexe. ' ' parado, ░▒▓█ cada vez mais movimento, | corte."""
    n, d = A["n"], A["diff"]
    out = []
    for k in range(width):
        a, b = int(k * n / width), max(int((k + 1) * n / width), int(k * n / width) + 1)
        if A["cut"][a:b].any():
            out.append("|")
            continue
        v = d[a:b].mean()
        out.append(" " if v < 0.35 else "░" if v < 2 else "▒" if v < 6 else "▓" if v < 14 else "█")
    return "".join(out)
