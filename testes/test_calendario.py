import unittest
from datetime import date

from nucleo.calendario import Ausencia, Calendario, feriados, pascoa


class TestFeriados(unittest.TestCase):
    def test_pascoa(self):
        self.assertEqual(pascoa(2026), date(2026, 4, 5))
        self.assertEqual(pascoa(2027), date(2027, 3, 28))
        self.assertEqual(pascoa(2024), date(2024, 3, 31))

    def test_feriados_de_osasco_2026(self):
        datas = {d: nome for d, nome, _ in feriados(2026)}
        self.assertIn(date(2026, 2, 19), datas)   # emancipação
        self.assertEqual(datas[date(2026, 4, 3)], "Paixão de Cristo")
        self.assertEqual(datas[date(2026, 6, 4)], "Corpus Christi")
        self.assertIn(date(2026, 6, 13), datas)   # Santo Antônio
        self.assertIn(date(2026, 7, 9), datas)    # estadual SP
        self.assertIn(date(2026, 11, 20), datas)  # consciência negra
        self.assertEqual(len(datas), 14)

    def test_sem_municipais(self):
        self.assertEqual(len(feriados(2026, incluir_osasco=False)), 10)


class TestCapacidade(unittest.TestCase):
    def setUp(self):
        self.cal = Calendario(ausencias=[
            Ausencia("Feriado", date(2026, 11, 2), date(2026, 11, 2), "Finados"),
            Ausencia("Meio período", date(2026, 10, 30), date(2026, 10, 30)),
            Ausencia("Férias", date(2026, 11, 9), date(2026, 11, 13)),
        ], capacidade_especifica={date(2026, 10, 29): 120})

    def test_capacidades(self):
        self.assertEqual(self.cal.capacidade(date(2026, 10, 26)), 300)  # segunda normal
        self.assertEqual(self.cal.capacidade(date(2026, 10, 29)), 120)  # ajustada
        self.assertEqual(self.cal.capacidade(date(2026, 10, 30)), 150)  # meio período
        self.assertEqual(self.cal.capacidade(date(2026, 10, 31)), 0)    # sábado
        self.assertEqual(self.cal.capacidade(date(2026, 11, 2)), 0)     # feriado
        self.assertEqual(self.cal.capacidade(date(2026, 11, 11)), 0)    # férias

    def test_dias_de_trabalho_pulam_folgas(self):
        dias = self.cal.dias_de_trabalho(date(2026, 10, 29), 3)
        self.assertEqual(dias, [date(2026, 10, 29), date(2026, 10, 30), date(2026, 11, 3)])

    def test_dia_nao_util(self):
        cal = Calendario(dias_uteis=frozenset({0, 1, 3, 4}))  # quarta desligada
        self.assertEqual(cal.capacidade(date(2026, 10, 28)), 0)
        self.assertEqual(cal.motivo_folga(date(2026, 10, 28)), "Dia não útil")


if __name__ == "__main__":
    unittest.main()
