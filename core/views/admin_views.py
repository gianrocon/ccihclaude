from django.contrib import messages
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, redirect, render

from core.models import CustomUser, Hospital, Vinculo
from core.views import staff_required


@staff_required
def gerenciar_usuarios(request):
    usuarios = (
        CustomUser.objects.prefetch_related(
            Prefetch("vinculos", queryset=Vinculo.objects.select_related("hospital"))
        )
        .order_by("username")
    )
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
        usuario.is_active = request.POST.get("ativo") == "1"
        usuario.save(update_fields=["is_active"])

        papeis_validos = {Vinculo.ROLE_CONSULTOR, Vinculo.ROLE_CARREGADOR}
        for h in hospitais:
            papel = request.POST.get(f"papel_{h.pk}", "")
            if papel in papeis_validos:
                Vinculo.objects.update_or_create(
                    usuario=usuario,
                    hospital=h,
                    defaults={"papel": papel},
                )
            else:
                # "Sem acesso" — remove o vínculo, se existir
                Vinculo.objects.filter(usuario=usuario, hospital=h).delete()

        messages.success(request, f"Usuário {usuario.username} atualizado.")
        return redirect("gerenciar_usuarios")

    papel_por_hospital = {
        v.hospital_id: v.papel for v in usuario.vinculos.all()
    }
    linhas = [
        {"hospital": h, "papel": papel_por_hospital.get(h.pk, "")}
        for h in hospitais
    ]
    return render(request, "core/editar_usuario.html", {
        "usuario": usuario,
        "linhas": linhas,
    })
