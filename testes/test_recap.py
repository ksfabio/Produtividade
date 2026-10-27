import unittest
from datetime import date

from nucleo.recap import AGUARDANDO, DECISAO, RISCO, TAREFA, eh_comigo, le_recap

SEG = date(2026, 10, 26)
NOME, APELIDOS = "FABIO KIYOSHI SATO", ["Fabio", "você"]

LIVRE = """Recap · Status Projeto Alfa

Resumo: o time revisou a migração. O go-live segue para 30/11.

Decisões:
- Manter o go-live em 30/11.

Itens de ação:
- Você: enviar a ata para o time hoje.
- FABIO KIYOSHI SATO: agendar o teste integrado com a área usuária até 06/11.
- Marcos: enviar o plano de migração até 28/10.

Pontos de atenção:
- Possível atraso na entrega do fornecedor.
"""

ESTRUTURADO = """DECISÃO: manter go-live em 30/11
TAREFA: consolidar riscos | RESPONSÁVEL: Fabio Sato | PRAZO: 29/10
AGUARDANDO: plano de migração | RESPONSÁVEL: Marcos | PRAZO: 28/10
TAREFA: revisar contrato | RESPONSÁVEL: Ana | PRAZO: 30/10
RISCO: atraso do fornecedor"""


class TestRecap(unittest.TestCase):
    def test_eh_comigo(self):
        for r in ("FABIO KIYOSHI SATO", "Fabio Sato", "fábio", "Você", "Fabio (PMO)"):
            self.assertTrue(eh_comigo(r, NOME, APELIDOS), r)
        for r in ("Marcos", "Ana Fabiola", None):
            self.assertFalse(eh_comigo(r, NOME, APELIDOS), r)

    def test_recap_livre(self):
        s = le_recap(LIVRE, SEG, NOME, APELIDOS)
        tipos = [x.tipo for x in s]
        self.assertEqual(tipos, [DECISAO, TAREFA, TAREFA, AGUARDANDO, RISCO])
        ata, teste, plano = s[1], s[2], s[3]
        self.assertEqual(ata.data_fixa, SEG)
        self.assertTrue(ata.texto.startswith("Enviar a ata"))
        self.assertEqual(teste.prazo, date(2026, 11, 6))
        self.assertEqual(plano.responsavel, "Marcos")
        self.assertEqual(plano.prazo, date(2026, 10, 28))
        self.assertFalse(s[4].aceita)  # risco vem desmarcado

    def test_recap_estruturado(self):
        s = le_recap(ESTRUTURADO, SEG, NOME, APELIDOS)
        self.assertEqual([x.tipo for x in s], [DECISAO, TAREFA, AGUARDANDO, AGUARDANDO, RISCO])
        self.assertEqual(s[1].prazo, date(2026, 10, 29))
        self.assertEqual(s[3].responsavel, "Ana")  # tarefa de outra pessoa vira aguardando


if __name__ == "__main__":
    unittest.main()
