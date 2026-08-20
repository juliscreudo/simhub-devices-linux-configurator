# SimHub Devices no Linux — fazer a aba Devices reconhecer volantes e caixas de botões

Repo deste projeto: `~/apps/simhub-devices-linux-configurator/` (ex-`simhub-devices-linux`,
renomeado em 2026-08-20 para seguir o padrão do irmão `conspit-linux-configurator`).

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

## Checklist — o que já custou caro esquecer

Cada item abaixo já causou horas ou dias de diagnóstico errado; o detalhe e a evidência estão
na seção que ele referencia.

- **Registro sempre em `Services\winebus`, nunca em `\Parameters`** — o driver não lê a
  segunda chave (custou 3 dias no projeto irmão; Receitas 1 e 2).
- **`EnableHidraw` sozinho quase não faz nada** — o passo que destrava um HID novo é a regra
  **udev** (Receita 1).
- **Depois de todo update do SimHub**: reinstalar `libusb-1.0.dll` da ponte **e** remover de
  novo `SimHub.Plug*` de `NativeImages_v4.0.30319_32/` — os dois voltam sozinhos, e sem o
  segundo, patch de IL vira no-op (armadilha do NGen).
- **`tools/hidenum.exe` é o deste repo, não o do projeto Conspit** — aquele tem VID `0x3514`
  cravado e devolve lista vazia pra Pokornyi/Cube Controls, parecendo que o device não existe.
- **`wineserver -k` depois de mexer em registro, porta serial ou `EnableHidraw`** — são
  valores voláteis/cacheados; a mudança só aparece após reiniciar.
- **Enumeração HID tem corrida**: meça na segunda passada do `hidenum`, ~3 s depois do
  `wineserver -k`.
- **Sondas e patches de IL: leitura por padrão, nunca escrever na firmware.** Registro do
  prefixo é reversível; firmware não.
- **Base Conspit Ares é 20 Nm** — nunca mande `=`, `sys.0.save`, `sys.0.format` ou `odrv.*`
  numa porta que possa ser a base (ver Segurança).
- **Entradas PnP obsoletas travam device em silêncio** — apague `Enum\HID\VID_xxxx&PID_xxxx*`
  remanescente e deixe o Wine recriar.
- **`ConspitManager.GetDriver()` é compartilhado** entre haptics e LEDs — um device parcial
  derruba os dois caminhos, e o sintoma aparece longe da causa.
- Erros `FindGamePath`/`CompatibilityStoreHelper` no log **não são** de device — ignore ao
  diagnosticar.
- `strings` sozinho não acha nomes em app .NET/Qt — use `strings -el` (UTF-16).

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
simhub-devices-linux-configurator  configura os devices na aba Devices        ← aqui
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

**Dois subagentes em `.claude/agents/` empacotam os fluxos recorrentes** — ambos read-only, com
as armadilhas de método já embutidas:

| agente | quando |
|---|---|
| `device-triage` | device não conecta na aba Devices — roda `doctor`, lê o log, aplica as 3 checagens e devolve a classe de falha |
| `il-recon` | medir constante/chamada no IL ofuscado (VID/PID, `usagePage`/`usage`, quem chama o quê) |

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
- ⚠️ **O atalho de menu que o `winemenubuilder` do Wine gera sozinho
  (`wine/Programs/SimHub/SimHub.desktop`) chama o `lsu-launch-wrapper` direto, sem subir o
  helper antes** — abrir por ele faz a tela falhar mesmo com tudo certo, porque a DLL da ponte
  devolve erro na primeira chamada sem o helper de pé. Não dá pra editar/esconder aquele
  `.desktop`: o Wine o recria a cada reinstall/update, e a mesma armadilha já tinha sido
  resolvida para o ConspitLink no projeto irmão. `simhub-devices install shortcut` lê o
  `Icon=` do atalho do Wine e escreve um atalho próprio em `~/.local/share/applications/` com
  `Exec=run-simhub`; os dois convivem com o mesmo `Name=SimHub`. Confirmado com o GTB Pro:
  reaberto pelo atalho novo, a tela conectou junto com os LEDs.
- ⚠️ O helper faz **fork por conexão** e limpa tudo quando o cliente cai. Sem isso: o SimHub
  mantém mais de um `SubProcess.X86.exe` vivo e (a) o velho segurava o único slot do helper,
  derrubando o novo com `TimeoutException` no `ConnectToScreen`, e (b) a interface ficava
  reivindicada, dando `LIBUSB_ERROR_BUSY` na instância seguinte.
- ✅ **O touch da tela funciona pela mesma ponte** (`intr ep=0x81`, reports de 14 bytes):
  o SimHub recebe os toques direto, sem evdev e sem disputa com o KDE — o kernel sequer vê
  a tela como input, já que nenhum driver a reivindica.
- ⚠️ O que **não** foi resolvido por isto: os **LEDs** da PDU5 (`usagePage 0xFF`).

### Por que o caminho nativo do Wine não fecha — e por que não vale reabrir

Arqueologia de 2026-08-16/18, resumida. Vale como registro de **"não tente de novo"**; a ponte
tornou os dois bloqueios abaixo irrelevantes, contornando-os em vez de resolvê-los.

O caminho do SimHub é `SimHub.BitmapDisplay.Vocore.dll` → `SimHub.LibUsbNative.dll` →
`libusb-1.0.dll`: **libusb puro**, a tela escrita como device USB bruto por endpoints bulk
(interface única `ff/ff/ff`, `ep_02` OUT + `ep_81` IN, nenhum driver de kernel ocupando). Não é
driver de display — essa hipótese foi descartada.

⚠️ **Os dois becos sem saída, ambos medidos — não reabra nenhum:**

1. **Nenhum driver ligado ao nó USB.** O nó nasce sem `Service` e sem interface registrada, e a
   libusb classifica device *lendo qual driver está ligado*. No Windows o instalador do SimHub
   liga o **WinUSB** (o que o Zadig faz); **não tente reproduzir isso no prefixo** — instalaria
   um driver de kernel do Windows que o Wine não executa. E não adiantaria: **a `winusb.dll` do
   Wine é stub** (medido: `"(%p) - stub"` nas strings). Não há hoje nada no Wine que faça o
   backend Windows da libusb funcionar.
2. **Wine não expõe controlador USB**, logo não há árvore para subir: `PortSignature` e
   `UsbPath` lançam `NullReferenceException` para **100% dos devices** (0 de 125). Como todas as
   telas VoCore são `c872:1004` — indistinguíveis —, o SimHub as casa com o volante subindo até
   o hub pai, e sem árvore isso é impossível **pelo PnP**. A ponte resolve porque o SimHub pede
   essa topologia **à própria libusb** (`libusb_get_parent`, `get_port_numbers`,
   `get_bus_number`), e a árvore real do Linux a tem — enumeração e identificação de uma vez.

✅ **O que continua vivo desta seção:** a permissão do nó USB. `/dev/bus/usb/BBB/DDD` nasce sem
`rw` para o usuário e a libusb precisa dele para `libusb_claim_interface`; sem isso a tela é
descartada em silêncio. É o que `udev/70-vocore.rules` corrige (PID `1004` exato — `c872` é
também o VID da Cube Controls).

⚠️ Detalhe de construção da ponte (as 32 funções, convenções `stdcall`, marshaling, ABI) mora no
repo dela, com `make check-abi` guardando o contrato. Não é replicado aqui.

### Fallback fora do SimHub: `mpro_drm` — ⚠️ SUPERADO, e não convive com a ponte

Driver DRM da VoCore (Vonger), em `~/apps/mpro_drm` (código de terceiro, fora deste repo) com
`linux-7.1-api.patch` para a API DRM atual. ⚠️ Kernel CachyOS é clang/LTO: `make LLVM=1`.

Continua sendo a única forma de usar a tela **fora** do SimHub — dentro dele, a ponte substituiu
esse caminho. ⚠️ **Os dois não convivem**: com o módulo carregado o kernel reivindica a interface
e a ponte para de enxergar o device. `rmmod mpro` desfaz.

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

## Confirmações de campo — a receita 1 generaliza

FGT, RALLY, GTB Pro (LEDs) e Cube Controls AMG foram plugados e testados separadamente em
2026-08-19. Juntos mostram que a receita 1 cobre device novo **sem passo específico** quando
três checagens batem — o teste a aplicar antes de plugar qualquer device ainda não testado:

1. a regra udev cobre o VID:PID (`70-pokornyi.rules` casa `cb??`; `70-cubecontrols.rules`
   casa `c872:20??`);
2. o PID está no `CATALOGO` do instalador, que gera o `EnableHidraw` — `install registry
   --apply` escreve o catálogo **inteiro** de uma vez, não device a device, então um PID pode
   já estar coberto antes mesmo de alguém pensar no device (caso do RALLY, `cb12`, coberto
   desde a primeira vez que o comando rodou);
3. `usagePage`/`usage` do manager batem com a collection que o Wine expõe (`ildump.py` no
   manager + `hidenum` no hardware) — quando **não** batem, o resultado é o muro da PDU5, sem
   uma linha de log.

| device | resultado | observação |
|---|---|---|
| FGT / RALLY | ✅ zero passo novo | só plugar e reabrir — as três checagens já estavam cobertas pelo catálogo |
| GTB Pro (LEDs) | ✅ zero passo novo | mesmo padrão; a tela só conectou depois de reabrir pelo atalho novo (ver "Telas VoCore") |
| Cube Controls AMG (`c872:200b`) | ✅ corrigido | faltavam as checagens 1 e 2: nenhuma regra udev cobria `c872:20??` (criada `70-cubecontrols.rules`) e o `CATALOGO` só tinha `200c` cadastrado (acrescentados `2007/2008/200a/200b/200c/200d/2010`) |

⚠️ **O descriptor da AMG (66 bytes, medido em `/sys/bus/usb/devices/*/report_descriptor` —
leitura raiz, não exige udev nem Wine) confirma o padrão dos MCP Pokornyi, não o da PDU5**: o
canal vendor é só um Report ID diferente (`0xFF00` OUT / `0xFF01` FEATURE) dentro da mesma TLC
Joystick, nunca uma collection separada. Só existe um PDO possível, e o IL de
`CubeControlsAC190LedsManager.GetDriver()` nem passa `usagePage` separado (diferente da
assinatura do `PokornyiDriver`) — não há descasamento possível, então nenhum patch de IL nem
NGen entram aqui. Outro fabricante, outro VID, mesma conclusão da receita 1 pura.

⚠️ Falta testar `c872:200c` (`CubeControlsAMGLedsManager`) — mesmo driver, manager irmão, mas
o descriptor dela pode diferir do `200b` (inferência de padrão, não medição).

## O que falta

- **PDU5 (LEDs, registro):** sem correção por registro/udev — depende de o Wine promover a
  collection vendor aninhada a PDO próprio; candidato a issue/patch no Wine (descriptor de 35
  bytes, receita 1).
- **F499 / PDU7:** falta plugar. Antes, `ildump.py` no manager (`PokornyiF499Manager` /
  `PokornyiPEPDU7Manager`) — se vier `usagePage 0xFF`, é o muro da PDU5; se vier `1/4`, deve
  conectar direto como o HYP-R/GTB Pro.
- **Cube Controls `200c`:** falta plugar; mesma receita do `200b`, descriptor não medido.
- **Cube Controls Phoenix:** PID não é constante no IL (`get_Pid()`) — precisa `lsusb` com o
  hardware na mão antes de cadastrar no `CATALOGO`.

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

A revisão da ponte (tipagem de token, teto de payload, `control_transfer` OUT, checagem de UID,
`make check-abi`, formato de fio congelado) está documentada **no README do repo dela** — aqui é
análise, lá é produto. Não replicado para não sair de sincronia.

## Segurança

⚠️ **A base Conspit Ares é de 20 Nm.** O SimHub varre portas seriais procurando Arduinos, e a
base aparece mapeada em mais de uma COM. Ela ignora texto que não seja comando OpenFFBoard,
então o risco é baixo — mas **confira se o auto-detect de Arduino do SimHub está restrito às
portas certas**, e nunca mande `=`, `sys.0.save`, `sys.0.format` ou calibração `odrv.*` numa
porta que possa ser a base.

Sondas de diagnóstico devem ser **somente leitura** por padrão. Escrever no registro do
prefixo é reversível (backup: `pfx/system.reg.bak-*`); escrever na firmware não é.

## Escopo

- Foco sim racing, Linux, SimHub sob Wine. Um único setup: o do autor.
- Nada aqui porta ou redistribui software de terceiros. O SimHub é da Wotever, o
  linux-simracing-utils e o Winecarte são da srounce. Este repo é análise e configuração.
- Projeto pessoal, sem garantia nem suporte.
