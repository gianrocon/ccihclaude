"""Testes da API JSON somente-leitura (/api/v1/).

Rodar::

    .venv\\Scripts\\python.exe manage.py test core.tests_api
"""

import json
from datetime import date

from django.test import TestCase, override_settings

from core.models import (
    Antibiograma,
    ControleAtbRaw,
    Cultura,
    Hospital,
    Paciente,
)

TOKEN = "token-de-teste-nao-usar-em-producao"
AUTH = {"HTTP_AUTHORIZATION": "Bearer %s" % TOKEN}


def _patch_token(valor=TOKEN):
    """``config()`` do decouple lê no import; sobrescrever direto no módulo."""
    from core.views import api_views

    api_views.config = lambda chave, default=None, **kw: (
        valor if chave == "API_TOKEN" else default
    )


class ApiTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.hospital = Hospital.objects.create(nome="Hospital Teste", sigla="HT")
        cls.outro = Hospital.objects.create(nome="Outro Hospital", sigla="HO")

        cls.paciente = Paciente.objects.create(
            hospital=cls.hospital, prontuario="12345", nome="PACIENTE TESTE"
        )
        # Homônimo de prontuário em OUTRO hospital: não pode vazar entre hospitais.
        Paciente.objects.create(
            hospital=cls.outro, prontuario="12345", nome="OUTRO PACIENTE"
        )

        cultura = Cultura.objects.create(
            paciente=cls.paciente,
            os="OS-1",
            unidade="UTI",
            dt_coleta=date(2026, 7, 30),
            dt_assinatura=date(2026, 8, 2),
            procedimento="HEMOCULTURA PARA AEROBIOS - 1a AMOSTRA",
            microrganismo="Klebsiella pneumoniae",
        )
        Antibiograma.objects.create(
            cultura=cultura, antibiotico="MEROPENEM", sensibilidade="R"
        )
        Antibiograma.objects.create(
            cultura=cultura, antibiotico="AMICACINA", sensibilidade="S"
        )

        ControleAtbRaw.objects.create(
            paciente=cls.paciente,
            acomodacao="UTI E01 L03",
            medicamento="MEROPENEM 1g PO LIOF INJ",
            dt_inicio=date(2026, 7, 28),
            dias_solic=14,
            dias_em_uso=5,
        )
        ControleAtbRaw.objects.create(
            paciente=cls.paciente,
            acomodacao="UTI E01 L03",
            medicamento="MEROPENEM 2g PO LIOF INJ",
            dt_inicio=date(2026, 8, 1),
            dias_solic=10,
            dias_em_uso=1,
        )

    def setUp(self):
        _patch_token()

    # ----------------------------------------------------------------- auth

    def test_sem_token_responde_401(self):
        r = self.client.get("/api/v1/hospitais/")
        self.assertEqual(r.status_code, 401)

    def test_token_errado_responde_401(self):
        r = self.client.get(
            "/api/v1/hospitais/", HTTP_AUTHORIZATION="Bearer token-errado"
        )
        self.assertEqual(r.status_code, 401)

    def test_sem_token_configurado_falha_fechada(self):
        _patch_token("")
        r = self.client.get("/api/v1/hospitais/", **AUTH)
        self.assertEqual(r.status_code, 503)

    def test_post_e_rejeitado(self):
        r = self.client.post("/api/v1/hospitais/", **AUTH)
        self.assertEqual(r.status_code, 405)

    # ------------------------------------------------------------ hospitais

    def test_lista_hospitais(self):
        r = self.client.get("/api/v1/hospitais/", **AUTH)
        self.assertEqual(r.status_code, 200)
        siglas = [h["sigla"] for h in r.json()["hospitais"]]
        self.assertEqual(siglas, ["HO", "HT"])

    # ------------------------------------------------------------- paciente

    def test_hospital_obrigatorio(self):
        r = self.client.get("/api/v1/paciente/?prontuario=12345", **AUTH)
        self.assertEqual(r.status_code, 400)
        self.assertIn("hospitais", r.json())

    def test_hospital_inexistente_responde_404(self):
        r = self.client.get(
            "/api/v1/paciente/?prontuario=12345&hospital=XX", **AUTH
        )
        self.assertEqual(r.status_code, 404)

    def test_paciente_completo(self):
        r = self.client.get(
            "/api/v1/paciente/?prontuario=12345&hospital=HT", **AUTH
        )
        self.assertEqual(r.status_code, 200)
        d = r.json()

        self.assertEqual(d["paciente"]["nome"], "PACIENTE TESTE")
        self.assertEqual(d["hospital"], "HT")

        # cultura com antibiograma ordenado S -> I -> R
        self.assertEqual(len(d["culturas"]), 1)
        cultura = d["culturas"][0]
        self.assertEqual(cultura["microrganismo"], "Klebsiella pneumoniae")
        self.assertIn("HEMOCULTURA", cultura["sitio"])
        self.assertEqual(
            [a["antibiotico"] for a in cultura["antibiograma"]],
            ["AMICACINA", "MEROPENEM"],
        )
        self.assertEqual(d["resistentes_na_ultima_cultura"], ["MEROPENEM"])

        # registros crus preservam as duas doses...
        doses = sorted(r["medicamento"] for r in d["atb_raw"])
        self.assertEqual(len(doses), 2)
        self.assertIn("1g", doses[0])
        self.assertIn("2g", doses[1])

        # ...enquanto os periodos fundem tudo num "MEROPENEM" so.
        # E exatamente por isso que os dois sao devolvidos.
        self.assertEqual([p["medicamento"] for p in d["atb_periodos"]], ["MEROPENEM"])

        self.assertTrue(d["_avisos"])

    def test_nao_vaza_entre_hospitais(self):
        r = self.client.get(
            "/api/v1/paciente/?prontuario=12345&hospital=HO", **AUTH
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["paciente"]["nome"], "OUTRO PACIENTE")
        self.assertEqual(r.json()["culturas"], [])

    def test_prontuario_com_zeros_a_esquerda(self):
        r = self.client.get(
            "/api/v1/paciente/?prontuario=0012345&hospital=HT", **AUTH
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["paciente"]["prontuario"], "12345")

    def test_paciente_inexistente_da_dica(self):
        r = self.client.get(
            "/api/v1/paciente/?prontuario=99999&hospital=HT", **AUTH
        )
        self.assertEqual(r.status_code, 404)
        self.assertIn("dica", r.json())

    # ------------------------------------------------------------ formulario

    def test_formulario_normaliza_e_deduplica(self):
        r = self.client.get("/api/v1/formulario/?hospital=HT", **AUTH)
        self.assertEqual(r.status_code, 200)
        d = r.json()
        # As duas doses de meropenem colapsam num item so
        self.assertEqual(d["total"], 1)
        item = d["antimicrobianos"][0]
        self.assertEqual(item["nome"], "MEROPENEM")
        self.assertEqual(item["n_prescricoes"], 2)
        self.assertEqual(item["primeira"], "2026-07-28")
        self.assertEqual(item["ultima"], "2026-08-01")

    def test_formulario_vazio_em_hospital_sem_dados(self):
        r = self.client.get("/api/v1/formulario/?hospital=HO", **AUTH)
        self.assertEqual(r.json()["total"], 0)

    # ------------------------------------------------------------- pacientes

    def test_busca_por_nome(self):
        r = self.client.get("/api/v1/pacientes/?q=TESTE&hospital=HT", **AUTH)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["total"], 1)
        self.assertEqual(r.json()["pacientes"][0]["prontuario"], "12345")

    def test_busca_sem_termo_responde_400(self):
        r = self.client.get("/api/v1/pacientes/?hospital=HT", **AUTH)
        self.assertEqual(r.status_code, 400)
