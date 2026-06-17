from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, render

from core.models import Paciente
from core.services import patient_service, chart_service


@login_required
def busca(request):
    termo = request.GET.get("q", "").strip()
    pacientes = []
    if termo:
        pacientes = patient_service.buscar_pacientes(termo, request.hospital_atual)
        if pacientes.count() == 1:
            from django.shortcuts import redirect
            return redirect("paciente_detalhe", pk=pacientes.first().pk)

    return render(request, "core/paciente_busca.html", {
        "termo": termo,
        "pacientes": pacientes,
    })


@login_required
def paciente_detalhe(request, pk):
    paciente = get_object_or_404(Paciente, pk=pk)
    if paciente.hospital != request.hospital_atual:
        raise Http404

    culturas      = patient_service.get_culturas(paciente)
    periodos_atb  = patient_service.get_periodos_atb(paciente)
    internamentos = patient_service.get_internamentos(paciente)
    resistentes   = patient_service.get_antibioticos_resistentes_recentes(paciente)

    culturas_com_atb = []
    for c in culturas:
        culturas_com_atb.append({
            "cultura": c,
            "antibiograma": patient_service.get_antibiograma(c),
        })

    gantt_atb_b64   = chart_service.render_gantt_atb_base64(paciente)
    gantt_int_b64   = chart_service.render_gantt_internamentos_base64(paciente)

    resistentes_norm = {r.upper() for r in resistentes}

    # Marca resistentes nos períodos ATB para uso simples no template
    for p in periodos_atb:
        med_upper = p["medicamento"].upper()
        p["is_resistant"] = any(r in med_upper for r in resistentes_norm)

    return render(request, "core/paciente_detalhe.html", {
        "paciente":        paciente,
        "culturas_com_atb": culturas_com_atb,
        "periodos_atb":    periodos_atb,
        "internamentos":   internamentos,
        "resistentes":     resistentes_norm,
        "gantt_atb_b64":   gantt_atb_b64,
        "gantt_int_b64":   gantt_int_b64,
    })
