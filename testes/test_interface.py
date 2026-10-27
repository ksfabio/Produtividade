"""Teste da interface com PySide6 real, sem abrir janelas (plataforma 'offscreen').

É pulado se o PySide6 não estiver instalado. Também salva capturas de tela em
testes/capturas/ para conferência visual (opcional).
"""
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# Sem isto, no Windows o modo "offscreen" não acha as fontes e mede tudo com uma fonte substituta
# bem mais larga (as larguras dos testes ficariam irreais).
if os.name == "nt":
    os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))

try:
    import PySide6  # noqa: F401
    TEM_QT = True
except ImportError:
    TEM_QT = False

SEG = date(2026, 10, 26)


@unittest.skipUnless(TEM_QT, "PySide6 não instalado (pip install -r requirements.txt)")
class TestInterface(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from ui.aplicacao import criar_app
        cls.app = criar_app([])

    def setUp(self):
        from dados.banco import Banco
        from nucleo.servico import Servico
        from ui.janela import JanelaPrincipal
        self.tmp = tempfile.TemporaryDirectory()
        self.banco = Banco(Path(self.tmp.name) / "dados.db")
        self.sv = Servico(self.banco, Path(self.tmp.name), lambda: SEG)
        for texto in ["enviar proposta m até hoje !", "e-mail para Ana 15min",
                      "consolidar riscos #alfa g até qui !", "plano @marcos até 26/10"]:
            self.sv.capturar(texto)
        from ui.bandeja import Bandeja
        from ui.mini_barra import MiniBarra
        self.janela = JanelaPrincipal(self.sv)
        self.mini = MiniBarra(self.janela)
        self.bandeja = Bandeja(self.janela, self.mini)
        self.janela.conectar_mini(self.mini, self.bandeja)
        self.janela.resize(1200, 820)
        self.janela.show()
        self.mini.show()
        self.app.processEvents()

    def tearDown(self):
        self.janela.janela_aviso.hide()
        self.mini.close()
        self.janela._saindo = True
        self.janela.close()
        self.banco.fechar()
        self.tmp.cleanup()

    def _captura(self, nome):
        pasta = Path(__file__).parent / "capturas"
        pasta.mkdir(exist_ok=True)
        self.app.processEvents()
        self.janela.grab().save(str(pasta / f"{nome}.png"))

    def test_hoje_e_captura(self):
        tela = self.janela.telas["hoje"]
        tela.captura.campo.setText("relatório semanal 30min até sex")
        self.assertIn("prazo até Sex 30/10", tela.captura.previa.text())
        self._captura("01-hoje-digitando")
        self.janela.activateWindow()
        self.app.processEvents()
        tela.captura.campo.returnPressed.emit()
        self.assertEqual(tela.captura.campo.text(), "")
        self.assertTrue(any(t.titulo == "relatório semanal" for t in self.banco.tarefas("aberta")))
        # o aviso aparece na janela ou, se o sistema der o foco à mini barra, junto a ela
        self.assertTrue(self.janela.aviso.isVisible() or self.mini.balao.isVisible())
        self._captura("02-hoje-aviso")

    def test_painel_sobreposto_e_fecha_ao_trocar_de_aba(self):
        t = self.banco.tarefas("aberta")[0]
        for aba in ["hoje", "semana", "concluidas"]:
            self.janela.ir_para(aba)
            self.janela.abrir_tarefa(t.id)
            self.app.processEvents()
            painel = self.janela.painel
            self.assertTrue(painel.isVisible())
            self.assertLess(self.janela.area_lay.indexOf(painel), 0)  # por cima, fora do layout
            self.assertEqual(painel.geometry().right(), self.janela.area.width() - 1)
            if aba != "concluidas":
                self._captura("03-hoje-painel" if aba == "hoje" else "04-semana-painel")
        self.janela.ir_para("hoje")  # trocar de aba fecha o painel
        self.assertFalse(self.janela.painel.isVisible())
        self.assertIsNone(self.janela.sel_id)
        self.janela.ir_para("semana")
        self._captura("05-semana")

    def test_clicar_no_titulo_edita(self):
        from PySide6.QtCore import QPoint, Qt
        from PySide6.QtTest import QTest
        from ui.widgets import TextoClicavel
        t = self.banco.tarefas("aberta")[0]
        self.janela.abrir_tarefa(t.id)
        self.app.processEvents()
        titulo = self.janela.painel.findChild(TextoClicavel)
        QTest.mouseClick(titulo, Qt.LeftButton, Qt.NoModifier, QPoint(5, 5))
        self.assertTrue(self.janela.painel.editando_titulo)

    def test_datas_inteiras(self):
        from PySide6.QtWidgets import QDateEdit
        t = self.banco.tarefas("aberta")[0]
        self.janela.abrir_tarefa(t.id)
        self.app.processEvents()
        for d in self.janela.painel.findChildren(QDateEdit):
            if d.isVisible():
                texto = d.fontMetrics().horizontalAdvance(d.text())
                self.assertGreater(d.width(), texto + 30, d.text())

    def test_diario_numa_linha(self):
        t = self.banco.tarefas("aberta")[0]
        self.janela.abrir_tarefa(t.id)
        self.app.processEvents()
        chips = list(self.janela.painel._chips_tipo.values())
        self.assertEqual(len({c.geometry().top() for c in chips}), 1, [c.geometry() for c in chips])

    def test_adiar_ate_decisao(self):
        from ui import dialogos
        t = next(x for x in self.banco.tarefas("aberta") if x.titulo == "e-mail para Ana")
        self.janela.adiar(t.id)
        self.janela.adiar(t.id)
        original = dialogos.DialogoDecisao.exec

        def escolher(dlg):
            dlg.escolha = "fazer_hoje"
            return 1
        dialogos.DialogoDecisao.exec = escolher
        try:
            self.janela.adiar(t.id)
        finally:
            dialogos.DialogoDecisao.exec = original
        self.assertEqual(self.banco.tarefa(t.id).data_fixa, SEG)

    def test_diario(self):
        t = self.banco.tarefas("aberta")[0]
        self.janela.abrir_tarefa(t.id)
        self.janela.painel._escolher_tipo("Próximo passo")
        self.janela.painel.texto.setPlainText("Incluir cenário pessimista")
        self.janela.painel._registrar()
        regs = self.banco.registros(t.id)
        self.assertEqual(regs[-1].tipo, "Próximo passo")
        self._captura("06-painel-diario")


    def test_painel_sem_rolagem_lateral(self):
        from PySide6.QtWidgets import QWidget
        # força a caixa de conflito com todos os botões (inclusive "Quebrar em 2")
        self.sv.capturar("tarefa enorme de teste 12h até ter")
        for t in self.banco.tarefas("aberta"):
            self.sv.anotar(t.id, "Próximo passo", "passo com um texto bem comprido para ver se quebra a linha " * 3)
            self.janela.abrir_tarefa(t.id)
            self.app.processEvents()
            painel = self.janela.painel
            livre = painel.rolagem.viewport().width()
            largos = sorted(
                (w.minimumSizeHint().width(), type(w).__name__, w.objectName(), (getattr(w, "text", lambda: "")() or "")[:30])
                for w in painel.corpo.findChildren(QWidget) if w.isVisibleTo(painel.corpo)
                and w.minimumSizeHint().width() > livre - 60)
            self.assertLessEqual(painel.corpo.minimumSizeHint().width(), livre, f"{t.titulo}: mais largos {largos[-5:]}")
        self._captura("08-painel-largura")

    def test_editar_texto(self):
        t = self.banco.tarefas("aberta")[0]
        self.janela.abrir_tarefa(t.id)
        self.janela.painel.editar_titulo()
        campo = self.janela.painel._campo_titulo
        campo.setText("texto corrigido")
        campo.returnPressed.emit()
        self.assertEqual(self.banco.tarefa(t.id).titulo, "texto corrigido")
        self.assertFalse(self.janela.painel.editando_titulo)

    def test_excluir(self):
        from PySide6.QtWidgets import QMessageBox
        t = self.banco.tarefas("aberta")[0]
        self.janela.abrir_tarefa(t.id)
        original = QMessageBox.exec
        QMessageBox.exec = lambda caixa: next(b for b in caixa.buttons() if b.text() == "Excluir").click() or 0
        try:
            self.janela.excluir(t.id)
        finally:
            QMessageBox.exec = original
        self.assertIsNone(self.banco.tarefa(t.id))
        self.assertFalse(self.janela.painel.isVisible())
        self.janela.desfazer()
        self.assertIsNotNone(self.banco.tarefa(t.id))

    # ---------------- etapa 4 ----------------
    def _sem_rolagem_lateral(self, onde: str):
        from PySide6.QtWidgets import QScrollArea, QWidget
        self.app.processEvents()
        for area in self.janela.findChildren(QScrollArea):
            if area.isVisible() and area.widget() is not None:
                livre = area.viewport().width()
                if area.widget().minimumSizeHint().width() <= livre:
                    continue
                # aponta o "culpado": o widget largo demais cujos filhos, sozinhos, cabem
                largos = [w for w in area.widget().findChildren(QWidget)
                          if w.isVisibleTo(area.widget()) and w.minimumSizeHint().width() > livre - 48]
                folhas = [w for w in largos if not any(f in largos for f in w.findChildren(QWidget))]
                detalhes = [(w.minimumSizeHint().width(), type(w).__name__, w.objectName(),
                             [(f.minimumSizeHint().width(), type(f).__name__, (getattr(f, "text", lambda: "")() or "")[:25])
                              for f in w.findChildren(QWidget) if f.parent() is w and f.isVisibleTo(w)][:8])
                            for w in folhas]
                self.fail(f"{onde}: conteúdo pede {area.widget().minimumSizeHint().width()} de {livre}. Culpados: {detalhes}")

    def test_aba_aguardando(self):
        from ui import dialogos
        self.janela.ir_para("aguardando")
        tela = self.janela.telas["aguardando"]
        tela.campo.setText("relatório de acessos")
        self.assertIn("@pessoa", tela.previa.text())
        tela.campo.setText("relatório de acessos @carla até 28/10")
        tela.campo.returnPressed.emit()
        self.assertEqual(tela.campo.text(), "")
        a = next(x for x in self.banco.aguardando() if x.o_que == "relatório de acessos")
        self.assertEqual(a.pessoa, "Carla")
        self._captura("09-aguardando")
        original = dialogos.DialogoEspera.exec

        def salvar(dlg):
            dlg.o_que.setText("relatório de acessos do TI")
            dlg.acao = "salvar"
            return 1
        dialogos.DialogoEspera.exec = salvar
        try:
            self.janela.editar_espera(a.id)
        finally:
            dialogos.DialogoEspera.exec = original
        self.assertEqual(next(x for x in self.banco.aguardando() if x.id == a.id).o_que, "relatório de acessos do TI")
        self._sem_rolagem_lateral("aguardando")

    def test_aba_concluidas(self):
        for t in self.banco.tarefas("aberta")[:2]:
            self.sv.concluir(t.id)
        self.janela.ir_para("concluidas")
        tela = self.janela.telas["concluidas"]
        self.assertIn("2 tarefas concluídas", tela.resumo.text())
        self._captura("10-concluidas")
        tela.filtro.setText("#alfa")
        self.app.processEvents()
        self._sem_rolagem_lateral("concluidas")
        tela.filtro.clear()
        t = self.banco.tarefas("concluida")[0]
        self.janela.executar(self.sv.reabrir, t.id)
        self.assertEqual(self.banco.tarefa(t.id).status, "aberta")

    def test_aba_reunioes(self):
        self.janela.ir_para("reunioes")
        tela = self.janela.telas["reunioes"]
        self._captura("11-reunioes-vazia")
        tela.nova_reuniao()
        tela.titulo.setText("Status Projeto Alfa")
        tela.recap.setPlainText("TAREFA: enviar ata | RESPONSÁVEL: FABIO KIYOSHI SATO | PRAZO: 28/10\n"
                                "AGUARDANDO: plano de migração | RESPONSÁVEL: Marcos | PRAZO: 29/10\n"
                                "DECISÃO: manter go-live em 30/11")
        self._captura("12-reunioes-nova")
        tela.ler_recap()
        self.assertEqual(tela.modo, tela.REVISAR)
        self.assertEqual(len(tela.sugestoes), 3)
        self.assertEqual(tela.criar.text(), "Criar 3 itens")
        self._captura("13-reunioes-revisar")
        self._sem_rolagem_lateral("reunioes revisar")
        tela.criar_itens()
        self.assertEqual(tela.modo, tela.DETALHE)
        self.assertTrue(any(t.titulo == "enviar ata" for t in self.banco.tarefas("aberta")))
        self._captura("14-reunioes-detalhe")
        self._sem_rolagem_lateral("reunioes detalhe")
        t = next(t for t in self.banco.tarefas("aberta") if t.titulo == "enviar ata")
        self.janela.abrir_tarefa(t.id)
        self.janela.abrir_reuniao(t.reuniao_id)
        self.assertEqual(tela.modo, tela.DETALHE)
        tela.ir(tela.LISTA)
        self._captura("15-reunioes-lista")

    def test_janela_estreita_com_painel(self):
        self.janela.resize(960, 700)
        t = self.banco.tarefas("aberta")[0]
        for aba in ["hoje", "aguardando", "reunioes", "concluidas"]:
            self.janela.ir_para(aba)
            self.janela.abrir_tarefa(t.id)
            self._sem_rolagem_lateral(aba)

    def test_aba_em_negrito_cabe(self):
        from PySide6.QtGui import QFont, QFontMetrics
        self.sv.concluir(self.banco.tarefas("aberta")[0].id)
        self.janela.ir_para("concluidas")
        self.app.processEvents()
        aba = self.janela.abas["concluidas"]
        negrito = QFont(aba.font())
        negrito.setWeight(QFont.Bold)
        self.assertGreaterEqual(aba.width(), QFontMetrics(negrito).horizontalAdvance(aba.text()) + 20, aba.text())

    def test_painel_campos_alinhados(self):
        from PySide6.QtWidgets import QLabel
        t = self.banco.tarefas("aberta")[0]
        self.janela.abrir_tarefa(t.id)
        self.app.processEvents()
        painel = self.janela.painel
        rotulos = {lb.text(): lb for lb in painel.findChildren(QLabel) if lb.text() in ("Tamanho", "Tempo Livre", "Prazo combinado")}
        self.assertEqual(len(rotulos), 3)
        xs = {lb.mapTo(painel, lb.rect().topLeft()).x() for lb in rotulos.values()}
        self.assertEqual(len(xs), 1)  # rótulos alinhados à esquerda
        self._captura("16-painel-alinhado")

    def test_espera_adiar_e_historico(self):
        from ui import dialogos
        self.sv.capturar("planilha @ana até 27/10")
        a = next(x for x in self.banco.aguardando() if x.o_que == "planilha")
        self.janela.ir_para("aguardando")
        self.janela.executar(self.sv.adiar_espera, a.id)
        visto = {}
        original = dialogos.DialogoEspera.exec

        def olhar(dlg):
            from PySide6.QtWidgets import QLabel
            visto["textos"] = [lb.text() for lb in dlg.findChildren(QLabel)]
            return 0
        dialogos.DialogoEspera.exec = olhar
        try:
            self.janela.editar_espera(a.id)
        finally:
            dialogos.DialogoEspera.exec = original
        self.assertTrue(any("adiado 1x" in t for t in visto["textos"]), visto["textos"])

    def test_focar_captura_fecha_painel(self):
        t = self.banco.tarefas("aberta")[0]
        self.janela.activateWindow()
        self.janela.abrir_tarefa(t.id)
        self.app.processEvents()
        self.assertTrue(self.janela.painel.isVisible())
        campo = self.janela.telas["hoje"].captura.campo
        from PySide6.QtCore import QEvent, Qt
        from PySide6.QtGui import QFocusEvent
        self.app.sendEvent(campo, QFocusEvent(QEvent.FocusIn, Qt.MouseFocusReason))
        self.assertFalse(self.janela.painel.isVisible())
        self.assertIsNone(self.janela.sel_id)
        # o foco que volta ao reativar a janela não fecha o painel
        self.janela.abrir_tarefa(t.id)
        self.app.sendEvent(campo, QFocusEvent(QEvent.FocusIn, Qt.ActiveWindowFocusReason))
        self.assertTrue(self.janela.painel.isVisible())

    # ---------------- etapa 5 ----------------
    def test_configuracoes(self):
        self.janela.ir_para("config")
        tela = self.janela.telas["config"]
        self.assertFalse(any(b.isChecked() for b in self.janela.abas.values()))
        self.assertTrue(self.janela.botoes_topo["config"].isChecked())
        self._captura("17-configuracoes")
        self._sem_rolagem_lateral("configuracoes")
        tela.horas.setText("4h")
        tela.horas.editingFinished.emit()
        self.assertEqual(self.sv.config().horas_padrao_min, 240)
        tela.chips_antes[15].click()
        self.assertEqual(self.sv.config().aviso_antecedencia_min, 15)
        self.assertIn("11:45", tela.resumo_avisos.text())
        tela.h_inicio.setTime(tela.h_inicio.time().fromString("14:00", "HH:mm"))
        tela.h_inicio.editingFinished.emit()  # depois do almoço: recusado e volta ao valor salvo
        self.assertEqual(self.sv.config().jornada_inicio, "09:00")
        self.assertEqual(tela.h_inicio.time().toString("HH:mm"), "09:00")

    def test_calendario_ausencias(self):
        from datetime import date
        self.janela.ir_para("config")
        tela = self.janela.telas["config"]
        tela._escolher_tipo("Férias")
        cal = tela.calendario
        cal.selecionar(date(2026, 11, 4), date(2026, 11, 6))
        self.assertIn("3 dias úteis", tela.dica_sel.text())
        tela.descricao.setText("praia")
        self._captura("18-configuracoes-calendario")
        tela._adicionar()
        ferias = [a for a in self.sv.ausencias_futuras() if a.tipo == "Férias"]
        self.assertEqual((ferias[0].inicio, ferias[0].fim, ferias[0].descricao), (date(2026, 11, 4), date(2026, 11, 6), "praia"))
        self.assertIsNone(cal.de)

    def test_manual_e_atalhos(self):
        from ui import manual
        self.janela.botoes_topo["manual"].click()
        self.assertEqual(self.janela.aba_atual, "manual")
        tela = self.janela.telas["manual"]
        for i in range(len(manual.TOPICOS)):
            tela.mostrar(i)
            self._sem_rolagem_lateral(f"manual {i}")
        tela.mostrar(1)
        self._captura("19-manual")
        original = manual.DialogoAtalhos.exec
        manual.DialogoAtalhos.exec = lambda dlg: 0
        try:
            self.janela.mostrar_atalhos()
        finally:
            manual.DialogoAtalhos.exec = original

    def test_aviso_de_horario(self):
        from datetime import datetime
        from ui.avisos import AgendadorAvisos
        disparados = []
        ag = AgendadorAvisos(self.sv, agora=lambda: datetime(2026, 10, 26, 17, 31))
        ag.disparar.connect(disparados.append)
        ag.verificar()
        ag.verificar()
        self.assertEqual(disparados, ["fim"])
        self.sv.salvar_configuracao(aviso_som="Desligado")  # teste sem barulho
        self.janela.mostrar_aviso_hora("fim")
        self.app.processEvents()
        self.assertTrue(self.janela.janela_aviso.isVisible())
        self.assertEqual(self.janela.janela_aviso.principal.text(), "Replanejar o resto agora")
        self.janela.janela_aviso.grab().save(str(Path(__file__).parent / "capturas" / "20-aviso-fim.png")) if (Path(__file__).parent / "capturas").exists() else None
        self.janela.janela_aviso.principal.click()
        self.assertFalse(self.janela.janela_aviso.isVisible())
        self.assertEqual(self.janela.aba_atual, "hoje")

    def test_mini_barra_clique_alterna_janela(self):
        t = self.mini.tarefa_em_foco()
        self.janela.showMinimized()
        self.app.processEvents()
        self.mini._abrir_foco()  # 1º clique: abre nos detalhes
        self.app.processEvents()
        self.assertTrue(self.janela.visivel())
        self.assertEqual(self.janela.sel_id, t.id)
        self.mini._abrir_foco()  # 2º clique: minimiza
        self.app.processEvents()
        self.assertTrue(self.janela.isMinimized())
        self.mini._abrir_foco()  # 3º: volta
        self.app.processEvents()
        self.assertTrue(self.janela.visivel())

    def test_mini_barra(self):
        self.assertEqual(self.mini.tarefa_em_foco().titulo, "enviar proposta")
        self.mini.navegar(1)
        segunda = self.mini.tarefa_em_foco()
        self.mini._feito()
        self.assertEqual(self.banco.tarefa(segunda.id).status, "concluida")
        self.mini.campo.setText("ligar para o fornecedor 15min")
        self.assertTrue(self.mini.balao.isVisible())
        self.mini._enter()
        self.assertTrue(any(t.titulo == "ligar para o fornecedor" for t in self.banco.tarefas("aberta")))
        self.mini.grab().save(str(Path(__file__).parent / "capturas" / "07-mini-barra.png")) if (Path(__file__).parent / "capturas").exists() else None
        self.mini.alternar_recolhida()
        self.assertFalse(self.mini.expandida.isVisible())
        self.assertTrue(self.sv.config().mini_barra_recolhida)
        self.mini.alternar_recolhida()
        self.assertTrue(self.mini.expandida.isVisible())

    def test_fechar_so_esconde(self):
        self.janela._saindo = False
        self.janela.close()
        self.app.processEvents()
        self.assertFalse(self.janela.isVisible())
        self.assertTrue(self.mini.isVisible())
        self.janela.mostrar_janela()
        self.assertTrue(self.janela.isVisible())


if __name__ == "__main__":
    unittest.main()
