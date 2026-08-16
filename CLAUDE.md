# SimHub Devices no Linux — fazer a aba Devices reconhecer volantes e caixas de botões

Repo deste projeto: `~/apps/simhub-devices-linux/`.

**O que este projeto resolve:** no Linux o SimHub roda sob Wine e a aba **Devices** fica em
`Searching device ...` para sempre — LEDs, telas e botões de volantes não conectam. Isso não
é limitação do hardware nem do SimHub: são lacunas específicas do Wine na árvore PnP, e cada
uma tem correção conhecida (ou diagnóstico fechado, no caso das telas).

**Estado: um device validado com hardware.** O Conspit H.AO HUB conecta e responde
(2026-08-16). Todo o resto é **inferência a partir do código do SimHub**, medida mas **não
testada com hardware** — está marcado como tal ao longo do arquivo. Não apague essas marcas
ao editar; elas são o que separa o que sabemos do que supomos.

## Projetos irmãos

- `~/apps/conspit-ares-linux/` — hardware Conspit no Linux. **A base de tudo que está aqui.**
  Leia o `CLAUDE.md` de lá antes de mexer em `winebus`/`EnableHidraw`/udev: o backend hidraw,
  a armadilha da chave `Services\winebus` (e não `\Parameters`) e as regras udev estão
  resolvidos e documentados lá, com os erros que custaram dias.
- `~/apps/diy-ffb-pedal-linux/` — pedal DIY FFB. Origem do aprendizado de Wine + serial.
- `~/apps/linux-simracing-utils/` — **de terceiro** (srounce), instalador de SimHub/CrewChief
  no Linux + Winecarte. É o prefixo onde o SimHub roda: `~/apps/linux-simracing-utils/pfx`.
  Candidato natural a receber as correções daqui como contribuição upstream.

## O SimHub não é open source

O repo público (`SHWotever/SimHub`) tem só wiki e issues. **A fonte de verdade são as DLLs**
do prefixo, e o código é **ofuscado** (nomes de método viram caracteres CJK: `귇`, `궏`…).
Duas técnicas, ambas com ferramenta neste repo:

| ferramenta | uso |
|---|---|
| `tools/ildump.py <dll> <Tipo>` | desmonta o IL de um tipo — chamadas e constantes sobrevivem à ofuscação |
| `tools/ilgrep.py <dll> <método>` | acha quem chama um método |

Precisa de `dnfile` (`pip install dnfile` num venv; ⚠️ PEP 668 barra `pip` global no Arch).

**A técnica que mais rendeu: sondas C# por reflexão, rodando DENTRO do prefixo.** O SimHub
carrega suas próprias DLLs, então dá para instanciar as classes dele e perguntar o que elas
enxergam — é medição, não leitura de código:

```bash
SH=~/apps/linux-simracing-utils/pfx/drive_c/Program\ Files\ \(x86\)/SimHub
cp sonda.cs "$SH/" && cd "$SH"
WINEPREFIX=~/apps/linux-simracing-utils/pfx WINEDEBUG=-all \
  wine 'C:\windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe' \
  /nologo /platform:x64 /r:SimHub.Plugins.dll /r:WoteverCommon.dll /out:sonda.exe sonda.cs
WINEPREFIX=~/apps/linux-simracing-utils/pfx WINEDEBUG=-all wine sonda.exe
```

- O `csc.exe` do próprio prefixo compila — não precisa de toolchain .NET no Linux.
- Ligar o **log4net no console** dentro da sonda revela o que a ofuscação esconde: as
  mensagens de log são montadas em runtime e saem em claro (`Missing ports informations
  for : COM37` foi o que apontou o elo quebrado).
- ⚠️ Filtre o ruído do Wine: `| grep -vE "fixme|WineDbg|^wine:"`.

## Arquitetura da aba Devices (medido: 214 descritores)

Cada device do catálogo é um **descritor** (`Name`, `DeviceTypeID` GUID, `Factory`,
`ScreenDetectionDescriptor`) num registro por marca (`<Marca>DevicesRegistry`).
⚠️ O namespace tem typo no próprio SimHub: `SimHub.Plugins.Devices.Regisry`.

A `Factory` devolve o driver. **Três tipos cobrem 85% do catálogo**, e cada um é um problema
diferente no Wine:

| driver | qtd | transporte | estado no Linux |
|---|---:|---|---|
| `CompositeDeviceInstance` | 101 | agrega os dois abaixo | parcial — ver abaixo |
| `LedModuleDevice` | 82 | HID **ou** serial, depende do manager | ✅ resolvido |
| `BitmapDisplayDevice<VOCORESettings>` | 13 | tela VoCore | ❌ bloqueado (topologia USB) |

**O composite é a boa notícia**: todo device com tela VoCore (HYP-R, GTB Pro, F499, PDU5,
PDU7, CSX3…) é `BitmapDisplayDevice` **+** `LedModuleDevice` juntos, e o inverso também vale
— quem não tem VoCore (FGT, AMG, MCP BB/IB/EB, H.AO HUB) é `LedModuleDevice` puro. As duas
metades do composite são independentes, então **os LEDs devem funcionar mesmo com a tela
bloqueada**. *(Inferido da composição; não testado — nenhum device com tela na bancada.)*

### Os dois transportes do LedModuleDevice

`LedsGenericManager<TDriver>` é a base comum. O que muda é o `TDriver`:

| manager | driver | transporte | marcas |
|---|---|---|---|
| `StandardProtocolManager` | `StandardProtocolDriver` | **serial** (CDC) | Conspit, Arduinos da wiki |
| `PokornyiFGTManager` e irmãos | `PokornyiDriver` | **HID** (`HidDeviceList::GetHidDevices`) | Pokornyi |
| `CubeControls*LedsManager` | `CubeControlsLedsDriverV2` | **HID** | Cube Controls |

`LedsGenericManagerWithSerialNumber<T>` acrescenta casamento por número de série
(`ISerialNumberManager`) — relevante quando há mais de uma unidade igual.

**Isso define duas receitas distintas**, e a receita certa depende do transporte. Descubra o
transporte ANTES de mexer no prefixo: `tools/ildump.py BA63Driver.dll <XDriver> | grep -E
"HidDevice|SerialPort"`.

## Receita 1 — devices HID (Pokornyi, Cube Controls)

**Esta é a receita mais simples, e o projeto Conspit já a resolveu inteira.** O trabalho é
só apontá-la para o VID novo.

O Wine, por padrão, entrega joysticks **sintetizados pelo SDL**, com uma collection só — os
canais vendor de 64 bytes por onde os LEDs falam não existem para o app. Em **hidraw** o
`hidclass` separa as top-level collections em `&Col01`/`&Col02`, como no Windows.

Em `HKLM\System\CurrentControlSet\Services\winebus` (⚠️ **NÃO** na subchave `\Parameters`,
que o driver nunca lê — erro que custou três dias no projeto Conspit):

| valor | tipo | papel |
|---|---|---|
| `EnableHidraw` | `REG_MULTI_SZ` | **quem faz o trabalho**: uma linha `VVVV:PPPP` por device |
| `Enable SDL` | `REG_DWORD` `0` | metade da rede de segurança |
| `DisableInput` | `REG_DWORD` `1` | a outra metade — **só funciona com as duas** |

VID/PID extraídos do IL dos managers *(medido no catálogo do SimHub; ⚠️ confira com `lsusb`
ao plugar — PID pode variar por revisão de firmware)*:

**Pokornyi — VID `0483`** (STMicroelectronics, o mesmo dos STM32; PIDs em `CBxx`):

| PID | device | | PID | device |
|---|---|---|---|---|
| `CB01` | PDU5 | | `CB12` | RALLY |
| `CB02` | PDU7 | | `CB14` | F499 |
| `CB03` | LED Brows | | `CB15` | FGT |
| `CB10` | HYP-R | | `CB40` | MCP ButtonBox |
| `CB11` | GTB Pro | | `CB41` | MCP EncoderBox |
| | | | `CB42` | MCP IgnitionBox |

**Cube Controls — VID `C872`** (PIDs em `20xx`): F-PRO `2007`, GT-PRO V2 `200A`,
AC190 `200B`, **AMG `200C`**, Astra `2010`.

⚠️ **`C872` é também o VID das telas VoCore** (PID `1004`). Um `EnableHidraw` com `C872:xxxx`
atinge só o PID listado, mas tenha isso em mente ao diagnosticar: dois tipos de device
diferentes compartilham o VID. É justamente por isso que o SimHub precisa da topologia USB
para telas — VID/PID não as distingue.

⚠️ **Verificação obrigatória** após aplicar: rode `hidenum.exe`
(`~/apps/conspit-ares-linux/tools/hidenum.c`) dentro do prefixo. Um device correto aparece
**duas vezes** — `usage 0x04` (joystick) e `usage 0x3A` (vendor, `in 64 out 64`). Se só sai
`usage 0x05` com `out 0`, ainda está sintetizado pelo SDL.

⚠️ **A enumeração tem corrida**: logo após `wineserver -k` a primeira passada pode não listar
tudo. Meça sempre na segunda, com ~3 s de intervalo.

## Receita 2 — devices seriais (Conspit) ✅ validada

Este é o caminho que estava sem solução e foi fechado em 2026-08-16. A cadeia:

1. `StandardProtocolManager.GetDriver()` procura **a porta COM cujo USB VID/PID bate**.
2. `SerialPort.GetPortNames()` lê `HKLM\HARDWARE\DEVICEMAP\SERIALCOMM` — chave **volátil**,
   preenchida pelo `wineboot` a partir de `dosdevices/com*`.
3. `WoteverCommon.DeviceInformation` monta o `Name` do device via **`DEVPKEY_NAME`** e extrai
   a porta por **regex `\((COM\d+)\)` sobre esse Name**; VID/PID vêm de regex sobre o
   instance ID.

**No Wine toda COM nasce sem identidade USB** (medido: 36 portas, todas `VID=0 PID=0`). A
correção é um nó PnP — mas o nó "legado" que basta para Qt/ConspitLink **não basta aqui**:

⚠️ **O SimHub lê `DEVPKEY_NAME`, e o Wine só o resolve pela subchave
`Properties\{fmtid}\{pid:04X}` com valor `hex(ffff0012)` (UTF-16LE + `00 00`).** Sem ela,
`SetupDiGetDevicePropertyW` devolve **erro 1168**, o nome cai no fallback, a regex não acha
porta nenhuma e o casamento falha em silêncio. `FriendlyName`/`DeviceDesc` legados **não
substituem**. Use `tools/nameprobe.c` para checar qual API responde o quê.

Receita completa (exemplo: H.AO, VID `3514` PID `0007`, serial USB `346534443132`):

```
Enum\USB\VID_3514&PID_0007\346534443132
    Class=Ports  ClassGUID={4d36e978-e325-11ce-bfc1-08002be10318}
    FriendlyName="CONSPIT H.AO (COM37)"     ← a regex extrai a porta DAQUI
    Service=Serial  ConfigFlags=0  HardwareId=USB\VID_3514&PID_0007
    Device Parameters\PortName=COM37
    Properties\{b725f130-47ef-101a-a5f1-02608c9eebac}\000A   ← DEVPKEY_NAME
    Properties\{a45c254e-df1c-4efd-8020-67d146a850e0}\000E   ← DEVPKEY_Device_FriendlyName
        ambos hex(ffff0012) com "CONSPIT H.AO (COM37)"
HKLM\Software\Wine\Ports\COM37 = /dev/serial/by-id/...
dosdevices/com37 -> /dev/serial/by-id/...
```

- ⚠️ **`reg add` não escreve `hex(ffff0012)`** — monte um `.reg` e importe com `regedit /S`.
- ⚠️ **COM > 32**: o `wineboot` preenche `com1..com32` varrendo `/dev/ttyS*` e sobrescreve
  qualquer symlink nessa faixa.
- ⚠️ **`wineserver -k` no fim**: o `SERIALCOMM` é volátil; symlink criado com o wineserver de
  pé só aparece depois de reiniciá-lo. *(Custou uma rodada de diagnóstico.)*
- Sempre `/dev/serial/by-id/` — `ttyACMn` renumera a cada reenumeração.

## Telas VoCore — diagnóstico fechado, sem correção por registro

O `ScreenUSBRequest` dos volantes com tela pede **VID `0xC872` PID `0x1004`** com
`HasParentHub=True`. Todas as telas VoCore compartilham esse mesmo VID/PID: são
indistinguíveis entre si. **O SimHub descobre a qual volante cada tela pertence subindo a
árvore USB até o hub pai** (`PortSignature` / `UsbPath` no `WoteverCommon`).

**No Wine essa árvore não existe.** Medido: `PortSignature` e `UsbPath` lançam
`NullReferenceException` para **100% dos devices** (0 de 125), porque o `DeviceType` sai do
nome do Service — `usbxhci` → Controller, `winehid`/`winebus` → Device — e **nenhum
controlador USB é exposto**. Sem controlador não há caminho para subir.

Não há correção por registro: exigiria o Wine expor topologia USB. Caminhos possíveis, em
ordem de custo: (a) confirmar com hardware se os **LEDs** do volante conectam sozinhos
(provável, e resolve boa parte do valor); (b) issue no Wine; (c) shim que sintetize a
hierarquia. **Não comece por (c).**

Sobre o driver da tela no Windows: ainda **não investigado**. A hipótese do usuário é que a
VoCore precise de driver instalado; sob Wine isso provavelmente significa um driver de
display USB, o que é problema à parte do PnP acima.

## O hardware desta bancada

Informado pelo usuário em 2026-08-16 e **conferido contra o catálogo do SimHub — bate
exatamente**. Nenhum destes está na bancada ainda, exceto o Conspit.

| device | VoCore | driver no SimHub | receita | ordem |
|---|:---:|---|---|:---:|
| Conspit H.AO HUB | não | `StandardProtocolManager` (serial) | 2 ✅ **validado** | — |
| Pokornyi MCP ButtonBox | não | `PokornyiMCPButtonBoxManager` (HID) | 1 | **1º** |
| Pokornyi MCP EncoderBox | não | `PokornyiMCPEncoderBoxManager` (HID) | 1 | 1º |
| Pokornyi MCP IgnitionBox | não | `PokornyiMCPIgnitionBoxManager` (HID) | 1 | 1º |
| Pokornyi FGT | não | `PokornyiFGTManager` (HID) | 1 | 2º |
| Cube Controls AMG | não | `CubeControlsAMGLedsManager` (HID) | 1 | 2º |
| Pokornyi HYP-R | **sim** | composite: LEDs (HID) + tela | 1 + ❌ | 3º |
| Pokornyi F499 | **sim** | composite: LEDs (HID) + tela | 1 + ❌ | 3º |
| Pokornyi GTB Pro | **sim** | composite: LEDs (HID) + tela | 1 + ❌ | 3º |
| Pokornyi PDU5 | **sim** | composite: LEDs (HID) + tela | 1 + ❌ | 3º |
| Pokornyi PDU7 | **sim** | composite: LEDs (HID) + tela | 1 + ❌ | 3º |

⚠️ Outra unidade do mesmo modelo pode diferir — confirme com `lsusb` ao plugar.

## Ordem de trabalho sugerida

1. **Comece por um MCP** (ButtonBox, EncoderBox ou IgnitionBox): sem tela, receita 1, e são
   três devices irmãos — o que funcionar num serve nos outros, validando a generalização de
   graça.
2. `lsusb` → confirmar VID/PID reais contra as tabelas acima.
3. Aplicar a receita 1 e verificar com `hidenum.exe` (as **duas** collections).
4. FGT e AMG a seguir: mesma receita, marcas/managers diferentes — confirma que o caminho
   não é específico da Pokornyi.
5. Só então um volante com tela (HYP-R, F499, GTB Pro) ou um dash (PDU5, PDU7), **medindo
   primeiro se a metade dos LEDs conecta sozinha**. Se conectar, boa parte do valor está
   entregue mesmo com a tela pendente.
6. Telas VoCore por último — é o único item sem correção conhecida.

## Segurança

⚠️ **A base Conspit Ares é de 20 Nm.** O SimHub varre portas seriais procurando Arduinos, e a
base aparece mapeada em mais de uma COM. Ela ignora texto que não seja comando OpenFFBoard,
então o risco é baixo — mas **confira se o auto-detect de Arduino do SimHub está restrito às
portas certas**, e nunca mande `=`, `sys.0.save`, `sys.0.format` ou calibração `odrv.*` numa
porta que possa ser a base.

Sondas de diagnóstico devem ser **somente leitura** por padrão. Escrever no registro do
prefixo é reversível (backup: `pfx/system.reg.bak-*`); escrever na firmware não é.

## Pegadinhas já pagas

1. **Entradas PnP obsoletas travam o device em silêncio.** Um `Enum\HID\VID_xxxx&PID_xxxx*`
   remanescente faz o `col01` ser registrado mas nunca ficar "present" — e o driver recebe
   `null`, com `NullReferenceException` a cada 2 s no log. Correção: apagar as entradas e
   deixar o Wine recriar. Foi o que destravou os pedais CPP.LITE.
2. **`ConspitManager.GetDriver()` é compartilhado** entre haptics e LEDs — um device parcial
   derruba os dois caminhos, e o sintoma aparece longe da causa.
3. **Erros `FindGamePath` / `CompatibilityStoreHelper` no log são de outra natureza** (achar
   jogos instalados, Steam nativo). Não são pista de problema de device — ignore ao
   diagnosticar Devices.
4. **Não confie em `strings` para achar nomes em app .NET/Qt** — UTF-16. Use `strings -el`.

## Escopo

- Foco sim racing, Linux, SimHub sob Wine. Um único setup: o do autor.
- Nada aqui porta ou redistribui software de terceiros. O SimHub é da Wotever, o
  linux-simracing-utils e o Winecarte são da srounce. Este repo é análise e configuração.
- Projeto pessoal, sem garantia nem suporte.
