"""Leitura de metadados .NET compartilhada pelas ferramentas de IL deste repo.

Existia em tres copias (ildump.py, ilgrep.py, pdu5-leds-patch.py), e um erro no
decodificador teria que ser corrigido em tres lugares — foi assim que dois erros
de tamanho de operando sobreviveram. Aqui e' UM lugar so'.

⚠️ O tamanho de operando NAO e' opcional. Errar um byte dessincroniza todo o
resto do metodo: aparecem `ldc.i4` que nao existem, some a chamada que interessa,
e a medicao vira ficcao — num projeto cujas conclusoes (usagePage 0xFF, PIDs do
catalogo) saem justamente daqui.
"""
import os

# ---- tamanho do operando por opcode de 1 byte (ECMA-335, Partition III) ----
# token de metadados (4 bytes)
_TOK = {0x27, 0x28, 0x29, 0x6F, 0x70, 0x71, 0x72, 0x73, 0x74, 0x75, 0x79, 0x7B,
        0x7C, 0x7D, 0x7E, 0x7F, 0x80, 0x81, 0x8C, 0x8D, 0x8F, 0xA3, 0xA4, 0xA5,
        0xC2, 0xC6, 0xD0}
# inteiro/float de 4 bytes e desvios longos (0x38..0x44 = br .. blt.un)
_I4 = {0x20, 0x22, 0xDD} | set(range(0x38, 0x45))
_I8 = {0x21, 0x23}
# operando de 1 byte: as formas .s. ⚠️ 0x2B..0x37 sao TODOS desvios curtos --
# 0x37 (blt.un.s) inclusive; classifica-lo como longo comia 3 bytes a mais.
# ⚠️ 0x0C/0x0D sao stloc.2/stloc.3 e NAO tem operando: nao entram aqui.
_I1 = {0x0E, 0x0F, 0x10, 0x11, 0x12, 0x13, 0x1F, 0xDE} | set(range(0x2B, 0x38))

OPERANDO = {}
for _o in range(0x100):
    OPERANDO[_o] = 8 if _o in _I8 else 4 if (_o in _TOK or _o in _I4) else 1 if _o in _I1 else 0

SWITCH = 0x45          # 4 bytes de contagem + 4 por alvo
PREFIXO2 = 0xFE        # opcodes de 2 bytes
_FE4 = {0x06, 0x07, 0x15, 0x16, 0x1C}    # ldftn ldvirtftn initobj constrained. sizeof
_FE2 = {0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E}   # ldarg ldarga starg ldloc ldloca stloc
_FE1 = {0x12, 0x19}                      # unaligned. no.


def operando_fe(op2):
    return 4 if op2 in _FE4 else 2 if op2 in _FE2 else 1 if op2 in _FE1 else 0


# ---- assembly ----
def abrir(caminho):
    """Devolve (dnPE, bytes do arquivo).

    Os bytes vem de open(), nao de dn.__data__: aquele e' atributo privado do
    pefile e ja' mudou de nome entre versoes.

    ⚠️ O logger do dnfile e' silenciado. O ilgrep varre tokens por forca bruta de
    proposito, entao token invalido e' o caso ESPERADO -- e cada um gerava um
    "stream is too small" no stderr, afogando o resultado. `ILDUMP_DEBUG=1`
    devolve as mensagens quando a suspeita for do proprio parser.
    """
    import logging
    import dnfile
    if not os.environ.get("ILDUMP_DEBUG"):
        for nome in ("dnfile", "dnfile.stream", "dnfile.utils", "dnfile.base"):
            logging.getLogger(nome).setLevel(logging.CRITICAL)
    with open(caminho, "rb") as f:
        dados = f.read()
    return dnfile.dnPE(caminho), dados


def rva2off(dn, rva):
    """RVA -> offset no arquivo, ou None se cair fora de toda secao."""
    for s in dn.sections:
        tam = max(s.Misc_VirtualSize, s.SizeOfRawData)
        if s.VirtualAddress <= rva < s.VirtualAddress + tam:
            return s.PointerToRawData + (rva - s.VirtualAddress)
    return None


def corpo(dados, off):
    """Cabecalho do metodo -> (offset do IL, tamanho do IL em bytes).

    ⚠️ O tamanho vem do cabecalho, nunca de um chute. Uma janela fixa de N bytes
    passa do fim do metodo e encontra padroes que pertencem ao metodo SEGUINTE --
    e um patch aplicado la' e' silencioso e errado.
    """
    if off is None or off + 1 > len(dados):
        return None, 0
    b0 = dados[off]
    if (b0 & 3) == 2:                                   # tiny: tamanho nos 6 bits altos
        return off + 1, b0 >> 2
    if off + 12 > len(dados):
        return None, 0
    tam = int.from_bytes(dados[off + 4:off + 8], "little")
    cabecalho = (int.from_bytes(dados[off:off + 2], "little") >> 12) * 4
    return off + cabecalho, tam


def metodos(dn, dados, filtro_tipo=None, filtro_metodo=None):
    """Itera (nome do tipo, nome do metodo, offset do IL, tamanho do IL)."""
    for t in dn.net.mdtables.TypeDef.rows:
        nome_t = str(t.TypeName)
        if filtro_tipo and filtro_tipo not in nome_t.lower():
            continue
        for mref in t.MethodList:
            m = mref.row
            if m is None or not m.Rva:
                continue
            nome_m = str(m.Name)
            if filtro_metodo and filtro_metodo not in nome_m.lower():
                continue
            ini, tam = corpo(dados, rva2off(dn, m.Rva))
            if ini is None or tam <= 0:
                continue
            yield nome_t, nome_m, ini, tam


def donos(dn):
    """rid de MethodDef -> nome do tipo que o declara (a tabela nao guarda isso)."""
    d = {}
    for t in dn.net.mdtables.TypeDef.rows:
        for m in t.MethodList:
            try:
                d[m.row_index] = str(t.TypeName)
            except Exception:
                pass
    return d


def nome_membro(dn, tok, dono=None):
    """Token de metadados -> nome legivel, ou '' se nao resolver."""
    md = dn.net.mdtables
    tabela, rid = tok >> 24, tok & 0xFFFFFF
    if rid == 0:
        return ""
    try:
        if tabela == 0x0A:                              # MemberRef
            r = md.MemberRef.rows[rid - 1]
            pai = str(r.Class.row.TypeName) if r.Class and r.Class.row else "?"
            return f"{pai}::{r.Name}"
        if tabela == 0x06:                              # MethodDef
            pai = (dono or {}).get(rid, "?")
            return f"{pai}::{md.MethodDef.rows[rid - 1].Name}"
        if tabela == 0x01:                              # TypeRef
            return str(md.TypeRef.rows[rid - 1].TypeName)
        if tabela == 0x02:                              # TypeDef
            return str(md.TypeDef.rows[rid - 1].TypeName)
        if tabela == 0x04:                              # Field
            return str(md.Field.rows[rid - 1].Name)
        if tabela == 0x70:                              # #US
            return str(dn.net.user_strings.get(rid).value)
    except Exception:
        pass
    return ""


def user_string(dn, tok):
    """Token 0x70xxxxxx -> string do heap #US (UTF-16)."""
    idx = tok & 0xFFFFFF
    try:
        return dn.net.user_strings.get(idx).value
    except Exception:
        return f"<us:{idx:x}>"


def exigir_dnfile():
    """Mensagem util em vez de ImportError cru. ⚠️ PEP 668 barra pip global no Arch."""
    import importlib.util
    if importlib.util.find_spec("dnfile") is None:
        raise SystemExit(
            "falta o modulo dnfile. Num venv:\n"
            "    python3 -m venv venv && ./venv/bin/pip install dnfile\n"
            "    ./venv/bin/python tools/<ferramenta>.py ...")
