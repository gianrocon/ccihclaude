"""Gantt em SVG/JS: o servidor so entrega dados (json_script), sem matplotlib."""

from datetime import date

from django.template.loader import render_to_string
from django.test import TestCase

from core.models import ControleAtbRaw, Hospital, Paciente
from core.services import chart_service


class GanttTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        h = Hospital.objects.create(nome="H", sigla="HT")
        cls.pac = Paciente.objects.create(hospital=h, prontuario="1", nome="P")
        ControleAtbRaw.objects.create(paciente=cls.pac, medicamento="MEROPENEM 1g", dt_inicio=date(2026, 9, 1), dias_em_uso=5)

    def test_dados_serializaveis(self):
        d = chart_service.dados_gantt_atb(self.pac)
        self.assertEqual(len(d), 1)
        self.assertEqual(d[0]["rotulo"], "MEROPENEM")
        self.assertEqual(d[0]["inicio"], "2026-09-01")
        self.assertFalse(d[0]["resistente"])

    def test_resistente_marcado(self):
        d = chart_service.dados_gantt_atb(self.pac, resistentes={"MEROPENEM"})
        self.assertTrue(d[0]["resistente"])

    def test_template_entrega_json_e_div(self):
        html = render_to_string("core/_tab_atb.html", {
            "periodos_atb": [{"medicamento": "X", "inicio": date(2026, 9, 1), "fim": date(2026, 9, 3), "total_dias": 3}],
            "gantt_atb": [{"rotulo": "X", "nome": "X", "inicio": "2026-09-01", "fim": "2026-09-03", "dias": 3, "resistente": False}],
        })
        self.assertIn('data-gantt="gantt-atb-dados"', html)
        self.assertIn('id="gantt-atb-dados"', html)
        self.assertNotIn("image/png", html)
