#!/usr/bin/env python3
"""Dump IL de metodos .NET filtrando por nome de tipo, sem decompilador.

Decodifica so' o que interessa aqui: ldstr (nomes/mensagens), ldc.i4* (PIDs e
constantes) e call/callvirt/newobj (para quem ele chama).

   ildump.py <assembly.dll> <substring do tipo> [substring do metodo]
"""
import sys
import dnfile
from dnfile.enums import MetadataTables

asm, filtro_tipo = sys.argv[1], sys.argv[2].lower()
filtro_met = sys.argv[3].lower() if len(sys.argv) > 3 else ""

dn = dnfile.dnPE(asm)
md = dn.net.mdtables


def rva2off(rva):
    for s in dn.sections:
        if s.VirtualAddress <= rva < s.VirtualAddress + max(s.Misc_VirtualSize, s.SizeOfRawData):
            return s.PointerToRawData + (rva - s.VirtualAddress)
    return None


data = dn.__data__


def user_string(tok):
    """Token 0x70xxxxxx -> string do heap #US (UTF-16)."""
    idx = tok & 0xFFFFFF
    us = dn.net.user_strings
    try:
        return us.get(idx).value
    except Exception:
        return f"<us:{idx:x}>"


# MethodDef rid -> tipo que o declara (a tabela nao guarda isso; e' por faixa)
_dono = {}
for _t in md.TypeDef.rows:
    for _m in _t.MethodList:
        try:
            _dono[_m.row_index] = str(_t.TypeName)
        except Exception:
            pass


def nome_membro(tok):
    tabela, rid = tok >> 24, tok & 0xFFFFFF
    try:
        if tabela == 0x0A:  # MemberRef
            r = md.MemberRef.rows[rid - 1]
            pai = str(r.Class.row.TypeName) if r.Class and r.Class.row else "?"
            return f"{pai}::{r.Name}"
        if tabela == 0x06:  # MethodDef
            return f"{_dono.get(rid, '?')}::{md.MethodDef.rows[rid - 1].Name}"
        if tabela == 0x01:  # TypeRef
            return str(md.TypeRef.rows[rid - 1].TypeName)
        if tabela == 0x02:  # TypeDef
            return str(md.TypeDef.rows[rid - 1].TypeName)
        if tabela == 0x04:  # Field
            return str(md.Field.rows[rid - 1].Name)
    except Exception:
        pass
    return f"tok:{tok:08x}"


# opcodes de 1 byte que nos interessam; o resto so' avanca o tamanho certo
TAM = {}
for o in range(0x00, 0x100):
    TAM[o] = 0
for o in list(range(0x02, 0x0E)) + list(range(0x0A, 0x0E)) + [0x25, 0x26] + list(range(0x58, 0x62)) + list(range(0x62, 0x70)):
    TAM[o] = 0
INLINE_I4 = {0x20}          # ldc.i4
INLINE_I1 = {0x1F, 0x0E, 0x0C, 0x10, 0x11, 0x12, 0x13, 0x2B, 0x2C, 0x2D, 0x2E, 0x2F,
             0x30, 0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x37, 0x38 - 20}
INLINE_TOK = {0x28, 0x6F, 0x73, 0x72, 0x74, 0x75, 0x7B, 0x7C, 0x7D, 0x7E, 0x7F, 0x80,
              0x81, 0x8C, 0x8D, 0xA5, 0xC2, 0xC6, 0x71, 0x70, 0x79}
INLINE_I8 = {0x21}
INLINE_R8 = {0x23}
INLINE_R4 = {0x22}
INLINE_BR4 = set(range(0x38, 0x45)) | {0x37}
INLINE_BR1 = set(range(0x2B, 0x38))
LDC_I4_S = {0x1F}
LDARG_S = {0x0E, 0x0F, 0x10, 0x11, 0x12, 0x13}


def decode(il):
    i, out = 0, []
    while i < len(il):
        op = il[i]
        ini = i
        i += 1
        if op == 0xFE:                      # prefixo de 2 bytes
            op2 = il[i]; i += 1
            if op2 in (0x06, 0x07, 0x15, 0x16, 0x1C):
                i += 4
            elif op2 in (0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E):
                i += 2
            continue
        if op == 0x72:                      # ldstr
            tok = int.from_bytes(il[i:i + 4], 'little'); i += 4
            out.append((ini, 'ldstr', repr(user_string(tok))))
        elif op == 0x20:                    # ldc.i4
            v = int.from_bytes(il[i:i + 4], 'little', signed=True); i += 4
            out.append((ini, 'ldc.i4', f"{v} (0x{v & 0xFFFFFFFF:X})"))
        elif op == 0x1F:                    # ldc.i4.s
            v = int.from_bytes(il[i:i + 1], 'little', signed=True); i += 1
            out.append((ini, 'ldc.i4.s', f"{v} (0x{v & 0xFF:02X})"))
        elif 0x16 <= op <= 0x1E:            # ldc.i4.0 .. ldc.i4.8
            out.append((ini, 'ldc.i4', str(op - 0x16)))
        elif op in (0x28, 0x6F, 0x73):      # call / callvirt / newobj
            tok = int.from_bytes(il[i:i + 4], 'little'); i += 4
            nome = {0x28: 'call', 0x6F: 'callvirt', 0x73: 'newobj'}[op]
            out.append((ini, nome, nome_membro(tok)))
        elif op in (0x7B, 0x7D, 0x7E, 0x7F, 0x80):   # ldfld/stfld/ldsfld/...
            tok = int.from_bytes(il[i:i + 4], 'little'); i += 4
            out.append((ini, 'fld', nome_membro(tok)))
        elif op in INLINE_TOK:
            i += 4
        elif op in INLINE_BR4:
            i += 4
        elif op in INLINE_BR1:
            i += 1
        elif op in LDARG_S or op in (0x0E, 0x0C, 0x0D, 0x11, 0x13):
            i += 1
        elif op == 0x21:
            i += 8
        elif op == 0x22:
            i += 4
        elif op == 0x23:
            i += 8
        elif op == 0x45:                    # switch
            n = int.from_bytes(il[i:i + 4], 'little'); i += 4 + 4 * n
    return out


for t in md.TypeDef.rows:
    if filtro_tipo not in str(t.TypeName).lower():
        continue
    print(f"\n{'='*70}\nTYPE {t.TypeNamespace}.{t.TypeName}")
    for m in t.MethodList:
        m = m.row
        if filtro_met and filtro_met not in str(m.Name).lower():
            continue
        if not m.Rva:
            continue
        off = rva2off(m.Rva)
        if off is None:
            continue
        b0 = data[off]
        if (b0 & 3) == 2:                   # tiny header
            tam, corpo = b0 >> 2, off + 1
        else:                               # fat header
            tam = int.from_bytes(data[off + 4:off + 8], 'little')
            corpo = off + ((int.from_bytes(data[off:off + 2], 'little') >> 12) * 4)
        il = data[corpo:corpo + tam]
        instr = decode(il)
        if not instr:
            continue
        print(f"\n  --- {m.Name} ---")
        for pos, op, arg in instr:
            print(f"    {pos:04x}  {op:<10} {arg}")
