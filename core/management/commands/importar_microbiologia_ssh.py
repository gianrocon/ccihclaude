"""Importa planilha de microbiologia via SSH, mesmo fluxo do upload web em
/importar/ (core/views/import_views.py::importar) - inclusive atualizacao de
cobertura e da "Data de upload" (ver core/services/patient_service.py::
get_ultima_importacao), sem precisar de sessao/navegador.
"""

from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from core.models import CustomUser, Hospital
from core.services import importer_service


class Command(BaseCommand):
    help = "Importa planilha de microbiologia (.xlsx) via SSH, igual ao upload pela pagina /importar/."

    def add_arguments(self, parser):
        parser.add_argument("--hospital", required=True, help="Sigla do hospital")
        parser.add_argument("--arquivo", required=True, help="Caminho do .xlsx no servidor")
        parser.add_argument(
            "--usuario", default="",
            help="Username a registrar em Importacao.usuario (opcional)",
        )

    def handle(self, *args, **options):
        sigla = options["hospital"].strip()
        hospital = Hospital.objects.filter(sigla__iexact=sigla, ativo=True).first()
        if hospital is None:
            raise CommandError("Hospital com sigla '%s' nao encontrado ou inativo." % sigla)

        path = Path(options["arquivo"])
        if not path.is_file():
            raise CommandError("Arquivo nao encontrado: %s" % path)
        if path.suffix.lower() != ".xlsx":
            raise CommandError("Microbiologia exige .xlsx (recebido: %s)" % path.suffix)

        usuario = None
        username = options["usuario"].strip()
        if username:
            usuario = CustomUser.objects.filter(username=username).first()
            if usuario is None:
                raise CommandError("Usuario '%s' nao encontrado." % username)

        try:
            n = importer_service.importar_com_validacao(path, hospital, usuario, "microbiologia")
        except ValueError as exc:
            raise CommandError(str(exc))

        self.stdout.write(self.style.SUCCESS(
            "Microbiologia: %d registro(s) importado(s) para %s." % (n, hospital.sigla)
        ))
