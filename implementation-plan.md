# Plano — tela VoCore da PDU5 no SimHub sob Linux

**Versão 3 — 2026-08-18.** A v2 foi reescrita a partir de medições com a bancada ligada; a
v3 registra o desfecho: **a tela funciona pela aba Devices do SimHub**, via ponte de
tradução da libusb (seções 8.1 e 8.2). O caminho `mpro_drm` + MMF das Fases 0-4 vira
**fallback** — fica documentado, mas não é mais o plano principal.

Convenção do projeto: ✅ **medido** = tem comando e saída neste documento;
⚠️ **inferido** = mecanismo identificado, não verificado. Não apague as marcas.

---

## 1. Objetivo e escopo

**Entregar o dash do SimHub na tela VoCore M-PRO da PDU5**, usando o device
`Special : Generic MMF rendering V2` da própria aba Devices como fonte dos frames e o
driver DRM `mpro_drm` como saída.

**Entra:** frames SimHub → tela; brilho; touch (a implementar); startup automatizado.

**NÃO entra — e precisa ficar dito:**

| Fora do escopo | Por quê |
|---|---|
| LEDs da PDU5 | `PokornyiPEPDU5Manager` pede `usagePage 0xFF / usage 1`; o Wine só expõe o PDO `0x0001/0x04`. Sem correção por registro ou udev — ver [CLAUDE.md](CLAUDE.md) e **H8** abaixo. |
| Device `Generic Vocore Screen` nativo | Bloqueado por driver/`winusb` (seção 3). Fica desabilitado no SimHub. |
| Associação automática tela↔volante | O MMF é um device genérico: quem escolhe o dash é você, não a topologia. |

⚠️ **Tela funcionando ≠ PDU5 funcionando.** Ao fim deste plano a PDU5 mostra o dash e
continua sem LEDs.

---

## 2. Estado medido da bancada (2026-08-18 15:42)

Tudo está atrás de uma cascata de hubs USB, em um único barramento **Bus 005 (480M)**.
Isso não é detalhe: é o que explica a associação tela↔volante e o que limita a banda.

### 2.1 Árvore USB ✅ medido (`lsusb -t`, `/sys/bus/usb/devices/5-*`)

```
Bus 005  root_hub xhci (2 portas, 480M)
└─ 5-2            0bda:5411  Realtek RTS5411          480M   ← hub principal da bancada
   ├─ 5-2.1       0bda:5411  RTS5411                  480M   (vazio)
   ├─ 5-2.2       0bda:5411  RTS5411                  480M
   │  ├─ 5-2.2.1      3514:0005  CONSPIT CPP.LITE      12M   HID
   │  ├─ 5-2.2.2      1a86:8091  QinHeng HUB          480M
   │  │  ├─ 5-2.2.2.1 303a:8333  FFB_Pedal_Brake       12M   HID
   │  │  └─ 5-2.2.2.2 1a86:55d3  CH340 Serial          12M   → ttyACM1
   │  ├─ 5-2.2.3      05e3:0610  Genesys HUB          480M
   │  │  ├─ 5-2.2.3.3 3514:0301  CONSPIT ARES          12M   ACM+HID → ttyACM0  ⚠️ base 20 Nm
   │  │  └─ 5-2.2.3.4 3514:0300  CONSPIT               12M   HID
   │  └─ 5-2.2.4      0424:2514  Microchip HUB        480M
   │     ├─ 5-2.2.4.1   0483:cb42  MCP IgnitionBox     12M   HID
   │     ├─ 5-2.2.4.2   1a86:8091  QinHeng HUB        480M   ← hub INTERNO do conjunto PDU5
   │     │  ├─ 5-2.2.4.2.3  0483:cb01  PE PDU5         12M   HID
   │     │  └─ 5-2.2.4.2.4  c872:1004  M-PRO Screen   480M   vendor ff, Driver=[none]
   │     ├─ 5-2.2.4.3   0483:cb41  MCP EncoderBox      12M   HID
   │     └─ 5-2.2.4.4   0483:cb40  MCP ButtonBox       12M   HID
   ├─ 5-2.3       0bda:5411  RTS5411                  480M   (vazio)
   └─ 5-2.4       0bda:5411  RTS5411                  480M   (vazio)
```

**A descoberta que importa:** a PDU5 (`5-2.2.4.2.3`) e a tela (`5-2.2.4.2.4`) penduram no
**mesmo hub interno** `5-2.2.4.2` (QinHeng `1a86:8091`). Essa é exatamente a relação
`HasParentHub=True` que o SimHub usa no Windows para saber que aquela tela é *daquele*
volante — e ela **existe de fato no Linux**, é só o Wine que não a expõe (seção 3).
Guarde isto: é o argumento central de **H7**.

⚠️ A tela é o **único device 480M** do ramo do volante; todo o resto é 12M via TT do hub.

### 2.2 Devices, nós e permissões ✅ medido

| device | VID:PID | port path | nó | ACL do usuário |
|---|---|---|---|:---:|
| PE MCP IgnitionBox | `0483:cb42` | `5-2.2.4.1` | `/dev/hidraw10` | ✅ |
| PE MCP EncoderBox | `0483:cb41` | `5-2.2.4.3` | `/dev/hidraw11` | ✅ |
| PE MCP ButtonBox | `0483:cb40` | `5-2.2.4.4` | `/dev/hidraw13` | ✅ |
| **PE PDU5** | `0483:cb01` | `5-2.2.4.2.3` | `/dev/hidraw12` | ✅ |
| **VoCore M-PRO Screen** | `c872:1004` | `5-2.2.4.2.4` | `/dev/bus/usb/005/033` | ✅ `rw` |
| CONSPIT ARES | `3514:0301` | `5-2.2.3.3` | `ttyACM0` + `/dev/hidraw14` | ✅ |
| CONSPIT | `3514:0300` | `5-2.2.3.4` | `/dev/hidraw15` | ✅ |
| CONSPIT CPP.LITE | `3514:0005` | `5-2.2.1` | `/dev/hidraw9` | ✅ |
| FFB_Pedal_Brake | `303a:8333` | `5-2.2.2.1` | `/dev/hidraw16` | ❌ **sem ACL** |

- As três regras estão **instaladas e funcionando**: `/etc/udev/rules.d/70-{conspit,pokornyi,vocore}.rules` ✅
- O nó USB da tela já nasce `crw-rw-r--+` com ACL `user:<USUARIO>:rw-` ✅ — a regra VoCore cumpre o papel dela.
- O usuário está nos grupos **`video`** e **`input`** ✅ → `/dev/fbN` e evdev **sem sudo**.
- ⚠️ O **H.AO HUB (`3514:0007`)** da tabela do CLAUDE.md **não está nesta árvore**. O que há
  são `3514:0300` e `3514:0301`. Reconferir antes de usar a receita 2 nesta configuração.

### 2.3 Tela VoCore ✅ medido (`lsusb -v -d c872:1004`)

```
iManufacturer  VoCore        iProduct  M-PRO Screen        bcdDevice 1.a0
bInterfaceClass 255 (vendor)  bNumEndpoints 2   Driver=[none]   480M (USB 2.0 HS)
  EP 0x81 IN   64 bytes      EP 0x02 OUT  512 bytes (bulk)
```

Nenhum driver do kernel ocupa a interface hoje → livre tanto para o `mpro_drm` quanto para
o caminho libusb do Wine (**nunca os dois ao mesmo tempo** — ver 5.1).

### 2.4 Software ✅ medido

| item | estado |
|---|---|
| SimHub | **9.11.22** (`SimHubWPF.exe`) — bate com a versão para a qual os offsets do MMF foram medidos |
| `Special : Generic MMF rendering V2` | existe no catálogo (string UTF-16 em `SimHub.Plugins.dll`) |
| Protocolo MMF | `SimHubDashRenderv2`, `RenderBuffer1`, `RenderBuffer2`, `Rendering request timeout` em `SimHub.BitmapDisplay.MMF.dll` |
| `mpro.ko` | compilado, `vermagic 7.1.8-1-cachyos` == kernel rodando; alias `usb:vC872p1004` |
| Relay compilado | `mmf-vocore-relay.exe` já existe no prefixo (16/ago 04:49) |
| Caminho já exercitado? | **não** — zero ocorrências de "MMF" em 16 MB de log do SimHub; `/dev/shm/simhub-mpro` inexistente |
| Sessão gráfica | **KDE Plasma / `kwin_wayland`** — relevante para **H1** |
| Wine | 11.15, WoW64 novo: há `i386-windows`, **não há `i386-unix`**; `winegcc`/`winebuild` presentes; `libusb-1.0.so` no host — relevante para **H7** |

---

## 3. Por que o caminho nativo do SimHub não fecha hoje

Ordem correta dos bloqueios (a v1 deste plano invertia os dois):

1. **Bloqueio primário — nenhum driver ligado ao nó, e `winusb.dll` é stub.**
   O nó PnP da tela nasce com `ClassGUID={00000000-…}` e **sem valor `Service`**, e nenhuma
   device interface é registrada (`GUID_DEVINTERFACE_USB_DEVICE`/`WINUSB` ausentes, em
   prefixo do SimHub e em prefixo limpo). A libusb classifica o device **lendo qual driver
   está ligado** (`The following device has no driver: '%s'`), então ele nunca entra na
   lista → `Screen ID` vazio, `Connection status: Not found`. E a `winusb.dll` do Wine que
   atenderia as chamadas é **stub** (`"(%p) - stub"` nas strings). O Wine traz `wineusb.sys`
   (bus driver) mas **nenhum `winusb.sys`** function driver.

2. **Bloqueio secundário — topologia USB ausente.**
   `PortSignature`/`UsbPath` do `WoteverCommon` lançam `NullReferenceException` em 100% dos
   devices, porque nenhum controlador USB é exposto. Isso decide *a qual volante* uma tela
   pertence — irrelevante enquanto (1) impedir que **qualquer** tela seja enumerada.

⚠️ **Correção de rumo em relação à v1:** ela dizia que resolver isso exigiria "implementar
`winusb.sys` no Wine — meses/anos". Isso descarta uma medição do próprio repo: a
`SimHub.LibUsbNative.dll` faz P/Invoke de **32 funções síncronas** da `libusb-1.0.dll`, e
uma DLL winelib que as repasse à `libusb-1.0.so` do host **dispensa SetupAPI, WinUSB e
topologia de uma vez**. O obstáculo real é outro — WoW64 32-bit — e está em **H7**.

---

## 4. Arquitetura escolhida

```
SimHub (Wine)  ── device "Special : Generic MMF rendering V2"  [aba Devices]
      │  MMF nomeado  SimHubDashRenderv2
      ▼
mmf-vocore-relay.exe (dentro do prefixo)      tools/mmf-vocore-relay.cs
      │  Z:\dev\shm\simhub-mpro   (mmap compartilhado Wine ↔ Linux)
      ▼
mpro-dash-daemon.py (nativo)                   tools/mpro-dash-daemon.py
      │  /dev/fbN   (fbdev emulation do DRM)
      ▼
mpro.ko  ──USB bulk EP 0x02 (RGB565)──►  VoCore M-PRO  [5-2.2.4.2.4]
      ▲
      └── touch: input_dev do mpro (ABS_X/ABS_Y/BTN_TOUCH) ──► daemon ──► relay ──► SimHub
```

**Por que esta arquitetura e não SimMonitor/monocoque:** o `Generic MMF rendering V2` é
**uma entrada da própria aba Devices**. O dash sai do SimHub, com as configurações do
SimHub, por um device do SimHub — é a integração nativa com o transporte trocado, não uma
solução paralela. O que se perde em relação ao device `Generic Vocore Screen` é só a
associação automática tela↔volante.

---

## 5. Inventário honesto do que existe

### 5.1 Fatos operacionais que condicionam tudo

- ⚠️ **`mpro` e o caminho USB do Wine são mutuamente exclusivos.** Com o módulo carregado o
  kernel reivindica a interface e `wineusb`/libusb perdem o device. `sudo rmmod mpro` desfaz.
  Consequência prática: **desabilite o device `Generic Vocore Screen` no SimHub**, senão ele
  fica em ciclo de start/close do subprocesso VOCORE a cada 2 s.
- **Resolução: 854×480** ✅ (informado pelo usuário, 2026-08-18).
  ⚠️ **Isso implica rotação, e o daemon não a tem.** O `mpro_mode_config_setup()` escolhe o
  modo por `mpro->screen` lido do device (`mpro.c:497`), e o caso que bate com 854 é
  `MODEL_5IN` (`case 0x00000005`), que o driver expõe como **480 largura × 854 altura —
  retrato**, com `margin = 320` se `version != 3`. Ou seja: o painel é retrato e a PDU5 o
  monta girado 90°, que é por que o dash útil é 854×480 paisagem. Consequências:
  1. o daemon pediria **480×854** ao SimHub (ele lê o fb por ioctl) → dash retrato, errado;
  2. falta **rotação de 90°** no caminho de pixel — e ela custa CPU a cada frame (numpy volta
     a ser dependência real, agora por transposição e não por 16bpp);
  3. o **touch** precisa da mesma rotação + troca de eixos: o `input_dev` reporta
     `ABS_X 0..width`, `ABS_Y 0..height` em coordenadas **do painel**, não do dash.
  ⚠️ Confirmar o modelo no `dmesg` no passo 1.1 antes de escrever a rotação — se o driver
  reportar 854×480 direto, os três itens acima caem.
- Formato: `mpro_pipe_formats` tem **só `DRM_FORMAT_XRGB8888`** → o `/dev/fbN` sai **32bpp**,
  e o driver converte para RGB565 na hora de mandar pro painel. O ramo 16bpp/numpy do daemon
  é código morto neste hardware; **numpy não é dependência real**.

### 5.2 Dívidas conhecidas no código (não são "pronto")

| item | onde | estado real |
|---|---|---|
| **Touch** | [mpro-dash-daemon.py:12](tools/mpro-dash-daemon.py#L12) | ❌ **não implementado**. O relay já lê `B_TP/B_TX/B_TY/B_ACT` do bridge ([relay:154-166](tools/mmf-vocore-relay.cs#L154-L166)), mas **ninguém escreve**. O docstring do daemon diz `[fase 2]`. |
| **Brightness** | [mpro-dash-daemon.py:187](tools/mpro-dash-daemon.py#L187) | ⚠️ meio-caminho: `acha_backlight()` casa certo (`mpro.c:352` registra `mpro_backlight`), mas `/sys/class/backlight/*/brightness` é root-only e o `PermissionError` é engolido em silêncio. **Falta regra udev.** |
| **Detecção de bridge inválido** | [mpro-dash-daemon.py:35](tools/mpro-dash-daemon.py#L35) | `MAGIC` e `B_ALIVE` são definidos e **nunca lidos** — o daemon não distingue "relay morto" de "sem frames". |
| **Tearing** | [relay:143](tools/mmf-vocore-relay.cs#L143) | bridge de buffer único, sem seqlock: o relay sobrescreve ~1 MB enquanto o daemon lê. |
| **Requester sujo** | [relay:110-111](tools/mmf-vocore-relay.cs#L110-L111) | não zera o buffer de 128 bytes antes de escrever `mpro-bridge`. |
| **Reprodutibilidade dos offsets** | [relay:23](tools/mmf-vocore-relay.cs#L23) | aponta para "docs; probe offsets3.cs", mas [docs/](docs/) está **vazio** — os probes existem só dentro do prefixo, fora do controle de versão. |
| **Registro no CLAUDE.md** | [CLAUDE.md](CLAUDE.md) | a frente MMF **não existe** lá (zero menções). |

---

## 6. Execução

Cada passo tem **critério de sucesso** — se ele não bater, pare e diagnostique; não siga.

### Fase 0 — pré-requisitos (10 min)

**0.1** Neutralizar o compositor **antes** de carregar o módulo (ver **H1**, é o risco nº 1):
```bash
sudo tee /etc/udev/rules.d/71-mpro-noseat.rules >/dev/null <<'EOF'
# a tela VoCore e' saida dedicada do dash: nao entregar ao compositor
SUBSYSTEM=="drm", KERNEL=="card*", ATTRS{idVendor}=="c872", ATTRS{idProduct}=="1004", TAG-="master-of-seat"
EOF
sudo udevadm control --reload
```
**0.2** ACL de escrita no backlight:
```bash
sudo tee /etc/udev/rules.d/71-mpro-backlight.rules >/dev/null <<'EOF'
SUBSYSTEM=="backlight", KERNEL=="mpro_backlight", RUN+="/bin/chgrp video /sys/class/backlight/%k/brightness", RUN+="/bin/chmod g+w /sys/class/backlight/%k/brightness"
EOF
sudo udevadm control --reload
```
**0.3** No SimHub, **desabilitar** o device `Generic Vocore Screen`.

> ✅ **Critério:** nenhum. São preparativos; a validação vem no passo 1.3.

### Fase 1 — driver DRM sozinho, sem SimHub (30 min)

**1.1** Carregar:
```bash
sudo insmod ~/apps/mpro_drm/mpro.ko && dmesg | tail -20 | grep -i mpro
```
> ✅ **Critério:** aparece um `/dev/fbN` novo **e** um `/dev/dri/cardN` novo.
> 📏 **Anotar modelo e resolução.** Esperado `MODEL_5IN` / **480×854 (retrato)** — se for
> isso, a rotação de 90° da seção 5.1 entra no escopo antes da Fase 2 fazer sentido.

**1.2** Confirmar que o compositor **não** pegou o card:
```bash
sudo fuser -v /dev/dri/card* 2>&1 | grep -i kwin || echo "kwin nao esta com o card do mpro"
```
> ✅ **Critério:** o `cardN` do mpro **não** aparece na lista do KWin, e a tela **não** vira
> um monitor novo no Plasma. Se virar → **H1** confirmada, resolver antes de seguir.

**1.3** Padrão de teste:
```bash
python3 tools/mpro-dash-daemon.py --test
```
> ✅ **Critério:** degradê visível na tela física. **Este é o go/no-go de toda a Fase 1.**
> Se o comando terminar sem erro e a tela ficar preta → **H1**. Se der `Permission denied` →
> grupo `video` (já conferido ✅, então não deve acontecer).

**1.4** Medir custo do frame cheio (**H4**/**H5**):
```bash
time (for i in $(seq 30); do python3 tools/mpro-dash-daemon.py --test >/dev/null; done)
```
> 📏 **Anotar:** se 30 frames cheios levarem bem mais que 1 s, o alvo de 30 fps não fecha.

### Fase 2 — ponte SimHub → tela (45 min)

**2.1** Recompilar o relay (o `.exe` do prefixo é de 16/ago; garanta que é o fonte atual):
```bash
SH=~/apps/linux-simracing-utils/pfx/drive_c/Program\ Files\ \(x86\)/SimHub
cp tools/mmf-vocore-relay.cs "$SH/" && cd "$SH"
WINEPREFIX=~/apps/linux-simracing-utils/pfx WINEDEBUG=-all \
  wine 'C:\windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe' \
  /nologo /platform:x64 /unsafe /out:mmf-vocore-relay.exe mmf-vocore-relay.cs
```

**2.2** Subir o daemon primeiro (é ele quem dita a resolução):
```bash
python3 tools/mpro-dash-daemon.py
```
> ✅ **Critério:** imprime `pedindo dash WxH; aguardando relay/SimHub…`

**2.3** Subir o relay:
```bash
WINEPREFIX=~/apps/linux-simracing-utils/pfx WINEDEBUG=-all wine "$SH/mmf-vocore-relay.exe"
```
> ✅ **Critério:** o relay imprime `pedindo WxH` — **isso prova H2** (a memória compartilhada
> atravessa a fronteira Wine↔Linux). Se ele imprimir só a linha do MMF e nunca `pedindo`,
> **H2 caiu** e a arquitetura precisa de outro transporte (socket/FIFO em vez de mmap).

**2.4** No SimHub: habilitar `Special : Generic MMF rendering V2`, atribuir um dash na
resolução anotada em 1.1, deixar o `screenId` vazio (o relay usa `""` por padrão).
> ✅ **Critério:** o daemon imprime `frames chegando do SimHub ✔` e o dash aparece na tela.
> ✅ **Isso prova H3** (offsets do MMF corretos). Se o log do SimHub disser
> `Rendering request timeout`, o heartbeat não está chegando → offsets errados, re-medir.

**2.5** Brilho: mexer no slider do SimHub.
> ✅ **Critério:** o backlight acompanha (depende de 0.2).

### Fase 2.5 — rotação de 90° (2-3 h, é implementação) — **só se 1.1 reportar retrato**

A tela é 854×480 no uso, mas o driver provavelmente expõe **480×854 retrato** (seção 5.1).
**2.5.1** `--rotate {0,90,180,270}` no daemon: pedir `854×480` ao SimHub via `B_RQW/B_RQH`
(em vez de copiar o `xres/yres` do fb) e transpor no caminho de pixel.
**2.5.2** Implementar com `numpy` (`arr.reshape(...).T` + `ascontiguousarray`) — a
transposição de ~410 K pixels por frame é o novo custo de CPU a vigiar.
> ✅ **Critério:** dash em paisagem, na orientação física correta, sem faixas pretas.
> 📏 Medir o tempo por frame: se a transposição custar mais que ~10 ms, avaliar rotacionar
> no `mpro.c` (o plano de plano de exibição do DRM) em vez de no daemon.

### Fase 3 — touch (2-4 h, é implementação)

**3.1** Ler `/dev/input/eventN` do `mpro` (via `evdev` ou `struct` cru), mapear
`ABS_X/ABS_Y/BTN_TOUCH` para `B_TX/B_TY/B_TP`.
**3.2** ⚠️ Aplicar **a mesma rotação da Fase 2.5** às coordenadas: o `input_dev` reporta em
coordenadas **do painel** (`ABS_X 0..width`, `ABS_Y 0..height`, `mpro.c:788-789`), não do
dash. Com rotação de 90° isso é troca de eixos + inversão de um deles.
**3.3** `EVIOCGRAB` no device para o KDE não receber os toques como cliques no desktop (**H6**).
**3.4** Opcional: botões de overlay via `B_ACT`/`B_ACTSEQ` (o relay já entrega ao SimHub).
> ✅ **Critério:** tocar no dash troca de página no SimHub e **não** move o cursor do desktop.

### Fase 4 — automação e higiene (1 h)

**4.1** `sudo make install` no `~/apps/mpro_drm` + `/etc/modules-load.d/mpro.conf`.
**4.2** Unit systemd `--user` para o daemon; relay junto do start do SimHub.
**4.3** Pagar as dívidas da tabela 5.2: checar `MAGIC`/`B_ALIVE`, zerar o `Requester`,
double-buffer no bridge.
**4.4** Copiar `offsets3.cs`/`probe1*.cs` do prefixo para [docs/](docs/) e registrar a frente
MMF no [CLAUDE.md](CLAUDE.md).

**Custo total realista:** Fases 0-2 ≈ **1 h 30** se a Fase 1 acender na primeira; Fase 2.5
≈ **2-3 h**; Fase 3 é trabalho novo de **2-4 h**; Fase 4 ≈ **1 h**. Total **6-9 h**. A v1
dizia "2-3 h" para tudo porque contava o touch como pronto e o compositor como trivial.

⚠️ **Antes de começar a Fase 2, leia a seção 8.** Com rotação e touch no escopo, o caminho
alternativo (**H7**, ponte de tradução da libusb) passou a custar potencialmente menos que o
que falta aqui — e o teste que decide entre os dois custa ~2 h.

---

## 7. Hipóteses — o que atacar e o que descartar

Ordenadas por decisão pendente. Cada uma tem o teste mais barato que a mata ou confirma.

### H1 — O KWin toma o card DRM e engole os frames do fbdev
- **Evidência:** sessão é `kwin_wayland` ✅ medido. O KWin abre todo card DRM entregue pelo
  logind e vira **DRM master**; desabilitar o *output* nas configurações do Plasma **não**
  solta o master. ⚠️ O `drm_fb_helper` só faz o flush do damage quando consegue o master
  interno — com o compositor dono do card, a escrita em `/dev/fbN` cai no shadow buffer e
  **nunca sobe pro painel**, sem erro nenhum *(mecanismo identificado, não medido)*.
- **Se for verdade:** a Fase 1 falha com tela preta e exit code 0 — o modo de falha mais
  caro de diagnosticar deste plano.
- **Teste:** passos 1.2 e 1.3. Custo: 5 min.
- **Recomendação: ✅ atacar preventivamente** (passo 0.1). É barato e elimina o pior sintoma.

### H2 — O mmap de `Z:\dev\shm\simhub-mpro` é coerente entre Wine e Linux
- **Evidência:** ⚠️ inferido — o Wine implementa file mapping com `mmap(MAP_SHARED)` do fd
  unix real, e `/dev/shm` é tmpfs. Nunca exercitado ✅ medido (bridge inexistente, zero MMF
  nos logs).
- **Se for falso:** toda a arquitetura cai; o plano B é socket unix ou FIFO, o que muda os
  dois lados mas não a ideia.
- **Teste:** passo 2.3 — o relay imprimir `pedindo WxH` prova coerência **nos dois sentidos**
  (o daemon escreveu, o Wine leu). Custo: já está no caminho crítico.
- **Recomendação: ✅ atacar** — é a fundação, e o teste é grátis.

### H3 — Os offsets do MMF v2 estão corretos
- **Evidência:** medidos por `DynamicMethod+ldflda` contra a DLL do SimHub **9.11.22**, e a
  versão instalada **é** 9.11.22 ✅. As constantes de protocolo conferem contra a DLL:
  `SimHubDashRenderv2`, `RenderBuffer1/2`, `Rendering request timeout` ✅. Mas nunca foram
  exercitados contra o SimHub vivo ✅ (zero MMF nos logs).
- **Se for falso:** o SimHub não conecta ou conecta e derruba com `Rendering request timeout`.
- **Teste:** passo 2.4. Custo: já está no caminho crítico. Re-medição = rodar `offsets3.cs`.
- **Recomendação: ✅ atacar** — mas **antes** copiar os probes para o repo (4.4), senão uma
  atualização do SimHub deixa o projeto sem como re-medir.

### H4 — A banda do USB 2.0 aguenta o dash em movimento
- **Evidência:** ✅ medido — barramento único 480M; a tela é HS com bulk OUT de 512 B; frame
  cheio = W×H×2 bytes (≈ 768 KB a 480×800). A 30 fps são **~23 MB/s**, contra ~35-40 MB/s
  práticos de um HS compartilhado com todos os HID (que são 12M via TT).
- **Se for falso:** dash com stutter, e possivelmente **input dos MCP/PDU5 engasgando** —
  que seria bem pior que a tela lenta.
- **Teste:** passo 1.4, depois observar latência dos botões com o dash rodando.
- **Recomendação: ⏸️ adiar** — medir na Fase 1, só otimizar se doer. Mitigação conhecida:
  limitar FPS no daemon, ou damage parcial (**H5**).

### H5 — O fbdev deferred-IO manda a tela inteira a cada frame
- **Evidência:** ⚠️ inferido — o daemon faz `memcpy` da tela toda, o que suja todas as
  páginas; o damage tracking do deferred-IO é por página, então o retângulo sujo vira a tela
  inteira. O `mpro.c` **tem** caminho de update parcial (`cmd_draw_part`), que ficaria ocioso.
- **Se for verdade:** o custo de banda de **H4** é sempre o pior caso.
- **Teste:** comparar o tempo de escrever a tela toda vs. um quarto dela.
- **Recomendação: ⏸️ adiar** — só vale se **H4** doer. Solução seria trocar o fbdev por um
  client KMS com `DRM_IOCTL_MODE_DIRTYFB` e retângulos vindos do SimHub.

### H6 — O touch do mpro vira ponteiro do KDE
- **Evidência:** ✅ medido no `mpro.c:776-789` — o driver registra um `input_dev` padrão com
  `ABS_X/ABS_Y/BTN_TOUCH`. O libinput/KDE captura qualquer touchscreen do seat.
- **Se for verdade:** tocar no dash clica no desktop.
- **Teste:** carregar o módulo e tocar na tela (Fase 1).
- **Recomendação: ✅ atacar junto com a Fase 3** — `EVIOCGRAB` no daemon resolve sem udev.

### H7 — Um `libusb-1.0.dll` de tradução torna o `mpro_drm` desnecessário
**✅ CONFIRMADA COM HARDWARE em 2026-08-18 16:36** — a tela acendeu com o dash do SimHub.
O teste decisivo está na seção 8.1; o resultado ponta a ponta, na **8.2**. O que segue abaixo
é a evidência que levou ao teste.

- **A pergunta por trás:** no Windows não existe driver de display para esta tela. Existe o
  **WinUSB**, que é só um atalho genérico para o user-mode falar USB bruto. No Linux esse
  atalho **já existe e já está pronto**: é o **usbfs** (`/dev/bus/usb/BBB/DDD`), que é o que
  a `libusb-1.0.so` nativa usa — e nós medimos que o nó da tela já está `rw` para o usuário
  e com `Driver=[none]` ✅. Falta só **traduzir as chamadas**, que é literalmente o que o
  Wine faz para todo o resto.
- **Evidência ✅ medida (2026-08-18):**
  - A superfície a traduzir são **32 funções, todas síncronas** — lista completa extraída de
    `SimHub.LibUsbNative.dll`: `init/exit/set_option/get_version`, `get_device_list/
    free_device_list/ref_device/unref_device/get_device`, `open/open_device_with_vid_pid/
    close`, `claim_interface/release_interface/set_interface_alt_setting/
    get_configuration/set_configuration/reset_device/clear_halt`,
    `bulk_transfer/interrupt_transfer/control_transfer/get_string_descriptor_ascii`,
    `get_device_descriptor/get_device_address/get_device_speed/get_max_packet_size/
    get_max_iso_packet_size`, **`get_bus_number/get_parent/get_port_number/
    get_port_numbers`**.
  - **Não há marshaling difícil.** A única struct passada por valor de conteúdo é
    `libusb_device_descriptor`, que é **só escalares** (18 bytes, layout idêntico em 32 e 64
    bits). `libusb_get_config_descriptor` — a que teria ponteiros aninhados — **não está na
    lista**. Todo o resto é escalar, buffer de bytes, ou ponteiro opaco (que vira token).
  - **`get_parent` + `get_port_numbers` + `get_bus_number` estão na lista** — a topologia
    que falta no PnP do Wine, o SimHub pede à própria libusb. E a árvore real do Linux a
    tem, com a PDU5 e a tela no mesmo hub `5-2.2.4.2` ✅ (seção 2.1).
  - `libusb-1.0.dll` do SimHub é **PE32** ✅ (`file`), e o serviço VOCORE roda no
    `SimHub.Subprocess.X86.exe`.
  - Toolchain presente nesta máquina ✅: **`i686-w64-mingw32-gcc`**, `x86_64-w64-mingw32-gcc`,
    `libusb-1.0.so.0`.
- ✅ **O bloqueio do WoW64 foi REFUTADO por medição** (seção 8.1), não só por argumento: ele
  vale apenas para **winelib** (DLL PE com metade unix `.so`). Uma DLL **PE pura** carrega
  normalmente no `SimHub.SubProcess.X86.exe` mesmo sem `i386-unix`. O desenho:

  ```
  libusb-1.0.dll  (PE32 puro, mingw, exporta os 32 símbolos)
        │  IPC (socket loopback) — sem código unix dentro do Wine
        ▼
  helper nativo Linux 64-bit  ──►  libusb-1.0.so  ──►  usbfs  ──►  tela
  ```

  Uma DLL **PE pura** carrega no processo 32-bit sem `i386-unix`, sem patch de IL para
  forçar o X64, e sem winelib — **verificado na prática** (seção 8.1). O custo por frame é
  uma cópia de ~800 KB por loopback — desprezível.
- **Se for verdade:** a tela é enumerada pelo SimHub, o `Generic Vocore Screen` (ou o device
  próprio da PDU5) conecta, e **`mpro_drm`, relay, daemon, rotação, conflito com o KWin e
  banda do fbdev deixam todos de existir** — a tela passa a ser tratada pelo SimHub
  exatamente como no Windows.
- ✅ **Convenção de chamada: medida e resolvida.** No binário original (objdump):
  **31 funções `stdcall`** (`libusb_init` → `ret $0x4`, `libusb_get_device_descriptor` →
  `ret $0x8`, `libusb_bulk_transfer` → `ret $0x18`, …) **+ `libusb_set_option` `cdecl`**
  (varargs, `ret` sem imediato). Exports **não decorados**. O shim reproduz os 32 tamanhos
  de pilha exatamente — conferido função a função antes de rodar.
- **O que ainda NÃO está medido:** se o `HasParentHub` (associação tela↔volante) é resolvido
  pela libusb ou pelo `PortSignature`/`UsbPath` do `WoteverCommon` (SetupAPI). A ponte
  conserta o primeiro com certeza; o segundo continuaria quebrado. **Medir com `ildump.py`
  quando a enumeração estiver de pé** — não bloqueia o começo da ponte.
- **Recomendação: ✅ CONFIRMADA — construir a ponte.** Ver seção 8.1.

### H8 — Patch no Wine promovendo TLC vendor aninhada a PDO resolve os LEDs da PDU5
- **Evidência ✅ medida:** o descriptor da PDU5 é uma collection Joystick **vazia** com a
  vendor aninhada dentro; o Wine expõe um PDO só (`0x0001/0x04`), e o
  `PokornyiPEPDU5Manager` pede `usagePage 0xFF / usage 1` → nunca casa. Nos MCP o canal
  vendor é alcançado pelo mesmo handle, por isso eles funcionam.
- **Se for verdade:** os LEDs da PDU5 passam a funcionar — o único item que falta para a PDU5
  ficar completa depois deste plano.
- **Custo:** patch no `hidclass`/`winehid` do Wine + ciclo upstream. Alto, mas o caso de teste
  é minúsculo (descriptor de 35 bytes) e o benefício vale para **qualquer** device com
  descriptor parecido, não só a Pokornyi.
- **Recomendação: ⏸️ adiar, atacar como issue upstream** com o caso de teste pronto. Não
  tem relação nenhuma com a tela — não misturar com as fases acima.

### H9 — Descartadas
| hipótese | por que morreu |
|---|---|
| A tela precisa de driver de display USB | ✅ é libusb bruto por bulk EP — `SimHub.BitmapDisplay.Vocore.dll → SimHub.LibUsbNative.dll → libusb-1.0.dll` |
| A `winusb.dll` builtin do Wine cobre o WinUSB | ✅ é **stub** (`"(%p) - stub"` nas strings) |
| Instalar o driver WinUSB dentro do prefixo (Zadig-like) | instalaria driver de kernel do Windows, que o Wine não executa |
| Permissão do nó USB é o bloqueio | ✅ **resolvido** — `/dev/bus/usb/005/033` já tem ACL `user:<USUARIO>:rw-` |
| Falta uma correção de registro para a tela | não existe: o problema é ausência de function driver, não de chave |
| `numpy` é dependência **por causa de 16bpp** | ✅ o fb sai 32bpp (`mpro_pipe_formats` só tem XRGB8888) — ⚠️ mas volta a ser dependência real pela **rotação** (Fase 2.5) |

---

## 8. Decisão: o `mpro_drm` é necessário? — **não** (resolvido em 2026-08-18)

**Resposta curta: não — ele é o plano B.** Existe porque até hoje ninguém traduzia as
chamadas da libusb dentro do Wine. O teste da seção 8.1 mostrou que **a tradução funciona**:
com a ponte pronta, o módulo, o relay, o daemon, a rotação de 90°, o conflito com o KWin e a
banda do fbdev **saem todos de cena de uma vez**.

⚠️ **Correção de termo:** `mpro_drm` **não é firmware** — é um **módulo de kernel** (driver
DRM). A tela já roda o firmware dela e fala um protocolo bulk proprietário; nada neste
projeto grava firmware em coisa nenhuma.

**Por que a intuição "no Windows nunca foi preciso" está certa:** no Windows não há driver
de display para esta tela. O que o instalador do SimHub faz é ligar o **WinUSB**, um atalho
genérico para o user-mode falar USB bruto. No Linux esse atalho **já existe e já está
pronto**: é o **usbfs**, que a `libusb-1.0.so` nativa usa. Medimos que o nó da tela está
`Driver=[none]` e já tem `rw` para o usuário ✅. O que falta não é driver — é tradutor.

| | **A) `mpro_drm` + MMF** (plano das Fases 0-4) | **B) `libusb-1.0.dll` de tradução** (H7) |
|---|---|---|
| O que é | reimplementa o protocolo da tela **dentro do kernel** | traduz 32 chamadas para a libusb do host |
| Estado | ~60% construído; módulo compila e carrega ✅ | **shim de log funcionando** ✅ (8.1); falta o encaminhamento real |
| Falta | rotação 90°, touch, KWin/DRM master, banda, startup | shim PE32 + helper nativo + token table |
| Integração | device **genérico** `Generic MMF rendering V2` | device **próprio** da tela, como no Windows |
| Touch / brilho / rotação | por nossa conta | por conta do SimHub, como no Windows |
| Convive com o outro caminho? | ❌ com `mpro` carregado, o Wine perde o device | ❌ idem, ao contrário — precisa de `rmmod mpro` |
| Sobrevive a update do SimHub? | ✅ não depende de interno do SimHub | ⚠️ depende do nome/ABI da `libusb-1.0.dll` (ABI pública, estável) |
| Risco maior | KWin engolir os frames (**H1**) | convenção de chamada / `HasParentHub` por SetupAPI |

**Recomendação — atualizada em 2026-08-18 após o teste da seção 8.1: seguir pelo caminho B.**
O teste decisivo passou: a substituição da DLL funciona, a convenção de chamada bate e o
SimHub chega a enumerar. Some-se a isso que a confirmação da resolução 854×480 **adicionou**
rotação de 90° ao caminho A, que já devia touch. O caminho B deixou de ser hipótese cara e
passou a ser o de menor custo restante **e** o de maior valor (integração nativa de verdade).

**Não jogar o caminho A fora:** ele é o fallback que não depende de nada interno do SimHub,
e o `mpro_drm` continua sendo a única forma de usar essa tela **fora** do SimHub. Se a ponte
travar em algum ponto do item 3 da seção 8.1, o plano volta para as Fases 0-4 sem perda —
o relay e o daemon continuam onde estão.


### 8.1 Resultado do teste decisivo ✅ (2026-08-18 16:25)

Construído `tools/libusb-shim/` — uma `libusb-1.0.dll` **PE32 pura** (mingw
`i686-w64-mingw32-gcc`) que exporta os 32 símbolos, registra cada chamada e devolve
resultado inócuo (init OK, lista de devices **vazia**). Original preservada em
`libusb-1.0.dll.orig`. **Resultado:**

```
[04847353] #0001 === ATTACH  pid=556  exe=C:\Program Files (x86)\SimHub\SimHub.SubProcess.X86.exe
[04847353] #0002 libusb_init(ctx=075DE9F4) -> 0 (ctx falso 7290602C)
[04847353] #0003 libusb_get_device_list(ctx=7290602C) -> 0 devices
[04852217] #0004 libusb_get_device_list(ctx=7290602C) -> 0 devices
... (polling a cada ~5 s)
```

O que isso prova, item a item:

| pergunta | resposta ✅ |
|---|---|
| A DLL substituída é carregada no lugar da original? | **Sim** — `ATTACH` no log |
| Quem carrega? | **`SimHub.SubProcess.X86.exe`**, o subprocesso 32-bit, como previsto |
| Uma DLL **PE pura** carrega no 32-bit sem `i386-unix`? | **Sim** — o WoW64 novo não é obstáculo |
| A convenção de chamada bate? | **Sim** — 14 chamadas, contexto falso volta íntegro, zero corrupção de pilha |
| O SimHub chega mesmo a enumerar? | **Sim** — `libusb_get_device_list` em polling de 5 s |

**Consequência direta:** o obstáculo que arquivava esta frente (WoW64 32-bit → precisaria de
winelib → precisaria de patch de IL para forçar o `SubProcess.X64`) **não existe**. Nenhum
patch no SimHub, nenhum winelib, nenhum módulo de kernel.

**O que falta para a tela funcionar por este caminho:** trocar os retornos inócuos por
encaminhamento real. Ordem natural de implementação:

1. **Helper nativo** (Linux 64-bit, contra `libusb-1.0.so`) + protocolo de request/response
   sobre loopback; tabela de tokens `uint32` ↔ ponteiros do host para `libusb_device*`,
   `libusb_device_handle*` e `libusb_context*`.
2. **Enumeração primeiro**: `init`, `get_device_list`, `get_device_descriptor`,
   `free_device_list`, `ref/unref`. Critério: o `Screen ID` da aba deixa de vir vazio.
3. **Abertura e transferência**: `open`, `claim_interface`, `bulk_transfer`,
   `control_transfer`, `close`. Critério: imagem na tela.
4. **Topologia**: `get_bus_number`, `get_parent`, `get_port_number`, `get_port_numbers` —
   é aqui que a associação tela↔volante se resolve, com a PDU5 e a tela no mesmo hub
   `5-2.2.4.2` (seção 2.1).

⚠️ Ao rodar este teste, o device `Generic Vocore Screen` precisa estar **habilitado**
(`PluginsData/Common/Devices/<instance>/settings.json` → `"Enabled": true`); com ele
desabilitado o SimHub nem sobe o subprocesso VOCORE e a libusb nunca é chamada. No teste
acima o estado original (desabilitado) foi restaurado ao fim, junto com a DLL original.

### 8.2 ✅ FUNCIONOU ponta a ponta (2026-08-18 16:36) — a tela acendeu

Implementada a ponte completa em `tools/libusb-bridge/`:

| peça | o que é |
|---|---|
| `shim.c` → `libusb-1.0.dll` | DLL **PE32 pura** (mingw), 32 exports, encaminha cada chamada por socket loopback |
| `helper.c` → `libusb-bridge-helper` | processo nativo 64-bit, executa na `libusb-1.0.so` do host (usbfs) |
| `proto.h` | envelope request/response; ponteiros **nunca** cruzam a fronteira — o helper mantém tokens `u32` |

**Log do SimHub:**

```
Screen connected : model MPRO D500FPC931A-A 854x480 (Screen 0x05, Ver. 0x03, FW 0.23,
    P.Up. True, LZ4 True, USB Path 5:2-2-4-2-4, Rev 0x1a0), size 854x480,
    id <SCREEN-ID>, leds 0
Device Status changed : Generic Vocore Screen (...) : Connected
VOCORE : Loading http://127.0.0.1:8888/Dash?...
```

**Log da ponte:**

```
open(tok 53) -> 0 (ok)                      # tok 53 = c872:1004
claim_interface(0) -> 0 (LIBUSB_SUCCESS)
control type=0x40 req=0xb5 wlen=5 -> 5      # handshake vendor
bulk ep=0x02 len=819840 -> 0 actual=819840  # 854*480*2 = frame cheio RGB565
bulk ep=0x02 len=18432  -> 0 actual=18432   # partial draws
```

✅ **Confirmado pelo usuário na tela física:** o dash apareceu e trocar de dashboard no
SimHub trocou o que a VoCore mostra. Zero erros de transferência.

**O que isso derruba de vez:**

| item | estado |
|---|---|
| `Screen ID` vazio / `Connection status: Not found` | **resolvido** — o device conecta pela aba Devices |
| Bloqueio "nenhum driver ligado ao nó PnP" | **contornado** — o caminho não passa pelo PnP do Wine |
| Bloqueio "`winusb.dll` é stub" | **contornado** — nenhuma chamada chega à `winusb.dll` |
| Bloqueio "topologia USB ausente" | **resolvido** — `USB Path 5:2-2-4-2-4` veio da libusb real |
| Rotação de 90° (Fase 2.5) | **não é necessária** — o painel reporta 854×480 direto ao SimHub |
| `mpro_drm`, relay MMF, daemon, conflito com KWin, banda do fbdev | **não são necessários** para a tela no SimHub |

✅ **Touch também funciona** (medido na mesma sessão): 175 transferências
`intr ep=0x81 -> actual=14` com dados — 14 bytes é exatamente o `MPRO_INPUT_TRS_SIZE` do
report de toque. O SimHub recebe o touch pela ponte, sem `EVIOCGRAB`, sem evdev, sem
disputa com o KDE (o kernel nem vê o device como input, já que nenhum driver o reivindica).

**O que ainda falta:**

1. **Persistência** — hoje o helper é iniciado à mão. Falta unit systemd `--user` e ordem de
   start (helper **antes** do SimHub; sem ele a DLL loga `helper não está ouvindo` e devolve erro).
2. ⚠️ **Update do SimHub sobrescreve a `libusb-1.0.dll`.** O original está em
   `libusb-1.0.dll.orig`; reinstalar a ponte depois de cada atualização.
3. **LEDs da PDU5** continuam fora (`usagePage 0xFF`, hipótese H8) — sem relação com isto.

### 8.3 Duas armadilhas operacionais pagas em 2026-08-18 (leia antes de mexer)

**1. ⚠️ Subir o SimHub por fora do `lsu-launch-wrapper` mata a telemetria.**
`wine SimHubWPF.exe` direto abre o app normalmente e os devices funcionam — mas **nenhuma
telemetria chega**. O wrapper é quem dispara o `lsu-winehub-manager`, que sobe o
**`winehub`** ("SimHub shared memory bridge for Wine games"): é ele que espelha a memória
compartilhada do jogo (`$rFactor2SMMP_Telemetry$`, `Local\SHSCSTelemetry`, …) para dentro do
prefixo, usando `wine2linux.exe`. Sem `winehub` rodando (`pfx/winehub.pid` ausente), SimHub
fica sem dados e o sintoma não aponta para a causa. **Sempre iniciar por:**

```bash
~/apps/linux-simracing-utils/bin/lsu-launch-wrapper \
  "C:\\ProgramData\\Microsoft\\Windows\\Start Menu\\Programs\\SimHub\\SimHub.lnk"
```

Nos jogos, o lado de lá é o `winecarte-run` nas launch options da Steam.

**2. ⚠️ O helper precisa de fork por conexão e de limpeza ao cair o cliente.**
Dois bugs reais da primeira versão, os dois com sintoma longe da causa:

| bug | sintoma | correção |
|---|---|---|
| helper não soltava nada quando o cliente sumia | `claim_interface(0) -> -6 (LIBUSB_ERROR_BUSY)` na instância seguinte do SimHub | `tok_reset()` ao cair o socket: fecha handles, solta refs, encerra contextos |
| helper atendia **um cliente por vez** | `System.TimeoutException` em `PipeBitmapDisplayServer.ConnectToScreen`, com o VOCORE em ciclo start/close de 2 s | **fork por conexão**: o SimHub mantém mais de um `SubProcess.X86.exe` vivo, e o velho segurava o slot |

O segundo é o mais traiçoeiro: o erro que aparece no log do SimHub é de **pipe**, entre o
processo principal e o subprocesso — nada aponta para USB, libusb ou a ponte.

## 9. Segurança

⚠️ **A base CONSPIT ARES (20 Nm) está em `/dev/ttyACM0` agora** (`5-2.2.3.3`, ✅ medido).
A Fase 2 sobe o SimHub, que varre portas seriais procurando Arduinos. Antes de rodar,
**confirme que o auto-detect de Arduino do SimHub está restrito às portas certas**. Nunca
mandar `=`, `sys.0.save`, `sys.0.format` ou `odrv.*` numa porta que possa ser a base.
Use sempre `/dev/serial/by-id/` — `ttyACM0/1` renumeram a cada reenumeração.

O daemon e o relay são **somente leitura** do lado do SimHub, exceto pelos campos de request
do MMF. Nada aqui escreve firmware.

---

## 10. Apêndice — como reproduzir as medições

```bash
lsusb -t                                  # arvore de hubs (secao 2.1)
for d in /sys/bus/usb/devices/5-*; do echo "$(basename $d) $(cat $d/idVendor):$(cat $d/idProduct)"; done
lsusb -v -d c872:1004 | grep -E "bcdDevice|iProduct|bEndpointAddress|wMaxPacketSize"
for h in /dev/hidraw*; do echo "$h $(grep HID_NAME /sys/class/hidraw/$(basename $h)/device/uevent)"; done
getfacl -p /dev/bus/usb/005/033           # ACL do no da tela
modinfo ~/apps/mpro_drm/mpro.ko | grep vermagic ; uname -r
SH=~/apps/linux-simracing-utils/pfx/drive_c/Program\ Files\ \(x86\)/SimHub
strings -el "$SH/SimHub.Plugins.dll" | grep -i "Generic MMF"
strings -el "$SH/SimHub.BitmapDisplay.MMF.dll" | grep -E "SimHubDashRender|Rendering request"
ls /usr/lib/wine/                         # i386-unix ausente => WoW64 novo
file "$SH/libusb-1.0.dll"                 # PE32 (H7)
strings -a "$SH/SimHub.LibUsbNative.dll" | grep -oE "^libusb_[a-z_]+" | sort -u   # as 32 funcoes
command -v i686-w64-mingw32-gcc           # toolchain do shim PE32 (H7)
```
