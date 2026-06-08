import io
import base64
import re

import matplotlib.dates as mdates
from matplotlib.figure import Figure

from core.services.patient_service import (
    get_periodos_atb,
    get_internamentos,
    get_antibioticos_resistentes_recentes,
)

PALETTE = [
    "#1565c0", "#2e7d32", "#6a1b9a", "#e65100", "#00695c",
    "#ad1457", "#4527a0", "#558b2f", "#0277bd", "#4e342e",
]


def _fig_to_base64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=96, bbox_inches="tight")
    buf.seek(0)
    data = base64.b64encode(buf.read()).decode("utf-8")
    return data


def _short_name(med: str) -> str:
    m = re.match(r"^([^\d,]+)", med.strip())
    if m:
        name = m.group(1).strip()
        return name[:34] + "…" if len(name) > 34 else name
    return med[:34]


def _make_gantt_figure(periodos, resistentes, fig_height=None):
    meds = list(dict.fromkeys(p["medicamento"] for p in periodos))
    n_meds = len(meds)
    med_idx = {m: i for i, m in enumerate(meds)}

    if fig_height is None:
        fig_height = max(2.2, 0.45 * n_meds + 1.2)

    fig = Figure(figsize=(14, fig_height), facecolor="#f5f5f5")
    ax = fig.add_subplot(1, 1, 1)
    ax.set_facecolor("#fafafa")

    color_map = {m: PALETTE[i % len(PALETTE)] for i, m in enumerate(meds)}

    for p in periodos:
        med = p["medicamento"]
        y = med_idx[med]
        inicio = p["inicio"]
        fim = p["fim"]
        duracao = (fim - inicio).days

        is_res = any(r in med.upper() for r in resistentes)
        color = color_map[med]
        edgecolor = "#c62828" if is_res else color

        ax.barh(
            y,
            duracao,
            left=mdates.date2num(inicio),
            height=0.55,
            color=color,
            edgecolor=edgecolor,
            linewidth=2.5 if is_res else 0.5,
            alpha=0.85,
        )

        mid_x = mdates.date2num(inicio) + duracao / 2
        ax.text(mid_x, y, f"{duracao}d", ha="center", va="center",
                fontsize=7.5, color="white", fontweight="bold")

    ax.set_yticks(range(n_meds))
    ax.set_yticklabels([_short_name(m) for m in meds], fontsize=8)
    ax.invert_yaxis()

    tick_dates = sorted({p["inicio"] for p in periodos} | {p["fim"] for p in periodos})
    tick_nums  = [mdates.date2num(d) for d in tick_dates]

    ax.xaxis_date()
    ax.set_xticks(tick_nums)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m/%Y"))
    for label in ax.get_xticklabels():
        label.set_rotation(40)
        label.set_ha("right")
        label.set_fontsize(7.5)

    for t in tick_nums:
        ax.axvline(t, color="#bdbdbd", linewidth=0.6, linestyle="--", zorder=0)

    ax.grid(False)
    fig.tight_layout(pad=0.8)
    return fig


def _make_internamento_figure(internamentos, fig_height=2.0):
    fig = Figure(figsize=(14, fig_height), facecolor="#f5f5f5")
    ax = fig.add_subplot(1, 1, 1)
    ax.set_facecolor("#fafafa")

    color = "#1565c0"
    for p in internamentos:
        entrada = p["entrada"]
        alta    = p["alta"]
        duracao = (alta - entrada).days + 1

        ax.barh(0, duracao, left=mdates.date2num(entrada),
                height=0.5, color=color, edgecolor=color,
                linewidth=0.5, alpha=0.85)

        mid_x = mdates.date2num(entrada) + duracao / 2
        ax.text(mid_x, 0, f"{duracao}d", ha="center", va="center",
                fontsize=7.5, color="white", fontweight="bold")

    ax.set_yticks([])
    ax.set_ylim(-0.6, 0.6)

    tick_dates = sorted({p["entrada"] for p in internamentos} | {p["alta"] for p in internamentos})
    tick_nums  = [mdates.date2num(d) for d in tick_dates]

    ax.xaxis_date()
    ax.set_xticks(tick_nums)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m/%Y"))
    for label in ax.get_xticklabels():
        label.set_rotation(40)
        label.set_ha("right")
        label.set_fontsize(7.5)

    for t in tick_nums:
        ax.axvline(t, color="#bdbdbd", linewidth=0.6, linestyle="--", zorder=0)

    ax.grid(False)
    fig.tight_layout(pad=0.8)
    return fig


def render_gantt_atb_base64(paciente) -> str:
    periodos = get_periodos_atb(paciente)
    if not periodos:
        return ""
    resistentes = get_antibioticos_resistentes_recentes(paciente)
    n_meds = len({p["medicamento"] for p in periodos})
    fig_height = max(2.2, 0.44 * n_meds + 1.1)
    fig = _make_gantt_figure(periodos, resistentes, fig_height=fig_height)
    return _fig_to_base64(fig)


def render_gantt_internamentos_base64(paciente) -> str:
    internamentos = get_internamentos(paciente)
    if not internamentos:
        return ""
    fig = _make_internamento_figure(internamentos)
    return _fig_to_base64(fig)
