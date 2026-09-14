from datetime import datetime
from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect

from core.models import ImagemExame, Paciente
from core.views import carregador_required

TAMANHO_MAX_BYTES = 700 * 1024
EXTENSOES_ACEITAS = (".png", ".jpg", ".jpeg")
CONTENT_TYPES_ACEITOS = ("image/png", "image/jpeg")


@carregador_required
def imagem_upload(request, pk):
    paciente = get_object_or_404(Paciente, pk=pk)
    if paciente.hospital != request.hospital_atual:
        raise Http404

    if request.method == "POST":
        arquivo = request.FILES.get("imagem")
        dt_exame_raw = request.POST.get("dt_exame", "").strip()

        if not arquivo:
            messages.error(request, "Nenhuma imagem selecionada.")
        elif not dt_exame_raw:
            messages.error(request, "Informe a data do exame.")
        elif not arquivo.name.lower().endswith(EXTENSOES_ACEITAS):
            messages.error(request, "Formato inválido. Envie um arquivo PNG ou JPG/JPEG.")
        elif arquivo.content_type not in CONTENT_TYPES_ACEITOS:
            messages.error(request, "Formato inválido. Envie um arquivo PNG ou JPG/JPEG.")
        elif arquivo.size > TAMANHO_MAX_BYTES:
            messages.error(request, "Imagem muito grande. O limite é 700 KB.")
        else:
            try:
                dt_exame = datetime.strptime(dt_exame_raw, "%Y-%m-%d").date()
            except ValueError:
                messages.error(request, "Data do exame inválida.")
            else:
                ImagemExame.objects.create(
                    paciente=paciente,
                    imagem=arquivo,
                    dt_exame=dt_exame,
                    enviado_por=request.user,
                )
                messages.success(request, "Imagem enviada com sucesso.")

    return redirect("paciente_detalhe", pk=paciente.pk)


@login_required
def imagem_download(request, pk):
    imagem = get_object_or_404(ImagemExame, pk=pk)
    if imagem.paciente.hospital != request.hospital_atual:
        raise Http404

    nome_arquivo = f"{imagem.paciente.prontuario}_{imagem.dt_exame:%Y-%m-%d}{Path(imagem.imagem.name).suffix.lower()}"
    return FileResponse(imagem.imagem.open("rb"), as_attachment=True, filename=nome_arquivo)


@carregador_required
def imagem_remover(request, pk):
    imagem = get_object_or_404(ImagemExame, pk=pk)
    if imagem.paciente.hospital != request.hospital_atual:
        raise Http404

    paciente_pk = imagem.paciente.pk
    if request.method == "POST":
        imagem.imagem.delete(save=False)
        imagem.delete()
        messages.success(request, "Imagem removida com sucesso.")

    return redirect("paciente_detalhe", pk=paciente_pk)
