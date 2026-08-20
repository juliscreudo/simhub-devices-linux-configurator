# Evidência — a ponte libusb da tela VoCore

Este documento era um plano de execução vivo, escrito durante a investigação de 2026-08-18.
Depois que a ponte libusb funcionou ponta a ponta, o plano em si (estado da bancada num
instante, hipóteses sobre o caminho `mpro_drm`/MMF que acabou virando fallback, fases de
execução daquele caminho) ficou obsoleto — a narrativa atualizada está no
[CLAUDE.md](CLAUDE.md), seção "Telas VoCore". O que sobrevive aqui é só o que não existe em
nenhum outro lugar: **o log do teste decisivo** e as duas armadilhas operacionais que ele
custou, preservados porque são o tipo de evidência que vale a pena poder reler se a ponte
algum dia voltar a quebrar.

O código da ponte em si — não este relato — está em
[wine-libusb-bridge](https://github.com/juliscreudo/wine-libusb-bridge).

Convenção do projeto: ✅ **medido** = tem comando e saída neste documento;
⚠️ **inferido** = mecanismo identificado, não verificado.

---

## Duas arquiteturas possíveis, e por que a da libusb venceu

| | **A) `mpro_drm` + MMF** (driver de kernel) | **B) `libusb-1.0.dll` de tradução** (a ponte) |
|---|---|---|
| O que é | reimplementa o protocolo da tela **dentro do kernel** | traduz 32 chamadas para a libusb do host |
| Integração | device **genérico** `Generic MMF rendering V2` | device **próprio** da tela, como no Windows |
| Touch / brilho / rotação | por nossa conta | por conta do SimHub, como no Windows |
| Convive com o outro caminho? | ❌ com `mpro` carregado, o Wine perde o device | ❌ idem, ao contrário — precisa de `rmmod mpro` |
| Sobrevive a update do SimHub? | ✅ não depende de interno do SimHub | ⚠️ depende do nome/ABI da `libusb-1.0.dll` (ABI pública, estável) |

**Por que a intuição "no Windows nunca foi preciso driver nenhum" está certa:** no Windows não
há driver de display para esta tela. O que o instalador do SimHub faz é ligar o **WinUSB**, um
atalho genérico para o user-mode falar USB bruto. No Linux esse atalho **já existe e já está
pronto**: é o **usbfs**, que a `libusb-1.0.so` nativa usa. O nó da tela está `Driver=[none]` e
já tem `rw` para o usuário. O que faltava não era driver — era tradutor.

O caminho A (`mpro_drm`) não foi jogado fora: é o fallback que não depende de nada interno do
SimHub, e continua sendo a única forma de usar essa tela **fora** dele. Ver "Telas VoCore" no
[CLAUDE.md](CLAUDE.md) para o estado atual dos dois.

---

## O teste decisivo ✅ (2026-08-18 16:25)

Construída uma `libusb-1.0.dll` **PE32 pura** (mingw `i686-w64-mingw32-gcc`) que exporta os 32
símbolos, registra cada chamada e devolve resultado inócuo (init OK, lista de devices
**vazia**). Original preservada em `libusb-1.0.dll.orig`. **Resultado:**

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

⚠️ Para reproduzir este teste, o device `Generic Vocore Screen` precisa estar **habilitado**
(`PluginsData/Common/Devices/<instance>/settings.json` → `"Enabled": true`); com ele
desabilitado o SimHub nem sobe o subprocesso VOCORE e a libusb nunca é chamada.

## Funcionou ponta a ponta ✅ (2026-08-18 16:36) — a tela acendeu

Implementada a ponte completa (`shim.c` → DLL PE32 com os 32 exports, encaminhando cada
chamada por socket loopback; `helper.c` → processo nativo 64-bit rodando contra a
`libusb-1.0.so` do host).

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

✅ **Confirmado na tela física:** o dash apareceu e trocar de dashboard no SimHub trocou o que
a VoCore mostra. Zero erros de transferência.

✅ **Touch também funciona** (medido na mesma sessão): 175 transferências
`intr ep=0x81 -> actual=14` com dados — 14 bytes é exatamente o `MPRO_INPUT_TRS_SIZE` do
report de toque. O SimHub recebe o touch pela ponte, sem `EVIOCGRAB`, sem evdev, sem disputa
com o KDE (o kernel nem vê o device como input, já que nenhum driver o reivindica).

## Duas armadilhas operacionais pagas em 2026-08-18 (leia antes de mexer)

**1. ⚠️ Subir o SimHub por fora do `lsu-launch-wrapper` mata a telemetria.**
`wine SimHubWPF.exe` direto abre o app normalmente e os devices funcionam — mas **nenhuma
telemetria chega**. O wrapper é quem dispara o `lsu-winehub-manager`, que sobe o **`winehub`**
("SimHub shared memory bridge for Wine games"): é ele que espelha a memória compartilhada do
jogo (`$rFactor2SMMP_Telemetry$`, `Local\SHSCSTelemetry`, …) para dentro do prefixo, usando
`wine2linux.exe`. Sem `winehub` rodando (`pfx/winehub.pid` ausente), SimHub fica sem dados e o
sintoma não aponta para a causa.

**2. ⚠️ O helper precisa de fork por conexão e de limpeza ao cair o cliente.**
Dois bugs reais da primeira versão, os dois com sintoma longe da causa:

| bug | sintoma | correção |
|---|---|---|
| helper não soltava nada quando o cliente sumia | `claim_interface(0) -> -6 (LIBUSB_ERROR_BUSY)` na instância seguinte do SimHub | `tok_reset()` ao cair o socket: fecha handles, solta refs, encerra contextos |
| helper atendia **um cliente por vez** | `System.TimeoutException` em `PipeBitmapDisplayServer.ConnectToScreen`, com o VOCORE em ciclo start/close de 2 s | **fork por conexão**: o SimHub mantém mais de um `SubProcess.X86.exe` vivo, e o velho segurava o slot |

O segundo é o mais traiçoeiro: o erro que aparece no log do SimHub é de **pipe**, entre o
processo principal e o subprocesso — nada aponta para USB, libusb ou a ponte.

Os dois já estão corrigidos no `wine-libusb-bridge` publicado; ficam aqui como registro do
porquê o helper é feito do jeito que é.

---

## Segurança

⚠️ Rodar o SimHub sobe a varredura de portas seriais dele à procura de Arduinos. Se você tem
uma base direct-drive de alto torque na bancada, confirme que o auto-detect de Arduino do
SimHub está restrito às portas certas antes de ligar o app pela primeira vez — ver a seção
"Segurança" no [CLAUDE.md](CLAUDE.md) deste repo para o procedimento completo.

---

## Apêndice — como reproduzir as medições

```bash
lsusb -t                                  # arvore de hubs
for d in /sys/bus/usb/devices/5-*; do echo "$(basename $d) $(cat $d/idVendor):$(cat $d/idProduct)"; done
lsusb -v -d c872:1004 | grep -E "bcdDevice|iProduct|bEndpointAddress|wMaxPacketSize"
for h in /dev/hidraw*; do echo "$h $(grep HID_NAME /sys/class/hidraw/$(basename $h)/device/uevent)"; done
getfacl -p /dev/bus/usb/005/033           # ACL do no da tela
SH=~/apps/linux-simracing-utils/pfx/drive_c/Program\ Files\ \(x86\)/SimHub
strings -el "$SH/SimHub.Plugins.dll" | grep -i "Generic MMF"
strings -el "$SH/SimHub.BitmapDisplay.MMF.dll" | grep -E "SimHubDashRender|Rendering request"
ls /usr/lib/wine/                         # i386-unix ausente => WoW64 novo
file "$SH/libusb-1.0.dll"                 # PE32
strings -a "$SH/SimHub.LibUsbNative.dll" | grep -oE "^libusb_[a-z_]+" | sort -u   # as 32 funcoes
command -v i686-w64-mingw32-gcc           # toolchain do shim PE32
```
