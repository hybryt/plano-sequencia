---
name: plano-sequencia
description: "Faz filmes curtos de motion (10 a 30 s) pra produto, app, skill ou feature em plano-sequência: cada beat nasce do anterior, sem virar slideshow. Uma composição HTML onde tudo é função pura do tempo, biblioteca de movimento própria (curvas, molas, câmera que persegue, handheld, tranco), render com motion blur real (1080p30 rascunho, 4K60 final), efeitos sonoros sintetizados numa sala só e um oráculo que reprova o filme antes de alguém assistir. Use pra: vídeo de lançamento, teaser, promo de app, demo de feature com a UI recriada em HTML a partir de print (sem gravar tela), 'meu motion parece PPT', 'transição seca', 'falta ritmo', 'faz um vídeo de 15 segundos do produto'. Não use pra talking head, edição de vídeo gravado ou vídeo longo."
---

# plano-sequencia

Filme curto de motion feito como um plano-sequência: **nada é trocado, tudo é carregado**. Um ponto vira
barra, a barra vira janela, a câmera entra na janela, a janela vira linha, a linha escreve a marca.

```
 referência ──▶ 3 conceitos ──▶ beat sheet ──▶ comp.html ──▶ stills ──▶ render ──▶ som ──▶ verify
  (números)     (1 escolhido)   (ritmo+carry)  (função de t)  (olhar)   (blur)    (sala)  (oráculo)
```

## Protocolo (nessa ordem)

### 1 · Desmontar a referência em números (se tiver uma)

```bash
python scripts/analyze_ref.py ref.mp4 --out ana/
```

Anote: % do tempo parado, quantos cortes secos e se vêm em rajada, menor e maior plano, velocidade típica.
O filme novo tem que bater esses números. Sem referência, use os padrões das regras abaixo.

### 2 · Três conceitos, o usuário escolhe um

Conceito é **uma frase sobre a imagem**, não sobre o produto. Três ideias centrais diferentes, por exemplo:

- **um elemento atravessa tudo**: o cursor vira menu, o menu vira anel de loading, o anel vira o pingo do i;
- **uma escala só**: um zoom contínuo do ano inteiro até meia hora livre na agenda, e volta;
- **causa e efeito**: cada beat é a colisão que dispara o próximo.

Nunca reaproveite a história da comp de exemplo. Paleta, câmera e transições se escolhem por filme.

### 3 · Beat sheet com ritmo e carry

Uma tabela: tempo · o que acontece · **o que atravessa a fronteira**. Regras:
- durações dos beats variam pelo menos 3x entre o menor e o maior;
- cada fronteira nomeia o objeto que sobrevive e vira o próximo beat;
- tem repouso (frame parado) de verdade: pelo menos 12% do filme, o ideal é ~30%.

### 4 · UI recriada, não gravada

Se o filme mostra um produto, reconstrua a interface em HTML/canvas a partir de prints. Assim a câmera
entra em qualquer zoom sem pixelar, e cada elemento pode se mover sozinho.

### 5 · Compor: um arquivo, tudo função de t

Copie `templates/comp.html` como ponto de partida técnico (não narrativo). Contrato:

| nome | o que é |
|---|---|
| `window.__ready` | Promise: fontes e pré-cálculos prontos |
| `window.__seek(t)` | desenha o frame t. Mesmo t, mesmo frame, sempre |
| `window.__meta` | `{dur, fps, w, h, beats}`; `beats` são as fronteiras que o verify mede |
| `window.__motion(t0, t1)` | opcional: maior deslocamento em px na tela; calibra quantas amostras de blur |
| `window.__events()` | opcional: `[{t, kind, x?}]` pro som (`whoosh`, `tick`, `pop`, `thud`, `chime`) |

Use `lib/ps.js` (`window.PS`):

| grupo | funções |
|---|---|
| básicos | `clamp lerp prog mix tween keys` |
| curvas | `curve.*` (sine, cubic, quart, expo, backOut, smoother), `bezier(x1,y1,x2,y2)`, `t80(fn)` |
| molas | `spring(t,{freq,damp})`, `springTo`, `ring` (batida que decai) |
| entradas | `rise pop leave typed stagger` |
| carry | `morph(t,t0,t1,rectA,rectB)` |
| câmera | `camera(t,keys)` (zoom em log), `follow(want,{dur})` (operador que persegue), `handheld`, `shake(t,hits)`, `view`, `cssView`, `project`, `dof` |
| sorte | `rng(seed)`, `noise(seed)`: nada de `Math.random()` no caminho do render |

Escolha a curva pelo `t80` (quanto do tempo leva pra chegar a 80%): ~0.23 é estalo (`expoOut`), ~0.6 é S suave.
Uma curva só pra tudo deixa todo movimento igual.

Teste ao vivo: abra `comp.html?play` no navegador, ou `comp.html?t=3.2` pra congelar um frame.

### 6 · Olhar antes de renderizar

```bash
python scripts/stills.py comp.html --times 0.5,1.2,2.8,4.0,5.5,7.5 --out stills.png
```

### 7 · Render

```bash
python scripts/render.py comp.html --out rascunho.mp4 --sfx sfx.wav          # 1920x1080 · 30 fps
python scripts/render.py comp.html --out final.mp4 --final --sfx sfx.wav      # 3840x2160 · 60 fps
```

Motion blur real: cada frame em movimento é a média de várias capturas no obturador aberto (180°), em luz
linear. Frame parado custa 1 captura. Roda vários Chromium em paralelo (`--workers`). O exemplo de 8 s leva
~16 s em 8 workers. 4K60 só depois do rascunho aprovado.

### 8 · Som

```bash
python scripts/sfx.py comp.html --out sfx.wav                    # só efeitos sintetizados
python scripts/sfx.py comp.html --out sfx.wav --music trilha.wav # + trilha, abaixada sob os impactos
```

Menos eventos que beats. Uma sala (um reverb) pra tudo. Música: só livre de royalties (YouTube Audio
Library, Pixabay Music, CC que permita uso) ou fornecida pelo cliente; guarde a licença junto.

### 9 · Verificar antes de mostrar

```bash
python scripts/verify.py rascunho.mp4 --comp comp.html [--ref ref.mp4]
```

| perna | reprova quando |
|---|---|
| ritmo | maior/menor beat < 3x ou variação (CV) < 0.35: metrônomo |
| repouso | menos de 12% do filme parado |
| continuidade | carry médio nas fronteiras < 0.5 (o quadro foi trocado em vez de transformado) |
| blur | aviso: movimento > 80 px/frame (confirme que renderizou com shutter) |
| audio | pico acima de -1 dBFS |

Só mostre pro usuário o que passou. Se reprovar, o número diz onde mexer.

## Regras duras

- **Nunca troque um beat, carregue.** Algo na tela sobrevive a cada fronteira e se transforma no próximo.
  Exceções: uma rajada de cortes secos com intenção, e o card final.
- **Nunca corte no metrônomo.** Beats do mesmo tamanho viram slide, por melhor que seja cada um.
- **Repouso existe.** Frame sempre em movimento cansa e nada bate.
- **Elemento pequeno, fundo grande.** Muito respiro; tela cheia é exceção.
- **A causa aparece.** Um cursor, uma mão, o próprio objeto: nada reage ao nada.
- **Câmera que persegue e não perde o sujeito.** Para quando o beat descansa.
- **Determinístico.** `__seek(t)` duas vezes dá o mesmo frame; o blur depende disso.
- **Sem confete, partícula, brilho genérico.** Lê como template.
- **Cor do sujeito nunca cruza a cor do fundo** numa transição (ele some por um frame; o verify pega).
- **Rascunho em 1080p30.** 4K60 só com o corte aprovado.

## Arquivos

| caminho | o que é |
|---|---|
| `lib/ps.js` | biblioteca de movimento (`window.PS` / `require`) |
| `templates/comp.html` | comp de exemplo de 8 s com o contrato completo |
| `scripts/render.py` | render com motion blur, paralelo, 1080p30 / 4K60 |
| `scripts/stills.py` | folha de stills |
| `scripts/verify.py` | oráculo (ritmo, repouso, continuidade, blur, áudio) |
| `scripts/analyze_ref.py` | desmonta uma referência em números + folhas de contato |
| `scripts/sfx.py` | efeitos sintetizados numa sala, ducking da trilha |
| `scripts/energy.py` | medidas compartilhadas (energia, cortes, carry) |
| `references/metodo.md` | o método com mais detalhe |
| `tests/test_lib.js` | testes da biblioteca (`node tests/test_lib.js`) |
