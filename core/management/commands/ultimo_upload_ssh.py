"""Devolve so a data do ultimo upload de planilha (microbiologia e controle
ATB) de um hospital, via SSH - sem cobertura, sem dados de paciente.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from core.models import Hospital
from core.services import patient_service as svc


def _fmt(dt):
    return dt.strftime("%Y-%m-%d %H:%M") if dt else "-"


class Command(BaseCommand):
    help = "Mostra a data do ultimo upload de microbiologia e de controle ATB para um hospital."

    def add_arguments(self, parser):
        parser.add_argument("--hospital", required=True, help="Sigla do hospital")

    def handle(self, *args, **options):
        sigla = options["hospital"].strip()
        hospital = Hospital.objects.filter(sigla__iexact=sigla, ativo=True).first()
        if hospital is None:
            raise CommandError("Hospital com sigla '%s' nao encontrado ou inativo." % sigla)

        self.stdout.write(
            "Microbiologia: %s" % _fmt(svc.get_ultima_importacao(hospital, "microbiologia"))
        )
        self.stdout.write(
            "Antimicrobianos: %s" % _fmt(svc.get_ultima_importacao(hospital, "controle_atb"))
        )
