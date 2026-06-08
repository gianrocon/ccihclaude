from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from core.models import CustomUser, Hospital
from core.views import staff_required


@staff_required
def gerenciar_usuarios(request):
    usuarios = CustomUser.objects.select_related("hospital").order_by("username")
    hospitais = Hospital.objects.filter(ativo=True).order_by("sigla")
    return render(request, "core/gerenciar_usuarios.html", {
        "usuarios": usuarios,
        "hospitais": hospitais,
    })


@staff_required
def editar_usuario(request, pk):
    usuario = get_object_or_404(CustomUser, pk=pk)
    hospitais = Hospital.objects.filter(ativo=True).order_by("sigla")

    if request.method == "POST":
        hospital_id = request.POST.get("hospital") or None
        papel = request.POST.get("papel")
        ativo = request.POST.get("ativo") == "1"

        if hospital_id:
            try:
                usuario.hospital = Hospital.objects.get(pk=hospital_id)
            except Hospital.DoesNotExist:
                usuario.hospital = None
        else:
            usuario.hospital = None

        if papel in (CustomUser.ROLE_CONSULTOR, CustomUser.ROLE_CARREGADOR):
            usuario.papel = papel

        usuario.is_active = ativo
        usuario.save()
        messages.success(request, f"Usuário {usuario.username} atualizado.")
        return redirect("gerenciar_usuarios")

    return render(request, "core/editar_usuario.html", {
        "usuario": usuario,
        "hospitais": hospitais,
    })
