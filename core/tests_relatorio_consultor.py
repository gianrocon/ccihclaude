"""Testes do comando relatorio_consultor.

Rodar::

    .venv\\Scripts\\python.exe manage.py test core.tests_relatorio_consultor
"""

import io
from datetime import date

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from core.models import Antibiograma, ControleAtbRaw, Cultura, Hospital, Paciente


class RelatorioConsultorTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.hospital = Hospital.objects.create(nome="Hospital Teste", sigla="HT")

        cultura = Cultura.objects.create(
            paciente=Paciente.objects.create(
                hospital=cls.hospital, prontuario="12345", nome="PACIENTE TESTE"
            ),
            os="OS-1",
            dt_coleta=date(2026, 7, 30),
            procedimento="HEMOCULTURA",
            microrganismo="Klebsiella pneumoniae",
        )
        cls.paciente = cultura.paciente
        Antibiograma.objects.create(cultura=cultura, antibiotico="MEROPENEM", sensibilidade="R")

        ControleAtbRaw.objects.create(
            paciente=cls.paciente,
            medicamento="MEROPENEM 1g PO LIOF INJ",
            dt_inicio=date(2026, 7, 28),
            dias_em_uso=5,
        )

    def _run(self, **options):
        out = io.StringIO()
        call_command("relatorio_consultor", stdout=out, **options)
        return out.getvalue()

    def test_cobertura_sem_prontuarios(self):
        texto = self._run(hospital="HT")
        self.assertIn("# Relatorio - Hospital Teste (HT)", texto)
        self.assertIn("## Cobertura de dados importados", texto)
        self.assertIn("### Culturas (microbiologia)", texto)
        self.assertIn("2026-07-30 a 2026-07-30", texto)
        self.assertIn("### Prescricoes de antibiotico", texto)
        self.assertIn("2026-07-28 a 2026-07-28", texto)
        self.assertNotIn("## Paciente", texto)

    def test_hospital_invalido_leva_commanderror(self):
        with self.assertRaises(CommandError):
            self._run(hospital="XX")

    def test_hospital_inativo_leva_commanderror(self):
        Hospital.objects.create(nome="Inativo", sigla="IN", ativo=False)
        with self.assertRaises(CommandError):
            self._run(hospital="IN")

    def test_paciente_com_culturas_e_atb(self):
        texto = self._run(hospital="HT", prontuarios="12345")
        self.assertIn("## Paciente 12345 - PACIENTE TESTE", texto)
        self.assertIn("### Culturas", texto)
        self.assertIn("Klebsiella pneumoniae", texto)
        self.assertIn("MEROPENEM: R", texto)
        self.assertIn("### Uso de antibiotico", texto)
        self.assertIn("| MEROPENEM | 2026-07-28 |", texto)
        self.assertNotIn("## Avisos", texto)

    def test_prontuario_inexistente_vira_aviso_sem_abortar(self):
        texto = self._run(hospital="HT", prontuarios="12345,99999")
        self.assertIn("## Paciente 12345 - PACIENTE TESTE", texto)
        self.assertIn("## Avisos", texto)
        self.assertIn("Prontuario 99999 nao encontrado no hospital HT", texto)

    def test_paciente_sem_culturas_nem_atb_mostra_nenhum_registro(self):
        Paciente.objects.create(hospital=self.hospital, prontuario="55555", nome="SEM DADOS")
        texto = self._run(hospital="HT", prontuarios="55555")
        self.assertIn("## Paciente 55555 - SEM DADOS", texto)
        self.assertIn("Nenhum registro.", texto)

    def test_prontuario_com_zeros_a_esquerda(self):
        texto = self._run(hospital="HT", prontuarios="0012345")
        self.assertIn("## Paciente 12345 - PACIENTE TESTE", texto)
