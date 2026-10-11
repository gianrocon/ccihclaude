"""Dados das linhas do tempo (Gantt) de antimicrobianos e internamentos.

O desenho é feito no navegador (SVG via JavaScript, templates/core/_gantt_js.html):
nítido em qualquer zoom, com tooltip. Antes era PNG do matplotlib (borrado ao ampliar).
Aqui só montamos a lista serializável que o template entrega com ``json_script``.
"""

import re

from core.services.patient_service import (
    get_antibioticos_resistentes_recentes,
    get_internamentos,
    get_periodos_atb,
)


def _short_name(med: str) -> str:
    m = re.match(r"^([^\d,]+)", med.strip())
    if m:
        name = m.group(1).strip()
        return name[:34] + "…" if len(name) > 34 else name
    return med[:34]


def dados_gantt_atb(paciente, periodos=None, resistentes=None) -> list:
    periodos = get_periodos_atb(paciente) if periodos is None else periodos
    if not periodos:
        return []
    if resistentes is None:
        resistentes = get_antibioticos_resistentes_recentes(paciente)
    res = {r.upper() for r in resistentes}
    return [
        {
            "rotulo": _short_name(p["medicamento"]),
            "nome": p["medicamento"],
            "inicio": p["inicio"].isoformat(),
            "fim": p["fim"].isoformat(),
            "dias": p.get("total_dias") or (p["fim"] - p["inicio"]).days + 1,
            "resistente": any(r in p["medicamento"].upper() for r in res),
        }
        for p in periodos
    ]


def dados_gantt_internamentos(paciente, internamentos=None) -> list:
    internamentos = get_internamentos(paciente) if internamentos is None else internamentos
    return [
        {
            "rotulo": "Internamento",
            "nome": "Internamento",
            "inicio": i["entrada"].isoformat(),
            "fim": i["alta"].isoformat(),
            "dias": (i["alta"] - i["entrada"]).days + 1,
            "resistente": False,
        }
        for i in internamentos
    ]
