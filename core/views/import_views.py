import uuid
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect, render

from core.services import importer_service
from core.views import carregador_required


@carregador_required
def importar(request):
    if request.method == "POST":
        arquivo = request.FILES.get("arquivo")
        if not arquivo:
            messages.error(request, "Nenhum arquivo selecionado.")
            return redirect("importar")

        suffix = Path(arquivo.name).suffix.lower()
        if suffix not in (".xlsx", ".xls"):
            messages.error(request, "Formato inválido. Envie um arquivo .xlsx ou .xls.")
            return redirect("importar")

        import_dir = Path(settings.MEDIA_ROOT) / "imports"
        import_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = import_dir / f"{uuid.uuid4()}{suffix}"

        with open(tmp_path, "wb+") as f:
            for chunk in arquivo.chunks():
                f.write(chunk)

        try:
            tipo, n = importer_service.importar_arquivo(tmp_path, request.user.hospital, request.user)
            TIPO_LABELS = {
                "microbiologia": "Microbiologia",
                "controle_atb": "Controle ATB",
                "passagens": "Passagens/Internamentos",
            }
            label = TIPO_LABELS.get(tipo, tipo)
            messages.success(request, f"{label}: {n} registro(s) importado(s) com sucesso.")
        except ValueError as exc:
            messages.error(request, f"Erro ao importar: {exc}")
        except Exception as exc:
            messages.error(request, f"Erro inesperado ao importar: {exc}")
        finally:
            tmp_path.unlink(missing_ok=True)

        return redirect("importar")

    return render(request, "core/importar.html")


@carregador_required
def limpar_banco(request):
    if request.method == "POST" and request.POST.get("confirmar") == "1":
        from core.services import patient_service
        patient_service.limpar_banco(request.user.hospital)
        messages.success(request, "Banco de dados do hospital limpo com sucesso.")
        return redirect("busca")

    return render(request, "core/limpar_banco.html")
