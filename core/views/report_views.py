from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from core.services import patient_service


@login_required
def cobertura(request):
    hospital = request.hospital_atual
    ctx = {}
    if hospital:
        ctx["culturas"]     = patient_service.get_cobertura_culturas(hospital)
        ctx["atb"]          = patient_service.get_cobertura_atb(hospital)
        ctx["internamentos"] = patient_service.get_cobertura_internamentos(hospital)
    return render(request, "core/cobertura.html", ctx)
