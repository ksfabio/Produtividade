"""Etapa 5: configurações, avisos de horário, sons, ausências e backup."""
import tempfile
import unittest
import wave
import io
from datetime import date, datetime
from pathlib import Path

from dados.banco import Banco
from nucleo.servico import Servico, le_hora
from nucleo.sons import SONS, gerar_wav

SEG = date(2026, 10, 26)


class TestConfiguracoes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.pasta = Path(self.tmp.name)
        self.banco = Banco(self.pasta / "dados.db")
        self.sv = Servico(self.banco, self.pasta, lambda: SEG)

    def tearDown(self):
        self.banco.fechar()
        self.tmp.cleanup()

    def test_le_hora(self):
        self.assertEqual(le_hora("9"), le_hora("09:00"))
        self.assertEqual(le_hora("13h30").minute, 30)
        self.assertIsNone(le_hora("25:00"))
        self.assertIsNone(le_hora("abc"))

    def test_validacoes(self):
        self.assertFalse(self.sv.salvar_configuracao(jornada_inicio="14:00").ok)  # depois do almoço
        self.assertFalse(self.sv.salvar_configuracao(jornada_fim="x").ok)
        self.assertFalse(self.sv.salvar_configuracao(dias_uteis=[]).ok)
        self.assertFalse(self.sv.salvar_configuracao(horas_padrao_min=5).ok)
        self.assertFalse(self.sv.salvar_configuracao(meu_nome="  ").ok)
        self.assertFalse(self.sv.salvar_configuracao(aviso_som="Trombone").ok)
        self.assertFalse(self.sv.salvar_configuracao(campo_que_nao_existe=1).ok)
        self.assertEqual(self.sv.config().jornada_inicio, "09:00")  # nada foi gravado

    def test_salvar_normaliza_e_replaneja(self):
        r = self.sv.salvar_configuracao(jornada_inicio="8", meu_nome="  FABIO   K SATO ", apelidos=["Fabio", " ", "FK"])
        self.assertTrue(r.ok)
        cfg = self.sv.config()
        self.assertEqual((cfg.jornada_inicio, cfg.meu_nome, cfg.apelidos), ("08:00", "FABIO K SATO", ["Fabio", "FK"]))
        self.assertEqual(self.sv.salvar_configuracao(jornada_inicio="08:00").mensagem, "Sem mudanças.")
        # menos horas por dia empurra tarefas
        for i in range(3):
            self.sv.capturar(f"tarefa {i} g")
        r = self.sv.salvar_configuracao(horas_padrao_min=240)
        self.assertIn("replanejada", r.mensagem)
        dias = [t.dia_planejado for t in self.banco.tarefas("aberta")]
        self.assertEqual(len(set(dias)), 3)  # uma tarefa de 4h por dia

    def test_dias_uteis_sem_sexta(self):
        self.sv.salvar_configuracao(dias_uteis=[0, 1, 2, 3])
        self.assertFalse(self.sv.calendario().eh_dia_de_trabalho(date(2026, 10, 30)))
        self.assertIn("4 dias por semana", self.sv.resumo_jornada())

    def test_resumo_jornada(self):
        self.assertIn("Jornada de 8h por dia, 5 dias", self.sv.resumo_jornada())

    def test_horarios_avisos(self):
        hs = self.sv.horarios_avisos(SEG)
        self.assertEqual(hs, [("manha", datetime(2026, 10, 26, 11, 30)), ("fim", datetime(2026, 10, 26, 17, 30))])
        self.assertEqual(self.sv.horarios_avisos(date(2026, 11, 2)), [])  # Finados
        self.assertEqual(self.sv.horarios_avisos(date(2026, 10, 31)), [])  # sábado
        self.sv.salvar_configuracao(aviso_manha=False, aviso_antecedencia_min=15)
        self.assertEqual(self.sv.horarios_avisos(SEG), [("fim", datetime(2026, 10, 26, 17, 45))])
        self.assertEqual(self.sv.resumo_avisos(), "Aviso do fim do dia às 17:45")
        self.sv.salvar_configuracao(aviso_fim=False)
        self.assertEqual(self.sv.resumo_avisos(), "Nenhum aviso ligado")

    def test_montar_aviso(self):
        self.sv.capturar("e-mail rápido 15min")
        self.sv.capturar("planilha @ana até 26/10")
        a = self.sv.montar_aviso("manha")
        self.assertEqual(a.titulo, "Faltam 30 min para o almoço")
        self.assertIn("Dá tempo de fechar: e-mail rápido", a.mensagem)
        self.assertIn("1 cobrança pendente", a.mensagem)
        f = self.sv.montar_aviso("fim")
        self.assertEqual((f.acao, f.acao_rotulo), ("replanejar", "Replanejar o resto agora"))
        for t in self.banco.tarefas("aberta"):
            self.sv.concluir(t.id)
        self.assertEqual(self.sv.montar_aviso("fim").acao, "ok")

    def test_sons(self):
        for nome in SONS:
            dados = gerar_wav(nome)
            with wave.open(io.BytesIO(dados)) as w:
                self.assertEqual((w.getnchannels(), w.getsampwidth()), (1, 2))
                dur = w.getnframes() / w.getframerate()
            if nome == "Desligado":
                self.assertEqual(dur, 0)
            else:
                self.assertTrue(0.3 < dur < 2.5, (nome, dur))

    def test_ausencia_valida_periodo(self):
        self.assertFalse(self.sv.adicionar_ausencia("Férias", date(2026, 10, 31), date(2026, 11, 1)).ok)  # fim de semana
        self.assertFalse(self.sv.adicionar_ausencia("Viagem", SEG, SEG).ok)
        r = self.sv.adicionar_ausencia("Férias", date(2026, 11, 6), date(2026, 11, 4), "praia")  # invertido
        self.assertTrue(r.ok)
        a = [x for x in self.sv.ausencias_futuras() if x.tipo == "Férias"][0]
        self.assertEqual((a.inicio, a.fim), (date(2026, 11, 4), date(2026, 11, 6)))

    def test_ausencias_futuras_e_facultativos(self):
        futuras = self.sv.ausencias_futuras()
        self.assertTrue(all(a.fim >= SEG for a in futuras))
        self.assertEqual(futuras[0].inicio, date(2026, 11, 2))  # Finados é o próximo feriado
        pend = self.sv.pontos_facultativos_pendentes()
        nomes = [n for _, n in pend]
        self.assertIn("Véspera de Natal", nomes)
        self.assertIn("Carnaval (segunda)", nomes)
        d, nome = next(x for x in pend if x[1] == "Véspera de Natal")
        self.sv.adicionar_ausencia("Feriado", d, d, nome)
        self.assertNotIn((d, nome), self.sv.pontos_facultativos_pendentes())

    def test_backup(self):
        self.assertIsNone(self.sv.ultimo_backup())
        r = self.sv.backup_agora()
        self.assertTrue(r.ok)
        self.assertIsNotNone(self.sv.ultimo_backup())
        self.assertTrue(self.sv.backup_agora().ok)  # refaz o de hoje sem erro
        destino = self.pasta / "onedrive" / "Produtividade"
        self.assertTrue(self.sv.salvar_configuracao(pasta_backup=str(destino)).ok)
        self.sv.backup_agora()
        self.assertEqual([p.name for p in destino.iterdir()], ["dados-backup.db"])

    def test_backup_um_arquivo_so(self):
        import os
        from dados.backup import fazer_backup
        pasta = self.pasta / "bk"
        pasta.mkdir()
        (pasta / "dados-2026-10-01.db").write_bytes(b"antigo")  # formato das versões anteriores
        self.assertIsNotNone(fazer_backup(self.banco.caminho, pasta, SEG))
        self.assertIsNone(fazer_backup(self.banco.caminho, pasta, SEG))  # mesmo dia: não refaz
        ontem = (pasta / "dados-backup.db").stat().st_mtime - 86400
        os.utime(pasta / "dados-backup.db", (ontem, ontem))
        self.sv.capturar("tarefa nova m")
        self.assertIsNotNone(fazer_backup(self.banco.caminho, pasta, date.today()))  # outro dia: substitui
        self.assertEqual(sorted(p.name for p in pasta.iterdir()), ["dados-backup.db"])
        import sqlite3
        con = sqlite3.connect(pasta / "dados-backup.db")
        self.assertEqual(con.execute("SELECT COUNT(*) FROM tarefa").fetchone()[0], 1)
        con.close()


if __name__ == "__main__":
    unittest.main()
