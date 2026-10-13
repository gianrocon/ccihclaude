"""Periodos de ATB a partir das fichas do relatec atb: dias_em_uso e o D# do CURSO quando a ficha foi encerrada."""

from datetime import date

from django.test import SimpleTestCase

from core.services.patient_service import periodos_de_fichas


def d(dia, mes):
    return date(2026, mes, dia)


class PeriodosDeFichasTests(SimpleTestCase):
    def test_curso_continuo_com_prorrogacoes(self):
        # 20/08 (D10), 30/08 (D11), 31/08 (D21), 10/09 (D28), 17/09 (D35): um curso so, ate 24/09
        p = periodos_de_fichas([(d(20, 8), 10), (d(30, 8), 11), (d(31, 8), 21), (d(10, 9), 28), (d(17, 9), 35)])
        self.assertEqual(len(p), 1)
        self.assertEqual((p[0]["inicio"], p[0]["fim"], p[0]["fim_incerto"]), (d(20, 8), d(24, 9), False))

    def test_suspensao_e_reinicio_dentro_da_mesma_ficha(self):
        # prorrogacao de 24/09 encerrada com D6: o D# zerou (suspenso ~28/09, reinicio 03/10); proxima ficha 09/10 (D9)
        p = periodos_de_fichas([(d(20, 8), 10), (d(30, 8), 11), (d(31, 8), 21), (d(10, 9), 28), (d(17, 9), 35),
                                (d(24, 9), 6), (d(9, 10), 9)])
        self.assertEqual(len(p), 2)
        self.assertEqual((p[0]["inicio"], p[0]["fim"], p[0]["fim_incerto"]), (d(20, 8), d(24, 9), True))
        self.assertEqual((p[1]["inicio"], p[1]["fim"], p[1]["fim_incerto"]), (d(3, 10), d(12, 10), False))

    def test_intervalo_entre_fichas_abre_curso_novo(self):
        p = periodos_de_fichas([(d(1, 3), 10), (d(1, 5), 7)])
        self.assertEqual([(x["inicio"], x["fim"]) for x in p], [(d(1, 3), d(11, 3)), (d(1, 5), d(8, 5))])

    def test_d_zerado_no_inicio_da_ficha_e_uso_continuo(self):
        # troca de dose/item novo: D# recomeca na propria ficha, sem intervalo -> um periodo so
        p = periodos_de_fichas([(d(28, 7), 5), (d(1, 8), 1)])
        self.assertEqual([(x["inicio"], x["fim"], x["fim_incerto"]) for x in p], [(d(28, 7), d(2, 8), False)])

    def test_d_zerado_na_ultima_ficha_sem_proxima_e_uso_continuo(self):
        # sem ficha seguinte nao ha como datar um reinicio: trata como continuo
        p = periodos_de_fichas([(d(1, 9), 20), (d(21, 9), 3)])
        self.assertEqual([(x["inicio"], x["fim"], x["fim_incerto"]) for x in p], [(d(1, 9), d(24, 9), False)])
