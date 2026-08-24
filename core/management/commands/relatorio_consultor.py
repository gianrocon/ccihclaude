"""Relatorio Markdown para o consultor externo, invocado por SSH.

Ver docs/superpowers/specs/2026-08-15-relatorio-consultor-ssh-design.md.
Nenhuma logica de negocio nova: reusa core.services.patient_service, as
mesmas funcoes que ja alimentam o relatorio /cobertura/ e a API /api/v1/.
"""

from __future__ import annotations

from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

from core.models import Hospital
from core.services import patient_service as svc


def _fmt_data(d):
    return d.strftime("%Y-%m-%d") if d else "-"


def _fmt_upload(dt):
    return dt.strftime("%Y-%m-%d %H:%M") if dt else "-"


def _fmt_cobertura(intervalos):
    if not intervalos:
        return "- Nenhum dado importado.\n"
    linhas = [
        "- %s a %s" % (_fmt_data(ini), _fmt_data(fim)) for ini, fim in intervalos
    ]
    return "\n".join(linhas) + "\n"


def _fmt_culturas(paciente):
    culturas = list(svc.get_culturas(paciente))
    if not culturas:
        return "Nenhum registro.\n"
    linhas = ["| Coleta | Sitio | Microrganismo | Antibiograma |", "|---|---|---|---|"]
    for c in culturas:
        antibiograma = ", ".join(
            "%s: %s" % (a.antibiotico, a.sensibilidade) for a in svc.get_antibiograma(c)
        ) or "-"
        linhas.append(
            "| %s | %s | %s | %s |"
            % (_fmt_data(c.dt_coleta), c.procedimento or "-", c.microrganismo or "-", antibiograma)
        )
    return "\n".join(linhas) + "\n"


def _fmt_atb_periodos(paciente):
    periodos = svc.get_periodos_atb(paciente)
    if not periodos:
        return "Nenhum registro.\n"
    linhas = ["| Medicamento | Inicio | Fim | Dias |", "|---|---|---|---|"]
    for p in periodos:
        linhas.append(
            "| %s | %s | %s | %s |"
            % (p["medicamento"], _fmt_data(p["inicio"]), _fmt_data(p["fim"]), p["total_dias"])
        )
    return "\n".join(linhas) + "\n"


def _resolver_paciente(hospital, prontuario):
    """Mesmo fallback de zeros a esquerda usado em core/views/api_views.py::paciente."""
    prontuario = prontuario.strip()
    pac = hospital.pacientes.filter(prontuario=prontuario).first()
    if pac is None:
        alternativo = prontuario.lstrip("0")
        if alternativo and alternativo != prontuario:
            pac = hospital.pacientes.filter(prontuario=alternativo).first()
    return pac


class Command(BaseCommand):
    help = "Gera relatorio Markdown de cobertura + culturas/ATB para o consultor, via SSH."

    def add_arguments(self, parser):
        parser.add_argument("--hospital", required=True, help="Sigla do hospital")
        parser.add_argument(
            "--prontuarios",
            default="",
            help="Lista de prontuarios separados por virgula (opcional)",
        )

    def handle(self, *args, **options):
        sigla = options["hospital"].strip()
        hospital = Hospital.objects.filter(sigla__iexact=sigla, ativo=True).first()
        if hospital is None:
            raise CommandError(
                "Hospital com sigla '%s' nao encontrado ou inativo." % sigla
            )

        prontuarios = [p.strip() for p in options["prontuarios"].split(",") if p.strip()]

        partes = [
            "# Relatorio - %s (%s)" % (hospital.nome, hospital.sigla),
            "Gerado em: %s\n" % datetime.now().strftime("%Y-%m-%d %H:%M"),
            "## Cobertura de dados importados",
            "### Microbiologia",
            "Data de cobertura:",
            _fmt_cobertura(svc.get_cobertura_culturas(hospital)),
            "Data de upload: %s\n"
            % _fmt_upload(svc.get_ultima_importacao(hospital, "microbiologia")),
            "### Antimicrobianos",
            "Data de cobertura:",
            _fmt_cobertura(svc.get_cobertura_atb(hospital)),
            "Data de upload: %s\n"
            % _fmt_upload(svc.get_ultima_importacao(hospital, "controle_atb")),
        ]

        avisos = []
        for prontuario in prontuarios:
            pac = _resolver_paciente(hospital, prontuario)
            if pac is None:
                avisos.append(
                    "Prontuario %s nao encontrado no hospital %s" % (prontuario, hospital.sigla)
                )
                continue
            partes.append("## Paciente %s - %s" % (pac.prontuario, pac.nome))
            partes.append("### Culturas")
            partes.append(_fmt_culturas(pac))
            partes.append("### Uso de antibiotico")
            partes.append(_fmt_atb_periodos(pac))

        if avisos:
            partes.append("## Avisos")
            partes.append("\n".join("- %s" % a for a in avisos) + "\n")

        self.stdout.write("\n".join(partes))
