#!/usr/bin/env python3
"""Corrige o usagePage/usage que impede os LEDs da PDU5/PDU7/LED Brows no Wine.

O problema (medido em 2026-08-18, ver CLAUDE.md, secao "O usagePage/usage e' POR MANAGER"):
  PokornyiPEPDU5Manager.GetDriver() pede a collection HID vendor
  (usagePage 0xFF, usage 1). O descriptor da PDU5 e' uma collection Joystick
  VAZIA com a vendor ANINHADA dentro -- e o Wine so' promove a PDO as collections
  IRMAS, entao o unico PDO que existe e' 0x0001/0x04. O filtro MatchUsage nunca
  casa e o device fica sem LEDs, em silencio.

  Nos MCP (que funcionam) o canal vendor -- report 0x5A -- e' alcancado pelo
  MESMO handle do joystick. Se o manager da PDU5 pedir 1/4 em vez de 0xFF/1,
  ele encontra o PDO que existe e o canal vendor vem junto.

A correcao sao dois opcodes de mesmo tamanho, no corpo do metodo:
    ldc.i4 0xFF  ->  ldc.i4 1     20 FF 00 00 00  ->  20 01 00 00 00
    ldc.i4.1     ->  ldc.i4.4     17              ->  1A

⚠️ Isto altera uma DLL do SimHub. Por isso este repo distribui O PATCHER, nunca a
   DLL corrigida. O patch se perde a cada atualizacao do SimHub -- rode de novo.
⚠️ A assembly nao e' strong-named (conferido pelo proprio script), entao a
   alteracao nao invalida assinatura nenhuma.

Uso:
    pdu5-leds-patch.py --check   [caminho/SimHub.Plugins.dll]
    pdu5-leds-patch.py --apply   [...]      (cria .bak-pdu5 antes)
    pdu5-leds-patch.py --revert  [...]

Saida de --check:  0 = nada pendente   1 = patch pendente   2 = erro

⚠️ ESTE PATCH SOZINHO NAO BASTA — O NGEN ENGOLE ELE.

O prefixo tem imagem nativa pre-compilada de SimHub.Plugins em
    drive_c/windows/assembly/NativeImages_v4.0.30319_32/SimHub.Plugins
e o SimHub roda 32-bit, entao ele executa a imagem nativa e IGNORA o IL patcheado.
Sondas compiladas com /platform:x64 JIT-am o IL do disco e "provam" que o patch
funciona — enquanto o app nao muda nada. Custou um dia inteiro de diagnostico.

`simhub-devices install pdu5-leds --apply` faz os dois passos de uma vez. A mao:

    NI=~/apps/linux-simracing-utils/pfx/drive_c/windows/assembly/NativeImages_v4.0.30319_32
    mv "$NI"/SimHub.Plug* /caminho/de/backup/

Ambos voltam a cada update do SimHub.
"""
import argparse
import os
import shutil
import sys

# realpath, nao abspath: estes scripts tambem podem ser chamados por symlink,
# e ai o abspath aponta para o diretorio do link, sem o ilcommon.py ao lado.
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import ilcommon

PADRAO_ORIG = bytes([0x20, 0xFF, 0x00, 0x00, 0x00, 0x17])   # ldc.i4 0xFF ; ldc.i4.1
PADRAO_NOVO = bytes([0x20, 0x01, 0x00, 0x00, 0x00, 0x1A])   # ldc.i4 1    ; ldc.i4.4

# managers que sofrem do mesmo problema (usagePage 0xFF): PDU5, PDU7, LED Brows
ALVOS = ("PokornyiPEPDU5Manager", "PokornyiPEPDU7Manager", "PokornyiLedBrowsManager")
METODO = "GetDriver"

PADRAO_DLL = os.path.expanduser(
    "~/apps/linux-simracing-utils/pfx/drive_c/Program Files (x86)/SimHub/SimHub.Plugins.dll")


def corpos_dos_alvos(caminho, dados):
    """[(tipo, inicio do IL, tamanho do IL)] dos GetDriver dos managers alvo.

    ⚠️ O tamanho vem do cabecalho do metodo, nunca de uma janela fixa. Uma janela
    de N bytes passa do fim do metodo curto e encontra o padrao no metodo
    SEGUINTE -- e o patch sai silencioso e no lugar errado.
    """
    dn, _ = ilcommon.abrir(caminho)
    if dn.net.Flags.CLR_STRONGNAMESIGNED:
        raise SystemExit("ERRO: assembly e' strong-named; patch invalidaria a assinatura.")
    return [(t, ini, tam) for t, m, ini, tam in ilcommon.metodos(dn, dados)
            if t in ALVOS and m == METODO]


def ocorrencias(buf, padrao):
    achados, i = [], buf.find(padrao)
    while i >= 0:
        achados.append(i)
        i = buf.find(padrao, i + 1)
    return achados


def escrever_atomico(caminho, dados):
    """⚠️ SimHub.Plugins.dll tem ~26 MB. Escrever por cima e' uma janela em que
    uma interrupcao deixa a DLL truncada; o os.replace troca o nome de uma vez."""
    tmp = caminho + ".tmp-pdu5"
    with open(tmp, "wb") as f:
        f.write(dados)
        f.flush()
        os.fsync(f.fileno())
    shutil.copystat(caminho, tmp)
    os.replace(tmp, caminho)


def main():
    ap = argparse.ArgumentParser(description="patch do usagePage dos managers PDU5/PDU7/LED Brows")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true", help="so' relata (0 = nada pendente, 1 = pendente)")
    g.add_argument("--apply", action="store_true")
    g.add_argument("--revert", action="store_true")
    ap.add_argument("dll", nargs="?", default=PADRAO_DLL)
    args = ap.parse_args()

    dll = args.dll
    bak = dll + ".bak-pdu5"

    if args.revert:
        if not os.path.exists(bak):
            raise SystemExit("sem backup em " + bak)
        shutil.copy2(bak, dll)
        print("revertido a partir de", bak)
        return 0

    if not os.path.exists(dll):
        raise SystemExit("nao encontrei " + dll)
    ilcommon.exigir_dnfile()
    with open(dll, "rb") as f:
        dados = bytearray(f.read())

    alvos = corpos_dos_alvos(dll, dados)
    if not alvos:
        raise SystemExit("nenhum manager alvo encontrado (SimHub mudou de versao?)")

    pendentes = []
    for nome, ini, tam in alvos:
        buf = bytes(dados[ini:ini + tam])
        orig, novo = ocorrencias(buf, PADRAO_ORIG), ocorrencias(buf, PADRAO_NOVO)
        if len(orig) > 1:
            # duas constantes iguais no mesmo corpo: qual delas e' o usagePage?
            print(f"  {nome:26s} {len(orig)} ocorrencias do padrao -- AMBIGUO, NAO mexer")
        elif orig:
            print(f"  {nome:26s} offset 0x{ini + orig[0]:06X}  usagePage 0xFF/1  -> PRECISA DE PATCH")
            pendentes.append(ini + orig[0])
        elif novo:
            print(f"  {nome:26s} offset 0x{ini + novo[0]:06X}  usagePage 1/4     -> ja corrigido")
        else:
            print(f"  {nome:26s} padrao nao encontrado -- NAO mexer")

    if args.check:
        return 1 if pendentes else 0
    if not pendentes:
        print("nada a fazer")
        return 0

    if not os.path.exists(bak):
        shutil.copy2(dll, bak)
        print("backup:", bak)
    for off in pendentes:
        dados[off:off + len(PADRAO_ORIG)] = PADRAO_NOVO
    escrever_atomico(dll, bytes(dados))
    print(f"aplicado em {len(pendentes)} manager(s). Reinicie o SimHub.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
