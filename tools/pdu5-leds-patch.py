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

⚠️ ESTE PATCH SOZINHO NAO BASTA — O NGEN ENGOLE ELE.

O prefixo tem imagem nativa pre-compilada de SimHub.Plugins em
    drive_c/windows/assembly/NativeImages_v4.0.30319_32/SimHub.Plugins
e o SimHub roda 32-bit, entao ele executa a imagem nativa e IGNORA o IL patcheado.
Sondas compiladas com /platform:x64 JIT-am o IL do disco e "provam" que o patch
funciona — enquanto o app nao muda nada. Custou um dia inteiro de diagnostico.

Depois de aplicar o patch, remova as imagens nativas:

    NI=~/apps/linux-simracing-utils/pfx/drive_c/windows/assembly/NativeImages_v4.0.30319_32
    mv "$NI"/SimHub.Plug* /caminho/de/backup/

Ambos voltam a cada update do SimHub.
"""
import argparse
import os
import shutil
import sys

PADRAO_ORIG = bytes([0x20, 0xFF, 0x00, 0x00, 0x00, 0x17])   # ldc.i4 0xFF ; ldc.i4.1
PADRAO_NOVO = bytes([0x20, 0x01, 0x00, 0x00, 0x00, 0x1A])   # ldc.i4 1    ; ldc.i4.4

# managers que sofrem do mesmo problema (usagePage 0xFF): PDU5, PDU7, LED Brows
ALVOS = ("PokornyiPEPDU5Manager", "PokornyiPEPDU7Manager", "PokornyiLedBrowsManager")

PADRAO_DLL = os.path.expanduser(
    "~/apps/linux-simracing-utils/pfx/drive_c/Program Files (x86)/SimHub/SimHub.Plugins.dll")


def corpos_dos_alvos(caminho):
    """Offsets de arquivo dos corpos de GetDriver dos managers alvo."""
    import dnfile
    dn = dnfile.dnPE(caminho)
    if dn.net.Flags.CLR_STRONGNAMESIGNED:
        sys.exit("ERRO: assembly e' strong-named; patch invalidaria a assinatura.")

    secoes = dn.sections

    def rva2off(rva):
        for s in secoes:
            if s.VirtualAddress <= rva < s.VirtualAddress + max(s.Misc_VirtualSize, s.SizeOfRawData):
                return rva - s.VirtualAddress + s.PointerToRawData
        return None

    achados = []
    tdefs = dn.net.mdtables.TypeDef
    for i, td in enumerate(tdefs.rows):
        nome = str(td.TypeName)
        if nome not in ALVOS:
            continue
        for m in td.MethodList:
            mrow = m.row
            if mrow is None or str(mrow.Name) != "GetDriver" or not mrow.Rva:
                continue
            off = rva2off(mrow.Rva)
            if off is None:
                continue
            achados.append((nome, off))
    return achados


def janela(dados, off, tam=512):
    """O corpo do metodo comeca no cabecalho; 512 bytes cobrem estes GetDriver."""
    return off, dados[off:off + tam]


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true")
    g.add_argument("--apply", action="store_true")
    g.add_argument("--revert", action="store_true")
    ap.add_argument("dll", nargs="?", default=PADRAO_DLL)
    args = ap.parse_args()

    dll = args.dll
    bak = dll + ".bak-pdu5"

    if args.revert:
        if not os.path.exists(bak):
            sys.exit("sem backup em " + bak)
        shutil.copy2(bak, dll)
        print("revertido a partir de", bak)
        return

    if not os.path.exists(dll):
        sys.exit("nao encontrei " + dll)
    dados = bytearray(open(dll, "rb").read())

    alvos = corpos_dos_alvos(dll)
    if not alvos:
        sys.exit("nenhum manager alvo encontrado (SimHub mudou de versao?)")

    pendentes = []
    for nome, off in alvos:
        base, buf = janela(dados, off)
        i_orig = buf.find(PADRAO_ORIG)
        i_novo = buf.find(PADRAO_NOVO)
        if i_orig >= 0:
            print(f"  {nome:26s} offset 0x{base + i_orig:06X}  usagePage 0xFF/1  -> PRECISA DE PATCH")
            pendentes.append(base + i_orig)
        elif i_novo >= 0:
            print(f"  {nome:26s} offset 0x{base + i_novo:06X}  usagePage 1/4     -> ja corrigido")
        else:
            print(f"  {nome:26s} padrao nao encontrado -- NAO mexer")

    if args.check:
        return
    if not pendentes:
        print("nada a fazer")
        return

    if not os.path.exists(bak):
        shutil.copy2(dll, bak)
        print("backup:", bak)
    for off in pendentes:
        dados[off:off + len(PADRAO_ORIG)] = PADRAO_NOVO
    open(dll, "wb").write(bytes(dados))
    print(f"aplicado em {len(pendentes)} manager(s). Reinicie o SimHub.")


if __name__ == "__main__":
    main()
