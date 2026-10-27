import unittest
from datetime import date, datetime, timedelta

from nucleo.calendario import Ausencia, Calendario
from nucleo.modelos import (CONFLITO_MAIOR_QUE_DIA, CONFLITO_NAO_CABE, CONFLITO_PRAZO_VENCIDO, Tarefa)
from nucleo.planejador import planejar, proxima_que_cabe, tarefas_do_dia

SEG, TER, QUA, QUI, SEX = (date(2026, 10, 26) + timedelta(days=i) for i in range(5))


def t(id, titulo, minutos, imp=0, prazo=None, fixa=None):
    return Tarefa(id=id, titulo=titulo, minutos=minutos, importancia=imp, prazo=prazo, data_fixa=fixa,
                  criada_em=datetime(2026, 10, 1) + timedelta(minutes=id))


def cenario():
    """O mesmo cenário do protótipo."""
    return [
        t(1, "Enviar proposta", 120, 1, SEG), t(2, "Revisar indicadores", 60, 1, TER),
        t(3, "E-mail para Ana", 15), t(4, "Questionário de auditoria", 240, 2, QUA),
        t(5, "Documentação de compras", 120), t(6, "Validar cronograma", 60, 1, QUI),
        t(7, "Consolidar riscos", 240, 1, QUI), t(8, "Organizar arquivos", 30), t(9, "Pauta da 1:1", 30, fixa=QUA),
    ]


CAL = Calendario(capacidade_especifica={QUA: 180, SEX: 240},
                 ausencias=[Ausencia("Feriado", date(2026, 11, 2), date(2026, 11, 2), "Finados")])


def por_id(res):
    return {x.id: x for x in res.tarefas}


class TestPlanejador(unittest.TestCase):
    def test_cenario_do_prototipo(self):
        r = por_id(planejar(cenario(), CAL, SEG))
        self.assertEqual([i for i in r if r[i].dia_planejado == SEG], [1, 2, 3, 6, 8])
        self.assertEqual(r[4].dia_planejado, TER)
        self.assertEqual(r[7].dia_planejado, QUI)
        self.assertEqual(r[5].dia_planejado, QUA)
        self.assertEqual(r[9].dia_planejado, QUA)
        self.assertFalse(any(x.conflito for x in r.values()))

    def test_estabilidade_ao_adiar(self):
        planejado = planejar(cenario(), CAL, SEG).tarefas
        alvo = next(x for x in planejado if x.id == 2)
        alvo.nao_antes_de = TER
        r = planejar(planejado, CAL, SEG, ignorar_movimento_de={2})
        self.assertEqual(por_id(r)[2].dia_planejado, TER)
        self.assertEqual(r.movidas, [])  # ninguém mais se mexeu

    def test_prazo_vencido_marca_conflito(self):
        planejado = planejar(cenario(), CAL, SEG).tarefas
        alvo = next(x for x in planejado if x.id == 1)  # prazo hoje, adiada para amanhã
        alvo.nao_antes_de = TER
        r = por_id(planejar(planejado, CAL, SEG, ignorar_movimento_de={1}))
        self.assertEqual(r[1].conflito, CONFLITO_PRAZO_VENCIDO)
        self.assertEqual(r[1].dia_planejado, SEX)  # primeiro dia com 2h livres

    def test_nao_cabe_fica_no_dia_do_prazo(self):
        cal = Calendario(capacidade_especifica={QUI: 120})
        r = por_id(planejar([t(1, "grande", 240, prazo=QUI), t(2, "ocupa", 300, prazo=SEG),
                             t(3, "ocupa", 300, prazo=TER), t(4, "ocupa", 300, prazo=QUA)], cal, SEG))
        self.assertEqual(r[1].conflito, CONFLITO_NAO_CABE)
        self.assertEqual(r[1].dia_planejado, QUI)

    def test_prazo_em_dia_sem_expediente(self):
        domingo = date(2026, 10, 25)
        r = por_id(planejar([t(1, "urgente", 120, prazo=domingo)], Calendario(), domingo))
        self.assertEqual(r[1].dia_planejado, SEG)  # primeiro dia útil, marcada
        self.assertEqual(r[1].conflito, CONFLITO_NAO_CABE)

    def test_sem_prazo_alem_do_horizonte_fica_sem_data(self):
        tarefas = [t(i, f"t{i}", 300) for i in range(1, 7)]
        r = planejar(tarefas, Calendario(), SEG, horizonte_dias=5)
        self.assertEqual(len(r.sem_data), 1)
        self.assertIsNone(r.sem_data[0].dia_planejado)
        self.assertIsNone(r.sem_data[0].conflito)

    def test_reserva_de_cobranca(self):
        r = por_id(planejar([t(1, "cheia", 300)], Calendario(), SEG, reservas={SEG: 5}))
        self.assertEqual(r[1].dia_planejado, TER)

    def test_maior_que_um_dia(self):
        r = por_id(planejar([t(1, "enorme", 600)], Calendario(), SEG))
        self.assertEqual(r[1].conflito, CONFLITO_MAIOR_QUE_DIA)
        self.assertEqual(r[1].dia_planejado, SEG)  # aparece logo, para ser quebrada

    def test_reduzir_capacidade_move_o_menos_prioritario(self):
        planejado = planejar(cenario(), CAL, SEG).tarefas
        cal = Calendario(capacidade_especifica={QUA: 180, SEX: 240, SEG: 200})
        r = planejar(planejado, cal, SEG)
        movidos = {m.tarefa_id for m in r.movidas}
        self.assertTrue(movidos)
        self.assertNotIn(1, movidos)  # a de prazo hoje continua hoje

    def test_feriado_e_pulado(self):
        tarefas = [t(i, f"t{i}", 300) for i in range(1, 7)]
        r = planejar(tarefas, CAL, date(2026, 10, 30))
        dias = {x.dia_planejado for x in r.tarefas}
        self.assertNotIn(date(2026, 11, 2), dias)

    def test_ordem_do_dia_e_ordem_manual(self):
        r = planejar(cenario(), CAL, SEG).tarefas
        self.assertEqual([x.id for x in tarefas_do_dia(r, SEG)], [1, 2, 6, 3, 8])
        oito = next(x for x in r if x.id == 8)
        oito.ordem_manual, oito.ordem_manual_dia = 0, SEG
        self.assertEqual(tarefas_do_dia(r, SEG)[0].id, 8)
        self.assertEqual(tarefas_do_dia(r, SEG)[0].id, 8)
        oito.ordem_manual_dia = SEG - timedelta(days=3)  # ordem de outro dia não vale mais
        self.assertEqual(tarefas_do_dia(r, SEG)[0].id, 1)

    def test_adiantar_sugere_quem_cabe(self):
        r = planejar(cenario(), CAL, SEG).tarefas
        self.assertIsNone(proxima_que_cabe(r, SEG, 10))
        self.assertEqual(proxima_que_cabe(r, SEG, 120).id, 5)


if __name__ == "__main__":
    unittest.main()
