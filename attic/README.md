# attic — o caminho que foi superado

O que está aqui **funcionava**, mas deixou de ser o caminho recomendado em
2026-08-18. Fica guardado como registro e como *fallback*, não como parte da
instalação. Nada em `tools/simhub-devices` chama estes arquivos.

## Tela VoCore via `mpro_drm` + MMF

| arquivo | papel |
|---|---|
| `mmf-vocore-relay.cs` | roda **dentro** do prefixo Wine; lê o device "Special : Generic MMF rendering V2" do SimHub e copia cada frame para `/dev/shm/simhub-mpro` |
| `mpro-dash-daemon.py` | roda no Linux; pega os frames do `/dev/shm` e escreve no framebuffer que o driver de kernel `mpro_drm` expõe |

**Por que foi superado:** a [ponte libusb](https://github.com/juliscreudo/wine-libusb-bridge)
faz a tela funcionar *pela própria aba Devices do SimHub*, sem driver de kernel,
sem relay, sem `/dev/shm`, e com **touch** de brinde. Ver o passo 4 do
[README](../README.md).

**Quando isto ainda serve:** para usar a tela **fora** do SimHub. O `mpro_drm`
entrega um `/dev/fbN` de verdade, que qualquer renderizador nativo
(SimMonitor, monocoque) consegue usar.

⚠️ **Os dois caminhos não convivem.** Com o `mpro_drm` carregado, o kernel
reivindica a interface USB e a ponte deixa de enxergar o device. `rmmod mpro`
desfaz.

⚠️ **Os offsets do relay são de RUNTIME e valem para o SimHub 9.11.22.** Não são
offsets de marshaling: o SimHub acessa o MMF por ponteiro cru (`bool` = 1 byte, e
`Marshal.OffsetOf` dá valores errados). Um update do SimHub pode movê-los, e não
há nada no repo que os re-meça — foi uma sonda descartável, feita com
`DynamicMethod`+`ldflda` contra a DLL da época. Se for reaproveitar isto, meça de
novo antes de confiar nos números.
