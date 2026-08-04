from collections import defaultdict
from datetime import date, timedelta

from django.db.models import Q

from core.models import Paciente, Cultura, ControleAtbRaw, Internamento, Importacao


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
        periods = []
        for inicio, dias in records:
            if not periods:
                periods.append([inicio, inicio + timedelta(days=dias)])
            else:
                period_start, period_fim = periods[-1]
                gap = (inicio - period_fim).days
                if gap == 0:
                    periods[-1][1] = max(period_fim, period_start + timedelta(days=dias))
                elif gap <= 1:
                    periods[-1][1] = max(period_fim, inicio + timedelta(days=dias))
                else:
                    periods.append([inicio, inicio + timedelta(days=dias)])

        for period_start, period_fim in periods:
            total = (period_fim - period_start).days
            resultado.append({
                "medicamento": med,
                "inicio": period_start,
                "fim": period_fim,
                "total_dias": total,
            })

    resultado.sort(key=lambda x: x["inicio"])
    return resultado


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


def limpar_banco(hospital):
    Paciente.objects.filter(hospital=hospital).delete()
