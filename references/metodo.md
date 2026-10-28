# O método, com números

## Por que motion de IA vira slideshow

Quase todo motion gerado sai assim: título, fade, tela de UI, fade, card, fade, logo. Cada plano pode
estar bonito e o conjunto ainda parece PPT, porque **as cenas se substituem**. O conserto tem duas metades:

```
            ritmo                                   carry
  ┌──────────────────────────┐        ┌──────────────────────────────────┐
  │ beats de tamanhos        │        │ algo atravessa cada fronteira    │
  │ diferentes (≥ 3x)        │        │ e vira o próximo beat            │
  │ repouso de verdade       │        │ (cresce, encolhe, anda, colapsa) │
  │ rajadas com intenção     │        │ câmera que acompanha sem cortar  │
  └──────────────────────────┘        └──────────────────────────────────┘
           ✅ só ritmo = slideshow bem cronometrado
           ✅ ritmo + carry = plano-sequência
```

## Jeitos de carregar um beat no próximo

| carry | exemplo |
|---|---|
| morph | a barra de prompt abre e vira a janela (`PS.morph`) |
| colapso | a janela achata numa linha; a linha atravessa a tela |
| crescer de dentro | o conteúdo nasce dentro da janela, não entra pela lateral |
| câmera atravessa | a câmera entra num card até ele virar a cena seguinte |
| causa | um objeto bate no outro e dispara o beat seguinte |
| escrever | a linha vira a base da marca, as letras sobem dela |

## Câmera

- `PS.camera(t, keys)`: chaves explícitas. Zoom interpolado em log; o ponto central anda proporcional ao
  zoom, então um mergulho de 1x a 100x não "derrapa".
- `PS.follow(want, {dur})`: você diz o que enquadrar a cada beat (`want(t) → {x, y, zoom}`) e uma mola
  persegue isso. Atrasa um pouco, encosta e assenta: lê como operador humano.
- Some `PS.handheld` (deriva lenta) e `PS.shake(t, hits)` (tranco no impacto) por cima.
- Câmera parada nos repousos. Movimento constante tira o peso dos movimentos que importam.

## Curvas

`PS.t80(fn)` diz quanto do tempo a curva leva pra chegar a 80% do caminho:

| curva | t80 | sensação |
|---|---|---|
| `expoOut` | ~0.23 | estalo, chega e para |
| `quartOut` | ~0.33 | rápido e firme |
| `cubicInOut` | ~0.63 | S clássico |
| `sineInOut` | ~0.70 | flutuante |

Molas (`PS.spring`) pra tudo que "pousa": `damp` 0.4 a 0.6 balança, 1 é crítico (sem passar do alvo).

## Motion blur

Movimento acima de ~80 px por frame sem blur vira cópias (estroboscópio). O render faz o blur de verdade:
várias capturas no obturador aberto, média em luz linear. Com `__motion(t0, t1)` a comp diz quanto anda,
e o render espalha amostras a cada ~6 px (até 32). Blur de CSS não resolve: ele borra parado também.

## Som

- Cinco materiais sintetizados (whoosh, tick, pop, thud, chime), um reverb só.
- Menos eventos que beats. Bip em todo evento é o slideshow do áudio.
- Trilha abaixa (ducking) debaixo dos impactos; pico final em -3 dBFS pra sobrar margem no AAC.

## O oráculo e suas limitações

O `verify.py` mede no vídeo final, sem confiar na comp:

- **ritmo**: duração dos beats declarados em `__meta.beats` (ou dos planos entre cortes);
- **repouso**: % de frames com mudança quase zero;
- **continuidade**: em cada fronteira, frame a frame, o primeiro plano anterior cabe no novo (cresceu) ou
  o novo cabe no anterior (encolheu). Corte seco ou objeto que some/surge de uma vez derruba pra 0;
- **blur**: fluxo óptico em áreas com textura (aviso, não reprova);
- **áudio**: pico e silêncio.

Limites conhecidos: um crossfade lento entre duas cenas pode passar como carry (a máscara da união contém
as duas); fundo que muda de cor o tempo todo confunde a máscara de primeiro plano. O olho humano continua
sendo a última perna.
