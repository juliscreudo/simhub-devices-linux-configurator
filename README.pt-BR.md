# SimHub Devices no Linux — LEDs, telas e botões funcionando na aba Devices

**🇧🇷 Português** · [🇬🇧 English](README.md)

Ferramentas e um passo a passo para fazer a aba **Devices** do
[SimHub](https://www.simhubdash.com/) reconhecer volantes, dashes e caixas de botões quando
ele roda **sob Wine no Linux** — LEDs, telas e botões.

O sintoma que este projeto ataca é a aba Devices presa em `Searching device ...` para
sempre. Não é limitação do hardware nem do SimHub: são lacunas específicas do **Wine** —
identidade USB das portas seriais, separação de collections HID, ausência de topologia USB —
e cada uma tem correção conhecida.

### O que este projeto é — e o que não é

Esta é **a solução que eu usei** para pôr meus periféricos para funcionar na aba Devices,
organizada para que outra pessoa consiga reproduzir.

**O SimHub não foi portado, nem reescrito, nem é redistribuído aqui.** Não existe build Linux
do SimHub: o app é o **binário oficial da Wotever**, que você baixa do site deles. Este repo é
análise, medição e configuração.

Mas **"não modifica nada" seria mentira**, e a diferença merece estar aqui em cima. O que este
projeto altera na *sua* instalação:

| o que | o que faz | reversível? |
|---|---|---|
| `pdu5-leds-patch.py` | troca **dois opcodes** no IL da sua cópia de `SimHub.Plugins.dll` | sim — `--revert`, com backup antes |
| `install bridge` | substitui a `libusb-1.0.dll` do SimHub pela [nossa](https://github.com/juliscreudo/wine-libusb-bridge) | sim — a original vira `.orig` |
| `install pdu5-leds` | remove o cache NGen do prefixo | sim — as imagens são **movidas**, não apagadas |
| `install udev` / `install registry` | regras udev do sistema e chaves do prefixo | sim — `system.reg` tem backup |

O repo distribui **o patcher, nunca a DLL corrigida**: a modificação acontece na sua máquina e
some no próximo update do SimHub. E a ponte não reimplementa o SimHub — ela reimplementa a ABI
da `libusb-1.0`, biblioteca livre, que é a peça que falta sob Wine.

O SimHub é da **Wotever**; o `linux-simracing-utils` e o Winecarte são da
**[srounce](https://github.com/srounce)**. Boa parte do crédito pelo que funciona é desses
projetos — este repo só junta as peças.

Projeto pessoal, sem garantia nem suporte.

Validado com o hardware conectado em **CachyOS** (kernel 7.1, Wine 11.15), entre 2026-08-16 e
2026-08-19. Nada aqui é específico de distro; só mudam nomes de pacote.

## O que funciona

| device | VID:PID | o que conecta | estado |
|---|---|---|---|
| Conspit H.AO HUB | `3514:0007` | LEDs + botões (serial) | ✅ **validado com hardware** |
| Pokornyi MCP ButtonBox | `0483:cb40` | LEDs + botões (HID) | ✅ **validado com hardware** |
| Pokornyi MCP EncoderBox | `0483:cb41` | LEDs + botões (HID) | ✅ **validado com hardware** |
| Pokornyi MCP IgnitionBox | `0483:cb42` | LEDs + botões (HID) | ✅ **validado com hardware** |
| Pokornyi PDU5 | `0483:cb01` | LEDs RPM (HID) + tela | ✅ **validado** — precisa do passo 5 |
| Pokornyi HYP-R | `0483:cb10` | LEDs (HID) + tela | ✅ **validado com hardware** |
| Pokornyi GTB Pro | `0483:cb11` | LEDs (HID) + tela | ✅ **validado com hardware** |
| Pokornyi FGT | `0483:cb15` | LEDs (HID) | ✅ **validado** — plugar e reabrir o SimHub bastou |
| Pokornyi RALLY | `0483:cb12` | LEDs (HID) | ✅ **validado** — idem, zero passo novo |
| Cube Controls AMG | `c872:200b` | LEDs + botões (HID) | ✅ **validado com hardware** |
| Tela VoCore | `c872:1004` | dash + **toque** (libusb) | ✅ **validado** — 854×480, via a ponte |

O **FGT** é a evidência de que a receita generaliza: nunca tinha sido ligado nesta bancada,
e bastou plugar e reabrir o SimHub — sem nenhuma configuração específica para ele. O porquê
está em [CLAUDE.md](CLAUDE.md).

> **Sobre a Cube Controls AMG:** o volante que todo mundo chama de **AMG** é o projeto
> **AC190**, e é ele que está validado aqui (`c872:200b`). O catálogo do SimHub também traz um
> `CubeControlsAMGLedsManager` apontando para *outro* PID (`c872:200c`) — possivelmente uma AMG
> nova que ainda não foi lançada. Os dois são cobertos pela mesma regra udev e pela mesma lista
> de registro, então a distinção não muda nada na prática: **quem desempata é o PID, nunca o
> nome comercial.**
>
> ⚠️ Uma diferença medida que vale saber: o manager do `200c` pede HID **`usage 8`**, enquanto
> todos os outros Cube Controls pedem `4`. Se aquele device expuser uma collection Joystick
> (`usage 4`), ele bate exatamente no muro da PDU5 — `Searching device ...` sem nada no log.
> Ver o passo [5](#passo-5--leds-da-pdu5-pdu7-e-led-brows).

E o que a receita **deveria** cobrir, sem ninguém ter testado: os demais Pokornyi (PDU7, LED
Brows, LMPH, F499, HYP-R PRO, LMP PRO V2, GTE PRO V3), o restante da Cube Controls
(F-PRO, GT-PRO V2, CSX3, GTX2, Astra, e a variante `200c` da AMG) e os demais volantes Conspit (300GT, MAX 01, 310 APEX,
290 GP, PW1, CSD). São **mais de 200 devices** no catálogo do SimHub; os três caminhos abaixo
cobrem a grande maioria.

> **Seu device não está aqui?** Isso é esperado — a bancada é uma só. Vá direto para
> [Meu device não está na lista](#meu-device-não-está-na-lista): quase tudo neste projeto casa
> por **transporte**, não por modelo, e há um roteiro de diagnóstico para descobrir qual é o
> seu.

### Os três caminhos

Todo device do catálogo cai em um destes, e **o caminho certo depende do transporte**, não da
marca:

| caminho | como o SimHub fala | quem usa | passo |
|---|---|---|---|
| **HID** | `/dev/hidraw*` via `winebus` | Pokornyi, Cube Controls | [1](#passo-1--udev-acesso-ao-hardware) + [2](#passo-2--registro-do-winebus-devices-hid) |
| **Serial** | porta COM (CDC) | Conspit, Arduinos da wiki | [3](#passo-3--devices-seriais-conspit-e-arduinos) |
| **Tela VoCore** | libusb, USB bruto | qualquer volante com tela | [4](#passo-4--telas-vocore-a-ponte-libusb) |

Volantes com tela são um **composite**: LEDs **e** tela como devices independentes. As duas
metades precisam de passos diferentes — e os LEDs são o device **primário**, então tela sem
LEDs não conecta.

---

## A pilha de camadas

Este projeto é a camada de cima. Cada uma só faz sentido com a de baixo pronta, e
diagnosticar fora de ordem manda você consertar a coisa errada:

```
linux-simracing-utils   instala o SimHub e cria o prefixo Wine
       ↓
wine-libusb-bridge      faz a libusb funcionar sob Wine (telas VoCore)
       ↓
simhub-devices-linux-configurator  configura os devices na aba Devices        ← este repo
```

`simhub-devices doctor` checa a pilha inteira nessa ordem e diz em qual camada você
está parado.

---

## O caminho, em 5 passos

| passo | o que resolve | obrigatório? |
|---|---|---|
| **1 — udev** | acesso a `/dev/hidraw*` e ao nó USB da tela | **sim**, para HID e telas |
| **2 — registro do winebus** | Wine entrega o device HID real, não o sintetizado pelo SDL | **sim**, para HID |
| **3 — device serial** | dá identidade USB à porta COM, que o Wine não dá | só para Conspit/Arduino |
| **4 — ponte libusb** | faz a tela VoCore ser enxergada e escrita | só para telas |
| **5 — PDU5 / PDU7 / LED Brows** | corrige a collection HID que o manager pede | só para esses três |

Se você só tem uma caixa de botões ou um volante sem tela, **os passos 1 e 2 bastam**.

Em qualquer ponto, `simhub-devices doctor` diz onde você está e o que falta.

---

## Pré-requisitos

```bash
git clone https://github.com/juliscreudo/simhub-devices-linux-configurator.git ~/apps/simhub-devices-linux-configurator
cd ~/apps/simhub-devices-linux-configurator
mkdir -p ~/.local/bin && ln -s "$PWD/tools/simhub-devices" ~/.local/bin/simhub-devices
```

> Se for **contribuir**, ative o hook de pre-commit (uma vez por clone — `core.hooksPath`
> não é versionado):
>
> ```bash
> git config core.hooksPath .githooks
> ```
>
> Ele checa sintaxe (Python, Bash, C) e barra dado pessoal nas linhas adicionadas: serial de
> hardware, caminho `/home/<usuario>`, e-mail, MAC. ⚠️ Serial de volante/base é **credencial
> de garantia**, não metadado — máscare como `<SERIAL>` em vez de apagar o exemplo. VID/PID e
> modelo passam de propósito: são públicos do fabricante e são o dado técnico deste repo.

O resto deste guia chama o comando como `simhub-devices`, sem o `tools/` na frente — o
symlink acima é o que torna isso possível. Confirme que `~/.local/bin` está no seu `PATH`
(a maioria das distros já deixa); se `simhub-devices doctor` der "comando não encontrado",
rode `export PATH="$HOME/.local/bin:$PATH"` (e acrescente ao seu `.bashrc`/`.zshrc`).

### Pacotes

| o que | usado para | Fedora | Arch / CachyOS |
|---|---|---|---|
| Python 3 | o instalador e as ferramentas | `python3` | `python` |
| `dnfile` | análise de IL (passo "meu device não está na lista") | via `venv` | via `venv` |
| `gcc-mingw-w64` *(opcional)* | compilar as sondas `.exe` de diagnóstico | `mingw64-gcc` | `mingw-w64-gcc` |
| `libusb` + `gcc` | compilar a ponte (passo 4) | `libusb1-devel` | `libusb` |

```bash
# Fedora
sudo dnf install -y python3 git mingw64-gcc libusb1-devel

# Arch / CachyOS
sudo pacman -S --needed python git mingw-w64-gcc libusb
```

O `dnfile` só é preciso se você for investigar um device que não está na lista:

```bash
python3 -m venv venv && ./venv/bin/pip install dnfile
```

> ⚠️ No Arch, **não** rode `pip install` global: a PEP 668 bloqueia, e o `venv` é o caminho
> certo.

### SimHub sob Wine (camada 1)

Este projeto **não instala o SimHub**. Ele espera um prefixo já pronto, criado pelo
**[linux-simracing-utils](https://github.com/srounce/linux-simracing-utils)** (srounce), em
`~/apps/linux-simracing-utils/pfx`:

```bash
git clone https://github.com/srounce/linux-simracing-utils ~/apps/linux-simracing-utils
cd ~/apps/linux-simracing-utils
bash install.sh          # escolha o componente SimHub
```

> ⚠️ **Sempre abra o SimHub pelo `lsu-launch-wrapper`** (é o que o `run-simhub` deste repo
> faz). Por fora dele o app abre e os devices funcionam, mas a **telemetria não chega**: é o
> wrapper que sobe o `winehub`, o daemon que espelha a memória compartilhada do jogo para
> dentro do prefixo. O sintoma aparece longe da causa.

### A ponte libusb (camada 2 — só para telas VoCore)

**[wine-libusb-bridge](https://github.com/juliscreudo/wine-libusb-bridge)** substitui a
`libusb-1.0.dll` do app por um repasse à `libusb` do Linux. É o que faz a tela VoCore
funcionar.

Você não precisa baixá-la: o `install bridge` (passo 4) busca a release fixada para `vendor/`
sozinho. **Não é submodule de propósito** — a ponte serve qualquer app Windows sob Wine, não só
o SimHub. Se quiser apontar para outra cópia, use `$SIMHUB_PONTE`; `SIMHUB_PONTE_VERSION` fixa
uma tag.

Se você não tem tela VoCore, **pule** — nada mais neste projeto depende dela.

---

## Passo 0 — diagnóstico

Antes de mexer em qualquer coisa:

```bash
simhub-devices doctor
```

Ele lista os devices conhecidos que estão plugados, diz se cada um tem acesso ao nó certo,
checa as três camadas da pilha e avisa se o **cache NGen** está ativo (ver passo 5).

> ⚠️ **Tudo no instalador é dry-run por padrão.** Sem `--apply`, ele só imprime o que faria.
> O `--apply` funciona em qualquer posição: `install bridge --apply` e
> `install --apply bridge` fazem o mesmo.

Comandos disponíveis:

```
simhub-devices doctor                  diagnóstico (padrão; só leitura)
simhub-devices install udev            ACL de /dev/hidraw* e do nó USB da tela
simhub-devices install registry        winebus: EnableHidraw / Enable SDL / DisableInput
simhub-devices install bridge          DLL da ponte libusb + launcher run-simhub
simhub-devices install pdu5-leds       patch do usagePage + remoção do cache NGen
simhub-devices install serial [...]    receita serial: nó PnP + porta COM
simhub-devices install shortcut        atalho de menu que abre pelo run-simhub
simhub-devices post-update             refaz o que um update do SimHub desfaz
simhub-devices clean-cache             remove o cache NGen
```

---

## Passo 1 — udev (acesso ao hardware)

Este é **o passo que destrava a receita HID**, e por muito tempo eu achei que fosse o
registro. Não é.

```bash
simhub-devices install udev --apply
```

Instala `udev/70-pokornyi.rules` e `udev/70-vocore.rules`, recarrega as regras e dispara o
trigger. Replugue o device (ou reinicie) se a ACL não aparecer.

Por padrão `/dev/hidraw*` é **root-only**: o `winebus` tenta abrir, falha, e **descarta o
device em silêncio** — nem erro, nem log, só o `Searching device ...` para sempre. O mesmo vale
para a tela, que precisa de **escrita** no nó USB para a libusb reivindicar a interface.

> ⚠️ **O prefixo `70-` é obrigatório.** Quem efetiva a `TAG+="uaccess"` é o
> `73-seat-late.rules` do systemd, e uma regra `99-` chega depois dessa checagem: o hidraw
> continua root-only, silenciosamente. Vale para qualquer regra que você acrescente.

> ⚠️ A regra dos Pokornyi casa `0483:cb??`, **não** o vendor inteiro — `0483` é o VID genérico
> da STMicroelectronics, e liberá-lo todo daria acesso a hardware sem relação nenhuma com sim
> racing. Como todo PID Pokornyi está na faixa `CBxx`, um modelo novo funciona sem editar o
> arquivo. A da VoCore casa o PID `1004` exato, porque `c872` é **também** o VID da Cube
> Controls.

Confira:

```bash
simhub-devices doctor        # a linha do seu device deve dizer "acessivel"
```

## Passo 2 — registro do winebus (devices HID)

```bash
simhub-devices install registry --apply
wineserver -k                      # o winebus precisa reler
```

Escreve três valores em `HKLM\System\CurrentControlSet\Services\winebus`:

| valor | tipo | papel |
|---|---|---|
| `EnableHidraw` | `REG_MULTI_SZ` | **quem faz o trabalho**: uma linha `VVVV:PPPP` por device |
| `Enable SDL` | `REG_DWORD` `0` | metade da rede de segurança |
| `DisableInput` | `REG_DWORD` `1` | a outra metade — **só funciona com as duas** |

> ⚠️ A chave é `Services\`**`winebus`**, **não** a subchave `\Parameters` — o driver nunca lê
> `\Parameters`. Escrever no lugar errado é ignorado **em silêncio**; esse erro custou três
> dias no projeto irmão da Conspit.

O que isso muda: por padrão o Wine entrega joysticks **sintetizados pelo SDL**, com uma
collection só. Os canais vendor de 64 bytes por onde os LEDs falam simplesmente **não existem**
para o app. Em **hidraw** o Wine passa o descriptor real e o `hidclass` separa as top-level
collections em `&Col01`/`&Col02`, como no Windows.

### Verificação com o `hidenum`

Esta é a medição que diz se o passo funcionou. Compile e rode **dentro do prefixo**:

```bash
x86_64-w64-mingw32-gcc tools/hidenum.c -o tools/hidenum.exe -lhid -lsetupapi
WINEPREFIX=~/apps/linux-simracing-utils/pfx wine tools/hidenum.exe 0483
```

Sem argumento lista tudo; com argumentos, filtra por VID em hex. **O esperado não é sempre
"duas linhas"** — depende da topologia do report descriptor:

| descriptor | esperado no `hidenum` |
|---|---|
| collections **irmãs** (ex.: Conspit CPP.LITE) | **duas** linhas: `usage 0x04` e `usage 0x3A`, ambas `in 64 out 64` |
| vendor **aninhada** (todos os Pokornyi) | **uma** linha: `usage 0x04`, `in 64 out 64` |
| ainda sintetizado pelo SDL | `usage 0x05` com `out 0` — **errado** nos dois casos |

O O Wine só promove a PDO as collections **irmãs**; numa vendor aninhada o canal vem pelo
**mesmo handle** do joystick — por isso os LEDs dos MCP funcionam com um PDO só.

> ⚠️ **A enumeração tem corrida.** Logo após um `wineserver -k` a primeira passada pode não
> listar tudo. Meça sempre na segunda, com ~3 s de intervalo.

## Passo 3 — devices seriais (Conspit e Arduinos)

Só para quem tem device do caminho **serial**. No catálogo do SimHub, **todos os sete volantes
Conspit** passam por aqui (medido em 2026-08-19), assim como os Arduinos da wiki oficial.

Primeiro veja o que está plugado:

```bash
simhub-devices install serial
```

Sem `--dev` ele só lista os devices seriais disponíveis. Depois:

```bash
simhub-devices install serial \
    --dev /dev/serial/by-id/usb-CONSPIT_H.AO_XXXXXXXX-if00 \
    --vid 3514 --pid 0007 --com 37 --nome 'CONSPIT H.AO' --apply
wineserver -k
```

### Por que isso é necessário

No Wine **toda porta COM nasce sem identidade USB** (medido: 36 portas, todas `VID=0 PID=0`),
e o SimHub casa o device justamente pelo VID/PID da porta. Sem um nó PnP que carregue esses
dados, o casamento falha em silêncio. O instalador cria esse nó.

> ⚠️ **O SimHub lê `DEVPKEY_NAME`**, e o Wine só o resolve por uma subchave `Properties\...`
> com valor `hex(ffff0012)`. `FriendlyName`/`DeviceDesc` legados **não substituem** — o nó
> "legado" que basta para Qt e ConspitLink **não basta aqui**. Use `tools/nameprobe.c` para
> ver qual API responde o quê, e [CLAUDE.md](CLAUDE.md) para a cadeia completa.

> ⚠️ **Use COM > 32.** O `wineboot` preenche `com1..com32` varrendo `/dev/ttyS*` e sobrescreve
> qualquer symlink nessa faixa. O instalador recusa números ≤ 32.

> ⚠️ **`wineserver -k` no fim é obrigatório**: o `SERIALCOMM` é volátil e só é repovoado
> quando o wineserver reinicia. Symlink criado com ele de pé não aparece.

> ⚠️ Sempre use `/dev/serial/by-id/` — `ttyACMn` renumera a cada reenumeração.

## Passo 4 — telas VoCore (a ponte libusb)

Só para volantes e dashes com tela.

```bash
simhub-devices install bridge --apply
run-simhub                              # abre a ponte e o SimHub, nessa ordem
```

O `install bridge` baixa (ou compila) a ponte, preserva a `libusb-1.0.dll` original como
`.orig`, instala a da ponte no lugar e cria o link `~/.local/bin/run-simhub`.

### Por que uma ponte, e não um driver

A tela **não tem driver de display**: o SimHub a escreve como device USB bruto, por libusb
(`SimHub.BitmapDisplay.Vocore.dll` → `SimHub.LibUsbNative.dll` → `libusb-1.0.dll`). No Windows
o instalador do SimHub **liga o WinUSB ao device** — sem isso, a libusb não fala com ele.

> ⚠️ **Não tente reproduzir esse passo no prefixo.** Instalaria um driver de kernel do Windows,
> que o Wine não executa; e a `winusb.dll` builtin do Wine é **stub**. Não há hoje nada no Wine
> que faça o backend Windows da libusb funcionar.

A ponte pula tudo isso: uma DLL **PE32 pura** repassa as 32 chamadas a um helper nativo que
fala com a `libusb-1.0.so` do Linux. E resolve um segundo problema de brinde: como toda tela
VoCore é `c872:1004`, o SimHub descobre a qual volante cada uma pertence subindo a árvore USB —
árvore que **não existe no PnP do Wine**, mas que ele pede à própria libusb, e a do Linux a tem.

- ✅ O **toque** da tela funciona pela mesma ponte, sem evdev e sem disputa com o desktop: o
  kernel sequer vê a tela como input, já que nenhum driver a reivindica.
- ⚠️ **Sempre use o `run-simhub`.** O helper precisa estar de pé **antes** do SimHub, senão a
  DLL devolve erro e a tela não conecta; e um helper pendurado depois que o SimHub morre deixa
  a interface reivindicada, dando `LIBUSB_ERROR_BUSY` na próxima abertura. O launcher cuida
  dos dois lados. **Abrir pelo atalho de menu do Windows/Wine não conta** — ele chama o
  SimHub direto, sem a ponte. `simhub-devices install shortcut --apply` cria um atalho
  de menu que já passa pelo `run-simhub`.
- ⚠️ Se você tiver o módulo de kernel `mpro_drm` carregado, **descarregue** (`rmmod mpro`): com
  ele o kernel reivindica a interface e a ponte para de enxergar o device. Os dois não convivem.

## Passo 5 — LEDs da PDU5, PDU7 e LED Brows

Só para esses três. Se seu volante não é um deles, **pule** — mas leia
[o item 4 do roteiro de diagnóstico](#4-hid-confira-o-usagepage-do-seu-manager), porque a
mesma armadilha pode existir em outro manager.

```bash
simhub-devices install pdu5-leds --apply
```

O comando faz **duas** correções, e **nenhuma sozinha resolve** (verificado por eliminação):

1. **A collection HID errada.** `PokornyiPEPDU5Manager` procura a collection **vendor**
   (`usagePage 0xFF`), mas o descriptor da PDU5 é uma collection Joystick **vazia** com a
   vendor **aninhada** dentro — e o Wine só promove a PDO as collections irmãs. O único PDO
   que existe é `0x0001/0x04`, então o filtro nunca casa. O patch troca dois opcodes no IL.
2. **O cache NGen.** O prefixo tem imagens nativas pré-compiladas, e o SimHub roda **32-bit**
   executando a de `SimHub.Plugins`: **o IL da DLL é ignorado**. Sem remover a imagem, o patch
   é um no-op.

> ⚠️ **Se você for patchear qualquer coisa no SimHub, lembre do NGen.** Sondas compiladas para
> **x64** JIT-am o IL do disco e "provam" que o patch funciona, enquanto o app 32-bit usa a
> imagem nativa e não muda nada — os dois mundos nunca concordam. Para detectar: altere uma
> constante fácil de observar num manager que já funciona e veja se o app reage. Se não reagir,
> é NGen. O caso completo está em [CLAUDE.md](CLAUDE.md).

> ⚠️ **Por que a falha era totalmente silenciosa.** A linha de log `Scanning ...` do
> `PokornyiDriver` vem **depois** do filtro de collection. Com o `usagePage` errado a lista sai
> vazia e **não há uma única linha** — nem erro, nem "Scanning".

## Depois de cada update do SimHub

Um update reinstala a `libusb-1.0.dll` original **e roda o `ngen` de novo**. Sem refazer os
dois passos, a tela e os LEDs da PDU5 param **sem avisar**:

```bash
simhub-devices post-update --apply
```

---

## Meu device não está na lista

A bancada é uma só, e o catálogo do SimHub tem **mais de 200 devices**. Quase tudo neste
projeto casa por **transporte**, não por modelo — a regra udev cobre todos os Pokornyi, as
chaves de registro são globais ao prefixo, e toda tela VoCore é `c872:1004`. Então há uma boa
chance de o seu device simplesmente funcionar depois dos passos 1 e 2.

Se não funcionar, este é o roteiro. Ele serve para qualquer marca.

### 1. Ele está no catálogo do SimHub?

```bash
SH=~/apps/linux-simracing-utils/pfx/drive_c/Program\ Files\ \(x86\)/SimHub
./venv/bin/python tools/ildump.py "$SH/SimHub.Plugins.dll" 'GetDevices>d__0' \
  | grep ldstr | awk -F"'" '{print $2}' | grep -vE '^[0-9A-F]{8}-' | sort -u
```

Isso lista os nomes de device do catálogo inteiro. Filtre pela sua marca:

```bash
... | grep -i ascher
```

Se o seu device **não aparece**, ele não tem descritor no SimHub e este projeto não ajuda —
o caminho é o protocolo customizado do SimHub (Arduino / serial genérico), que é assunto da
wiki oficial da Wotever, não daqui.

### 2. Qual é o transporte?

Esta é a pergunta que decide tudo, e você a responde **antes** de mexer no prefixo. Ache o
driver do seu device e veja o que ele usa:

```bash
./venv/bin/python tools/ildump.py "$SH/BA63Driver.dll" "AscherDriver" \
  | grep -oE "HidDevice[A-Za-z]*|SerialPort[A-Za-z]*" | sort | uniq -c
```

| o que aparece | transporte | vá para |
|---|---|---|
| `HidDeviceList`, `HidDeviceExtensions` | **HID** | passos [1](#passo-1--udev-acesso-ao-hardware) e [2](#passo-2--registro-do-winebus-devices-hid) |
| `SerialPortBase`, `SerialPorts` | **serial** | passo [3](#passo-3--devices-seriais-conspit-e-arduinos) |
| tem `BitmapDisplayDevice` no descritor | **tela VoCore** | passo [4](#passo-4--telas-vocore-a-ponte-libusb) |

⚠️ Duas armadilhas de onde procurar:

- Os **managers** estão em `SimHub.Plugins.dll`; os **drivers**, em `BA63Driver.dll`. Procurar
  na DLL errada devolve vazio e parece que o tipo não existe.
- Volantes com tela são **composite**: precisam do transporte dos LEDs **e** do passo 4. Os
  LEDs são o device **primário** — se eles não conectam, a tela também não.

### 3. Descubra o VID/PID e siga a receita

```bash
lsusb                              # com o device plugado
simhub-devices doctor        # diz se ele já é conhecido e se o acesso está ok
```

Se o VID não for `0483` (Pokornyi), `c872` (Cube Controls / VoCore) nem `3514` (Conspit), você
precisa acrescentá-lo:

- **udev**: copie `udev/70-pokornyi.rules` para `udev/70-<marca>.rules` e troque
  `idVendor`/`idProduct`. Mantenha o prefixo `70-` e prefira `TAG+="uaccess"` a
  `MODE="0666"` — o primeiro dá acesso só ao usuário da sessão ativa.
- **registro**: acrescente o par ao dicionário `CATALOGO` no topo de `tools/simhub-devices` e
  rode `install registry --apply`. O `EnableHidraw` é montado a partir dele.

Depois **meça com o `hidenum`** (passo 2) — é ele que diz se o Wine passou a entregar o
device real ou continua entregando o sintetizado pelo SDL.

### 4. HID: confira o `usagePage` do SEU manager

⚠️ **Este é o passo que ninguém pensa em fazer, e é o que travou a PDU5 por dias.**

Cada manager pede uma collection HID específica, e o argumento sai como **constante no IL**. O
valor é **por manager**, não por marca — dois devices da mesma fabricante podem pedir coisas
diferentes.

```bash
./venv/bin/python tools/ildump.py "$SH/SimHub.Plugins.dll" "PokornyiPEPDU5Manager" \
  | grep -B8 "GetDevice" | grep "ldc.i4"
```

A assinatura é `GetDevice(mapper, pid, usagePage, usage, BWButtonsCount, serial, vid)`, então
as constantes saem nesta ordem:

```
ldc.i4  51969 (0xCB01)   <- pid
ldc.i4  1                <- usagePage   ]  precisa casar com o que o
ldc.i4  4                <- usage       ]  hidenum mostrou
ldc.i4  0                <- BWButtonsCount
ldc.i4  1155 (0x483)     <- vid
```

Compare `usagePage`/`usage` com a linha que o `hidenum` imprimiu para o seu device. Se não
baterem, o filtro `MatchUsage` nunca casa e **não há uma única linha no log** — nem erro, nem
"Scanning". Nesse caso `tools/pdu5-leds-patch.py` serve de modelo: são dois opcodes de mesmo
tamanho, e o script confere que a assembly não é strong-named antes de escrever.

⚠️ **Se você patchear qualquer coisa, remova o cache NGen** (`install pdu5-leds` já faz, ou
`clean-cache --apply`). Sem isso o patch é um no-op no app — ver [passo 5](#passo-5--leds-da-pdu5-pdu7-e-led-brows).

### 5. "Falhou" não é a mesma coisa que "nem foi tentado"

Esta distinção é o motivo de o instalador existir, e ela muda para onde você olha:

| o que você vê | o que significa | onde procurar |
|---|---|---|
| `Searching device ...` na UI | o SimHub **está tentando** e não achou | acesso (udev), registro, VID/PID |
| device aparece no log em DEBUG, mas não conecta | ele **foi varrido** e falhou | driver, serial number, firmware |
| **nada** no log em DEBUG | ele **nem foi escaneado** | `usagePage`, cache NGen — a montante do driver |

Para ver o log em DEBUG, ajuste o nível em `SimHubWPF.exe.config` dentro do prefixo.

### 6. Contribua a medição de volta

Se você conseguir (ou não conseguir) fazer um device funcionar, o dado que interessa é: **a
saída do `hidenum`**, as **constantes do manager** e o que apareceu no log. É com isso que dá
para dizer se a receita generaliza ou se aquele modelo tem algo próprio. Abra uma issue com
esses três.

> ⚠️ **Os seriais agora saem mascarados por padrão — confira mesmo assim.** Serial não é só
> identificador: vários fabricantes o usam como prova de titularidade para acionar garantia. Se
> alguém abrir um chamado com o **seu**, quem pode ficar sem cobertura é você. Por isso o
> `hidenum` imprime `<INSTANCIA>` no lugar do instance ID (`--serial` devolve o valor real, para
> uso local) e o dry-run do `install serial` ecoa `<SERIAL>` no lugar do serial USB. O que vier
> de outra fonte, troque à mão.
>
> O `doctor` também imprime caminhos absolutos com o seu nome de usuário — bem menos grave, mas
> troque por `~/` se quiser. **VID/PID e modelo podem ficar**: são públicos do fabricante e são
> justamente o dado técnico que interessa na issue.

---

## Problemas conhecidos

### O device não aparece, e não há nada no log

Na ordem de probabilidade:

1. **`/dev/hidraw*` sem ACL** — passo 1. É a causa mais comum e a mais silenciosa.
2. **`winebus` sem `EnableHidraw`** — passo 2. Confira com o `hidenum`: `usage 0x05` com
   `out 0` significa que você ainda está com o joystick sintetizado pelo SDL.
3. **`usagePage` errado no manager** — item 4 do roteiro acima.
4. **Cache NGen** engolindo um patch — passo 5.

### Entradas PnP obsoletas

Um `Enum\HID\VID_xxxx&PID_xxxx*` remanescente — típico de trocar uma PCB pela mesma de outro
serial — faz a collection ser registrada mas nunca ficar "present", e o driver recebe `null`.
Aparece como `NullReferenceException` a cada 2 s no log. Apagar as entradas e deixar o Wine
recriar resolve, mas a limpeza ainda é manual: exige editar `system.reg` com o wineserver
parado.

### Sonda HID devolve lista vazia

⚠️ **Sondas HID só funcionam com o SimHub PARADO.** Com ele de pé,
`HidDeviceList.GetHidDevices` devolve lista vazia para **todos** os PIDs, inclusive os que ele
mesmo tem conectados.

### Composites não logam `Device Status changed` com dois campos

Nem os que funcionam. Eles usam a forma de **três** campos, com o `CompositeLabel`. Concluir
"o device não recebe `Update()`" a partir da ausência do log de dois campos é **inválido** —
essa conclusão errada custou tempo aqui.

### Erros de `FindGamePath` / `CompatibilityStoreHelper` no log

São de outra natureza (achar jogos instalados, Steam nativo). **Não** são pista de problema de
device — ignore ao diagnosticar a aba Devices.

---

## Ferramentas

| arquivo | o que faz |
|---|---|
| `tools/simhub-devices` | **o instalador e o diagnóstico** — dry-run por padrão |
| `tools/run-simhub` | sobe a ponte libusb e o SimHub na ordem certa, e limpa ao sair |
| `tools/pdu5-leds-patch.py` | patch do `usagePage` da PDU5 (`--check` / `--apply` / `--revert`) |
| `tools/ildump.py` | desmonta o IL de um tipo — chamadas e constantes sobrevivem à ofuscação |
| `tools/ilgrep.py` | acha quem chama um método |
| `tools/ilcommon.py` | leitura de metadados .NET compartilhada pelas três acima |
| `tools/hidenum.c` | enumera HID **de dentro do prefixo**: o que o SimHub enxerga |
| `tools/nameprobe.c` | mostra qual API do SetupAPI responde o quê (usado no passo 3) |
| `udev/70-pokornyi.rules` | ACL de `/dev/hidraw*` para Pokornyi (`0483:cb??`) |
| `udev/70-cubecontrols.rules` | ACL de `/dev/hidraw*` para Cube Controls (`c872:20??`) |
| `udev/70-vocore.rules` | ACL de escrita no nó USB da tela VoCore (`c872:1004`) |
| `attic/` | o caminho superado (`mpro_drm` + MMF) — fallback, fora da instalação |

As duas sondas em C se compilam com mingw:

```bash
x86_64-w64-mingw32-gcc tools/hidenum.c   -o tools/hidenum.exe   -lhid -lsetupapi
x86_64-w64-mingw32-gcc tools/nameprobe.c -o tools/nameprobe.exe -lsetupapi
```

### O SimHub é ofuscado

O repo público (`SHWotever/SimHub`) tem só wiki e issues. **A fonte de verdade são as DLLs do
prefixo**, e o código é ofuscado — nomes de método viram caracteres CJK (`귇`, `궏`…). O que
sobrevive à ofuscação, e é o que as ferramentas acima extraem: **strings, constantes e
chamadas**.

O detalhamento técnico completo — arquitetura da aba Devices, as hipóteses testadas e
refutadas, e as armadilhas de método — está em [CLAUDE.md](CLAUDE.md) (em português; também
serve de contexto para LLM).

---

## Segurança

⚠️ **Se você tem uma base direct drive de alto torque, leia isto.** O SimHub varre portas
seriais procurando Arduinos, e uma base OpenFFBoard aparece mapeada em mais de uma COM. Ela
ignora texto que não seja comando válido, então o risco é baixo — mas **confira se o
auto-detect de Arduino do SimHub está restrito às portas certas**, e nunca mande `=`,
`sys.0.save`, `sys.0.format` ou calibração `odrv.*` numa porta que possa ser a base.

As sondas de diagnóstico deste repo são **somente leitura** por padrão, e o instalador é
**dry-run** até você passar `--apply`. Escrever no registro do prefixo é reversível (o
instalador faz backup de `system.reg` antes); escrever na firmware não é.

---

## Escopo e créditos

- Foco sim racing, Linux, SimHub sob Wine. Um único setup: o do autor.
- Nada aqui porta ou redistribui software de terceiros. O SimHub é da
  **[Wotever](https://www.simhubdash.com/)**; o `linux-simracing-utils` e o Winecarte são da
  **[srounce](https://github.com/srounce)**; a ponte libusb é
  **[nossa](https://github.com/juliscreudo/wine-libusb-bridge)**, mas vive em repo próprio
  porque serve qualquer app Windows sob Wine.
- Este repo é **análise e configuração**.
- Projeto pessoal, sem garantia nem suporte.

Licenciado sob **[GPL-3.0](LICENSE)**: use, estude, modifique, forke. Quem distribuir uma versão
modificada tem de manter o fonte aberto sob a mesma licença — ninguém fecha isto num produto
proprietário. ⚠️ A licença cobre **este repo**; o SimHub continua sendo da Wotever, sob os
termos dela.
