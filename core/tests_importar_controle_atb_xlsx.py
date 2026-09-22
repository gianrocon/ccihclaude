"""Testes do importador de controle de antimicrobiano em .xlsx (novo formato
exportado pelo SMPEP, que substituiu o .xls). Ver core/services/importer_service.py.

Rodar::

    .venv\\Scripts\\python.exe manage.py test core.tests_importar_controle_atb_xlsx
"""

import tempfile
from datetime import date
from pathlib import Path

import openpyxl
from django.test import TestCase

from core.models import ControleAtbRaw, Hospital, Importacao, Paciente
from core.services.importer_service import importar_arquivo


def _xlsx_controle_atb(path: Path):
    """Reproduz a estrutura real exportada pelo SMPEP: cabeçalho da planilha,
    bloco 'Prontuário'/'Paciente'/'Acomodação' e, para cada paciente, um
    cabeçalho 'Início'/'Dias Solic.'/'Dias CCIH'/'Medicamento'/'Dias em
    uso'/'Médico' seguido das linhas de datas. A célula 'Medicamento' fica
    mesclada numa coluna diferente da coluna onde o valor realmente aparece
    nas linhas de dados — é essa mesclagem que quebrava o parser antigo."""
    wb = openpyxl.Workbook()
    ws = wb.active

    ws.append(["INSTITUTO FERNANDO FILGUEIRAS"] + [None] * 15 + ["SMPEP - Sistema de Gestão Hospitalar"])
    ws.append(["CNES: 0003778 - HOSPITAL TESTE"])
    ws.append(["Lista de Controle Antimicrobiano"])

    ws.append(["Prontuário", None, None, "Paciente", None, None, None, None,
               None, None, None, None, None, None, None, "Acomodação"])
    ws.append(["4679", None, None, "LIZANDRA GONCALVES SANTOS", None, None, None, None,
               None, None, None, None, None, None, None, "SAPH VIRTUAL 20"])

    ws.append(["Início", None, "Dias Solic.", None, "Dias CCIH", None, "Medicamento",
               None, None, None, None, None, None, None, "Dias em uso", None, None, "Médico"])
    ws.append([date(2026, 9, 1), None, 7, None, 7, None, None,
               "Nistatina 100.000 UI/mL FR 50mL", None, None, None, None, None, None,
               5, None, None, "IZABELLE FRAGA GOMES"])
    ws.append([date(2026, 9, 1), None, 7, None, 7, None, None,
               "meTRONidazol 250 mg COM REV", None, None, None, None, None, None,
               4, None, None, "IZABELLE FRAGA GOMES"])

    ws.append(["Prontuário", None, None, "Paciente", None, None, None, None,
               None, None, None, None, None, None, None, "Acomodação"])
    ws.append(["22224", None, None, "MARCIA MOREIRA DA SILVA", None, None, None, None,
               None, None, None, None, None, None, None, "INTERNAÇÃO P8 E012 L01"])

    ws.append(["Início", None, "Dias Solic.", None, "Dias CCIH", None, "Medicamento",
               None, None, None, None, None, None, None, "Dias em uso", None, None, "Médico"])
    ws.append([date(2026, 9, 2), None, 1, None, 1, None, None,
               "cefTRIAXona Sódica 1g PO SOL INJ EV", None, None, None, None, None, None,
               8, None, None, "LUCAS NASCIMENTO SOUZA"])

    ws.append(["Impresso em 22/09/2026 10:00"])

    wb.save(path)


class ImportarControleAtbXlsxTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.hospital = Hospital.objects.create(nome="Hospital Teste", sigla="HT")

    def test_importa_xlsx_com_colunas_mescladas(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "controle_atb.xlsx"
            _xlsx_controle_atb(path)
            tipo, n = importar_arquivo(path, self.hospital)

        self.assertEqual(tipo, "controle_atb")
        self.assertEqual(n, 3)
        self.assertEqual(
            ControleAtbRaw.objects.filter(paciente__hospital=self.hospital).count(), 3
        )

        pac = Paciente.objects.get(hospital=self.hospital, prontuario="4679")
        self.assertEqual(pac.nome, "LIZANDRA GONCALVES SANTOS")

        raw = ControleAtbRaw.objects.get(
            paciente=pac, medicamento="Nistatina 100.000 UI/mL FR 50mL"
        )
        self.assertEqual(raw.acomodacao, "SAPH VIRTUAL 20")
        self.assertEqual(raw.dias_solic, 7)
        self.assertEqual(raw.dias_ccih, 7)
        self.assertEqual(raw.dias_em_uso, 5)
        self.assertEqual(raw.medico, "IZABELLE FRAGA GOMES")
        self.assertEqual(raw.dt_inicio, date(2026, 9, 1))

        pac2 = Paciente.objects.get(hospital=self.hospital, prontuario="22224")
        self.assertEqual(pac2.nome, "MARCIA MOREIRA DA SILVA")

        imp = Importacao.objects.get(hospital=self.hospital, tipo="controle_atb")
        self.assertEqual(imp.registros, 3)

    def test_reimportar_mesmo_arquivo_nao_duplica(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "controle_atb.xlsx"
            _xlsx_controle_atb(path)
            importar_arquivo(path, self.hospital)
            tipo, n = importar_arquivo(path, self.hospital)

        self.assertEqual(tipo, "controle_atb")
        self.assertEqual(n, 0)
        self.assertEqual(
            ControleAtbRaw.objects.filter(paciente__hospital=self.hospital).count(), 3
        )
