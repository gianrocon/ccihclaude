r"""Testes: planilha de outro hospital e medico da linha com mais dias.

Rodar::

    .venv\Scripts\python.exe manage.py test core.tests_hospital_e_medico
"""

import tempfile
from datetime import date
from pathlib import Path

import openpyxl
from django.test import TestCase

from core.models import ControleAtbRaw, Hospital
from core.services.importer_service import importar_controle_atb, importar_microbiologia


def _atb(path: Path, cnes="0003778", linhas=()):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["INSTITUTO"])
    ws.append(["CNES: %s - HOSPITAL TESTE" % cnes])
    ws.append(["Lista de Controle Antimicrobiano"])
    ws.append(["Prontuário", None, None, "Paciente", None, None, None, None,
               None, None, None, None, None, None, None, "Acomodação"])
    ws.append(["4679", None, None, "PACIENTE TESTE", None, None, None, None,
               None, None, None, None, None, None, None, "LEITO 1"])
    ws.append(["Início", None, "Dias Solic.", None, "Dias CCIH", None, "Medicamento",
               None, None, None, None, None, None, None, "Dias em uso", None, None, "Médico"])
    for dias, medico in linhas:
        ws.append([date(2026, 9, 10), None, dias, None, dias, None, None,
                   "ceftriaxona 1g", None, None, None, None, None, None,
                   2, None, None, medico])
    ws.append(["Impresso em 22/09/2026 10:00"])
    wb.save(path)


def _micro(path: Path, origem="HCB"):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Relatório de microbiologia detalhado"])
    ws.append(["PARAMETROS: Origem: %s, Data Inicial: 01/09/2026, Data Final: 07/09/2026" % origem])
    ws.append(["OS", "Prontuário", "Nome Pac."])
    wb.save(path)


class ChecagemHospitalTestCase(TestCase):
    def setUp(self):
        self.hm = Hospital.objects.create(nome="Hospital da Mulher", sigla="HM", cnes="0003778")
        self.hpel = Hospital.objects.create(nome="HPEL", sigla="HPEL", cnes="0003980")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def _f(self, nome):
        return Path(self.tmp.name) / nome

    def test_atb_de_outro_hospital_e_recusado(self):
        f = self._f("a.xlsx"); _atb(f, cnes="0003980", linhas=[(7, "DR A")])
        with self.assertRaises(ValueError):
            importar_controle_atb(f, self.hm)
        self.assertEqual(ControleAtbRaw.objects.count(), 0)

    def test_atb_do_proprio_hospital_importa(self):
        f = self._f("a.xlsx"); _atb(f, cnes="0003778", linhas=[(7, "DR A")])
        self.assertEqual(importar_controle_atb(f, self.hm), 1)

    def test_hospital_sem_cnes_nao_bloqueia_se_cnes_do_arquivo_e_desconhecido(self):
        h = Hospital.objects.create(nome="Novo", sigla="NOVO")
        f = self._f("a.xlsx"); _atb(f, cnes="9999999", linhas=[(7, "DR A")])
        self.assertEqual(importar_controle_atb(f, h), 1)

    def test_hospital_sem_cnes_recusa_cnes_de_outro_cadastrado(self):
        h = Hospital.objects.create(nome="Novo", sigla="NOVO")
        f = self._f("a.xlsx"); _atb(f, cnes="0003980", linhas=[(7, "DR A")])
        with self.assertRaises(ValueError):
            importar_controle_atb(f, h)

    def test_micro_origem_de_outro_hospital_e_recusada(self):
        Hospital.objects.create(nome="HCB", sigla="HCB")
        f = self._f("m.xlsx"); _micro(f, origem="HCB")
        with self.assertRaises(ValueError):
            importar_microbiologia(f, self.hm)

    def test_micro_origem_desconhecida_nao_bloqueia(self):
        f = self._f("m.xlsx"); _micro(f, origem="QUALQUER")
        importar_microbiologia(f, self.hm)  # nao levanta


class MedicoMaiorTempoTestCase(TestCase):
    def setUp(self):
        self.h = Hospital.objects.create(nome="H", sigla="H")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def _imp(self, linhas):
        f = Path(self.tmp.name) / "a.xlsx"; _atb(f, linhas=linhas)
        importar_controle_atb(f, self.h)
        return ControleAtbRaw.objects.get()

    def test_medico_e_o_da_linha_com_mais_dias(self):
        r = self._imp([(3, "DR A"), (7, "DR B")])
        self.assertEqual((r.dias_solic, r.medico), (7, "DR B"))

    def test_ordem_inversa_mantem_o_de_mais_dias(self):
        r = self._imp([(7, "DR B"), (3, "DR A")])
        self.assertEqual((r.dias_solic, r.medico), (7, "DR B"))
