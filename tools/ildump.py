#!/usr/bin/env python3
"""Dump IL de metodos .NET filtrando por nome de tipo, sem decompilador.

Decodifica so' o que interessa aqui: ldstr (nomes/mensagens), ldc.i4* (PIDs e
constantes) e call/callvirt/newobj (para quem ele chama). O resto so' avanca o
tamanho certo -- que e' a parte que precisa estar certa (ver ilcommon.py).

   ildump.py <assembly.dll> <substring do tipo> [substring do metodo]
"""
import os
import sys

# realpath, nao abspath: estes scripts tambem podem ser chamados por symlink,
# e ai o abspath aponta para o diretorio do link, sem o ilcommon.py ao lado.
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import ilcommon


def decode(il, dn, dono):
    """(offset, mnemonico, argumento) das instrucoes que interessam."""
    i, out = 0, []
    while i < len(il):
        ini = i
        op = il[i]
        i += 1

        if op == ilcommon.PREFIXO2:
            if i >= len(il):
                break
            op2 = il[i]
            i += 1 + ilcommon.operando_fe(op2)
            continue

        if op == ilcommon.SWITCH:
            n = int.from_bytes(il[i:i + 4], "little")
            i += 4 + 4 * n
            continue

        tam = ilcommon.OPERANDO[op]
        if op == 0x72:                                  # ldstr
            tok = int.from_bytes(il[i:i + 4], "little")
            out.append((ini, "ldstr", repr(ilcommon.user_string(dn, tok))))
        elif op == 0x20:                                # ldc.i4
            v = int.from_bytes(il[i:i + 4], "little", signed=True)
            out.append((ini, "ldc.i4", f"{v} (0x{v & 0xFFFFFFFF:X})"))
        elif op == 0x1F:                                # ldc.i4.s
            v = int.from_bytes(il[i:i + 1], "little", signed=True)
            out.append((ini, "ldc.i4.s", f"{v} (0x{v & 0xFF:02X})"))
        elif 0x16 <= op <= 0x1E:                        # ldc.i4.0 .. ldc.i4.8
            out.append((ini, "ldc.i4", str(op - 0x16)))
        elif op in (0x28, 0x6F, 0x73):                  # call / callvirt / newobj
            tok = int.from_bytes(il[i:i + 4], "little")
            nome = {0x28: "call", 0x6F: "callvirt", 0x73: "newobj"}[op]
            out.append((ini, nome, ilcommon.nome_membro(dn, tok, dono) or f"tok:{tok:08x}"))
        elif op in (0x7B, 0x7C, 0x7D, 0x7E, 0x7F, 0x80):  # ldfld/ldflda/stfld/ldsfld/...
            tok = int.from_bytes(il[i:i + 4], "little")
            out.append((ini, "fld", ilcommon.nome_membro(dn, tok, dono) or f"tok:{tok:08x}"))
        i += tam
    return out


def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__.strip())
    ilcommon.exigir_dnfile()
    asm, filtro_tipo = sys.argv[1], sys.argv[2].lower()
    filtro_met = sys.argv[3].lower() if len(sys.argv) > 3 else ""

    dn, dados = ilcommon.abrir(asm)
    dono = ilcommon.donos(dn)

    tipo_atual = None
    for nome_t, nome_m, ini, tam in ilcommon.metodos(dn, dados, filtro_tipo, filtro_met):
        instr = decode(dados[ini:ini + tam], dn, dono)
        if not instr:
            continue
        if nome_t != tipo_atual:
            tipo_atual = nome_t
            print(f"\n{'=' * 70}\nTYPE {nome_t}")
        print(f"\n  --- {nome_m} ---")
        for pos, op, arg in instr:
            print(f"    {pos:04x}  {op:<10} {arg}")


if __name__ == "__main__":
    main()
