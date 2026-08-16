#!/usr/bin/env python3
"""Acha metodos cujo IL referencia um membro/string dado.

   ilgrep.py <assembly.dll> <substring>
"""
import sys
import dnfile

asm, alvo = sys.argv[1], sys.argv[2].lower()
dn = dnfile.dnPE(asm)
md = dn.net.mdtables
data = dn.__data__


def rva2off(rva):
    for s in dn.sections:
        if s.VirtualAddress <= rva < s.VirtualAddress + max(s.Misc_VirtualSize, s.SizeOfRawData):
            return s.PointerToRawData + (rva - s.VirtualAddress)
    return None


def nome(tok):
    tab, rid = tok >> 24, tok & 0xFFFFFF
    try:
        if tab == 0x0A:
            r = md.MemberRef.rows[rid - 1]
            pai = str(r.Class.row.TypeName) if r.Class and r.Class.row else "?"
            return f"{pai}::{r.Name}"
        if tab == 0x06:
            return str(md.MethodDef.rows[rid - 1].Name)
        if tab == 0x01:
            return str(md.TypeRef.rows[rid - 1].TypeName)
        if tab == 0x02:
            return str(md.TypeDef.rows[rid - 1].TypeName)
        if tab == 0x04:
            return str(md.Field.rows[rid - 1].Name)
        if tab == 0x70:
            return str(dn.net.user_strings.get(rid).value)
    except Exception:
        pass
    return ""


for t in md.TypeDef.rows:
    for mref in t.MethodList:
        m = mref.row
        if not m.Rva:
            continue
        off = rva2off(m.Rva)
        if off is None:
            continue
        b0 = data[off]
        if (b0 & 3) == 2:
            tam, corpo = b0 >> 2, off + 1
        else:
            tam = int.from_bytes(data[off + 4:off + 8], 'little')
            corpo = off + ((int.from_bytes(data[off:off + 2], 'little') >> 12) * 4)
        il = data[corpo:corpo + tam]
        # varredura bruta de tokens: qualquer sequencia de 4 bytes que resolva
        achou = set()
        for i in range(0, max(0, len(il) - 4)):
            tok = int.from_bytes(il[i:i + 4], 'little')
            tab = tok >> 24
            if tab in (0x01, 0x02, 0x04, 0x06, 0x0A, 0x70):
                n = nome(tok)
                if n and alvo in n.lower():
                    achou.add(n)
        if achou:
            print(f"{t.TypeNamespace}.{t.TypeName}::{m.Name}   -> {sorted(achou)}")
