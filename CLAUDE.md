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
via — a **ponte de tradução da libusb** (`~/apps/wine-libusb-bridge`, receita 3). O que sobra sem
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
### A pilha de camadas

Este projeto é a camada de cima. Cada uma só faz sentido com a de baixo pronta, e
diagnosticar fora de ordem manda a pessoa consertar a coisa errada:

```
linux-simracing-utils   instala o SimHub e cria o prefixo Wine
       ↓
wine-libusb-bridge      faz a libusb funcionar sob Wine (telas VoCore)
       ↓
simhub-devices-linux    configura os devices na aba Devices        ← aqui
```

`tools/simhub-devices doctor` checa a pilha inteira nessa ordem.

⚠️ **A ponte é dependência de camada, não submodule** — mesmo modelo que o
`linux-simracing-utils` usa para o Winecarte: o instalador traz a release fixada para um
diretório **gitignorado** (`vendor/`) e anota a tag em `.ponte-version`; nada é versionado
junto. Precedência de busca: `$SIMHUB_PONTE` → `vendor/` → `~/apps/wine-libusb-bridge`
(cópia de desenvolvimento). `SIMHUB_PONTE_VERSION` fixa uma tag, como `LSU_WINECARTE_VERSION`
faz lá.

O repo da ponte é `github.com/juliscreudo/wine-libusb-bridge`. ⚠️ Enquanto não houver uma
**release publicada** (tag), o instalador não acha tarball e cai na cópia local — que é o
comportamento correto, não um erro.

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
AMG/AC190 `200B` (**validado**), AMG variante `200C`, Astra `2010`.

⚠️ **Nomenclatura da Cube Controls, fixada em 2026-08-20.** O volante é vendido e conhecido
como **AMG**; `AC190` é o nome do *projeto*. Chame de **"Cube Controls AMG"** em todo lugar —
99% dos usuários não reconhecem "AC190", e um README que só diz AC190 faz a pessoa concluir
que o volante dela não está coberto. O que existem são **dois PIDs**, com managers distintos
sobre o mesmo `CubeControlsLedsDriverV2`:

| PID | manager | usage pedido | estado |
|---|---|:---:|---|
| `200B` | `CubeControlsAC190LedsManager` | 4 | ✅ **é o volante da bancada**, o "AMG" que se compra hoje |
| `200C` | `CubeControlsAMGLedsManager` | **8** | não testado — possivelmente uma AMG nova ainda não lançada |

Quem desempata é o **PID**, nunca o nome comercial. As duas receitas (udev `20??` e a lista
`EnableHidraw`) cobrem os dois, então na prática a distinção não muda nenhum passo.

⚠️ **Mas o `200C` pede `usage 8`, e todos os outros Cube Controls pedem `4`** (medido no IL
em 2026-08-20). `usage 8` na página Generic Desktop é *Multi-axis Controller*. Se o device
físico expuser uma collection **Joystick** (`usage 4`), como o AMG/AC190 expõe, o
`MatchUsage` nunca casa — e o sintoma é o da PDU5: `Searching device ...` **sem uma única
linha no log**. Meça com o `hidenum` antes de concluir que o volante está quebrado; se for o
caso, a correção é um patch de IL do mesmo tipo do `pdu5-leds-patch.py`, trocando `8` por `4`.
Isso reforça a leitura de que o `200C` é *outro* aparelho, não a AMG que se compra hoje.

**Catálogo completo dos managers Cube Controls** (medido no IL em 2026-08-20, com o
`ildump.py` corrigido — todos sobre `CubeControlsLedsDriverV2`):

| manager | VID:PID | usage | no `CATALOGO` |
|---|---|:---:|---|
| `CubeControlsFPROLedsManager` | `c872:2007` | 4 | ✅ |
| `CubeControlsCSX3LedsManager` | `c872:2008` | 4 | ✅ (acrescentado em 2026-08-20) |
| `CubeControlsGTPro2LedsManager` | `c872:200a` | 4 | ✅ |
| `CubeControlsAC190LedsManager` | `c872:200b` | 4 | ✅ **validado** |
| `CubeControlsAMGLedsManager` | `c872:200c` | **8** | ✅ |
| `CubeControlsGTX2LedsManager` | `c872:200d` | 4 | ✅ (acrescentado em 2026-08-20) |
| `CubeControlsAstraLedsManager` | `c872:2010` | 4 | ✅ |
| `CubeControlsPhoenixLedsManager` | `c872:?` | 9 | ❌ — o PID vem de `get_Pid()`, **não é constante no IL** |

⚠️ O Phoenix é o único que não dá para ler estaticamente: o manager chama
`GetDevice(Mapper, get_Pid(), 9, 0xC872, 21)`, com o PID vindo de uma propriedade. Para
cadastrá-lo é preciso `lsusb` com o hardware na mão. A regra udev `20??` provavelmente já o
cobre; o `EnableHidraw` não.

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

- Código e protocolo: [wine-libusb-bridge](https://github.com/juliscreudo/wine-libusb-bridge)
  (`shim.c`, `helper.c`, `proto.h`).
- Medido: `open` ok, `claim_interface(0)` ok, `bulk ep=0x02 len=819840 actual=819840`
  (854×480×2 = frame cheio em RGB565), `USB Path 5:2-2-4-2-4` resolvido **pela libusb real**.
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
| Pokornyi FGT | `0483:cb15` | não | `PokornyiFGTManager` (HID) | ✅ **conecta** — plugar e reabrir bastou (2026-08-19) |
| Pokornyi RALLY | `0483:cb12` | não | `PokornyiRallyManager` (HID) | ✅ **conecta** — plugar e reabrir bastou, zero passo novo (2026-08-19) |
| **Cube Controls AMG** (projeto AC190) | `c872:200b` | não | `CubeControlsAC190LedsManager` (HID) | ✅ **conecta** — receita 1 pura, sem usagePage errado (2026-08-19) |
| Cube Controls AMG variante `200c` | `c872:200c` | não | `CubeControlsAMGLedsManager` (HID) | não testado — receita 1, mesmo driver |
| Pokornyi HYP-R | `0483:cb10` | **sim** | composite: LEDs (HID) + tela | ✅ **LEDs e tela conectam** (2026-08-18) |
| Pokornyi F499 | `0483:cb14` | **sim** | composite: LEDs (HID) + tela | não testado |
| Pokornyi GTB Pro | `0483:cb11` | **sim** | composite: LEDs (HID) + tela | ✅ **LEDs e tela conectam** (2026-08-19) |
| Pokornyi PDU7 | `0483:cb02` | **sim** | composite: LEDs (HID) + tela | não testado |

⚠️ Outra unidade do mesmo modelo pode diferir — confirme com `lsusb` ao plugar.

⚠️ **Antes de assumir que os outros volantes com tela terão o mesmo problema da PDU5:**
o `usagePage 0xFF` é **por manager**, não por marca. A PDU5 falha porque o descriptor dela é
uma collection Joystick **vazia** (nenhum botão, nenhum eixo — é um dash, não um controle).
Um HYP-R ou F499, que têm botões de verdade, provavelmente têm descriptor como o dos MCP —
**meça com `hidenum` e com `ildump.py` no manager do modelo antes de concluir**.

## GTB Pro e o atalho de menu do Wine — 2026-08-19

LEDs do GTB Pro (`0483:cb11`) conectaram na hora de plugar, mesmo padrão do FGT/RALLY —
quarta confirmação. **A tela não conectou**, mas por um motivo já catalogado e alheio ao
GTB Pro: o usuário abriu o SimHub pelo item de menu do CachyOS, que é o atalho que o
`winemenubuilder` do Wine gera sozinho em `wine/Programs/SimHub/SimHub.desktop` — ele chama
`lsu-launch-wrapper` direto, **sem** subir o helper da ponte libusb primeiro. Sem o helper de
pé, a `libusb-1.0.dll` da ponte devolve erro na primeira chamada e a tela nunca aparece —
comportamento já documentado (seção "Telas VoCore"), não um caso novo.

⚠️ **Por que não dá para editar aquele `.desktop` direto**: o Wine o recria sempre que o
prefixo reindexa o Start Menu (reinstall, update, às vezes só abrir o `winecfg`). É o mesmo
problema que o projeto irmão `conspit-linux-configurator` já tinha resolvido para o
ConspitLink — a correção que fica é um atalho **fora** da árvore que o Wine gerencia.

Adicionado `simhub-devices install shortcut`: lê o `Icon=` do atalho do Wine (evita precisar
extrair o ícone de novo), e escreve
`~/.local/share/applications/simhub-devices-linux-run-simhub.desktop` com `Exec=run-simhub`.
Os dois atalhos convivem com o mesmo `Name=SimHub` — o do Wine continua existindo e
reaparecendo, só que agora há um alternativo correto ao lado. Não tentei suprimir o do Wine
(precisaria de um `Hidden=true` casando o Desktop ID exato dele,
`wine-Programs-SimHub-SimHub.desktop`, e voltaria a cada regeneração de qualquer forma).

**Confirmado**: reaberto pelo atalho novo (`install shortcut`), a tela do GTB Pro conectou
junto com os LEDs. Fecha o ciclo: o bloqueio nunca foi do device, foi só o caminho que abria
o SimHub sem subir o helper primeiro.

## Pokornyi RALLY — a confirmação mais barata das três

Validado em 2026-08-19, no mesmo dia da AMG, e mais rápido de fechar: **nenhum passo
novo foi necessário**, nem sequer para diagnosticar. `0483:cb12` já estava no `CATALOGO`
desde o início (junto com todos os outros PIDs Pokornyi do catálogo), e `install registry
--apply` escreve **todo o `CATALOGO` de uma vez**, não device a device — então o RALLY já
tinha entrada no registro desde a primeira vez que o comando rodou, muito antes de ele ser
plugado. ⚠️ **Desde 2026-08-20 a lista gravada é a UNIÃO do `CATALOGO` com o que já estava
no prefixo**, e não mais uma substituição: o valor é compartilhado, e sobrescrevê-lo apagava
em silêncio as entradas `3514:*` que o projeto irmão grava para os pedais Conspit. A
cobertura automática por faixa de PID continua igual; o que mudou é não estragar o vizinho. A regra `udev/70-pokornyi.rules` (`cb??`)
também já cobria. Bastou plugar e reabrir o SimHub.

É a terceira confirmação de que a receita generaliza (depois do FGT e da AMG), e a mais
informativa sobre **como** ela generaliza: a cobertura não é "por device testado", é "por
faixa de PID cadastrada" — um device pode funcionar antes mesmo de alguém pensar nele.

## Cube Controls AMG — validada em 2026-08-19, e a lacuna era simples

O usuário plugou a **Cube Controls AMG** e a aba Devices não conectou. A `lsusb` mostrou
`c872:200b`, que no catálogo do SimHub é servido pelo `CubeControlsAC190LedsManager` — e não
pelo `CubeControlsAMGLedsManager`, que aponta para `c872:200c`.

⚠️ **Isso NÃO significa que o volante "não é uma AMG".** Foi essa a leitura inicial, e ela
está errada: **AC190 é o nome do projeto do volante que a Cube Controls vende como AMG**. O
`200c`, cujo manager leva o nome AMG no catálogo, é provavelmente uma variante nova ainda não
lançada. Por isso a nomenclatura deste repo é **"Cube Controls AMG"** em todo lugar, com o PID
desempatando quando precisar (ver a tabela na receita 1). O device confirmado com hardware é o
`200b`; o `200c` segue não testado.

⚠️ **Por que ficou preso em `Searching device...` sem log nenhum: o device era novo neste
projeto, e faltavam exatamente os dois passos da receita 1** — não é o muro da PDU5.

1. **Sem regra udev.** `/dev/hidraw24` (o nó da AMG) saía `crw------- root root`. Nenhuma
   regra deste repo cobria `c872:20??`: a `70-vocore.rules` casa só o PID `1004` (subsystem
   `usb`, não `hidraw`), e não havia regra nenhuma para os volantes Cube Controls. Criado
   `udev/70-cubecontrols.rules`, casando `idProduct=="20??"` — cobre toda a faixa conhecida
   (F-PRO `2007`, GT-PRO V2 `200A`, AMG `200B`, AMG-`200C`, Astra `2010`) sem tocar no
   `1004` da tela, que não bate no padrão.
2. **Sem entrada no `EnableHidraw`.** O `CATALOGO` do `tools/simhub-devices` só tinha
   `c872:200c` cadastrado; nada gerava a linha `c872:200b` (a AMG real) na lista. Acrescentados os
   cinco PIDs da faixa Cube Controls ao `CATALOGO`.

**Medido o report descriptor da AMG** (66 bytes, via
`/sys/bus/usb/devices/1-3:1.0/*/report_descriptor` — leitura raiz não exige udev nem Wine):

```
05 01 09 04 a1 01                 Generic Desktop / Joystick   <- UMA collection so'
  85 01 09 01 a1 00 ... c0        Report ID 1: eixos Z/Rx (Pointer, physical)
  05 09 19 01 29 40 ... 81 02     Button 1..64
  85 03 06 00 ff 09 01 ... 91 02  Report ID 3: vendor 0xFF00, 19 bytes (OUT — os LEDs)
  85 02 06 01 ff 09 01 ... b1 02  Report ID 2: vendor 0xFF01, 19 bytes (FEATURE)
c0
```

**Mesmo padrão dos MCP Pokornyi, não o da PDU5**: o canal vendor não é uma collection
aninhada nem irmã — é só um **Report ID diferente dentro da mesma** TLC Joystick. Só existe
um PDO possível, e é ele que o Wine expõe. Medido no IL:
`CubeControlsAC190LedsManager.GetDriver()` chama `CubeControlsLedsDriverV2::GetDevice(pid=
0x200B, usage=4, vid=0xC872)` — **sem** `usagePage` separado no argumento (diferente da
assinatura do `PokornyiDriver`); a collection pedida é a única que existe. Não há o
descasamento que trava a PDU5, e portanto **nenhum patch de IL nem NGen entram aqui** — a
receita 1 pura resolve.

**Confirmado com hardware em 2026-08-19.** `install udev --apply` + `install registry --apply`
+ `wineserver -k`: a AMG passou a aparecer normalmente na aba Devices, sem precisar de
patch de IL nem de mexer no NGen — a receita 1 pura bastou.

⚠️ **Continua faltando testar a variante `c872:200c`.** Mesmo driver
(`CubeControlsLedsDriverV2`), manager irmão — a expectativa é que funcione igual, mas isso
é inferência do padrão, não medição; o descriptor dela pode diferir do `200b`.

## Ordem de trabalho sugerida

Passos 1–3 **feitos e validados** em 2026-08-16 (os três MCP). O que sobra:

1. ~~Comece por um MCP~~ ✅ — os três conectam, LEDs controláveis pelo SimHub.
2. ~~`lsusb` → confirmar VID/PID~~ ✅ — bateram todos.
3. ~~Aplicar a receita 1 e verificar com `hidenum`~~ ✅ — **e o passo decisivo foi o udev**,
   não o registro (ver receita 1).
4. ~~**FGT**~~ ✅ **2026-08-19 — e é o resultado mais informativo até agora.** O usuário
   plugou o volante e reabriu o SimHub: funcionou, **sem nenhum passo específico**. Não foi
   sorte, e o porquê é verificável antes de plugar o próximo: (a) a regra udev casa `cb??`,
   então o PID novo já tinha ACL; (b) o `EnableHidraw` é montado a partir do `CATALOGO` do
   instalador, que já listava `cb15`; (c) `PokornyiFGTManager` pede `usagePage 1 / usage 4`
   (medido no IL), a collection que o Wine expõe. **Essas três checagens são o teste a
   aplicar em qualquer device novo** — quando a (c) falha, o resultado é a PDU5.
   ✅ A **Cube Controls AMG** (`c872:200b`) fechou esse teste em 2026-08-19 — outro
   fabricante, outro VID, e mesmo assim receita 1 pura. Falta só a variante `c872:200c`
   (`CubeControlsAMGLedsManager`), que é a mesma receita com outro PID.
5. ~~Um volante com tela~~ HYP-R ✅ e GTB Pro ✅ confirmam o padrão: `usagePage 1/4`, LEDs
   conectam sem patch. **Falta o F499** — antes de plugar, `ildump.py` no
   `PokornyiF499Manager` para o mesmo check; se vier `0xFF/1`, é o muro da PDU5.
6. **PDU5 (LEDs)**: sem correção por registro/udev. Depende de o Wine promover a collection
   vendor aninhada a PDO próprio — candidato a issue/patch no Wine, com um caso de teste
   pequeno e claro (descriptor de 35 bytes, na receita 1).
7. ~~**Telas VoCore**~~ ✅ **RESOLVIDO em 2026-08-18** pela ponte libusb
   (`~/apps/wine-libusb-bridge`), não pelo DRM nativo. ~~Confirmar o touch~~ ✅. ~~Subir o
   helper antes do SimHub~~ ✅ resolvido pelo launcher `run-simhub` (não unit systemd — ver
   "Projetos irmãos"), e desde 2026-08-19 também por `simhub-devices install shortcut`, que
   cria um atalho de menu fora da árvore do Wine apontando pro `run-simhub` — o atalho que o
   Wine gera sozinho (`winemenubuilder`) abre direto, sem a ponte, e some/reaparece a cada
   reinstall/update. Falta só reinstalar a DLL da ponte após cada update do SimHub.

## Code review de 2026-08-20 — o que mudou de comportamento

Revisão completa dos dois repos. A maior parte foi limpeza, mas **estes itens mudam
comportamento** e quem for mexer aqui precisa saber, porque alguns "consertam" de volta
sem querer:

| o que era | o que é agora | por quê |
|---|---|---|
| `REPO = dirname(dirname(abspath(__file__)))` | `realpath` | o comando é usado pelo PATH, via symlink em `~/.local/bin`. Com `abspath`, `REPO` virava `~/.local` e **`install udev` morria com "nenhuma regra em ~/.local/udev"** — o passo 1 do README não funcionava do jeito documentado de instalar |
| `--apply` no meio virava dry-run silencioso | funciona nas três posições | `argparse` copia o namespace do subparser sobre o do pai; sem `default=argparse.SUPPRESS`, o parser de terceiro nível reaplicava `apply2=False`. `install --apply bridge` não fazia nada e dizia DRY-RUN |
| `EnableHidraw` era **substituído** | é a **união** com o que já existe | valor compartilhado do prefixo; ver a seção do RALLY |
| `regedit`/patcher com returncode descartado | falha aborta com mensagem | falha silenciosa é o pecado que este projeto existe para não repetir |
| `hidenum` imprimia o instance ID inteiro | imprime `<INSTANCIA>`; `--serial` mostra | o instance ID carrega o **serial do hardware**, e os READMEs pedem essa saída para colar em issue |
| dry-run do `install serial` ecoava o serial USB | ecoa `<SERIAL>` | idem — o registro recebe o valor real, quem é mascarado é o eco na tela |
| `run-simhub` dormia 5 s e já checava se o SimHub morreu | espera o processo **aparecer** (até 120 s) | em prefixo frio o app demorava mais que isso, o `pgrep` dava vazio na primeira volta e o trap **derrubava a ponte** — a tela não conectava, de forma intermitente |
| `run-simhub` fixava `~/apps/wine-libusb-bridge` e a porta 47100 | mesma precedência do instalador (`$SIMHUB_PONTE` → `vendor/` → local) e `$LIBUSB_BRIDGE_PORT` | o instalador copiava a DLL do `vendor/` e o launcher subia o helper da cópia local: duas metades da ponte de versões diferentes |
| `pdu5-leds-patch.py` procurava numa janela de 512 bytes | usa o **CodeSize do cabeçalho** do método, e recusa padrão ambíguo | a janela passava do fim de um método curto e podia casar no método seguinte — patch silencioso e no lugar errado. Escrita agora é atômica (`os.replace`) |
| `tools/mmf-vocore-relay.cs` + `mpro-dash-daemon.py` em `tools/` | movidos para `attic/` com README próprio | caminho `mpro_drm`+MMF, superado pela ponte em 2026-08-18; não eram citados em lugar nenhum e ninguém saberia que estavam mortos |

⚠️ **O decodificador de IL do `ildump.py` estava errado** — `blt.un.s` (0x37) classificado como
desvio longo e `stloc.2/3` (0x0C/0x0D) tratados como se tivessem operando; e `leave`/`leave.s`
não eram tratados. Medido na `SimHub.Plugins.dll`: **51,6% dos 35.295 métodos** decodificavam
diferente, e em **777 deles apareciam constantes que não existem** no código. A tabela de
operandos agora é completa e vive em `tools/ilcommon.py` (uma cópia, não três).

✅ **As conclusões deste projeto NÃO foram afetadas** — medido por eliminação: nenhum
`GetDriver` de manager Pokornyi/CubeControls/StandardProtocol está entre os 777. O
`PokornyiPEPDU5Manager::GetDriver` continua lendo `0xCB01`, usagePage `1`, usage `4`,
VID `0x483`, exatamente como registrado aqui. Mas a ferramenta não era confiável em geral.

### Na ponte (`wine-libusb-bridge`)

- **Token agora carrega tipo, e o tipo é conferido.** Um `FN_CLOSE` com token de device
  executava `libusb_close()` sobre um `libusb_device*`. Não era hipotético: o watchdog libera
  a tabela após 5 s sem conexão, e uma thread .NET que sobreviva a isso reconecta com tokens
  da geração anterior. Por isso, também: **token nunca mais é reciclado**.
- **Todo comprimento vindo do cliente tem teto** (`BRIDGE_MAX_PAYLOAD`). Um request de 40
  bytes pedindo 2 GB derrubava o helper — e com ele a tela.
- **`control_transfer` OUT só envia o que chegou.** Enviava `wLength` bytes mesmo com menos
  dados recebidos, colocando no barramento o resto do buffer reciclado da thread.
- **O helper confere o UID do outro lado** (via `/proc/net/tcp`; TCP não tem `SO_PEERCRED`).
  Loopback é compartilhado por todos os usuários da máquina. `--allow-any-uid` desliga.
- **Transferência OUT não é mais copiada** para o buffer de saída antes de ir para a libusb:
  eram ~819 KB por quadro, ~49 MB/s de cópia inútil a 60 fps.
- **`make check-abi`** compara os símbolos decorados do binário (`_libusb_init@4` — o `@N`
  *é* o tamanho de pilha stdcall) contra `abi.expected`. Errar a convenção de chamada é o
  único erro que não dá mensagem: o processo morre sem explicação.
- ⚠️ **O formato de fio é congelado de propósito.** DLL e helper de versões diferentes
  continuam conversando — verificado: os 32 exports e as decorações são idênticos antes e
  depois da revisão.

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
