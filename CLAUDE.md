# SimHub Devices no Linux — fazer a aba Devices reconhecer volantes e caixas de botões

Repo deste projeto: `~/apps/simhub-devices-linux/`.

**O que este projeto resolve:** no Linux o SimHub roda sob Wine e a aba **Devices** fica em
`Searching device ...` para sempre — LEDs, telas e botões de volantes não conectam. Isso não
é limitação do hardware nem do SimHub: são lacunas específicas do Wine na árvore PnP, e cada
uma tem correção conhecida (ou diagnóstico fechado, no caso das telas).

**Estado: cinco devices validados com hardware — incluindo a tela VoCore.** O Conspit H.AO HUB (serial, receita 2) e
os três Pokornyi MCP — ButtonBox, EncoderBox, IgnitionBox (HID, receita 1) — conectam e
respondem, com os LEDs controláveis pelo SimHub (2026-08-16). **As duas receitas estão
validadas.** A **tela VoCore da PDU5 também funciona** desde 2026-08-18, por uma terceira
via — a **ponte de tradução da libusb** (`tools/libusb-bridge/`, receita 3). O que sobra sem
solução são os **LEDs** da PDU5, por um motivo próprio e diagnosticado (seção no fim). O resto continua **inferência a partir do código do
SimHub**, medida mas **não testada com hardware** — está marcado como tal ao longo do
arquivo. Não apague essas marcas ao editar; elas são o que separa o que sabemos do que
supomos.

## Projetos irmãos

- `~/apps/conspit-linux-configurator/` (ex-`conspit-ares-linux`) — hardware Conspit no Linux. **A base de tudo que está aqui.**
  Leia o `CLAUDE.md` de lá antes de mexer em `winebus`/`EnableHidraw`/udev: o backend hidraw,
  a armadilha da chave `Services\winebus` (e não `\Parameters`) e as regras udev estão
  resolvidos e documentados lá, com os erros que custaram dias.
- `~/apps/diy-ffb-pedal-linux/` — pedal DIY FFB. Origem do aprendizado de Wine + serial.
- `~/apps/wine-libusb-bridge/` — **nosso**, extraído daqui em 2026-08-18. Substitui a
  `libusb-1.0.dll` de um app Windows por uma ponte para a libusb do Linux. É o que faz a
  tela VoCore funcionar, e serve a qualquer app sob Wine que use a API síncrona da libusb
  (no SimHub: VoCore ✅ provado, e também AX206, Conspit e SimLab, que passam pela mesma
  `SimHub.LibUsbNative.dll`). Saiu deste repo porque aqui é análise; lá é produto.
⚠️ **A ponte é PRÉ-REQUISITO deste projeto, não submodule.** `tools/simhub-devices install
bridge` a procura em `~/apps/wine-libusb-bridge` (ou em `SIMHUB_PONTE`) e roda `make` se
faltar binário. Não vira submodule de propósito: ela serve qualquer app Windows sob Wine com
libusb síncrona, e pendurá-la num repo de sim racing inverteria esse desenho. ⚠️ Ela ainda
**não tem remote** — publicar é o passo que falta para o pré-requisito ser instalável por
terceiros.

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
| `tools/hidenum.c` | enumera HID **de dentro do prefixo**: o que o SimHub enxerga. `wine hidenum.exe [VID...]` |
| `tools/nameprobe.c` | qual API do SetupAPI responde o quê (usado na receita 2) |
| `udev/70-pokornyi.rules` | ACL de `/dev/hidraw*` para Pokornyi — **o passo que destrava a receita 1** |
| `udev/70-vocore.rules` | ACL de escrita no nó USB da tela VoCore (libusb) |
| ~~`tools/libusb-bridge/`~~ | **mudou de repo** → `~/apps/wine-libusb-bridge` (ver "Projetos irmãos"). É a ponte que fez a tela funcionar |

⚠️ Os managers do catálogo estão em **`SimHub.Plugins.dll`**
(`SimHub.Plugins.OutputPlugins.GraphicalDash.PSE.*`); os drivers, em **`BA63Driver.dll`**.
Procurar o manager na DLL errada devolve vazio e parece que ele não existe.

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
| `BitmapDisplayDevice<VOCORESettings>` | 13 | tela VoCore | ✅ resolvido pela ponte libusb |

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

## Receita 1 — devices HID (Pokornyi, Cube Controls) ✅ validada

**Validada com hardware em 2026-08-16**: MCP ButtonBox, EncoderBox e IgnitionBox conectaram
e os LEDs respondem pelo SimHub. E a validação trouxe uma correção de rumo importante:

⚠️ **O passo que faltava não era registro — era `udev`.** Este arquivo dava a receita como
"apontar o `EnableHidraw` para o VID novo". Num prefixo que já tem `Enable SDL=0` **+**
`DisableInput=1` isso é **quase inócuo**: a rede de segurança já força `prefer_hidraw` para
qualquer joystick, então o `EnableHidraw` só documenta a intenção. O que realmente bloqueava
era `/dev/hidraw*` ser **root-only** para VID `0483` — o winebus tentava abrir, falhava, e
descartava o device **em silêncio**.

Medido: a regra udev entrou às 02:49, e o log do SimHub registrou os três MCP em
`Connected` às **02:49:52**, com o app já aberto e sem reiniciar nada. Depois de um
`wineserver -k` + reabrir, conectaram de novo sozinhos — a configuração persiste.

**Comece pelo udev**, não pelo registro: `udev/70-pokornyi.rules` (VID `0483`, PIDs `cb??` —
o casamento por PID existe porque `0483` é o VID genérico da ST, ver comentários no arquivo).

O Wine, por padrão, entrega joysticks **sintetizados pelo SDL**, com uma collection só — os
canais vendor de 64 bytes por onde os LEDs falam não existem para o app. Em **hidraw** o
`hidclass` separa as top-level collections em `&Col01`/`&Col02`, como no Windows.

⚠️ **Mas só as collections IRMÃS.** Uma collection vendor **aninhada** continua dentro do
PDO externo, e isso decide qual device funciona (medido nos report descriptors, 2026-08-16):

```
Conspit CPP.LITE — irmãs, viram dois PDOs:
   09 04 a1 01 ... c0      TLC #1  Joystick     -> &col01, usage 0x04
   09 3a a1 01 ... c0      TLC #2  vendor 0x3A  -> &col02, usage 0x3A

Pokornyi (todos) — aninhada, vira UM PDO:
   09 04 a1 01
         05 ff 09 01 a1 01 ... c0     nao vira PDO proprio
      c0
```

Nos Pokornyi o canal vendor (report ID `0x5A`, 63 bytes in + 63 out = os 64 do
`reportBuffer` do `PokornyiDriver`) é alcançado **pelo mesmo handle** do joystick. Por isso
os LEDs dos MCP funcionam com um PDO só.

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

⚠️ **Verificação obrigatória** após aplicar: rode **`tools/hidenum.exe` DESTE repo** dentro
do prefixo (`wine hidenum.exe 0483` filtra por VID; sem argumento lista tudo). O que esperar
depende da topologia do descriptor, e **não é sempre "duas vezes"**:

| descriptor | esperado no `hidenum` |
|---|---|
| collections irmãs (Conspit) | **duas** linhas: `usage 0x04` e `usage 0x3A`, ambas `in 64 out 64` |
| vendor aninhada (Pokornyi) | **uma** linha: `usage 0x04`, `in 64 out 64` |
| ainda sintetizado pelo SDL | `usage 0x05` com `out 0` — errado nos dois casos |

⚠️ **NÃO use o `hidenum.c` do projeto Conspit aqui.** Ele tem `attr.VendorID == 0x3514`
**cravado no código** e devolve lista vazia para Pokornyi/Cube Controls — parece que o device
não existe. Custou uma conclusão errada em 2026-08-16 ("nenhum `VID_0483` no prefixo"),
contradita pelo usuário, que via os três MCP conectados na tela enquanto a ferramenta dizia
que não havia nenhum. A versão deste repo aceita VID por argumento e marca `[sem acesso]` em
vez de omitir o device que não conseguiu abrir.

⚠️ **A enumeração tem corrida**: logo após `wineserver -k` a primeira passada pode não listar
tudo. Meça sempre na segunda, com ~3 s de intervalo.

### O `usagePage`/`usage` é POR MANAGER

⚠️ **HISTÓRICO (2026-08-18 → 2026-08-19).** Esta seção chegou a ser marcada como refutada,
porque o patch parecia não ter efeito no app. **O diagnóstico do `usagePage` estava CERTO** — o
que não funcionava era o patch, engolido pelo cache NGen (ver "A armadilha do NGen" abaixo).
Resolvido em 2026-08-19: a PDU5 conecta LEDs **e** tela.

Cada manager pede uma collection específica, e o argumento sai como constante no IL
(assinatura medida: `PokornyiDriver.GetDevice(mapper, pid, usagePage, usage, BWButtonsCount,
requestedSerialNumber, vid)`). O filtro final é `HidDeviceExtensions.MatchUsage`, que compara
com o **caps da top-level collection** (`HidP_GetCaps`) — exatamente o que o `hidenum` mostra:

| manager | usagePage | usage | casa com o hardware? |
|---|---|---|---|
| `PokornyiMCPButtonBoxManager` | `1` | `4` | ✅ o PDO é `0x0001/0x04` |
| `PokornyiMCPIgnitionBoxManager` | `1` | `4` | ✅ |
| `PokornyiHYPRManager` | `1` | `4` | ✅ |
| **`PokornyiPEPDU5Manager`** (original) | **`0xFF`** | **`1`** | ❌ nunca casa |

A PDU5 é procurada pela collection **vendor** — mas o descriptor dela é uma collection Joystick
**vazia** (sem botões e sem eixos, é um dash) com a vendor aninhada dentro, então o único PDO que
o Wine expõe é `0x0001/0x04`. `tools/pdu5-leds-patch.py` troca `0xFF/1` por `1/4` no IL.

⚠️ **Por que a falha é TOTALMENTE silenciosa.** Medido no IL de `PokornyiDriver.GetDevice`:

```
devices = HidDeviceList.GetHidDevices(vid, pid).Where(d => d.MatchUsage(usagePage, usage))
foreach (d in devices):
    Log.Debug('Scanning {0}, sn {1} (requested : {2}, {3}, {4})')   <- so o que SOBREVIVEU ao filtro
    if (SerialNumbersStore.IsMatchingSerialNumber(...)):
        Log.Debug('Connecting ...') ; return new PokornyiDriver(...)
```

O log só existe **depois** do `MatchUsage`. Com `usagePage` errado a lista sai vazia e **não há uma
única linha** — nem erro, nem "Scanning". Foi isso que fez o device parecer "nunca varrido".

### A armadilha do NGen — por que patch de IL no SimHub não faz nada (2026-08-19)

⚠️ **O prefixo tem imagens nativas pré-compiladas em
`drive_c/windows/assembly/NativeImages_v4.0.30319_32/`, e `SimHub.Plugins` é uma delas (26 MB).**
O SimHub roda **32-bit** e executa essa imagem nativa: **o IL da DLL é ignorado**. Todo patch em
`SimHub.Plugins.dll` é um **no-op no app** até a imagem ser removida.

O que tornou isso quase invisível por um dia inteiro:

- As **sondas** deste projeto são compiladas com `/platform:x64`. Não existe imagem nativa 64-bit
  do SimHub.Plugins, então a sonda **JIT-a o IL do disco** — e vê o patch funcionando.
- O **app** é 32-bit e usa a imagem nativa — e não vê o patch.
- Resultado: `PokornyiPEPDU5Manager.GetDriver()` devolvia `IsConnected=True` por sonda enquanto o
  app jamais varria a PDU5. Os dois mundos nunca concordaram, e cada medição "provava" o oposto
  da outra.

⚠️ **Os dois passos são necessários — medido por eliminação em 2026-08-19.** Com o NGen já
removido, revertendo **só** o patch do `usagePage`, a PDU5 volta a não conectar (`51969` nunca
requisitado). Reaplicando o patch, volta a conectar na mesma sessão. Ou seja: o patch conserta a
collection errada; a remoção do NGen faz o patch **executar**. Nenhum dos dois sozinho resolve.

**Como detectar:** patcheie uma constante fácil de observar (ex.: o `pid` do ctor de um manager
que funciona) e veja se o app muda de comportamento. Se não mudar, é NGen.
Medido: patchei o ctor do `PokornyiMCPButtonBoxManager` de `CB40` para `CB01` e ele **continuou
conectando no `pid_cb40`** — o app não estava lendo a DLL.

**Correção (é o que destravou tudo):**

```bash
NI=~/apps/linux-simracing-utils/pfx/drive_c/windows/assembly/NativeImages_v4.0.30319_32
mv "$NI"/SimHub.Plug* /algum/lugar/de/backup/     # SimHub.Plugins e variantes
```

⚠️ **Volta a cada update do SimHub** (o instalador roda ngen). Junto com a `libusb-1.0.dll` da
ponte, são as duas coisas a refazer depois de atualizar.

### O composite da PDU5 — RESOLVIDO em 2026-08-19

Sintoma antigo: `Searching device ...` / `Leds not found` para sempre, **sem uma linha no log**.
Causa: `usagePage 0xFF` (patch existia mas o NGen o ignorava). Com a imagem nativa removida:

```
Device Status changed : Pokornyi Engineering PDU5 - LEDs : Connected
Pokornyi Engineering PDU5 Found screen 2A-...  ->  Connecting to screen
```

Os **LEDs RPM respondem e são ajustáveis pelo SimHub** (confirmado pelo usuário). A metade da tela
também conecta, pela ponte libusb.

Estrutura, medida instanciando a `Factory` por reflexão:

```
PDU5 = CompositeDeviceInstance
   ├── BitmapDisplayDevice<VOCORESettings>   IsPrimary=False   CompositeCode=LCD
   └── LedModuleDevice                        IsPrimary=True    CompositeCode=LEDS
```

Os **LEDs são o device primário**; a tela depende deles (`PrimaryDeviceMissing` bloqueia os
secundários). Por isso o `usagePage` errado derrubava as **duas** metades — e por isso a tela
passou a funcionar sozinha assim que os LEDs conectaram.

**Hipóteses testadas e REFUTADAS** (não refaça):

| hipótese | como foi testada | resultado |
|---|---|---|
| estado velho da instância | Delete + Add new device pela UI (2×) | ❌ |
| metade LCD desabilitada segurava o composite | `LCD.display.Enabled` False→True | ❌ |
| `HasParentHub=True` (topologia USB) | patch de 3 bytes + **HYP-R conectando com `hub=True`** | ❌ |
| composite é quebrado no Wine | device de controle "Generic Vocore Screen with I2C LEDs" | ❌ conecta normal |
| enumeração HID contaminada por handles abertos | MCP + H.AO desabilitados | ❌ |
| interação com outros devices | PDU5 como ÚNICO device habilitado | ❌ |
| plugins segurando o device | só o `DevicesPlugin` habilitado | ❌ |
| hot-plug destrava (como no HYP-R) | desplugado alguns minutos e replugado | ❌ |
| firmware desatualizado da PDU5 | descartado por evidência, sem gravar nada | ❌ o driver já conectava por sonda |

⚠️ **Entradas PnP obsoletas: anomalia real, mas NÃO era a causa.** A PDU5 tinha **3** instâncias
em `Enum\{HID,USB,WINEBUS}` e **3** em `Control\DeviceClasses` (contra **1** de cada outro
device) — duas delas da **segunda PCB de PDU5** do usuário, com outro serial. Limpar e deixar o
Wine recriar deixou a árvore correta (medido: 1 instância, serial certo), mas **não** fez o device
conectar. Vale limpar mesmo assim; só não credite a correção a isso.

⚠️ **Armadilhas de método que custaram caro nesta investigação:**

1. **Sonda HID só funciona com o SimHub PARADO.** Com ele de pé, `HidDeviceList.GetHidDevices`
   devolve lista vazia para todos os PIDs, inclusive os que ele mesmo tem conectados.
2. **Composites NUNCA logam `Device Status changed` na forma de dois campos** — nem o HYP-R que
   funciona. Eles usam `'{0} - {1} : {2}'` com o `CompositeLabel`. Concluir "o device não recebe
   `Update()`" a partir da ausência do log de dois campos é **inválido**.
3. **Simular o ciclo offline não é fiel.** `DeviceInstance.Update(null, null, false)` lança
   `NullReferenceException` em `BitmapDisplayDevice.DataUpdate` — **e o HYP-R que funciona lança
   exatamente a mesma coisa.** Artefato dos argumentos nulos.
4. **Instância de device criada à mão não é confiável.** `Settings:{}` fez o `ConvertToInstance`
   lançar `KeyNotFoundException` (logado como `Failed to reload device`), e mesmo com settings
   clonadas a instância ficou inerte. Adicione pela UI.
5. **Sempre rode o mesmo teste num device que funciona antes de concluir.** Foi o controle com o
   HYP-R e com o ButtonBox que derrubou três conclusões erradas minhas.

### Topologia USB real desta bancada (medida com `lsusb -t`)

```
Dev 058 hub
 └ Dev 060 hub
    ├ Dev 062  Conspit CPP.LITE
    └ Dev 064  hub  ← MCP ButtonBox (é um hub USB também)
       ├ Dev 065  0483:cb42  MCP IgnitionBox
       ├ Dev 067  0483:cb41  MCP EncoderBox
       ├ Dev 069  0483:cb40  MCP ButtonBox (parte HID)
       └ Dev 066  hub  ← a própria PDU5 tem um hub interno
          ├ Dev 068  0483:cb01  PDU5 (LEDs)
          └ Dev 070  c872:1004  tela VoCore   [Driver=none]
```

O HYP-R entra por passthrough USB no eixo da base Conspit, e também tem hub interno com a própria
VoCore. `HasParentHub=True` funciona nos dois — a topologia que o SimHub usa para casar tela e
volante vem da **libusb** (pela ponte), não do PnP do Wine.

### O que os descritores pedem (medido nos 9 devices Pokornyi)

| device | LED | Screen |
|---|---|---|
| MCP ButtonBox / IgnitionBox | `0483:CB40` / `CB42` | (null) |
| FGT / RALLY | `0483:CB15` / `CB12` | (null) — **não têm tela** |
| PDU5 / HYP-R / HYP-R PRO / F499 / GTB Pro | `0483:CB01`/`CB10`/`CB16`/`CB14`/`CB11` | `C872:1004` `HasParentHub=True` |

⚠️ A correlação "quem tem `ScreenDetectionDescriptor` nulo funciona" é **trivial** — é só
"tem tela ou não". Não a use como evidência de causa.

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

Receita completa (exemplo: H.AO, VID `3514` PID `0007`, serial USB `<SERIAL-USB>` —
substitua pelo serial real do seu device; ele aparece em `/dev/serial/by-id/`):

```
Enum\USB\VID_3514&PID_0007\<SERIAL-USB>
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

## Telas VoCore — ✅ RESOLVIDO em 2026-08-18 pela ponte libusb

⚠️ **Leia isto antes do resto da seção.** Tudo abaixo continua **factualmente correto** sobre
por que o caminho *nativo do Wine* não fecha — mas a conclusão "sem solução" **caiu**. A tela
da PDU5 mostra o dash do SimHub, pela aba Devices, desde 2026-08-18 16:36.

**Como:** substituindo a `libusb-1.0.dll` do SimHub por uma **DLL PE32 pura** que encaminha
as 32 chamadas (todas síncronas) a um **helper nativo** rodando contra a `libusb-1.0.so` do
Linux, que fala com o device por **usbfs**. Nenhum driver de kernel, nenhum `winusb`, nenhum
patch no SimHub, nenhum `mpro_drm`.

- Código e protocolo: `tools/libusb-bridge/` (`shim.c`, `helper.c`, `proto.h`).
- Medido: `open` ok, `claim_interface(0)` ok, `bulk ep=0x02 len=819840 actual=819840`
  (854×480×2 = frame cheio em RGB565), `USB Path 5:2-2-4-2-4` resolvido **pela libusb real**.
- Plano e evidência completos: `implementation-plan.md`, seções 8.1 e 8.2.
- ⚠️ **A DLL cai a cada update do SimHub** — o original fica em `libusb-1.0.dll.orig`.
- ⚠️ **O helper precisa estar de pé ANTES do SimHub**, senão a DLL devolve erro.
- ⚠️ **Suba o SimHub pelo `lsu-launch-wrapper`, nunca com `wine SimHubWPF.exe` direto.** Por
  fora do wrapper o app abre e os devices funcionam, mas **a telemetria não chega**: é o
  wrapper que sobe o `winehub`, o daemon que espelha a memória compartilhada do jogo para
  dentro do prefixo (via `wine2linux.exe`). Sintoma longe da causa; custou um diagnóstico.
- ⚠️ O helper faz **fork por conexão** e limpa tudo quando o cliente cai. Sem isso: o SimHub
  mantém mais de um `SubProcess.X86.exe` vivo e (a) o velho segurava o único slot do helper,
  derrubando o novo com `TimeoutException` no `ConnectToScreen`, e (b) a interface ficava
  reivindicada, dando `LIBUSB_ERROR_BUSY` na instância seguinte.
- ✅ **O touch da tela funciona pela mesma ponte** (`intr ep=0x81`, reports de 14 bytes):
  o SimHub recebe os toques direto, sem evdev e sem disputa com o KDE — o kernel sequer vê
  a tela como input, já que nenhum driver a reivindica.
- ⚠️ O que **não** foi resolvido por isto: os **LEDs** da PDU5 (`usagePage 0xFF`).

### Por que o caminho nativo do Wine não fecha (o diagnóstico que levou à ponte)

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

### O "driver da VoCore": investigado em 2026-08-16 — é libusb, não driver de display

A hipótese antiga (driver de display USB) está **descartada**. O caminho do SimHub é

```
SimHub.BitmapDisplay.Vocore.dll -> SimHub.LibUsbNative.dll -> libusb-1.0.dll
```

— libusb puro, a tela é escrita como device USB bruto por endpoints bulk (medido no
hardware: interface única `ff/ff/ff`, `ep_02` OUT + `ep_81` IN, **nenhum driver do kernel**
ocupando). O que o instalador do SimHub faz no Windows é **ligar o WinUSB ao device** (o que
o Zadig faz), porque no Windows a libusb não fala com device sem WinUSB/libusbK ligado.
**Não tente reproduzir esse passo no prefixo**: instalaria um driver de kernel do Windows
que o Wine não executa.

⚠️ **Correção (2026-08-16, apontada pelo usuário):** este arquivo chegou a afirmar que "a
`winusb.dll` builtin do Wine é implementada sobre a libusb do host". **Falso** — a
`winusb.dll` do Wine é **stub** (medido: `"(%p) - stub"` nas strings do binário). Não há
hoje NADA no Wine que faça o backend Windows da libusb funcionar. O usuário conferiu o
`wine uninstaller` e notou a ausência dos instaladores de driver (VoCore, AX206) que o
SimHub instala no Windows — a ausência é sintoma esperado (instalador de driver de kernel
não roda sob Wine), mas a réplica dele a esta suposição é que forçou a medição do stub.

Isso torna o sintoma legível na UI: a aba da tela mostra **`Screen ID` vazio** e
`Connection status: Not found` porque a enumeração de telas volta **lista vazia**.

**Dois bloqueios em série, ambos medidos:**

1. **Permissão do nó USB — RESOLVIDO.** `/dev/bus/usb/BBB/DDD` nasce `crw-rw-r--` (só
   leitura para o usuário) e a libusb precisa de **rw** para `libusb_claim_interface`. O
   `wineusb` falhava com `Access denied (insufficient permissions)` e descartava a tela em
   silêncio. Corrigido por `udev/70-vocore.rules` (PID `1004` exato — `c872` é também o VID
   da Cube Controls). Depois disso o trace `WINEDEBUG=+wineusb` mostra
   `add_usb_device ... vendor c872, product 1004` e o nó PnP aparece:
   `Enum\USB\VID_C872&PID_1004\...`, com `CompatibleIDs = USB\Class_ff...`.

2. **Nenhum driver ligado ao nó — SEM SAÍDA DENTRO DO WINE ATUAL.** O nó nasce com
   `ClassGUID={00000000-...}` e **sem valor `Service`**, e **nenhuma** interface de device é
   registrada (medido: `DeviceClasses` não tem `{A5DCBF10-...}` GUID_DEVINTERFACE_USB_DEVICE
   nem `{88BAE032-...}` GUID_DEVINTERFACE_WINUSB, em prefixo do SimHub **e** em prefixo
   limpo recém-criado). A libusb que o SimHub carrega classifica o device **lendo qual driver
   está ligado** — as mensagens estão no próprio binário: `The following device has no
   driver: '%s'` e `unsupported API call for '%s' (unrecognized device driver)`. Sem driver e
   sem interface, o device nunca entra na lista — e mesmo que o nó fosse consertado à mão, a
   `winusb.dll` que atenderia as chamadas é stub (ver correção acima).

   O prefixo tem só `wineusb.inf`, que instala o **bus driver** em `root\wineusb`; o Wine traz
   `wineusb.sys` + `winusb.dll` user-mode, mas **nenhum `winusb.sys`** function driver. O
   estado é o mesmo de um device no Windows *antes* de o instalador ligar o WinUSB nele.

⚠️ Este bloqueio é **independente** do de topologia USB acima. O da topologia decide *a qual
volante* uma tela pertence (`HasParentHub`); este decide se **alguma** tela chega a ser
enumerada. A entrada genérica "Generic Vocore Screen" do catálogo esbarra neste, não naquele.
Atacar a topologia sem resolver este não produz nada.

### O caminho nativo viável — ponte libusb ✅ EXECUTADO em 2026-08-18

Estava arquivado como "caro". **Não era.** As medições que sustentavam a ideia estavam
certas, e o obstáculo que a arquivava estava errado (ver a correção do WoW64 abaixo):

- `SimHub.LibUsbNative.dll` faz P/Invoke de exatamente **32 funções** da `libusb-1.0.dll`,
  **todas da API síncrona** — sem callbacks, sem transferências assíncronas, sem hotplug.
  Uma DLL winelib que repasse essas 32 chamadas à `libusb-1.0.so` do host substitui o
  backend Windows inteiro (SetupAPI, hubs, WinUSB — tudo dispensado).
- A lista inclui `libusb_get_parent`, `libusb_get_port_numbers`, `libusb_get_bus_number`:
  **a topologia que falta no PnP do Wine, o SimHub pede à própria libusb** — e a árvore USB
  real do Linux a tem. A ponte resolveria enumeração E identificação de uma vez.
- ⚠️ **CORREÇÃO (2026-08-18): o obstáculo do WoW64 não existia.** Este arquivo dizia que a
  ponte esbarrava em o Wine ser WoW64 novo (sem `i386-unix`) e o serviço VOCORE rodar no
  `SimHub.SubProcess.X86.exe` 32-bit. **Isso só vale para winelib** (DLL PE com metade unix
  `.so`). Uma DLL **PE pura** que converse com um helper por socket carrega normalmente no
  processo 32-bit — medido: `ATTACH pid=556 exe=SimHub.SubProcess.X86.exe`. Não foi preciso
  patch de IL nenhum no `RemoteClassProxy`3.CreateProcess`; a investigação do seletor X86/X64
  virou irrelevante.
- Convenção de chamada, medida no binário original com `objdump`: **31 funções `stdcall`**
  (`libusb_init` → `ret $0x4`, `libusb_bulk_transfer` → `ret $0x18`, …) **+
  `libusb_set_option` `cdecl`** (varargs). Exports **não decorados** — daí o `.def` +
  `-Wl,--kill-at`. Conferir os 32 tamanhos de pilha antes de rodar evita um crash mudo.
- Marshaling: **não há caso difícil.** A única struct de conteúdo é
  `libusb_device_descriptor`, só escalares (18 bytes, idêntica em 32 e 64 bits).
  `libusb_get_config_descriptor` — a que teria ponteiros aninhados — **não é usada**.

### Decisão de 2026-08-16: tela via DRM nativo (fora do SimHub) — ⚠️ SUPERADA em 2026-08-18

⚠️ Mantido como registro e como **fallback**. Com a ponte libusb funcionando, o `mpro_drm`
não é necessário para usar a tela **no SimHub**; ele continua sendo a única forma de usar a
tela **fora** dele. ⚠️ Os dois não convivem: com o módulo carregado, o kernel reivindica a
interface e a ponte para de enxergar o device.

O usuário pesquisou a comunidade e fechou: para a tela, o caminho é o **driver DRM
`mpro_drm`** (Vonger, o criador da VoCore) + um renderizador nativo (SimMonitor/monocoque).
As issues `vocore2#56` e `#21` confirmam por eliminação: são sobre o **fbusb**, o driver
antigo de framebuffer, quebrado em kernels modernos (`mmap` → `ENODEV` no 6.10) — o
`mpro_drm` é o sucessor.

- Clone com patch e módulo compilado: **`~/apps/mpro_drm`** (fora deste repo — código de
  terceiro). `linux-7.1-api.patch` adapta o código (que é para kernel 6.12) à API DRM
  atual: `drm_fb_xrgb8888_to_rgb565` sem o `bool` final, `#include <drm/drm_print.h>`,
  campo `.date` removido, `drm_client_setup()` + `DRM_FBDEV_SHMEM_DRIVER_OPS` no lugar de
  `drm_fbdev_ttm_setup()`. ⚠️ Kernel CachyOS é clang/LTO: compile com **`make LLVM=1`**.
- O driver casa `USB_DEVICE(0xc872, 0x1004)` e tem touch + backlight. Com `fbdev`
  emulado, aparece também um `/dev/fbN`.
- ⚠️ Com o módulo carregado, o kernel reivindica a interface e o caminho USB do SimHub
  (wineusb/libusb) morre — os dois não convivem ao mesmo tempo. `rmmod mpro` desfaz.
- No SimHub, desabilitar o device "Generic Vocore Screen" para parar o ciclo de
  start/close do subprocesso VOCORE a cada 2 s.

## O hardware desta bancada

Informado pelo usuário em 2026-08-16 e **conferido contra o catálogo do SimHub — bate
exatamente**. VID/PID reconferidos com `lsusb` ao plugar: bateram todos, sem surpresa de
revisão de firmware.

| device | VID:PID | VoCore | driver no SimHub | estado |
|---|---|:---:|---|---|
| Conspit H.AO HUB | `3514:0007` | não | `StandardProtocolManager` (serial) | ✅ **conecta** (receita 2) |
| Pokornyi MCP ButtonBox | `0483:cb40` | não | `PokornyiMCPButtonBoxManager` (HID) | ✅ **conecta, LEDs OK** |
| Pokornyi MCP EncoderBox | `0483:cb41` | não | `PokornyiMCPEncoderBoxManager` (HID) | ✅ **conecta, LEDs OK** |
| Pokornyi MCP IgnitionBox | `0483:cb42` | não | `PokornyiMCPIgnitionBoxManager` (HID) | ✅ **conecta, LEDs OK** |
| Pokornyi PDU5 | `0483:cb01` | **sim** | composite: LEDs (HID) + tela | ✅ **LEDs e tela conectam** (patch + NGen removido) |
| tela da PDU5 | `c872:1004` | — | `BitmapDisplayDevice` via libusb | ✅ **conecta e mostra o dash** (receita 3: ponte libusb) — MPRO D500FPC931A-A, 854×480 |
| Pokornyi FGT | `0483:cb15` | não | `PokornyiFGTManager` (HID) | não testado — receita 1 |
| Cube Controls AMG | `c872:200c` | não | `CubeControlsAMGLedsManager` (HID) | não testado — receita 1 |
| Pokornyi HYP-R | `0483:cb10` | **sim** | composite: LEDs (HID) + tela | ✅ **LEDs e tela conectam** (2026-08-18) |
| Pokornyi F499 | `0483:cb14` | **sim** | composite: LEDs (HID) + tela | não testado |
| Pokornyi GTB Pro | `0483:cb11` | **sim** | composite: LEDs (HID) + tela | não testado |
| Pokornyi PDU7 | `0483:cb02` | **sim** | composite: LEDs (HID) + tela | não testado |

⚠️ Outra unidade do mesmo modelo pode diferir — confirme com `lsusb` ao plugar.

⚠️ **Antes de assumir que os outros volantes com tela terão o mesmo problema da PDU5:**
o `usagePage 0xFF` é **por manager**, não por marca. A PDU5 falha porque o descriptor dela é
uma collection Joystick **vazia** (nenhum botão, nenhum eixo — é um dash, não um controle).
Um HYP-R ou F499, que têm botões de verdade, provavelmente têm descriptor como o dos MCP —
**meça com `hidenum` e com `ildump.py` no manager do modelo antes de concluir**.

## Ordem de trabalho sugerida

Passos 1–3 **feitos e validados** em 2026-08-16 (os três MCP). O que sobra:

1. ~~Comece por um MCP~~ ✅ — os três conectam, LEDs controláveis pelo SimHub.
2. ~~`lsusb` → confirmar VID/PID~~ ✅ — bateram todos.
3. ~~Aplicar a receita 1 e verificar com `hidenum`~~ ✅ — **e o passo decisivo foi o udev**,
   não o registro (ver receita 1).
4. **FGT e AMG**: mesma receita, marcas/managers diferentes — confirma que o caminho não é
   específico da Pokornyi. A AMG é o teste mais informativo, por ser outro fabricante.
5. Um volante com tela (HYP-R, F499, GTB Pro): **antes de plugar**, rode `ildump.py` no
   manager do modelo e veja o `usagePage`/`usage` que ele pede. Se for `1/4`, a metade dos
   LEDs deve conectar como nos MCP; se for `0xFF/1`, cai no mesmo muro da PDU5.
6. **PDU5 (LEDs)**: sem correção por registro/udev. Depende de o Wine promover a collection
   vendor aninhada a PDO próprio — candidato a issue/patch no Wine, com um caso de teste
   pequeno e claro (descriptor de 35 bytes, na receita 1).
7. ~~**Telas VoCore**~~ ✅ **RESOLVIDO em 2026-08-18** pela ponte libusb
   (`tools/libusb-bridge/`), não pelo DRM nativo. O que falta ali é acabamento: confirmar o
   **touch**, criar unit systemd para o helper subir antes do SimHub, e reinstalar a DLL
   após cada update do SimHub.

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
