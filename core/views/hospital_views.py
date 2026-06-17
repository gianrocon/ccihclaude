from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

from core.middleware import SESSION_KEY


@login_required
def selecionar_hospital(request):
    """Define o hospital ativo na sessão (seletor da navbar)."""
    if request.method == "POST":
        try:
            hid = int(request.POST.get("hospital", ""))
        except (TypeError, ValueError):
            hid = None

        if hid is not None and any(
            h.pk == hid for h in request.user.hospitais_disponiveis()
        ):
            request.session[SESSION_KEY] = hid

    destino = request.POST.get("next") or request.META.get("HTTP_REFERER") or "busca"
    return redirect(destino)
