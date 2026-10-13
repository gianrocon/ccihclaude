from collections import defaultdict
from datetime import date, timedelta

from django.db.models import Q

from core.models import Paciente, Cultura, ControleAtbRaw, Internamento, Importacao, ImagemExame


def upsert_paciente(prontuario, nome, hospital):
    pac, created = Paciente.objects.get_or_create(
        hospital=hospital,
        prontuario=str(prontuario).strip(),
        defaults={"nome": str(nome).strip()},
    )
    if not created and str(nome).strip():
        pac.nome = str(nome).strip()
        pac.save(update_fields=["nome"])
    return pac


def buscar_pacientes(termo, hospital):
    t = termo.strip()
    if not t:
        return Paciente.objects.none()
    return (
        Paciente.objects.filter(hospital=hospital)
        .filter(Q(nome__icontains=t) | Q(prontuario__icontains=t))
        .order_by("nome")
    )


def get_culturas(paciente):
    return paciente.culturas.prefetch_related("antibiograma").order_by("-dt_coleta")


def get_antibiograma(cultura):
    from django.db.models import Case, When, IntegerField
    return cultura.antibiograma.annotate(
        ordem=Case(
            When(sensibilidade="S", then=0),
            When(sensibilidade="I", then=1),
            When(sensibilidade="R", then=2),
            default=3,
            output_field=IntegerField(),
        )
    ).order_by("ordem", "antibiotico")


def _normalize_med_name(med: str) -> str:
    parts = med.strip().split()
    name_parts = []
    for p in parts:
        if any(c.isdigit() for c in p):
            break
        name_parts.append(p)
    result = " ".join(name_parts).rstrip(",").strip()
    return result if result else med.strip()


def get_periodos_atb(paciente):
    rows = (
        ControleAtbRaw.objects.filter(paciente=paciente)
        .values("medicamento", "dt_inicio", "dias_solic", "dias_em_uso")
        .order_by("medicamento", "dt_inicio")
    )

    by_med = defaultdict(list)
    for r in rows:
        med = _normalize_med_name(r["medicamento"] or "")
        inicio = r["dt_inicio"]
        if not inicio:
            continue
        dias = max(int(r["dias_em_uso"] or 1), 1)
        by_med[med].append((inicio, dias))

    resultado = []
    for med, records in by_med.items():
        records.sort(key=lambda r: r[0])
        for p in periodos_de_fichas(records):
            resultado.append({"medicamento": med, **p})

    resultado.sort(key=lambda x: x["inicio"])
    return resultado


def periodos_de_fichas(records):
    """Periodos de uso de UMA droga a partir das fichas do relatec atb [(dt_inicio, dias_em_uso)], ordenadas.

    Cada linha do relatec e uma FICHA (solicitacao/prorrogacao), e ``dias_em_uso`` e o D# da prescricao quando
    a ficha foi encerrada/substituida (ou no dia do relatorio, se ainda ativa) — contado desde o inicio do CURSO,
    nao da ficha. Uma ficha pode atravessar suspensao + reinicio: o D# zera e ``dias_em_uso`` fica menor que a
    distancia do inicio do curso ate a propria ficha. Nesse caso o curso anterior fecha na data da ficha
    (``fim_incerto``: a suspensao foi entre essa data e o reinicio; a data exata so existe na prescricao) e o novo
    curso comeca em (inicio da proxima ficha - dias_em_uso). Ex.: fichas 17/09 (D35), 24/09 (D6), 09/10 (D9) =
    curso ate ~24/09..03/10 e novo curso desde 03/10.
    """
    periods = []  # [inicio, fim, fim_incerto]
    for i, (inicio, dias) in enumerate(records):
        prox = records[i + 1][0] if i + 1 < len(records) else None
        if periods and (inicio - periods[-1][1]).days <= 1:
            cur = periods[-1]
            if cur[0] + timedelta(days=dias) >= inicio:  # D# continua contando desde o inicio do curso
                cur[1] = max(cur[1], cur[0] + timedelta(days=dias))
                continue
            # D# zerou nesta ficha. Reinicio datado pela ficha seguinte; se cair logo no inicio da ficha (troca de
            # dose/item novo) ou nao houver ficha seguinte, e uso continuo
            novo = max(inicio, prox - timedelta(days=dias)) if prox else inicio
            if (novo - inicio).days <= 1:
                cur[1] = max(cur[1], novo + timedelta(days=dias))
                continue
            cur[1], cur[2] = max(cur[1], inicio), True  # suspensao entre a data da ficha e o reinicio
            periods.append([novo, novo + timedelta(days=dias), False])
        else:
            periods.append([inicio, inicio + timedelta(days=dias), False])
    return [{"inicio": a, "fim": b, "total_dias": (b - a).days, "fim_incerto": inc} for a, b, inc in periods]


def get_formulario(hospital):
    """Antimicrobianos já prescritos neste hospital, normalizados e distintos.

    É a melhor aproximação disponível do formulário da farmácia: o agente de
    interconsulta só pode sugerir droga que já apareceu aqui, porque o
    antibiograma do laboratório testa antimicrobianos que a farmácia não
    dispensa.

    Devolve uma lista de dicts ordenada por nome::

        [{"nome": "MEROPENEM", "n_prescricoes": 412,
          "primeira": date(...), "ultima": date(...)}, ...]
    """
    rows = (
        ControleAtbRaw.objects.filter(paciente__hospital=hospital)
        .values_list("medicamento", "dt_inicio")
    )

    agregado = {}
    for medicamento, inicio in rows:
        nome = _normalize_med_name(medicamento or "").upper()
        if not nome:
            continue
        item = agregado.setdefault(
            nome, {"nome": nome, "n_prescricoes": 0, "primeira": None, "ultima": None}
        )
        item["n_prescricoes"] += 1
        if inicio:
            if item["primeira"] is None or inicio < item["primeira"]:
                item["primeira"] = inicio
            if item["ultima"] is None or inicio > item["ultima"]:
                item["ultima"] = inicio

    return sorted(agregado.values(), key=lambda x: x["nome"])


def get_antibioticos_resistentes_recentes(paciente):
    cultura = paciente.culturas.order_by("-dt_coleta").first()
    if not cultura:
        return set()
    return set(
        cultura.antibiograma.filter(sensibilidade="R").values_list("antibiotico", flat=True)
    )


def get_internamentos(paciente):
    rows = (
        Internamento.objects.filter(paciente=paciente, dias__gte=3)
        .values("dt_entrada", "dt_alta", "dias")
        .order_by("dt_entrada")
    )

    periodos = []
    for r in rows:
        entrada = r["dt_entrada"]
        if not entrada:
            continue
        alta = r["dt_alta"]
        if not alta:
            alta = entrada + timedelta(days=int(r["dias"] or 1) - 1)
        periodos.append([entrada, alta])

    if not periodos:
        return []

    periodos.sort(key=lambda p: p[0])
    merged = [list(periodos[0])]
    for entrada, alta in periodos[1:]:
        if (entrada - merged[-1][1]).days <= 1:
            merged[-1][1] = max(merged[-1][1], alta)
        else:
            merged.append([entrada, alta])

    return [
        {"entrada": ini, "alta": fim, "dias": (fim - ini).days + 1}
        for ini, fim in merged
    ]


def _find_intervals(dates, gap_days=14):
    sorted_dates = sorted(set(d for d in dates if d))
    if not sorted_dates:
        return []
    intervals, start, prev = [], sorted_dates[0], sorted_dates[0]
    for d in sorted_dates[1:]:
        if (d - prev).days > gap_days:
            intervals.append((start, prev))
            start = d
        prev = d
    intervals.append((start, prev))
    return intervals


def get_cobertura_culturas(hospital):
    dates = list(
        Cultura.objects.filter(paciente__hospital=hospital)
        .exclude(dt_coleta=None)
        .values_list("dt_coleta", flat=True)
        .distinct()
        .order_by("dt_coleta")
    )
    return _find_intervals(dates)


def get_cobertura_atb(hospital):
    dates = list(
        ControleAtbRaw.objects.filter(paciente__hospital=hospital)
        .exclude(dt_inicio=None)
        .values_list("dt_inicio", flat=True)
        .distinct()
        .order_by("dt_inicio")
    )
    return _find_intervals(dates)


def get_cobertura_internamentos(hospital):
    dates = list(
        Internamento.objects.filter(paciente__hospital=hospital)
        .exclude(dt_entrada=None)
        .values_list("dt_entrada", flat=True)
        .distinct()
        .order_by("dt_entrada")
    )
    return _find_intervals(dates)


def get_ultima_importacao(hospital, tipo):
    """Data/hora do upload mais recente de um .xlsx do tipo dado, mesmo sem
    novos registros — todo upload reconhecido cria um Importacao (ver
    importer_service), então isso não precisa de rastreio próprio."""
    imp = (
        Importacao.objects.filter(hospital=hospital, tipo=tipo)
        .order_by("-importado_em")
        .first()
    )
    return imp.importado_em if imp else None


def limpar_banco(hospital):
    Paciente.objects.filter(hospital=hospital).delete()


def get_imagens_exame(paciente):
    return ImagemExame.objects.filter(paciente=paciente).order_by("-dt_exame", "-criado_em")
