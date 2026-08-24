"""Testes do comando ultimo_upload_ssh.

Rodar::

    .venv\\Scripts\\python.exe manage.py test core.tests_ultimo_upload_ssh
"""

import io

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from core.models import Hospital, Importacao


class UltimoUploadSshTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.hospital = Hospital.objects.create(nome="Hospital Teste", sigla="HT")

    def _run(self, **options):
        out = io.StringIO()
        call_command("ultimo_upload_ssh", stdout=out, **options)
        return out.getvalue()

    def test_sem_uploads_mostra_tracos(self):
        texto = self._run(hospital="HT")
        self.assertIn("Microbiologia: -", texto)
        self.assertIn("Antimicrobianos: -", texto)

    def test_com_uploads_mostra_datas(self):
        Importacao.objects.create(
            hospital=self.hospital, arquivo="micro.xlsx", tipo="microbiologia", registros=0,
        )
        Importacao.objects.create(
            hospital=self.hospital, arquivo="atb.xls", tipo="controle_atb", registros=2,
        )
        texto = self._run(hospital="HT")
        self.assertRegex(texto, r"Microbiologia: \d{4}-\d{2}-\d{2} \d{2}:\d{2}")
        self.assertRegex(texto, r"Antimicrobianos: \d{4}-\d{2}-\d{2} \d{2}:\d{2}")

    def test_nao_mostra_cobertura_nem_pacientes(self):
        texto = self._run(hospital="HT")
        self.assertNotIn("cobertura", texto.lower())
        self.assertNotIn("Paciente", texto)

    def test_hospital_invalido(self):
        with self.assertRaises(CommandError):
            self._run(hospital="XX")

    def test_hospital_inativo(self):
        Hospital.objects.create(nome="Inativo", sigla="IN", ativo=False)
        with self.assertRaises(CommandError):
            self._run(hospital="IN")
