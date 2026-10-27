import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from dados.banco import Banco
from nucleo.modelos import CONCLUIDA, DELEGADA
from nucleo.recap import TAREFA
from nucleo.servico import Servico

SEG = date(2026, 10, 26)


class Relogio:
    def __init__(self, d):
        self.d = d

    def __call__(self):
        return self.d


class TestServico(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.pasta = Path(self.tmp.name)
        self.relogio = Relogio(SEG)
        self.banco = Banco(self.pasta / "dados.db")
        self.sv = Servico(self.banco, self.pasta, self.relogio)

    def tearDown(self):
        self.banco.fechar()
        self.tmp.cleanup()

    def test_feriados_pre_carregados(self):
        datas = {a.inicio for a in self.banco.ausencias()}
        self.assertIn(date(2026, 11, 2), datas)
        self.assertIn(date(2027, 2, 19), datas)  # ano seguinte também
        Servico(self.banco, self.pasta, self.relogio)  # reabrir não duplica
        self.assertEqual(len(self.banco.ausencias()), 28)

    def test_captura_e_encaixe(self):
        r = self.sv.capturar("e-mail para Ana 15min")
        self.assertIn("Encaixada em Hoje", r.mensagem)
        self.assertEqual(r.tarefa.dia_planejado, SEG)
        regs = self.banco.registros(r.tarefa.id)
        self.assertEqual(regs[0].tipo, "Criada")

    def test_captura_aguardando_reserva_5min(self):
        r = self.sv.capturar("plano @marcos até 28/10")
        self.assertIn("Em Aguardando: Marcos", r.mensagem)
        self.assertEqual(self.sv.reservas(), {date(2026, 10, 28): 5})

    def test_adiar_tres_vezes_pede_decisao(self):
        t = self.sv.capturar("relatório m").tarefa
        for _ in range(2):
            r = self.sv.adiar(t.id, "falta de tempo")
            self.assertFalse(r.precisa_decisao)
        r = self.sv.adiar(t.id)
        self.assertTrue(r.precisa_decisao)
        self.assertEqual(self.banco.tarefa(t.id).adiamentos, 2)
        r = self.sv.decidir(t.id, "quebrar")
        self.assertIn("Quebrada em 2 partes de 1h", r.mensagem)
        partes = [x for x in self.banco.tarefas("aberta") if "(parte" in x.titulo]
        self.assertEqual(len(partes), 2)

    def test_adiar_registra_no_diario(self):
        t = self.sv.capturar("relatório m").tarefa
        self.sv.adiar(t.id, "bloqueio")
        ultimo = self.banco.registros(t.id)[-1]
        self.assertEqual(ultimo.tipo, "Adiamento")
        self.assertIn("bloqueio", ultimo.texto)
        self.assertEqual(self.banco.tarefa(t.id).dia_planejado, SEG + timedelta(days=1))

    def test_concluir_e_desfazer(self):
        t = self.sv.capturar("relatório m").tarefa
        self.sv.concluir(t.id)
        self.assertEqual(self.banco.tarefa(t.id).status, CONCLUIDA)
        self.sv.desfazer()
        self.assertEqual(self.banco.tarefa(t.id).status, "aberta")
        self.assertNotIn("Concluída", [r.tipo for r in self.banco.registros(t.id)])

    def test_desfazer_captura_remove_tarefa(self):
        t = self.sv.capturar("tarefa errada").tarefa
        self.sv.desfazer()
        self.assertIsNone(self.banco.tarefa(t.id))

    def test_cobrei_e_recebi_com_tarefa(self):
        self.sv.capturar("plano @marcos até 26/10")
        a = self.banco.aguardando("aberto")[0]
        r = self.sv.cobrei(a.id)
        self.assertIn("Próxima cobrança", r.mensagem)
        a = self.banco.aguardando("aberto")[0]
        self.assertEqual(a.cobrancas, [SEG])
        self.assertEqual(a.cobrar_em, date(2026, 10, 28))
        r = self.sv.recebi(a.id, "revisar o plano 30min até qui")
        self.assertIn("Nova tarefa", r.mensagem)
        recebido = self.banco.aguardando("recebido")[0]
        self.assertIsNotNone(recebido.tarefa_gerada_id)
        self.assertEqual(self.banco.tarefa(recebido.tarefa_gerada_id).minutos, 30)

    def test_virada_do_dia_reencaixa_pendentes(self):
        t = self.sv.capturar("relatório m").tarefa
        self.relogio.d = SEG + timedelta(days=1)
        r = self.sv.abrir_o_dia()
        self.assertIn("1 tarefa(s) de dias anteriores", r.mensagem)
        self.assertEqual(self.banco.tarefa(t.id).dia_planejado, SEG + timedelta(days=1))
        self.assertTrue((self.pasta / "backup" / "dados-backup.db").exists())

    def test_ausencia_replaneja(self):
        t = self.sv.capturar("relatório m").tarefa
        r = self.sv.adicionar_ausencia("Férias", SEG, SEG + timedelta(days=1), "viagem")
        self.assertIn("Férias cadastrado(a)", r.mensagem)
        self.assertEqual(self.banco.tarefa(t.id).dia_planejado, SEG + timedelta(days=2))

    def test_desfazer_horas_e_ausencia(self):
        t = self.sv.capturar("relatório m").tarefa
        self.sv.definir_capacidade(SEG, 0)
        self.assertEqual(self.banco.tarefa(t.id).dia_planejado, SEG + timedelta(days=1))
        self.sv.desfazer()
        self.assertEqual(self.sv.calendario().capacidade(SEG), 300)
        self.sv.adicionar_ausencia("Férias", SEG, SEG)
        self.sv.desfazer()
        self.assertTrue(self.sv.calendario().eh_dia_de_trabalho(SEG))

    def test_reduzir_horas_do_dia(self):
        a = self.sv.capturar("a 3h").tarefa
        b = self.sv.capturar("b 2h").tarefa
        r = self.sv.definir_capacidade(SEG, 180)
        self.assertIn("1 outra replanejada", r.mensagem)
        self.assertEqual(self.banco.tarefa(b.id).dia_planejado, SEG + timedelta(days=1))

    def test_reuniao_cria_tarefas_e_aguardando(self):
        recap = "Itens de ação:\n- FABIO KIYOSHI SATO: enviar a ata hoje.\n- Marcos: plano de migração até 28/10."
        sug = self.sv.ler_recap(recap)
        self.assertEqual([s.tipo for s in sug], [TAREFA, "AGUARDANDO"])
        r = self.sv.criar_da_reuniao("Status Alfa", recap, sug)
        self.assertIn("2 itens criados", r.mensagem)
        self.assertEqual(len(self.banco.reunioes()), 1)
        self.assertEqual(self.banco.aguardando("aberto")[0].pessoa, "Marcos")

    def test_delegar(self):
        t = self.sv.capturar("relatório m").tarefa
        self.sv.decidir(t.id, "delegar")
        self.assertEqual(self.banco.tarefa(t.id).status, DELEGADA)
        self.assertEqual(self.banco.aguardando("aberto")[0].tarefa_origem_id, t.id)

    def test_fim_de_semana(self):
        self.relogio.d = date(2026, 10, 25)  # domingo
        t = self.sv.capturar("urgente m até hoje").tarefa
        self.assertEqual(t.dia_planejado, SEG)
        self.sv.adiar(t.id)
        self.assertEqual(self.banco.tarefa(t.id).dia_planejado, SEG + timedelta(days=1))  # adiar sai do dia em que estava
        self.sv.decidir(t.id, "fazer_hoje")
        self.assertEqual(self.banco.tarefa(t.id).dia_planejado, SEG)  # "hoje" num domingo = próximo dia útil

    def test_config_persiste(self):
        cfg = self.sv.config()
        cfg.meu_nome = "OUTRO NOME"
        cfg.apelidos = ["Outro"]
        self.banco.salvar_config(cfg)
        self.assertEqual(self.sv.config().meu_nome, "OUTRO NOME")
        self.assertEqual(self.sv.config().apelidos, ["Outro"])


    def test_renomear(self):
        t = self.sv.capturar("enviar proposta m").tarefa
        r = self.sv.renomear(t.id, "  enviar proposta   revisada ")
        self.assertEqual(self.banco.tarefa(t.id).titulo, "enviar proposta revisada")
        self.assertIn("enviar proposta", self.banco.registros(t.id)[-1].texto)
        self.assertTrue(r.pode_desfazer)
        self.assertFalse(self.sv.renomear(t.id, "   ").pode_desfazer)
        self.assertEqual(self.banco.tarefa(t.id).titulo, "enviar proposta revisada")
        self.sv.desfazer()
        self.assertEqual(self.banco.tarefa(t.id).titulo, "enviar proposta")

    def test_excluir_e_desfazer(self):
        a = self.sv.capturar("tarefa de teste g").tarefa
        b = self.sv.capturar("tarefa real g").tarefa
        self.sv.anotar(a.id, "Feito", "rascunho")
        dia_b = self.banco.tarefa(b.id).dia_planejado
        n_regs = len(self.banco.registros(a.id))
        r = self.sv.excluir(a.id)
        self.assertIn("excluída", r.mensagem)
        self.assertIsNone(self.banco.tarefa(a.id))
        self.assertEqual(self.banco.registros(a.id), [])
        self.assertLessEqual(self.banco.tarefa(b.id).dia_planejado, dia_b)
        self.sv.desfazer()
        volta = self.banco.tarefa(a.id)
        self.assertIsNotNone(volta)
        self.assertEqual(volta.titulo, "tarefa de teste")
        self.assertEqual(len(self.banco.registros(a.id)), n_regs)
        # uma nova tarefa depois do desfazer não reaproveita confusamente o diário
        c = self.sv.capturar("outra p").tarefa
        self.assertNotEqual(c.id, a.id)

    def test_excluir_limpa_ligacao_com_aguardando(self):
        self.sv.capturar("planilha @marcos")
        ag = self.banco.aguardando()[0]
        t = self.sv.recebi(ag.id, "revisar planilha").tarefa
        self.sv.excluir(t.id)
        self.assertIsNone(self.banco.aguardando()[0].tarefa_gerada_id)
        self.sv.desfazer()
        self.assertEqual(self.banco.aguardando()[0].tarefa_gerada_id, t.id)

    # ---------- etapa 4 ----------
    def test_espera_exige_pessoa(self):
        self.assertFalse(self.sv.capturar_espera("plano de migração até 28/10").pode_desfazer)
        self.assertEqual(self.banco.aguardando(), [])
        self.sv.capturar_espera("plano de migração @marcos até 28/10")
        a = self.banco.aguardando()[0]
        self.assertEqual((a.pessoa, a.cobrar_em), ("Marcos", date(2026, 10, 28)))  # @marcos vira "Marcos"

    def test_editar_excluir_reabrir_espera(self):
        self.sv.capturar("planilha @ana")
        a = self.banco.aguardando()[0]
        self.sv.editar_espera(a.id, "Ana Paula", "planilha de custos", date(2026, 10, 30))
        a = self.banco.aguardando()[0]
        self.assertEqual((a.pessoa, a.o_que, a.cobrar_em), ("Ana Paula", "planilha de custos", date(2026, 10, 30)))
        self.assertIn(date(2026, 10, 30), self.sv.reservas())
        self.sv.recebi(a.id)
        self.assertEqual(self.banco.aguardando()[0].status, "recebido")
        self.sv.reabrir_espera(a.id)
        a = self.banco.aguardando()[0]
        self.assertEqual((a.status, a.recebido_em, a.cobrar_em), ("aberto", None, SEG))
        self.sv.excluir_espera(a.id)
        self.assertEqual(self.banco.aguardando(), [])
        self.sv.desfazer()
        self.assertEqual(self.banco.aguardando()[0].id, a.id)

    def test_historico_e_filtro(self):
        t1 = self.sv.capturar("fechar relatório #kpis p").tarefa
        t2 = self.sv.capturar("revisar contrato p").tarefa
        self.sv.concluir(t1.id)
        self.sv.concluir(t2.id)
        self.sv.capturar("plano @marcos")
        a = self.banco.aguardando()[0]
        self.sv.cobrei(a.id)
        self.sv.recebi(a.id)
        h = self.sv.historico()
        self.assertEqual({i.tipo for i in h}, {"tarefa", "recebido"})
        self.assertEqual(len(h), 3)
        self.assertIn("cobrado 1x", next(i for i in h if i.tipo == "recebido").detalhe)
        self.assertEqual([i.titulo for i in self.sv.historico("#kpis")], ["fechar relatório"])
        self.assertEqual([i.titulo for i in self.sv.historico("relatorio")], ["fechar relatório"])
        self.assertEqual([i.tipo for i in self.sv.historico("marcos")], ["recebido"])

    def test_reuniao_completa(self):
        recap = ("TAREFA: enviar ata | RESPONSÁVEL: Fabio | PRAZO: 28/10\n"
                 "AGUARDANDO: plano de migração | RESPONSÁVEL: Marcos | PRAZO: 29/10\n"
                 "DECISÃO: manter go-live em 30/11\n"
                 "RISCO: atraso do fornecedor")
        sug = self.sv.ler_recap(recap)
        for s in sug:
            s.aceita = True
        r = self.sv.criar_da_reuniao("  Status   Alfa ", recap, sug, date(2026, 10, 23))
        self.assertIn("2 itens criados", r.mensagem)
        resumos = self.sv.reunioes()
        self.assertEqual(len(resumos), 1)
        rr = resumos[0]
        self.assertEqual(rr.reuniao.titulo, "Status Alfa")
        self.assertEqual(rr.reuniao.quando.date(), date(2026, 10, 23))
        self.assertEqual(rr.decisoes, ["manter go-live em 30/11"])
        self.assertEqual(rr.riscos, ["atraso do fornecedor"])
        self.assertEqual(len(rr.tarefas), 1)
        self.assertEqual(len(rr.aguardando), 1)
        self.assertIn("1 tarefa", rr.legenda)
        self.assertEqual(len(self.sv.reunioes("go-live")), 1)
        self.assertEqual(self.sv.reunioes("orçamento"), [])
        # excluir mantém as tarefas e o Desfazer devolve a reunião com as ligações
        rid = rr.reuniao.id
        self.sv.excluir_reuniao(rid)
        self.assertEqual(self.sv.reunioes(), [])
        self.assertIsNone(self.banco.tarefa(rr.tarefas[0].id).reuniao_id)
        self.sv.desfazer()
        self.assertEqual(self.sv.reunioes()[0].reuniao.id, rid)
        self.assertEqual(self.banco.tarefa(rr.tarefas[0].id).reuniao_id, rid)
        self.assertEqual(self.banco.aguardando()[0].reuniao_id, rid)

    def test_reuniao_desfazer_criacao(self):
        sug = self.sv.ler_recap("TAREFA: enviar ata | RESPONSÁVEL: Fabio")
        self.sv.criar_da_reuniao("Kickoff", "x", sug)
        self.sv.desfazer()
        self.assertEqual(self.sv.reunioes(), [])
        self.assertEqual(self.banco.tarefas(), [])

    def test_migracao_banco_antigo(self):
        import sqlite3
        caminho = self.pasta / "antigo.db"
        con = sqlite3.connect(caminho)
        con.executescript("""
            CREATE TABLE meta (chave TEXT PRIMARY KEY, valor TEXT);
            INSERT INTO meta VALUES ('versao', '1');
            CREATE TABLE reuniao (id INTEGER PRIMARY KEY AUTOINCREMENT, titulo TEXT NOT NULL,
                quando TEXT NOT NULL, recap_original TEXT NOT NULL DEFAULT '');
            INSERT INTO reuniao (titulo, quando, recap_original) VALUES ('Antiga', '2026-10-01T10:00:00', 'texto');
            CREATE TABLE aguardando (id INTEGER PRIMARY KEY AUTOINCREMENT, pessoa TEXT NOT NULL, o_que TEXT NOT NULL,
                cobrar_em TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'aberto', cobrancas TEXT NOT NULL DEFAULT '[]',
                recebido_em TEXT, reuniao_id INTEGER, tarefa_origem_id INTEGER, tarefa_gerada_id INTEGER);
            INSERT INTO aguardando (pessoa, o_que, cobrar_em, cobrancas) VALUES ('Ana', 'planilha', '2026-10-28', '["2026-10-20", "2026-10-22"]');
        """)
        con.commit()
        con.close()
        from dados.banco import Banco
        b = Banco(caminho)
        r = b.reunioes()[0]
        self.assertEqual((r.titulo, r.notas), ("Antiga", []))
        self.assertEqual(b._meta("versao"), "3")
        self.assertTrue((self.pasta / "antigo-antes-v3.db").exists())  # cópia de segurança antes da migração
        ag = b.aguardando()[0]
        self.assertEqual(ag.contar("Cobrado"), 2)  # histórico montado a partir das cobranças antigas
        b.fechar()

    def test_historico_da_espera(self):
        self.sv.capturar("planilha @ana até 27/10")
        a = self.banco.aguardando()[0]
        self.sv.cobrei(a.id)
        r = self.sv.adiar_espera(a.id)
        a = self.banco.aguardando()[0]
        self.assertIn("adiada para", r.mensagem)
        self.sv.adiar_espera(a.id)
        self.sv.editar_espera(a.id, "Ana", "planilha de custos", date(2026, 11, 10))
        self.sv.recebi(a.id, "revisar planilha p")
        a = self.banco.aguardando()[0]
        self.assertEqual([e["tipo"] for e in a.eventos],
                         ["Criado", "Cobrado", "Adiado", "Adiado", "Adiado", "Editado", "Recebido"])
        self.assertEqual((a.contar("Cobrado"), a.contar("Adiado")), (1, 3))
        self.assertIn("revisar planilha", a.eventos[-1]["texto"])
        self.assertIn("adiado 3x", self.sv.historico()[0].detalhe)
        self.sv.reabrir_espera(a.id)
        self.assertEqual(self.banco.aguardando()[0].eventos[-1]["tipo"], "Reaberto")
        self.sv.desfazer()
        self.assertEqual(self.banco.aguardando()[0].eventos[-1]["tipo"], "Recebido")

    def test_adiar_espera_vai_para_proximo_dia_util(self):
        self.sv.capturar("planilha @ana até 30/10")  # sexta
        a = self.banco.aguardando()[0]
        self.sv.adiar_espera(a.id)
        self.assertEqual(self.banco.aguardando()[0].cobrar_em, date(2026, 11, 3))  # seg 02/11 é feriado

if __name__ == "__main__":
    unittest.main()
