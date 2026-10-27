import unittest
from datetime import date, timedelta

from nucleo.captura import formata_minutos, le_captura, le_dia, le_duracao

SEG = date(2026, 10, 26)  # segunda-feira


class TestCaptura(unittest.TestCase):
    def test_exemplo_do_manual(self):
        c = le_captura("consolidar riscos #alfa g até qui !", SEG)
        self.assertEqual(c.titulo, "consolidar riscos")
        self.assertEqual(c.minutos, 240)
        self.assertEqual(c.projeto, "alfa")
        self.assertEqual(c.prazo, date(2026, 10, 29))
        self.assertEqual(c.importancia, 1)
        self.assertIsNone(c.data_fixa)

    def test_so_texto_usa_padroes(self):
        c = le_captura("ligar para o fornecedor", SEG)
        self.assertEqual(c.titulo, "ligar para o fornecedor")
        self.assertIsNone(c.minutos)
        self.assertIn("2h (padrão)", c.descricao())
        self.assertIn("encaixe automático", c.descricao())

    def test_tempos(self):
        self.assertEqual(le_captura("e-mail Ana 15min", SEG).minutos, 15)
        self.assertEqual(le_captura("relatório 1h30", SEG).minutos, 90)
        self.assertEqual(le_captura("ligar 2min", SEG).minutos, 2)
        self.assertEqual(le_duracao("1,5h"), 90)
        self.assertEqual(le_duracao("20", aceitar_numero=True), 20)
        self.assertIsNone(le_duracao("20"))

    def test_numero_solto_fica_no_titulo(self):
        self.assertEqual(le_captura("revisar item 3 do contrato", SEG).titulo, "revisar item 3 do contrato")

    def test_data_fixa_e_prazo(self):
        c = le_captura("pauta da 1:1 amanhã p", SEG)
        self.assertEqual(c.data_fixa, SEG + timedelta(days=1))
        self.assertEqual(c.minutos, 30)
        c = le_captura("proposta até 30/10", SEG)
        self.assertEqual(c.prazo, date(2026, 10, 30))

    def test_amanha_na_sexta_vai_para_segunda(self):
        sexta = date(2026, 10, 30)
        prox = lambda d: d + timedelta(days=3) if d.weekday() == 4 else d + timedelta(days=1)
        self.assertEqual(le_dia("amanhã", sexta, prox), date(2026, 11, 2))

    def test_data_de_janeiro_digitada_em_dezembro(self):
        self.assertEqual(le_dia("05/01", date(2026, 12, 20)), date(2027, 1, 5))

    def test_aguardando_e_muito_importante(self):
        c = le_captura("plano de migração @marcos até 28/10 !!", SEG)
        self.assertEqual(c.pessoa, "marcos")
        self.assertTrue(c.eh_aguardando)
        self.assertEqual(c.importancia, 2)
        self.assertIn("vai para Aguardando", c.descricao())

    def test_formata(self):
        self.assertEqual(formata_minutos(285), "4h45")
        self.assertEqual(formata_minutos(120), "2h")
        self.assertEqual(formata_minutos(15), "15min")


if __name__ == "__main__":
    unittest.main()
