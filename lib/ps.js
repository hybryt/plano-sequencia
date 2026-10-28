// plano-sequencia · biblioteca de movimento
// Tudo aqui é função pura do tempo: f(t) sempre devolve o mesmo valor. É isso que deixa
// o render buscar qualquer frame (e várias amostras dentro de um frame pro motion blur).
(function (root) {
  'use strict';

  // ---------- básicos ----------
  const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
  const lerp = (a, b, u) => a + (b - a) * u;
  // progresso 0..1 de t dentro de [t0, t1]
  const prog = (t, t0, t1) => (t1 === t0 ? (t >= t1 ? 1 : 0) : clamp((t - t0) / (t1 - t0)));
  const mix = (a, b, u) => {
    if (typeof a === 'number') return lerp(a, b, u);
    const o = {};
    for (const k in a) o[k] = lerp(a[k], b[k], u);
    return o;
  };

  // ---------- curvas ----------
  const PI = Math.PI;
  const curve = {
    linear: u => u,
    sineIn: u => 1 - Math.cos((u * PI) / 2),
    sineOut: u => Math.sin((u * PI) / 2),
    sineInOut: u => 0.5 - 0.5 * Math.cos(u * PI),
    quadOut: u => 1 - (1 - u) * (1 - u),
    cubicIn: u => u * u * u,
    cubicOut: u => 1 - Math.pow(1 - u, 3),
    cubicInOut: u => (u < 0.5 ? 4 * u * u * u : 1 - Math.pow(-2 * u + 2, 3) / 2),
    quartOut: u => 1 - Math.pow(1 - u, 4),
    expoIn: u => (u <= 0 ? 0 : Math.pow(2, 10 * u - 10)),
    expoOut: u => (u >= 1 ? 1 : 1 - Math.pow(2, -10 * u)),
    expoInOut: u => {
      if (u <= 0) return 0;
      if (u >= 1) return 1;
      return u < 0.5 ? Math.pow(2, 20 * u - 10) / 2 : (2 - Math.pow(2, -20 * u + 10)) / 2;
    },
    backOut: (u, s = 1.6) => 1 + (s + 1) * Math.pow(u - 1, 3) + s * Math.pow(u - 1, 2),
    smoother: u => u * u * u * (u * (u * 6 - 15) + 10),
  };

  // Bézier cúbica estilo CSS (x1,y1,x2,y2), resolvida por Newton + bisseção.
  function bezier(x1, y1, x2, y2) {
    const bx = s => 3 * x1 * s * (1 - s) ** 2 + 3 * x2 * s * s * (1 - s) + s ** 3;
    const by = s => 3 * y1 * s * (1 - s) ** 2 + 3 * y2 * s * s * (1 - s) + s ** 3;
    const dx = s => 3 * x1 * (1 - s) ** 2 + 6 * (x2 - x1) * s * (1 - s) + 3 * (1 - x2) * s * s;
    return u => {
      if (u <= 0) return 0;
      if (u >= 1) return 1;
      let s = u;
      for (let i = 0; i < 6; i++) {
        const d = dx(s);
        if (Math.abs(d) < 1e-6) break;
        s = clamp(s - (bx(s) - u) / d);
      }
      let lo = 0, hi = 1;
      for (let i = 0; i < 20 && Math.abs(bx(s) - u) > 1e-6; i++) {
        if (bx(s) < u) lo = s; else hi = s;
        s = (lo + hi) / 2;
      }
      return by(s);
    };
  }

  // Quanto do tempo a curva leva pra chegar a 80% do caminho. Baixo = estalo, ~0.6 = S suave.
  function t80(fn, n = 400) {
    for (let i = 0; i <= n; i++) if (fn(i / n) >= 0.8) return i / n;
    return 1;
  }

  // Interpola de a até b entre t0 e t1 com a curva escolhida.
  const tween = (t, t0, t1, a, b, fn = curve.cubicInOut) => mix(a, b, fn(prog(t, t0, t1)));

  // Keyframes: [{t, v, curve?}] (v número ou objeto). A curva da chave vale pro trecho que chega nela.
  function keys(t, ks, fallback = curve.cubicInOut) {
    if (!ks.length) return 0;
    if (t <= ks[0].t) return ks[0].v;
    const last = ks[ks.length - 1];
    if (t >= last.t) return last.v;
    let i = 0;
    while (ks[i + 1].t < t) i++;
    const A = ks[i], B = ks[i + 1];
    return mix(A.v, B.v, (B.curve || fallback)(prog(t, A.t, B.t)));
  }

  // ---------- molas (solução analítica, sem integrar) ----------
  // Resposta ao degrau de um oscilador amortecido: 0 em t=0, tende a 1.
  // freq em Hz (rapidez), damp = razão de amortecimento (1 = crítico, <1 balança).
  function spring(t, { freq = 2.2, damp = 0.55 } = {}) {
    if (t <= 0) return 0;
    const w = 2 * PI * freq, z = damp;
    if (z < 1) {
      const wd = w * Math.sqrt(1 - z * z);
      return 1 - Math.exp(-z * w * t) * (Math.cos(wd * t) + (z * w / wd) * Math.sin(wd * t));
    }
    if (z === 1) return 1 - Math.exp(-w * t) * (1 + w * t);
    const r = Math.sqrt(z * z - 1), a = -w * (z - r), b = -w * (z + r);
    return 1 - (b * Math.exp(a * t) - a * Math.exp(b * t)) / (b - a);
  }
  // Mola que começa em t0 indo de a até b.
  const springTo = (t, t0, a, b, opt) => mix(a, b, spring(t - t0, opt));
  // Batida que decai: 0 → pico → 0 (pra squash, tremida de impacto, pulso).
  function ring(t, t0, { freq = 3, decay = 6 } = {}) {
    const s = t - t0;
    if (s <= 0) return 0;
    return Math.sin(2 * PI * freq * s) * Math.exp(-decay * s);
  }

  // ---------- aleatório determinístico ----------
  function rng(seed = 1) {
    let a = seed >>> 0;
    return () => {
      a = (a + 0x6d2b79f5) >>> 0;
      let x = a;
      x = Math.imul(x ^ (x >>> 15), x | 1);
      x ^= x + Math.imul(x ^ (x >>> 7), x | 61);
      return ((x ^ (x >>> 14)) >>> 0) / 4294967296;
    };
  }
  // Ruído 1D suave (value noise com interpolação quíntica), determinístico por seed.
  function noise(seed = 7) {
    const R = rng(seed), table = new Float64Array(512);
    for (let i = 0; i < 512; i++) table[i] = R() * 2 - 1;
    return x => {
      const i = Math.floor(x), f = x - i;
      const a = table[((i % 512) + 512) % 512], b = table[(((i + 1) % 512) + 512) % 512];
      return lerp(a, b, curve.smoother(f));
    };
  }

  // ---------- entradas e saídas (devolvem estilo pronto) ----------
  // Sobe e aparece. Devolve {o, y} (opacidade, deslocamento em px).
  function rise(t, t0, { dist = 40, dur = 0.7, fn = curve.expoOut } = {}) {
    const u = fn(prog(t, t0, t0 + dur));
    return { o: clamp(u * 1.4), y: (1 - u) * dist };
  }
  // Pop com mola: escala 0 → 1 com overshoot.
  function pop(t, t0, { freq = 2.4, damp = 0.45 } = {}) {
    const s = spring(t - t0, { freq, damp });
    return { o: clamp((t - t0) * 8), s: Math.max(0, s) };
  }
  // Sai: {o, y, s}
  function leave(t, t0, { dist = -30, dur = 0.4, fn = curve.cubicIn } = {}) {
    const u = fn(prog(t, t0, t0 + dur));
    return { o: 1 - u, y: u * dist, s: 1 - 0.06 * u };
  }
  // Digitação: quantos caracteres de `text` estão visíveis. cps = caracteres por segundo.
  function typed(t, t0, text, { cps = 18, jitter = 0.35, seed = 3 } = {}) {
    const R = rng(seed);
    let acc = t0, n = 0;
    for (; n < text.length; n++) {
      acc += (1 / cps) * (1 + (R() * 2 - 1) * jitter);
      if (acc > t) break;
    }
    return text.slice(0, n);
  }
  // Escalonamento: índice i de n começa em t0 + i*gap.
  const stagger = (t0, i, gap = 0.06) => t0 + i * gap;

  // ---------- carregar um elemento no próximo ----------
  // Retângulo que vira outro retângulo {x,y,w,h,r} (r = raio do canto).
  const morph = (t, t0, t1, A, B, fn = curve.expoInOut) => mix(A, B, fn(prog(t, t0, t1)));

  // ---------- câmera ----------
  // Câmera por chaves {t, x, y, zoom, rot}. (x, y) é o ponto do mundo no centro do quadro.
  // Zoom interpolado em log: 1→100 parece uma velocidade constante ao olho.
  function camera(t, ks, { fn = curve.cubicInOut } = {}) {
    if (!ks.length) return { x: 960, y: 540, zoom: 1, rot: 0 };
    const norm = k => ({ x: k.x, y: k.y, zoom: k.zoom || 1, rot: k.rot || 0 });
    if (t <= ks[0].t) return norm(ks[0]);
    if (t >= ks[ks.length - 1].t) return norm(ks[ks.length - 1]);
    let i = 0;
    while (ks[i + 1].t < t) i++;
    const A = norm(ks[i]), B = norm(ks[i + 1]);
    const u = (ks[i + 1].curve || fn)(prog(t, ks[i].t, ks[i + 1].t));
    // Ponto no centro anda proporcional ao zoom pra não "derrapar" num zoom profundo.
    const za = Math.log(A.zoom), zb = Math.log(B.zoom), z = Math.exp(lerp(za, zb, u));
    const w = za === zb ? u : (1 / A.zoom - 1 / z) / (1 / A.zoom - 1 / B.zoom);
    return { x: lerp(A.x, B.x, w), y: lerp(A.y, B.y, w), zoom: z, rot: lerp(A.rot, B.rot, u) };
  }

  // Operador que persegue um alvo: want(t) → {x, y, zoom}. Mola crítica integrada uma vez
  // (pré-computada a 240 Hz), depois consultada por interpolação. Atrasa, encosta e assenta.
  function follow(want, { dur, freq = 1.2, damp = 0.9, zoomFreq = 0.8, hz = 240 } = {}) {
    const n = Math.ceil(dur * hz) + 2;
    const X = new Float64Array(n), Y = new Float64Array(n), Z = new Float64Array(n);
    const w0 = want(0);
    let x = w0.x, y = w0.y, lz = Math.log(w0.zoom || 1), vx = 0, vy = 0, vz = 0;
    const dt = 1 / hz;
    const step = (p, v, target, f) => {
      const w = 2 * PI * f, a = w * w * (target - p) - 2 * damp * w * v;
      v += a * dt;
      return [p + v * dt, v];
    };
    for (let i = 0; i < n; i++) {
      const g = want(i * dt);
      [x, vx] = step(x, vx, g.x, freq);
      [y, vy] = step(y, vy, g.y, freq);
      [lz, vz] = step(lz, vz, Math.log(g.zoom || 1), zoomFreq);
      X[i] = x; Y[i] = y; Z[i] = lz;
    }
    return t => {
      const f = clamp(t * hz, 0, n - 1), i = Math.floor(f), j = Math.min(n - 1, i + 1), u = f - i;
      return { x: lerp(X[i], X[j], u), y: lerp(Y[i], Y[j], u), zoom: Math.exp(lerp(Z[i], Z[j], u)), rot: 0 };
    };
  }

  // Mão de operador: deriva lenta. amp em px, sempre a mesma pro mesmo seed.
  function handheld(t, { amp = 4, speed = 0.35, seed = 11 } = {}) {
    if (!handheld._n) handheld._n = {};
    const k = seed;
    if (!handheld._n[k]) handheld._n[k] = [noise(seed), noise(seed + 1), noise(seed + 2)];
    const [nx, ny, nr] = handheld._n[k];
    return { x: nx(t * speed) * amp, y: ny(t * speed) * amp, rot: nr(t * speed) * 0.0015 * amp };
  }
  // Tranco num impacto: soma das batidas em hits [{t, amp}] (px).
  function shake(t, hits, { freq = 9, decay = 9 } = {}) {
    let x = 0, y = 0;
    for (const h of hits) {
      const a = h.amp || 10;
      x += ring(t, h.t, { freq, decay }) * a;
      y += ring(t, h.t + 0.013, { freq: freq * 1.3, decay }) * a * 0.6;
    }
    return { x, y };
  }

  // Matriz de visão pro canvas 2D: ctx.setTransform(...view(cam)).
  // depth < 1 = camada mais distante (paralaxe: anda e amplia menos).
  function view(cam, { W = 1920, H = 1080, depth = 1, extra } = {}) {
    const z = Math.pow(cam.zoom, depth), rot = (cam.rot || 0) * depth;
    const ox = (extra && extra.x) || 0, oy = (extra && extra.y) || 0;
    const cx = W / 2 + (cam.x - W / 2) * depth, cy = H / 2 + (cam.y - H / 2) * depth;
    const c = Math.cos(rot) * z, s = Math.sin(rot) * z;
    // tela = R·S·(mundo - centro) + meio da tela + extra
    return [c, s, -s, c, W / 2 + ox - (c * cx - s * cy), H / 2 + oy - (s * cx + c * cy)];
  }
  // Mesmo transform em CSS pra uma camada DOM do tamanho do quadro.
  function cssView(cam, opt) {
    const [a, b, c, d, e, f] = view(cam, opt);
    return `matrix(${a},${b},${c},${d},${e},${f})`;
  }
  // Ponto do mundo → tela, com a mesma câmera.
  function project(cam, p, opt) {
    const [a, b, c, d, e, f] = view(cam, opt);
    return { x: a * p.x + c * p.y + e, y: b * p.x + d * p.y + f };
  }

  // Desfoque de profundidade em px pra uma camada fora do foco.
  const dof = (depth, focus = 1, k = 6) => Math.abs(depth - focus) * k;

  const PS = {
    version: '1.0.0',
    clamp, lerp, prog, mix, curve, bezier, t80, tween, keys,
    spring, springTo, ring, rng, noise,
    rise, pop, leave, typed, stagger, morph,
    camera, follow, handheld, shake, view, cssView, project, dof,
  };
  root.PS = PS;
  if (typeof module === 'object' && module.exports) module.exports = PS;
})(typeof window !== 'undefined' ? window : globalThis);
