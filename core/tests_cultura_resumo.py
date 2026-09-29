"""Testes do resumo copiável das culturas positivas.

Rodar::

    .venv\\Scripts\\python.exe manage.py test core.tests_cultura_resumo
"""

from datetime import date
from types import SimpleNamespace as N

from django.test import SimpleTestCase, TestCase

from core.models import Antibiograma, Cultura, Hospital, Paciente, Vinculo
from core.services.cultura_resumo_service import (
    antibioticos_da_obs,
    sigla_antibiotico,
    texto_culturas_positivas,
)


def _cult(proc, micro, obs="", dia=1):
    return N(procedimento=proc, microrganismo=micro, obs=obs,
             dt_coleta=date(2026, 9, dia), dt_assinatura=None)


def _atb(nome, sens):
    return N(antibiotico=nome, sensibilidade=sens)


class SiglaTests(SimpleTestCase):
    def test_siglas(self):
        casos = {
            "SULFAMETOXAZOL/TRIMETOPRIM": "SXT",
            "AMPICILINA/SULBACTAM": "SAM",
            "AMPICILINA": "AMP",
            "PIPERACILINA/TAZOBACTAM": "TZP",
            "CEFTAZIDIMA/AVIBACTAM": "CZA",
            "CEFTAZIDIMA": "CAZ",
            "CEFEPIMA": "FEP",
            "MEROPENEM": "MEM",
            "IMIPENEM": "IPM",
            "Ciprofloxacino": "CIP",
            "CEFTRIAXONA": "CRO",
            "POLIMIXINA B": "PMB",
        }
        for nome, sigla in casos.items():
            self.assertEqual(sigla_antibiotico(nome), sigla, nome)


class ObsTests(SimpleTestCase):
    def test_extrai_status_da_obs(self):
        self.assertEqual(antibioticos_da_obs("Sensível à vancomicina."), {"VAN": "S"})
        self.assertEqual(antibioticos_da_obs("Polimixina B: sensível"), {"PMB": "S"})
        self.assertEqual(antibioticos_da_obs("VANCOMICINA: S; POLIMIXINA B = R"),
                         {"VAN": "S", "PMB": "R"})
        self.assertEqual(
            antibioticos_da_obs("Resistente a oxacilina, sensível a vancomicina e linezolida"),
            {"OXA": "R", "VAN": "S", "LNZ": "S"},
        )

    def test_trecho_ambiguo_ignorado(self):
        self.assertEqual(antibioticos_da_obs("Teste de sensibilidade realizado"), {})


class TextoTests(SimpleTestCase):
    def test_formato_e_filtros(self):
        itens = [
            {"cultura": _cult("CULTURA DE VIGILÂNCIA", "Klebsiella pneumoniae", "Produtor de KPC"),
             "antibiograma": [_atb("MEROPENEM", "R"), _atb("AMICACINA", "S"),
                              _atb("PIPERACILINA/TAZOBACTAM", "R"), _atb("CIPROFLOXACINO", "I")]},
            {"cultura": _cult("CULTURA DE SWAB RETAL", "Klebsiella pneumoniae"),
             "antibiograma": [_atb("MEROPENEM", "R")]},
            {"cultura": _cult("HEMOCULTURA", "Staphylococcus aureus", "Sensível à vancomicina.", 2),
             "antibiograma": [_atb("OXACILINA", "R"), _atb("CLINDAMICINA", "R"),
                              _atb("SULFAMETOXAZOL/TRIMETOPRIM", "S")]},
            {"cultura": _cult("CULTURA DE LÍQUIDO", "Acinetobacter baumannii", "Polimixina B: sensível", 3),
             "antibiograma": [_atb("MEROPENEM", "R"), _atb("AMPICILINA/SULBACTAM", "I"),
                              _atb("AMICACINA", "S")]},
            {"cultura": _cult("UROCULTURA", "Negativo"), "antibiograma": []},
            {"cultura": _cult("UROCULTURA", "Enterococcus faecalis", dia=4),
             "antibiograma": [_atb("VANCOMICINA", "S"), _atb("AMPICILINA", "S"),
                              _atb("NITROFURANTOINA", "S")]},
            {"cultura": _cult("UROCULTURA", "Proteus mirabilis", dia=5),
             "antibiograma": [_atb("CEFTAZIDIMA/AVIBACTAM", "S"), _atb("CEFTAZIDIMA", "R")]},
        ]
        self.assertEqual(texto_culturas_positivas(itens).splitlines(), [
            "CULTURA DE VIGILÂNCIA - 01/09/2026 - Produtor de KPC - Klebsiella pneumoniae: MEM-R CIP-I TZP-R.",
            "HEMOCULTURA - 02/09/2026 - Sensível à vancomicina - Staphylococcus aureus: SXT-S OXA-R VAN-S.",
            "CULTURA DE LÍQUIDO - 03/09/2026 - Polimixina B: sensível - Acinetobacter baumannii: MEM-R SAM-I PMB-S.",
            "UROCULTURA - 04/09/2026 - Enterococcus faecalis: AMP-S VAN-S.",
            "UROCULTURA - 05/09/2026 - Proteus mirabilis: CAZ-R.",
        ])

    def test_microrganismo_fora_dos_paineis_traz_tudo(self):
        itens = [{"cultura": _cult("HEMOCULTURA", "Staphylococcus epidermidis"),
                  "antibiograma": [_atb("OXACILINA", "R"), _atb("LINEZOLIDA", "S")]}]
        self.assertEqual(texto_culturas_positivas(itens),
                         "HEMOCULTURA - 01/09/2026 - Staphylococcus epidermidis: OXA-R LNZ-S.")


class ViewTests(TestCase):
    def test_botao_na_aba_culturas(self):
        from django.contrib.auth import get_user_model

        hospital = Hospital.objects.create(nome="Hospital Teste", sigla="HT")
        user = get_user_model().objects.create_user("u", password="x")
        Vinculo.objects.create(usuario=user, hospital=hospital, papel="consultor")
        pac = Paciente.objects.create(hospital=hospital, prontuario="1", nome="Fulano")
        c = Cultura.objects.create(paciente=pac, os="10", procedimento="HEMOCULTURA",
                                   microrganismo="Staphylococcus aureus",
                                   obs="Vancomicina: sensível", dt_coleta=date(2026, 9, 1))
        Antibiograma.objects.create(cultura=c, antibiotico="OXACILINA", sensibilidade="R")

        self.client.force_login(user)
        from django.urls import reverse
        resp = self.client.get(reverse("paciente_detalhe", args=[pac.pk]))
        self.assertContains(resp, "HEMOCULTURA - 01/09/2026 - Vancomicina: sensível - "
                                  "Staphylococcus aureus: OXA-R VAN-S.")
        self.assertContains(resp, 'data-copiar="culturas-copia-texto"')
