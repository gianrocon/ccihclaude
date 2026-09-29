"""Resumo textual das culturas positivas (botão "Copiar" da aba Culturas).

Formato de cada linha::

    MATERIAL dd/mm/aa OBS - Microrganismo: MEM-R CIP-S TZP-I.

- Só culturas positivas (com microrganismo isolado); culturas de swab nunca entram.
- Antibióticos em siglas de 3 letras (padrão WHONET/EUCAST), cada um seguido de
  ``-S``, ``-I`` ou ``-R``, separados por espaço e com ponto final.
- Para S. aureus, enterobactérias/BGN não fermentadores, Enterococcus e
  Acinetobacter só entram os antibióticos de interesse, na ordem definida.
- Vancomicina, polimixina e afins às vezes só aparecem no texto de observação
  da microbiologista; ``antibioticos_da_obs`` tenta extraí-los de lá.
"""

import re
import unicodedata


def _norm(texto) -> str:
    texto = unicodedata.normalize("NFKD", str(texto or ""))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return texto.upper()


# (sigla, palavras-chave normalizadas). Ordem importa: combinações antes dos
# componentes isolados ("AMPICILINA/SULBACTAM" antes de "AMPICILINA").
_SIGLAS = [
    ("SXT", ["SULFAMETOXAZOL", "TRIMETOPRIM", "COTRIMOXAZOL", "BACTRIM"]),
    ("SAM", ["AMPICILINA/SULBACTAM", "AMPICILINA-SULBACTAM", "AMPICILINA + SULBACTAM",
             "AMPICILINA E SULBACTAM", "AMPICILINA SULBACTAM", "SULBACTAM"]),
    ("TZP", ["PIPERACILINA", "TAZOBACTAM"]),
    ("AMC", ["AMOXICILINA/CLAV", "AMOXICILINA-CLAV", "AMOXICILINA + CLAV",
             "AMOXICILINA E CLAV", "AMOXICILINA CLAV", "CLAVULAN"]),
    ("CZA", ["CEFTAZIDIMA/AVIBACTAM", "CEFTAZIDIMA-AVIBACTAM", "CEFTAZIDIMA + AVIBACTAM",
             "CEFTAZIDIMA E AVIBACTAM", "CEFTAZIDIMA AVIBACTAM", "AVIBACTAM"]),
    ("CZT", ["CEFTOLOZAN"]),
    ("AMX", ["AMOXICILINA"]),
    ("AMP", ["AMPICILINA"]),
    ("OXA", ["OXACILINA"]),
    ("PEN", ["PENICILINA", "BENZILPENICILINA"]),
    ("MEM", ["MEROPENEM"]),
    ("IPM", ["IMIPENEM"]),
    ("ETP", ["ERTAPENEM"]),
    ("CRO", ["CEFTRIAXONA"]),
    ("CAZ", ["CEFTAZIDIMA"]),
    ("FEP", ["CEFEPIMA", "CEFEPIME"]),
    ("CTX", ["CEFOTAXIMA"]),
    ("FOX", ["CEFOXITINA"]),
    ("CXM", ["CEFUROXIMA"]),
    ("CFZ", ["CEFAZOLINA"]),
    ("CFL", ["CEFALOTINA"]),
    ("LEX", ["CEFALEXINA"]),
    ("ATM", ["AZTREONAM"]),
    ("CIP", ["CIPROFLOXACIN"]),
    ("LVX", ["LEVOFLOXACIN"]),
    ("MFX", ["MOXIFLOXACIN"]),
    ("NOR", ["NORFLOXACIN"]),
    ("NAL", ["NALIDIXICO"]),
    ("GEN", ["GENTAMICINA"]),
    ("AMK", ["AMICACINA", "AMIKACINA"]),
    ("TOB", ["TOBRAMICINA"]),
    ("VAN", ["VANCOMICINA"]),
    ("TEC", ["TEICOPLANINA"]),
    ("LNZ", ["LINEZOLIDA"]),
    ("DAP", ["DAPTOMICINA"]),
    ("TGC", ["TIGECICLINA"]),
    ("MNO", ["MINOCICLINA"]),
    ("DOX", ["DOXICICLINA"]),
    ("TCY", ["TETRACICLINA"]),
    ("CLI", ["CLINDAMICINA"]),
    ("ERY", ["ERITROMICINA"]),
    ("AZM", ["AZITROMICINA"]),
    ("RIF", ["RIFAMPICINA", "RIFAMPINA"]),
    ("NIT", ["NITROFURANTOINA"]),
    ("FOS", ["FOSFOMICINA"]),
    ("CHL", ["CLORANFENICOL"]),
    ("PMB", ["POLIMIXINA B", "POLIMIXINA"]),
    ("COL", ["COLISTINA", "COLISTIMETATO"]),
]


def sigla_antibiotico(nome) -> str:
    n = _norm(nome)
    for sigla, chaves in _SIGLAS:
        if any(k in n for k in chaves):
            return sigla
    letras = re.sub(r"[^A-Z]", "", n)
    return letras[:3] or n[:3]


# Painéis por microrganismo (ordem = ordem de impressão)
_PAINEL_SAUREUS = ["SXT", "CIP", "OXA", "GEN", "CRO", "VAN"]
_PAINEL_BGN = ["MEM", "IPM", "CIP", "CRO", "TZP", "FEP", "CAZ"]
_PAINEL_ENTEROCOCO = ["AMP", "VAN"]
_PAINEL_ACINETO = ["MEM", "TZP", "SAM", "PMB", "COL"]

_BGN_GENEROS = [
    # Enterobactérias (fermentadoras)
    "ESCHERICHIA", "E. COLI", "E.COLI", "KLEBSIELLA", "ENTEROBACTER", "SERRATIA",
    "PROTEUS", "MORGANELLA", "CITROBACTER", "PROVIDENCIA", "SALMONELLA",
    "SHIGELLA", "HAFNIA", "PANTOEA", "RAOULTELLA", "KLUYVERA", "CRONOBACTER",
    "ENTEROBACTERIA", "KOSAKONIA", "LELLIOTTIA", "KLEBSIELLA AEROGENES",
    # Não fermentadores (exceto Acinetobacter, que tem painel próprio)
    "PSEUDOMONAS", "STENOTROPHOMONAS", "BURKHOLDERIA", "ACHROMOBACTER",
    "SPHINGOMONAS", "ELIZABETHKINGIA", "CHRYSEOBACTERIUM", "RALSTONIA",
    "BACILO GRAM NEGATIVO NAO FERMENTADOR", "NAO FERMENTADOR",
]


def painel_do_microrganismo(microrganismo):
    """Lista de siglas de interesse, ou ``None`` para imprimir o antibiograma inteiro."""
    m = _norm(microrganismo)
    if "ACINETOBACTER" in m:
        return _PAINEL_ACINETO
    if "ENTEROCOCC" in m or "ENTEROCOCO" in m:
        return _PAINEL_ENTEROCOCO
    if "AUREUS" in m and ("STAPH" in m or "ESTAF" in m or "S. AUREUS" in m or "S.AUREUS" in m):
        return _PAINEL_SAUREUS
    if any(g in m for g in _BGN_GENEROS):
        return _PAINEL_BGN
    return None


_NEGATIVOS = [
    "NEGATIV", "NAO HOUVE CRESCIMENTO", "SEM CRESCIMENTO", "AUSENCIA DE CRESCIMENTO",
    "NAO HOUVE DESENVOLVIMENTO", "NAO ISOLADO", "NENHUM MICRORGANISMO", "ESTERIL",
]


def is_positiva(cultura) -> bool:
    m = _norm(cultura.microrganismo).strip()
    if not m or m in ("-", "--", "."):
        return False
    return not any(neg in m for neg in _NEGATIVOS)


def is_swab(cultura) -> bool:
    return "SWAB" in _norm(cultura.procedimento)


_STATUS_OBS = [
    ("I", re.compile(r"INTERMEDIARI|SENSIBILIDADE AUMENTADA|DOSE[- ]DEPENDENTE")),
    ("R", re.compile(r"RESISTEN")),
    ("S", re.compile(r"SENSIVE")),
]
_LETRA_APOS = re.compile(r"^[\s:=-]*\(?([SRI])\)?(?![A-Z])")


def _status_em(texto) -> set:
    return {s for s, rx in _STATUS_OBS if rx.search(texto)}


def _siglas_no_trecho(trecho):
    """``[(sigla, fim_do_match)]`` citados no trecho, sem casar a mesma região duas
    vezes ("AMPICILINA/SULBACTAM" vira só SAM, não SAM + AMP)."""
    achados = []
    for sigla, chaves in _SIGLAS:
        for k in chaves:
            for m in re.finditer(r"\b" + re.escape(k) + r"[A-Z]*", trecho):
                achados.append((sigla, m.start(), m.end()))
            if any(a[0] == sigla for a in achados):
                break
        # mascara a região casada para as siglas seguintes
        for a in achados:
            if a[0] == sigla:
                trecho = trecho[:a[1]] + " " * (a[2] - a[1]) + trecho[a[2]:]
    return [(sigla, fim) for sigla, _ini, fim in achados], trecho


def antibioticos_da_obs(obs) -> dict:
    """Extrai ``{sigla: S/I/R}`` do texto livre de observação.

    - "VANCOMICINA: S" / "POLIMIXINA B = R": letra logo após o nome.
    - Trechos (separados por ponto, ponto e vírgula ou quebra de linha) com um
      único status por extenso (sensível/resistente/intermediário): todo
      antibiótico citado no trecho recebe esse status. Trechos ambíguos são
      ignorados.
    - "MRSA" implica oxacilina resistente.
    """
    resultado = {}
    texto = _norm(obs)
    for trecho in re.split(r"[.;\n\r]+", texto):
        citados, _ = _siglas_no_trecho(trecho)
        if not citados:
            continue
        status_trecho = _status_em(trecho)
        for sigla, fim in citados:
            m = _LETRA_APOS.match(trecho[fim:])
            if m:
                resultado.setdefault(sigla, m.group(1))
                continue
            # prefere o status da oração (entre vírgulas) onde o nome aparece:
            # "RESISTENTE A OXACILINA, SENSIVEL A VANCOMICINA"
            ini = trecho.rfind(",", 0, fim) + 1
            f = trecho.find(",", fim)
            status = _status_em(trecho[ini:f if f != -1 else None]) or status_trecho
            if len(status) == 1:
                resultado.setdefault(sigla, next(iter(status)))
    if re.search(r"\bMRSA\b", texto):
        resultado.setdefault("OXA", "R")
    return resultado


def antibiograma_completo(cultura, antibiograma):
    """Linhas do antibiograma + as extraídas da obs que não estão na tabela.

    Retorna lista de tuplas ``(sigla, nome, sensibilidade, da_obs)``.
    """
    linhas = []
    vistas = set()
    for a in antibiograma:
        sigla = sigla_antibiotico(a.antibiotico)
        vistas.add(sigla)
        linhas.append((sigla, a.antibiotico, a.sensibilidade, False))
    for sigla, sens in antibioticos_da_obs(cultura.obs).items():
        if sigla not in vistas:
            linhas.append((sigla, sigla, sens, True))
    return linhas


def _texto_antibiograma(cultura, antibiograma) -> str:
    linhas = antibiograma_completo(cultura, antibiograma)
    painel = painel_do_microrganismo(cultura.microrganismo)
    por_sigla = {}
    for sigla, _nome, sens, _obs in linhas:
        por_sigla.setdefault(sigla, sens)
    if painel is None:
        siglas = list(por_sigla)
    else:
        siglas = [s for s in painel if s in por_sigla]
    return " ".join(f"{s}-{por_sigla[s]}" for s in siglas)


def is_hemocultura(cultura) -> bool:
    return "HEMOCULTURA" in _norm(cultura.procedimento)


def _material(cultura) -> str:
    # "HEMOCULTURA PARA AERÓBIOS - 2ª AMOSTRA" vira só "HEMOCULTURA"
    if is_hemocultura(cultura):
        return "HEMOCULTURA"
    if "UROCULTURA" in _norm(cultura.procedimento):
        return "UROCULTURA"
    return " ".join(cultura.procedimento.split())


def linha_cultura(cultura, antibiograma) -> str:
    data = cultura.dt_coleta or cultura.dt_assinatura
    cabeca = _material(cultura)
    if data:
        cabeca += " " + data.strftime("%d/%m/%y")
    partes = []
    obs = " ".join((cultura.obs or "").split()).rstrip(" .;")
    if obs:
        partes.append(obs)
    partes.append(" ".join(cultura.microrganismo.split()))
    texto = cabeca + " " + " - ".join(p for p in partes if p)
    atb = _texto_antibiograma(cultura, antibiograma)
    if atb:
        texto += ": " + atb
    return texto.rstrip(".") + "."


def texto_culturas_positivas(culturas_com_atb) -> str:
    """``culturas_com_atb``: lista de ``{"cultura": c, "antibiograma": [...]}``.

    Hemoculturas (1ª/2ª amostra) da mesma data com o mesmo microrganismo viram
    uma linha só — a de antibiograma mais completo. Microrganismos
    discordantes entre as amostras saem em linhas separadas.
    """
    linhas = []  # [chave_hemocultura_ou_None, texto, n_antibioticos]
    por_chave = {}
    for item in culturas_com_atb:
        c = item["cultura"]
        if is_swab(c) or not is_positiva(c):
            continue
        texto = linha_cultura(c, item["antibiograma"])
        n_atb = len(_texto_antibiograma(c, item["antibiograma"]).split())
        if not is_hemocultura(c):
            linhas.append([None, texto, n_atb])
            continue
        chave = (c.dt_coleta or c.dt_assinatura,
                 " ".join(_norm(c.microrganismo).split()))
        if chave in por_chave:
            existente = por_chave[chave]
            if n_atb > existente[2]:
                existente[1], existente[2] = texto, n_atb
            continue
        por_chave[chave] = [chave, texto, n_atb]
        linhas.append(por_chave[chave])
    return "\n".join(l[1] for l in linhas)
