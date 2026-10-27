"""Janela principal: abas, painel da tarefa (sempre por cima, à direita) e avisos com Desfazer."""
from __future__ import annotations

from datetime import date

from PySide6.QtCore import QEvent, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetrics, QKeySequence, QShortcut
from PySide6.QtWidgets import (QButtonGroup, QFrame, QGraphicsDropShadowEffect, QHBoxLayout,
                               QLineEdit, QMainWindow, QMessageBox, QPushButton, QStackedWidget,
                               QVBoxLayout, QWidget)

from nucleo.captura import formata_dia
from nucleo.servico import Resultado, Servico

from . import estilo
from .aguardando import TelaAguardando
from .avisos import AgendadorAvisos, JanelaAvisoHora, tocar
from .configuracoes import TelaConfiguracoes
from .manual import DialogoAtalhos, TelaManual
from .concluidas import TelaConcluidas
from .dialogos import DialogoDecisao, DialogoEspera, DialogoRecebi
from .hoje import DIAS_LONGOS, TelaHoje
from .reunioes import TelaReunioes
from .painel import PainelTarefa
from .semana import TelaSemana
from .widgets import Aviso, botao, rotulo


class BotaoAba(QPushButton):
    """Aba do topo. Reserva a largura do texto em negrito, que é como ela fica quando selecionada:
    sem isso o texto em destaque não cabia e as pontas (ex.: o "C" de Concluídas) ficavam cortadas."""

    def __init__(self, texto: str):
        super().__init__(texto)
        self.setProperty("tipo", "aba")
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)

    def sizeHint(self) -> QSize:
        base = super().sizeHint()
        negrito = QFont(self.font())
        negrito.setWeight(QFont.Bold)
        extra = QFontMetrics(negrito).horizontalAdvance(self.text()) - self.fontMetrics().horizontalAdvance(self.text())
        return QSize(base.width() + max(0, extra) + 6, base.height())

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()


class JanelaPrincipal(QMainWindow):
    LARGURA_MINIMA = 960

    def __init__(self, servico: Servico):
        super().__init__()
        self.sv = servico
        self.sel_id: int | None = None
        self._ultimo_adiado: int | None = None
        self.mini = None      # MiniBarra, ligada por conectar_mini()
        self.bandeja = None   # Bandeja, ligada por conectar_mini()
        self._saindo = False
        self._dia = self.sv.hoje()
        self.setWindowTitle("Produtividade")
        self.setMinimumSize(self.LARGURA_MINIMA, 640)
        self.resize(1120, 800)

        central = QWidget()
        central.setObjectName("fundo")
        self.setCentralWidget(central)
        raiz = QVBoxLayout(central)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)
        raiz.addWidget(self._barra_topo())

        self.area = QWidget()
        self.area_lay = QHBoxLayout(self.area)
        self.area_lay.setContentsMargins(0, 0, 0, 0)
        self.area_lay.setSpacing(0)
        self.pilha = QStackedWidget()
        self.telas = {
            "hoje": TelaHoje(self),
            "semana": TelaSemana(self),
            "aguardando": TelaAguardando(self),
            "reunioes": TelaReunioes(self),
            "concluidas": TelaConcluidas(self),
            "config": TelaConfiguracoes(self),   # sem aba: botão Configurações no topo
            "manual": TelaManual(self),          # sem aba: botão Manual no topo (F1)
        }
        for tela in self.telas.values():
            self.pilha.addWidget(tela)
        self.area_lay.addWidget(self.pilha, 1)
        self.painel = PainelTarefa(self, self.area)  # filho da área, fora do layout: abre por cima
        self.painel.hide()
        sombra = QGraphicsDropShadowEffect(self.painel)
        sombra.setBlurRadius(24)
        sombra.setOffset(-6, 0)
        sombra.setColor(QColor(0, 0, 0, 45))
        self.painel.setGraphicsEffect(sombra)
        self.area.installEventFilter(self)
        raiz.addWidget(self.area, 1)

        self.aviso = Aviso(central)
        self.aviso.desfazer.connect(self.desfazer)
        self.aviso.motivo.connect(self._motivo)

        self._atalhos()
        self.relogio = QTimer(self)
        self.relogio.timeout.connect(self._verificar_virada)
        self.relogio.start(60_000)
        self.janela_aviso = JanelaAvisoHora()
        self.janela_aviso.acao.connect(self._acao_aviso)
        self.agendador = AgendadorAvisos(self.sv, parent=self)
        self.agendador.disparar.connect(self.mostrar_aviso_hora)
        self.ir_para("hoje")

    # ---------------- montagem ----------------
    def _barra_topo(self) -> QFrame:
        barra = QFrame()
        barra.setObjectName("barraTopo")
        h = QHBoxLayout(barra)
        h.setContentsMargins(16, 0, 16, 0)
        h.setSpacing(2)
        self.grupo_abas = QButtonGroup(self)
        self.abas = {}
        for chave, nome in [("hoje", "Hoje"), ("semana", "Semana"), ("aguardando", "Aguardando"),
                            ("reunioes", "Reuniões"), ("concluidas", "Concluídas")]:
            b = BotaoAba(nome)
            b.clicked.connect(lambda _=False, c=chave: self.ir_para(c))
            self.grupo_abas.addButton(b)
            self.abas[chave] = b
            h.addWidget(b)
        h.addStretch(1)
        self.rotulo_data = rotulo("", "subtitulo")
        h.addWidget(self.rotulo_data)
        h.addSpacing(12)
        self.botoes_topo = {}
        for chave, nome, dica, acao in [("config", "Configurações", "Jornada, avisos, ausências e backup (Ctrl+,)", lambda: self.ir_para("config")),
                                        ("manual", "Manual", "Manual de uso (F1)", lambda: self.ir_para("manual")),
                                        ("atalhos", "? Atalhos", "Cola: como escrever uma tarefa e os atalhos", self.mostrar_atalhos)]:
            b = botao(nome, ao_clicar=acao, dica=dica)
            if chave != "atalhos":
                b.setCheckable(True)
            self.botoes_topo[chave] = b
            h.addWidget(b)
        return barra

    def mostrar_atalhos(self):
        DialogoAtalhos(self._pai_dialogo(), abrir_manual=lambda: self.ir_para("manual")).exec()

    def _atalhos(self):
        QShortcut(QKeySequence("Ctrl+N"), self, self._nova_tarefa)
        QShortcut(QKeySequence(Qt.Key_F1), self, lambda: self.ir_para("manual"))
        QShortcut(QKeySequence("Ctrl+,"), self, lambda: self.ir_para("config"))
        QShortcut(QKeySequence("Ctrl+Return"), self, lambda: self.sel_id and self.executar(self.sv.concluir, self.sel_id))
        QShortcut(QKeySequence("Ctrl+Enter"), self, lambda: self.sel_id and self.executar(self.sv.concluir, self.sel_id))
        QShortcut(QKeySequence("Ctrl+D"), self, lambda: self.sel_id and self.adiar(self.sel_id))
        QShortcut(QKeySequence("Ctrl+Z"), self, self.desfazer)
        QShortcut(QKeySequence(Qt.Key_F2), self, lambda: self.painel.isVisible() and self.painel.editar_titulo())
        QShortcut(QKeySequence("Ctrl+J"), self, self.alternar_janela)
        QShortcut(QKeySequence("Ctrl+B"), self, lambda: self.mini and self.mini.alternar_recolhida())
        QShortcut(QKeySequence(Qt.Key_Escape), self, self._esc)
        for i, chave in enumerate(["hoje", "semana", "aguardando", "reunioes", "concluidas"], start=1):
            QShortcut(QKeySequence(f"Ctrl+{i}"), self, lambda c=chave: self.ir_para(c))

    # ---------------- navegação ----------------
    def ir_para(self, chave: str):
        """Troca de aba e fecha o painel da tarefa."""
        self.sel_id = None
        self.painel.tarefa_id = None
        self.painel.editando_titulo = False
        self.aba_atual = chave
        if chave in self.abas:
            self.abas[chave].setChecked(True)
        else:  # Configurações e Manual não são abas: nenhuma aba fica marcada
            self.grupo_abas.setExclusive(False)
            for b in self.abas.values():
                b.setChecked(False)
            self.grupo_abas.setExclusive(True)
        for k, b in getattr(self, "botoes_topo", {}).items():
            if b.isCheckable():
                b.setChecked(k == chave)
        self.pilha.setCurrentWidget(self.telas[chave])
        self._posicionar_painel()
        self.recarregar()

    def _esc(self):
        """Esc limpa o campo de texto em foco; sem texto, fecha o painel da tarefa."""
        if self.painel.isVisible() and self.painel.cancelar_edicao():
            return
        foco = self.focusWidget()
        if isinstance(foco, QLineEdit) and foco.text():
            foco.clear()
        else:
            self.fechar_painel()

    def _nova_tarefa(self):
        self.ir_para("hoje")
        self.telas["hoje"].focar_captura()

    def abrir_tarefa(self, tarefa_id: int):
        self.sel_id = tarefa_id
        self.painel.mostrar(tarefa_id)
        self._posicionar_painel()
        self.recarregar(painel=False)

    def fechar_painel(self):
        self.sel_id = None
        self.painel.tarefa_id = None
        self.painel.hide()
        self.recarregar(painel=False)

    def _posicionar_painel(self):
        """Em todas as abas o painel abre por cima do conteúdo, encostado à direita, com sombra."""
        x = self.area.width() - PainelTarefa.LARGURA
        self.painel.setGeometry(max(0, x), 0, PainelTarefa.LARGURA, self.area.height())
        self.painel.setVisible(self.sel_id is not None)
        if self.sel_id is not None:
            self.painel.raise_()

    def eventFilter(self, obj, ev):
        if obj is self.area and ev.type() == QEvent.Resize:
            self._posicionar_painel()
        return super().eventFilter(obj, ev)

    # ---------------- janela, mini barra e bandeja ----------------
    def conectar_mini(self, mini, bandeja):
        self.mini, self.bandeja = mini, bandeja

    def mostrar_janela(self, recarregar: bool = True):
        if self.isMinimized():
            self.showNormal()
        else:
            self.show()
        self.raise_()
        self.activateWindow()
        if recarregar:
            self.recarregar()

    def mostrar_tarefa(self, tarefa_id: int):
        """Usado pela mini barra: abre a janela já em Hoje com o painel da tarefa, redesenhando uma vez só."""
        self.aba_atual = "hoje"
        self.abas["hoje"].setChecked(True)
        self.pilha.setCurrentWidget(self.telas["hoje"])
        self.sel_id = tarefa_id
        self.painel.mostrar(tarefa_id)
        self._posicionar_painel()
        self.mostrar_janela(recarregar=False)
        self.recarregar(painel=False)

    def alternar_janela(self):
        if self.isVisible() and not self.isMinimized():
            self.hide()
        else:
            self.mostrar_janela()

    def visivel(self) -> bool:
        return self.isVisible() and not self.isMinimized()

    def closeEvent(self, ev):
        """O X só esconde: a mini barra e o ícone da bandeja continuam. Para sair: bandeja › Sair."""
        if self._saindo or self.bandeja is None:
            ev.accept()
            return
        ev.ignore()
        self.hide()
        self.bandeja.avisar_que_continua()

    def sair(self):
        self._saindo = True
        if self.mini:
            self.mini.salvar_posicao()
            self.mini.close()
        if self.bandeja:
            self.bandeja.hide()
        self.janela_aviso.hide()
        self.close()
        from PySide6.QtWidgets import QApplication
        QApplication.quit()

    def avisar(self, mensagem: str, pode_desfazer: bool = True, pedir_motivo: bool = False):
        """Mostra o aviso onde a pessoa está olhando: na janela, se visível; senão, junto à mini barra."""
        na_mini = (self.mini is not None and self.mini.isVisible()
                   and (not self.visivel() or (self.mini.isActiveWindow() and not self.isActiveWindow())))
        if na_mini:
            self.mini.avisar(mensagem, pode_desfazer)
        else:
            self.aviso.mostrar(mensagem, pode_desfazer, pedir_motivo)

    def _pai_dialogo(self):
        return self if self.visivel() else None

    # ---------------- ações (usadas pelas telas) ----------------
    def recarregar(self, painel: bool = True):
        h = self.sv.hoje()
        self.rotulo_data.setText(f"{DIAS_LONGOS[h.weekday()]}, {h:%d/%m}")
        n_ag = len(self.sv.banco.aguardando("aberto"))
        self.abas["aguardando"].setText(f"Aguardando ({n_ag})" if n_ag else "Aguardando")
        n_c = len(self.sv.banco.tarefas("concluida"))
        self.abas["concluidas"].setText(f"Concluídas ({n_c})" if n_c else "Concluídas")
        self.telas[self.aba_atual].atualizar()
        if painel and self.painel.isVisible():
            self.painel.atualizar()
        if self.mini:
            self.mini.atualizar()
        if self.bandeja:
            self.bandeja.atualizar()

    def executar(self, funcao, *args, **kwargs) -> Resultado:
        r = funcao(*args, **kwargs)
        if isinstance(r, Resultado):
            self.avisar(r.mensagem, r.pode_desfazer)
        self.recarregar()
        return r

    def capturar(self, texto: str):
        self.executar(self.sv.capturar, texto)

    def definir_capacidade(self, dia: date, minutos: int):
        self.executar(self.sv.definir_capacidade, dia, minutos)

    def adiar(self, tarefa_id: int):
        r = self.sv.adiar(tarefa_id)
        if r.precisa_decisao:
            t = self.sv.banco.tarefa(tarefa_id)
            dlg = DialogoDecisao(t.titulo, t.adiamentos, self._pai_dialogo())
            if dlg.exec() and dlg.escolha:
                if dlg.escolha == "adiar_mesmo":
                    r = self.sv.adiar(tarefa_id, forcar=True)
                else:
                    r = self.sv.decidir(tarefa_id, dlg.escolha)
                    self.avisar(r.mensagem, r.pode_desfazer)
                    self.recarregar()
                    return
            else:
                return
        self._ultimo_adiado = tarefa_id
        self.avisar(r.mensagem, r.pode_desfazer, pedir_motivo=True)
        self.recarregar()

    def _motivo(self, motivo: str):
        if self._ultimo_adiado:
            self.sv.anotar_motivo_adiamento(self._ultimo_adiado, motivo.lower())
            self.recarregar()

    def recebi(self, aguardando_id: int):
        a = next(x for x in self.sv.banco.aguardando() if x.id == aguardando_id)
        dlg = DialogoRecebi(self, a.pessoa, a.o_que, self._pai_dialogo())
        if dlg.exec():
            self.executar(self.sv.recebi, aguardando_id, dlg.texto_tarefa)

    def excluir(self, tarefa_id: int):
        t = self.sv.banco.tarefa(tarefa_id)
        if t is None:
            return
        caixa = QMessageBox(QMessageBox.Warning, "Excluir tarefa",
                            f"Excluir “{t.titulo}”?\n\nA tarefa e o diário dela serão apagados. "
                            "Se foi sem querer, use Desfazer (Ctrl+Z) logo em seguida.",
                            QMessageBox.NoButton, self._pai_dialogo())
        sim = caixa.addButton("Excluir", QMessageBox.DestructiveRole)
        cancelar = caixa.addButton("Cancelar", QMessageBox.RejectRole)
        caixa.setDefaultButton(cancelar)  # Enter sem pensar não apaga nada
        caixa.exec()
        if caixa.clickedButton() is not sim:
            return
        if self.sel_id == tarefa_id:
            self.fechar_painel()
        self.executar(self.sv.excluir, tarefa_id)

    def editar_espera(self, aguardando_id: int):
        a = next((x for x in self.sv.banco.aguardando() if x.id == aguardando_id), None)
        if a is None:
            return
        dlg = DialogoEspera(a.pessoa, a.o_que, a.cobrar_em, self._pai_dialogo(), a.eventos)
        if not dlg.exec():
            return
        if dlg.acao == "excluir":
            self.executar(self.sv.excluir_espera, aguardando_id)
        elif dlg.acao == "salvar":
            self.executar(self.sv.editar_espera, aguardando_id, dlg.pessoa.text(), dlg.o_que.text(), dlg.cobrar_em)

    def abrir_reuniao(self, reuniao_id: int):
        self.fechar_painel()
        self.ir_para("reunioes")
        self.telas["reunioes"].mostrar_detalhe(reuniao_id)

    def excluir_reuniao(self, reuniao_id: int):
        r = self.sv.banco.reuniao(reuniao_id)
        if r is None:
            return
        caixa = QMessageBox(QMessageBox.Warning, "Excluir reunião",
                            f"Excluir a reunião “{r.titulo}”?\n\nAs tarefas e esperas criadas por ela continuam. "
                            "Se foi sem querer, use Desfazer (Ctrl+Z) logo em seguida.",
                            QMessageBox.NoButton, self._pai_dialogo())
        sim = caixa.addButton("Excluir", QMessageBox.DestructiveRole)
        cancelar = caixa.addButton("Cancelar", QMessageBox.RejectRole)
        caixa.setDefaultButton(cancelar)
        caixa.exec()
        if caixa.clickedButton() is sim:
            self.executar(self.sv.excluir_reuniao, reuniao_id)

    # ---------------- avisos de horário ----------------
    def mostrar_aviso_hora(self, tipo: str):
        """Toca o som escolhido e mostra o cartão no canto da tela (também usado pelos botões de teste)."""
        aviso = self.sv.montar_aviso(tipo)
        tocar(self.sv.config().aviso_som)
        self.janela_aviso.mostrar(aviso)

    def _acao_aviso(self, acao: str):
        if acao == "ver_hoje":
            self.mostrar_janela(recarregar=False)
            self.ir_para("hoje")
        elif acao == "replanejar":
            self.mostrar_janela(recarregar=False)
            self.ir_para("hoje")
            self.executar(self.sv.replanejar_resto_do_dia)

    def desfazer(self):
        r = self.sv.desfazer()
        self.avisar(r.mensagem, False)
        self.recarregar()

    # ---------------- virada do dia ----------------
    def _verificar_virada(self):
        hoje = self.sv.hoje()
        if hoje != self._dia:
            self._dia = hoje
            r = self.sv.abrir_o_dia()
            if r:
                self.avisar(r.mensagem)
            self.recarregar()
