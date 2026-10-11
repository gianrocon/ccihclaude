"""Testes de /api/v1/cobertura/ e /api/v1/importar/ (importacao por token, sem SSH).

Rodar::

    .venv\\Scripts\\python.exe manage.py test core.tests_api_escrita
"""

from datetime import date
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from core.models import ControleAtbRaw, Cultura, Hospital, Paciente
from core.tests_api import AUTH, _patch_token


class CoberturaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.hospital = Hospital.objects.create(nome="Hospital Teste", sigla="HT")
        pac = Paciente.objects.create(hospital=cls.hospital, prontuario="1", nome="P")
        Cultura.objects.create(paciente=pac, os="A", procedimento="X", dt_coleta=date(2026, 9, 1))
        Cultura.objects.create(paciente=pac, os="B", procedimento="X", dt_coleta=date(2026, 9, 19))
        ControleAtbRaw.objects.create(paciente=pac, medicamento="VANCO", dt_inicio=date(2026, 8, 23))

    def setUp(self):
        _patch_token()

    def test_exige_token(self):
        self.assertEqual(self.client.get("/api/v1/cobertura/?hospital=HT").status_code, 401)

    def test_intervalos_e_upload(self):
        r = self.client.get("/api/v1/cobertura/?hospital=HT", **AUTH)
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual(d["microbiologia"]["cobertura"][-1]["fim"], "2026-09-19")
        self.assertEqual(d["antimicrobianos"]["cobertura"][-1]["fim"], "2026-08-23")
        self.assertIsNone(d["microbiologia"]["ultimo_upload"])


class ImportarTests(TestCase):
    URL = "/api/v1/importar/?hospital=HT&tipo=microbiologia"

    @classmethod
    def setUpTestData(cls):
        cls.hospital = Hospital.objects.create(nome="Hospital Teste", sigla="HT")

    def setUp(self):
        _patch_token()

    def _arq(self, nome="relatec-micro.xlsx"):
        return SimpleUploadedFile(nome, b"PK\x03\x04conteudo", content_type="application/octet-stream")

    def test_get_nao_permitido(self):
        self.assertEqual(self.client.get(self.URL, **AUTH).status_code, 405)

    def test_sem_token_401(self):
        r = self.client.post(self.URL, {"arquivo": self._arq()})
        self.assertEqual(r.status_code, 401)

    def test_falha_fechada_sem_token_configurado(self):
        _patch_token("")
        self.assertEqual(self.client.post(self.URL, {"arquivo": self._arq()}, **AUTH).status_code, 503)

    def test_tipo_invalido_400(self):
        r = self.client.post("/api/v1/importar/?hospital=HT&tipo=passagens", {"arquivo": self._arq()}, **AUTH)
        self.assertEqual(r.status_code, 400)

    def test_sem_arquivo_400(self):
        self.assertEqual(self.client.post(self.URL, {}, **AUTH).status_code, 400)

    def test_extensao_errada_400(self):
        r = self.client.post(self.URL, {"arquivo": self._arq("x.xls")}, **AUTH)
        self.assertEqual(r.status_code, 400)

    def test_hospital_desconhecido_404(self):
        r = self.client.post("/api/v1/importar/?hospital=ZZ&tipo=microbiologia", {"arquivo": self._arq()}, **AUTH)
        self.assertEqual(r.status_code, 404)

    def test_sucesso_chama_importador_validado(self):
        with mock.patch("core.views.api_views.importer_service.importar_com_validacao", return_value=7) as imp:
            r = self.client.post(self.URL, {"arquivo": self._arq()}, **AUTH)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"tipo": "microbiologia", "hospital": "HT", "registros": 7})
        path, hosp, usuario, tipo = imp.call_args[0]
        self.assertEqual(path.name, "relatec-micro.xlsx")  # nome original preservado
        self.assertEqual((hosp, usuario, tipo), (self.hospital, None, "microbiologia"))

    def test_recusa_da_validacao_vira_400(self):
        with mock.patch("core.views.api_views.importer_service.importar_com_validacao",
                        side_effect=ValueError("planilha de outro hospital")):
            r = self.client.post(self.URL, {"arquivo": self._arq()}, **AUTH)
        self.assertEqual(r.status_code, 400)
        self.assertIn("outro hospital", r.json()["erro"])
