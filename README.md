# plano-sequencia

Skill pro Claude Code que faz filmes curtos de motion (10 a 30 s) em **plano-sequência**: cada beat nasce
do anterior, nada é trocado. Pra lançamento de produto, teaser, promo de app e demo de feature.

```
  ●  ──▶  [ barra de prompt ]  ──▶  ┌ janela ┐  ──▶  câmera entra  ──▶  ───────  ──▶  marca
 ponto       o ponto abre           a barra abre      no conteúdo       a janela      a linha
                                                                         colapsa     escreve o nome
```

Versão própria, escrita do zero, **sem código do onetake** e sem dependência do onetake Pro. Livre pra uso
comercial (licença MIT).

## Instalação

```bash
git clone https://github.com/hybryt/alto-onetake-free.git ~/.claude/skills/plano-sequencia
pip install -r ~/.claude/skills/plano-sequencia/requirements.txt
python -m playwright install chromium
```

Precisa também de `ffmpeg` no PATH e `node` (só pros testes).

## Uso

No Claude Code, peça algo como:

- "faz um vídeo de 15 segundos de lançamento do app X"
- "demo da feature de agendamento recriando a UI desses prints, sem gravar tela"
- "meu motion tá parecendo PPT, conserta"

Ou rode o pipeline na mão:

```bash
python scripts/stills.py templates/comp.html --out stills.png        # olha os quadros-chave
python scripts/sfx.py templates/comp.html --out sfx.wav              # efeitos sonoros
python scripts/render.py templates/comp.html --out demo.mp4 --sfx sfx.wav
python scripts/verify.py demo.mp4 --comp templates/comp.html         # oráculo
node tests/test_lib.js                                               # testes da biblioteca
```

O exemplo de 8 s renderiza em ~16 s (8 workers) e passa no oráculo; um slideshow de controle com cortes a
cada 2 s reprova em ritmo e continuidade.

## O que tem aqui

| | |
|---|---|
| `SKILL.md` | o protocolo que o Claude segue |
| `lib/ps.js` | biblioteca de movimento: curvas, molas, entradas, morph, câmera por chaves, câmera que persegue, handheld, tranco |
| `templates/comp.html` | comp de exemplo com o contrato `__seek` / `__ready` / `__meta` / `__motion` / `__events` |
| `scripts/render.py` | render com motion blur real (média em luz linear), paralelo, 1080p30 e 4K60 |
| `scripts/verify.py` | oráculo: ritmo, repouso, continuidade, blur, áudio |
| `scripts/analyze_ref.py` | desmonta um vídeo de referência em números |
| `scripts/sfx.py` | efeitos sintetizados numa sala só, com ducking de trilha |
| `references/metodo.md` | o método com números |

## Diferenças pro original (onetake)

O [onetake](https://github.com/feitangyuan/onetake) é de Patrick (feitangyuan), licença **PolyForm
Noncommercial 1.0.0**: uso comercial é proibido sem o onetake Pro (que vende licença comercial + o código
fonte dos filmes). Como a ALTO usaria isso em trabalho de cliente, esta versão **não copia nem deriva do
código, textos, fontes ou filmes do onetake**. Foi escrita do zero a partir da ideia pública (plano-sequência,
composição como função do tempo, blur por amostragem, oráculo), que não é protegida por direito autoral.

| | onetake (lite, público) | plano-sequencia |
|---|---|---|
| licença | não comercial | MIT, uso comercial ok |
| biblioteca de movimento | ~38 movimentos (sims, fluidos, lattice, 3D) | núcleo: curvas, molas, entradas, morph, câmera, follow, handheld, tranco |
| render com motion blur | ✅ | ✅ (amostragem adaptativa via `__motion`) |
| oráculo | ritmo, rajada, continuidade (probe por elemento), curvas, enquadramento, áudio | ritmo, repouso, continuidade (máscara de primeiro plano), blur, áudio |
| análise de referência | ✅ | ✅ (mapa, cortes, planos, folhas de contato) |
| som | paleta sintetizada + pipeline com samples gravados e LUFS | paleta sintetizada numa sala, ducking, pico -3 dBFS |
| narração / legenda / multi-idioma | Kokoro TTS + faster-whisper | ❌ não incluso |
| gravação de footage real, kit de UI | ✅ | ❌ (recrie a UI direto na comp) |
| looks prontos, fontes, galeria, 11 filmes de case | ✅ | ❌ (fontes: use Google Fonts no HTML) |
| verificação de enquadramento (`inFrame`) | ✅ | ❌ |

Nada aqui contorna verificação de licença: o onetake não tem trava técnica, a restrição é contratual. Se
um dia quiser os filmes-fonte ou os movimentos avançados do original pra uso comercial, o caminho é comprar
o Pro em onetakemotion.com.

## Licença

MIT. Veja `LICENSE`.
