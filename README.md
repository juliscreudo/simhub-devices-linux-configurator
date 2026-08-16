# SimHub Devices no Linux

Fazer a aba **Devices** do [SimHub](https://www.simhubdash.com/) reconhecer volantes, dashes
e caixas de botões quando ele roda sob Wine no Linux — LEDs, telas e botões.

O sintoma que este projeto ataca é a aba Devices presa em `Searching device ...` para
sempre. Não é limitação do hardware nem do SimHub: são lacunas específicas do Wine na
árvore PnP (identidade USB das portas seriais, separação de collections HID, topologia USB),
cada uma com correção conhecida — ou diagnóstico fechado, no caso das telas.

## Estado

| caminho | devices | estado |
|---|---|---|
| **Serial** (`StandardProtocolManager`) | Conspit | ✅ validado com hardware |
| **HID** (`PokornyiDriver`, `CubeControlsLedsDriverV2`) | Pokornyi, Cube Controls | receita conhecida, **não testada** |
| **Telas VoCore** (`BitmapDisplayDevice`) | HYP-R, F499, GTB Pro, PDU5/7… | ❌ bloqueado — depende de topologia USB que o Wine não expõe |

Volantes com tela agregam LEDs **e** tela como devices independentes: espera-se que a metade
dos LEDs funcione mesmo com a tela bloqueada. Ainda não medido.

## Pré-requisitos

- SimHub rodando sob Wine — via [linux-simracing-utils](https://github.com/srounce/linux-simracing-utils) (srounce)
- Python 3 com [`dnfile`](https://github.com/malwarefrank/dnfile) para as ferramentas de análise
- `mingw-w64` para compilar as sondas em C

## Ferramentas

| arquivo | o que faz |
|---|---|
| `tools/ildump.py` | desmonta o IL de um tipo das DLLs do SimHub (que são ofuscadas) |
| `tools/ilgrep.py` | acha quem chama um método |
| `tools/nameprobe.c` | mostra quais APIs de nome PnP o Wine responde para um device |

O detalhamento técnico — arquitetura da aba Devices, as duas receitas, tabelas de VID/PID e
as pegadinhas já pagas — está no [CLAUDE.md](CLAUDE.md).

## Escopo

Projeto pessoal, sem garantia nem suporte. Nada aqui porta ou redistribui software de
terceiros: o SimHub é da Wotever, o linux-simracing-utils e o Winecarte são da srounce. Este
repo é análise e configuração.
