"""Testes dos comandos importar_microbiologia_ssh / importar_atb_ssh.

Rodar::

    .venv\\Scripts\\python.exe manage.py test core.tests_importar_ssh
"""

import io
import tempfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

import openpyxl
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from core.models import CustomUser, Hospital, Importacao


def _xlsx_microbiologia(path: Path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["RELATORIO DE MICROBIOLOGIA"])
    ws.append([
        "OS", "Prontuario", "Nome Paciente", "Unidade", "Coleta", "Assinatura",
        "Procedimento", "Microrganismo", "Resistente", "Sensivel", "Intermediario", "Obs", "Trat",
    ])
    ws.append([
        "100", "99999", "TESTE SSH", "UTI", date(2026, 8, 1), date(2026, 8, 2),
        "HEMOCULTURA", "E. coli", "MEROPENEM", "AMICACINA", "", "", "",
    ])
    wb.save(path)


def _xlsx_outro_tipo(path: Path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["CONTROLE DE ANTIMICROBIANO"])
    wb.save(path)


class ImportarMicrobiologiaSshTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.hospital = Hospital.objects.create(nome="Hospital Teste", sigla="HT")
        cls.usuario = CustomUser.objects.create(username="carregador1")

    def _run(self, **options):
        out = io.StringIO()
        call_command("importar_microbiologia_ssh", stdout=out, **options)
        return out.getvalue()

    def test_importa_com_sucesso_e_registra_upload(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "micro.xlsx"
            _xlsx_microbiologia(path)
            texto = self._run(hospital="HT", arquivo=str(path), usuario="carregador1")

        self.assertIn("1 registro(s) importado(s)", texto)
        imp = Importacao.objects.get(hospital=self.hospital, tipo="microbiologia")
        self.assertEqual(imp.registros, 1)
        self.assertEqual(imp.usuario, self.usuario)

    def test_arquivo_de_outro_tipo_e_recusado(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nao_e_micro.xlsx"
            _xlsx_outro_tipo(path)
            with self.assertRaises(CommandError):
                self._run(hospital="HT", arquivo=str(path))
        self.assertFalse(Importacao.objects.filter(hospital=self.hospital).exists())

    def test_extensao_errada_e_recusada(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "arquivo.xls"
            path.write_bytes(b"fake")
            with self.assertRaises(CommandError):
                self._run(hospital="HT", arquivo=str(path))

    def test_arquivo_inexistente(self):
        with self.assertRaises(CommandError):
            self._run(hospital="HT", arquivo="/caminho/que/nao/existe.xlsx")

    def test_hospital_invalido(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "micro.xlsx"
            _xlsx_microbiologia(path)
            with self.assertRaises(CommandError):
                self._run(hospital="XX", arquivo=str(path))

    def test_usuario_inexistente(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "micro.xlsx"
            _xlsx_microbiologia(path)
            with self.assertRaises(CommandError):
                self._run(hospital="HT", arquivo=str(path), usuario="ninguem")

    def test_upload_repetido_sem_registro_novo_ainda_atualiza_data_de_upload(self):
        from core.services import patient_service as svc

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "micro.xlsx"
            _xlsx_microbiologia(path)
            self._run(hospital="HT", arquivo=str(path))
            primeira = svc.get_ultima_importacao(self.hospital, "microbiologia")
            self._run(hospital="HT", arquivo=str(path))
            segunda = svc.get_ultima_importacao(self.hospital, "microbiologia")

        self.assertEqual(Importacao.objects.filter(hospital=self.hospital, tipo="microbiologia").count(), 2)
        self.assertGreaterEqual(segunda, primeira)


class ImportarAtbSshTestCase(TestCase):
    """.xls nao pode ser gerado sem xlwt (nao instalado neste projeto), entao
    o caminho feliz e testado via mock de importar_com_validacao; as
    validacoes de argumento (hospital/extensao/arquivo) rodam sem mock."""

    @classmethod
    def setUpTestData(cls):
        cls.hospital = Hospital.objects.create(nome="Hospital Teste", sigla="HT")

    def _run(self, **options):
        out = io.StringIO()
        call_command("importar_atb_ssh", stdout=out, **options)
        return out.getvalue()

    def test_extensao_errada_e_recusada(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "arquivo.xlsx"
            path.write_bytes(b"fake")
            with self.assertRaises(CommandError):
                self._run(hospital="HT", arquivo=str(path))

    def test_hospital_invalido(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "atb.xls"
            path.write_bytes(b"fake")
            with self.assertRaises(CommandError):
                self._run(hospital="XX", arquivo=str(path))

    @patch("core.services.importer_service.importar_com_validacao")
    def test_chama_importar_com_validacao_com_tipo_controle_atb(self, mock_importar):
        mock_importar.return_value = 3
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "atb.xls"
            path.write_bytes(b"fake")
            texto = self._run(hospital="HT", arquivo=str(path))

        self.assertIn("3 registro(s) importado(s)", texto)
        args, _ = mock_importar.call_args
        self.assertEqual(args[0], path)
        self.assertEqual(args[1], self.hospital)
        self.assertIsNone(args[2])
        self.assertEqual(args[3], "controle_atb")

    @patch("core.services.importer_service.importar_com_validacao")
    def test_arquivo_de_outro_tipo_e_recusado(self, mock_importar):
        mock_importar.side_effect = ValueError("Arquivo nao reconhecido como 'controle_atb'")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "atb.xls"
            path.write_bytes(b"fake")
            with self.assertRaises(CommandError):
                self._run(hospital="HT", arquivo=str(path))
