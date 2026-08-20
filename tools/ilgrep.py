#!/usr/bin/env python3
"""Acha metodos cujo IL referencia um membro/string dado.

Varredura BRUTA de tokens: testa toda janela de 4 bytes do corpo do metodo e
guarda as que resolvem para um nome. Nao decodifica instrucoes de proposito --
acha referencia mesmo em opcode que o ildump nao trata. Em troca, pode acusar
coincidencia; confirme com o ildump.py.

   ilgrep.py <assembly.dll> <substring>
"""
import os
import sys

# realpath, nao abspath: estes scripts tambem podem ser chamados por symlink,
# e ai o abspath aponta para o diretorio do link, sem o ilcommon.py ao lado.
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import ilcommon

TABELAS = (0x01, 0x02, 0x04, 0x06, 0x0A, 0x70)


def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__.strip())
    ilcommon.exigir_dnfile()
    asm, alvo = sys.argv[1], sys.argv[2].lower()

    dn, dados = ilcommon.abrir(asm)
    dono = ilcommon.donos(dn)

    for nome_t, nome_m, ini, tam in ilcommon.metodos(dn, dados):
        il = dados[ini:ini + tam]
        achou = set()
        # ⚠️ len(il) - 3: com len(il) - 4 a ultima janela de 4 bytes ficava de
        # fora, e um metodo terminado em `callvirt <token>` nunca era encontrado.
        for i in range(0, max(0, len(il) - 3)):
            tok = int.from_bytes(il[i:i + 4], "little")
            if (tok >> 24) not in TABELAS:
                continue
            n = ilcommon.nome_membro(dn, tok, dono)
            if n and alvo in n.lower():
                achou.add(n)
        if achou:
            print(f"{nome_t}::{nome_m}   -> {sorted(achou)}")


if __name__ == "__main__":
    main()
