// node tests/test_lib.js
const assert = require('assert');
const PS = require('../lib/ps.js');
let n = 0;
const ok = (name, fn) => { fn(); n++; console.log('  ok ', name); };
const near = (a, b, e = 1e-6) => assert.ok(Math.abs(a - b) <= e, `${a} != ${b}`);

ok('curvas começam em 0 e terminam em 1', () => {
  for (const [k, f] of Object.entries(PS.curve)) { near(f(0), 0, 1e-3); near(f(1), 1, 1e-3); }
});
ok('bezier CSS ease ≈ referência', () => {
  const e = PS.bezier(0.25, 0.1, 0.25, 1);
  near(e(0.5), 0.8024, 2e-3);
});
ok('t80: expoOut estala, sineInOut é S', () => {
  assert.ok(PS.t80(PS.curve.expoOut) < 0.25);
  assert.ok(PS.t80(PS.curve.sineInOut) > 0.65);
});
ok('mola sai de 0, passa de 1 (subamortecida) e assenta', () => {
  near(PS.spring(0), 0);
  let max = 0; for (let t = 0; t < 2; t += 0.005) max = Math.max(max, PS.spring(t, { damp: 0.4 }));
  assert.ok(max > 1.05);
  near(PS.spring(6, { damp: 0.4 }), 1, 1e-4);
  near(PS.spring(6, { damp: 1 }), 1, 1e-4);
  near(PS.spring(8, { damp: 1.5 }), 1, 1e-3);
});
ok('rng determinístico por seed', () => {
  const a = PS.rng(42), b = PS.rng(42);
  for (let i = 0; i < 100; i++) assert.strictEqual(a(), b());
});
ok('keys interpola objetos', () => {
  const v = PS.keys(0.5, [{ t: 0, v: { x: 0 } }, { t: 1, v: { x: 10 }, curve: PS.curve.linear }]);
  near(v.x, 5);
});
ok('câmera: zoom em log, ponto médio geométrico', () => {
  const c = PS.camera(0.5, [{ t: 0, x: 0, y: 0, zoom: 1, curve: PS.curve.linear }, { t: 1, x: 100, y: 0, zoom: 100, curve: PS.curve.linear }], { fn: PS.curve.linear });
  near(c.zoom, 10, 1e-6);
});
ok('view/project: centro da câmera cai no meio da tela', () => {
  const cam = { x: 300, y: 200, zoom: 3, rot: 0.2 };
  const p = PS.project(cam, { x: 300, y: 200 });
  near(p.x, 960, 1e-9); near(p.y, 540, 1e-9);
});
ok('follow persegue e assenta no alvo', () => {
  const f = PS.follow(t => (t < 1 ? { x: 0, y: 0, zoom: 1 } : { x: 500, y: 100, zoom: 4 }), { dur: 8 });
  const a = f(1.2), z = f(7.9);
  assert.ok(a.x > 0 && a.x < 500);
  near(z.x, 500, 1); near(z.zoom, 4, 0.05);
  assert.deepStrictEqual(f(3.3), f(3.3));
});
ok('typed respeita o tempo e é determinístico', () => {
  assert.strictEqual(PS.typed(0, 0, 'abc'), '');
  assert.strictEqual(PS.typed(10, 0, 'abc'), 'abc');
  assert.strictEqual(PS.typed(0.1, 0, 'abcdefgh'), PS.typed(0.1, 0, 'abcdefgh'));
});
ok('handheld e shake são puros', () => {
  assert.deepStrictEqual(PS.handheld(2.5), PS.handheld(2.5));
  const s = PS.shake(1.05, [{ t: 1, amp: 10 }]);
  assert.ok(Math.abs(s.x) > 0);
  near(PS.shake(0.5, [{ t: 1 }]).x, 0);
});
console.log(`${n} testes passaram`);
