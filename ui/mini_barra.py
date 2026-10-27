"""Mini barra: sempre por cima, arrastável, recolhível. Trabalha a tarefa em foco e captura novas."""
from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QColor, QGuiApplication, QKeySequence, QPainter, QPainterPath, QShortcut
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QToolButton,
                               QVBoxLayout, QWidget)

from nucleo.captura import formata_dia, formata_minutos
from nucleo.planejador import tarefas_do_dia

from . import estilo
from .hoje import CONFLITOS, meta_tarefa

LARGURA, LARGURA_RECOLHIDA, ALTURA = 760, 156, 56
ESCURO, ESCURO_2, CINZA_CLARO = "#1F2328", "#2B3137", "#C9D1D9"

QSS_MINI = f"""
QWidget#mini {{ background: transparent; }}
QLabel {{ color: white; }}
QLabel[papel="sub"] {{ color: {CINZA_CLARO}; font-size: 11px; }}
QLabel[papel="foco"] {{ color: white; font-size: 15px; font-weight: 600; }}
QPushButton, QToolButton {{ color: white; background: transparent; border: 1px solid #57606A;
    border-radius: 6px; padding: 4px 10px; min-height: 22px; }}
QPushButton:hover, QToolButton:hover {{ background: {ESCURO_2}; }}
QPushButton:focus, QToolButton:focus {{ border: 2px solid #6C9BF0; }}
QPushButton[tipo="primario"] {{ background: {estilo.ACENTO}; border: none; font-weight: 600; }}
QPushButton[tipo="primario"]:hover {{ background: {estilo.ACENTO_ESCURO}; }}
QPushButton#focoBotao {{ border: none; text-align: left; padding: 2px 4px; }}
QPushButton#focoBotao:hover {{ background: {ESCURO_2}; }}
QLineEdit {{ color: white; background: {ESCURO_2}; border: 1px solid #3D444D; border-radius: 6px; padding: 5px 9px; }}
QLineEdit:focus {{ border: 2px solid #6C9BF0; padding: 4px 8px; }}
QToolButton#alca {{ border: none; padding: 0; }}
"""


class _Alca(QToolButton):
    """Alça pontilhada para arrastar a barra."""

    def __init__(self, barra: "MiniBarra"):
        super().__init__()
        self.barra = barra
        self.setObjectName("alca")
        self.setFixedSize(22, 44)
        self.setCursor(Qt.SizeAllCursor)
        self.setToolTip("Arraste para mover")
        self.setAccessibleName("Arrastar a barra para outro lugar da tela")
        self._inicio: QPoint | None = None

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#8A929C"))
        for cx in (7, 14):
            for cy in (14, 22, 30):
                p.drawEllipse(QPoint(cx, cy), 2, 2)

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            self._inicio = ev.globalPosition().toPoint() - self.barra.frameGeometry().topLeft()

    def mouseMoveEvent(self, ev):
        if self._inicio is not None:
            self.barra.mover_para(ev.globalPosition().toPoint() - self._inicio)

    def mouseReleaseEvent(self, ev):
        if self._inicio is not None:
            self._inicio = None
            self.barra.salvar_posicao()


class _Balao(QFrame):
    """Janela flutuante abaixo (ou acima) da barra: prévia da captura, título completo ou aviso."""

    def __init__(self, barra: "MiniBarra"):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.barra = barra
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setStyleSheet(f"QFrame {{ background: white; border: 1px solid {estilo.BORDA_FORTE}; border-radius: 10px; }}"
                           f"QLabel {{ border: none; background: transparent; }}"
                           f"QPushButton {{ border: 1px solid {estilo.BORDA_FORTE}; border-radius: 6px; padding: 4px 10px; background: white; }}")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 10, 10)
        lay.setSpacing(10)
        textos = QVBoxLayout()
        textos.setSpacing(2)
        self.titulo = QLabel()
        self.titulo.setWordWrap(True)
        self.detalhe = QLabel()
        self.detalhe.setWordWrap(True)
        self.detalhe.setStyleSheet(f"color: {estilo.MUTED}; font-size: 12px;")
        textos.addWidget(self.titulo)
        textos.addWidget(self.detalhe)
        lay.addLayout(textos, 1)
        self.btn = QPushButton("Desfazer")
        self.btn.setCursor(Qt.PointingHandCursor)
        self.btn.clicked.connect(self._desfazer)
        lay.addWidget(self.btn)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.hide)
        self.modo = ""

    def exibir(self, titulo: str, detalhe: str = "", cor: str = estilo.TINTA, desfazer: bool = False,
               modo: str = "", segundos: int = 0):
        self.modo = modo
        self.titulo.setText(titulo)
        self.titulo.setStyleSheet(f"color: {cor}; font-size: 14px; font-weight: 600;")
        self.detalhe.setText(detalhe)
        self.detalhe.setVisible(bool(detalhe))
        self.btn.setVisible(desfazer)
        largura = self.barra.width() if modo != "dica" else min(self.barra.width(), 460)
        self.setFixedWidth(max(320, largura))
        self.adjustSize()
        self.posicionar()
        self.show()
        self.raise_()
        if segundos:
            self.timer.start(segundos * 1000)
        else:
            self.timer.stop()

    def posicionar(self):
        g = self.barra.frameGeometry()
        tela = (self.barra.screen() or QGuiApplication.primaryScreen()).availableGeometry()
        y = g.bottom() + 6
        if y + self.height() > tela.bottom():
            y = g.top() - self.height() - 6
        x = min(max(tela.left(), g.left()), tela.right() - self.width())
        self.move(x, y)

    def _desfazer(self):
        self.hide()
        self.barra.janela.desfazer()


class MiniBarra(QWidget):
    def __init__(self, janela):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.janela = janela
        self.sv = janela.sv
        self.idx = 0
        self.modo_anotar = False
        self.setObjectName("mini")
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet(QSS_MINI)
        self.setWindowTitle("Produtividade · mini barra")
        self.balao = _Balao(self)

        self.raiz = QHBoxLayout(self)
        self.raiz.setContentsMargins(4, 6, 10, 6)
        self.raiz.setSpacing(8)
        self.raiz.addWidget(_Alca(self))

        # --- parte expandida ---
        self.expandida = QWidget()
        ex = QHBoxLayout(self.expandida)
        ex.setContentsMargins(0, 0, 0, 0)
        ex.setSpacing(8)
        self.foco = QPushButton()
        self.foco.setObjectName("focoBotao")
        self.foco.setFixedWidth(210)
        self.foco.setCursor(Qt.PointingHandCursor)
        self.foco.setAccessibleName("Abrir detalhes da tarefa em foco")
        self.foco.clicked.connect(self._abrir_foco)
        self.foco.installEventFilter(self)
        fv = QVBoxLayout(self.foco)
        fv.setContentsMargins(4, 0, 4, 0)
        fv.setSpacing(0)
        self.foco_sub = QLabel()
        self.foco_sub.setProperty("papel", "sub")
        self.foco_titulo = QLabel()
        self.foco_titulo.setProperty("papel", "foco")
        for lb in (self.foco_sub, self.foco_titulo):
            lb.setAttribute(Qt.WA_TransparentForMouseEvents)
            fv.addWidget(lb)
        ex.addWidget(self.foco)
        setas = QVBoxLayout()
        setas.setSpacing(2)
        self.sobe = self._seta(Qt.UpArrow, "Tarefa anterior do dia", lambda: self.navegar(-1))
        self.desce = self._seta(Qt.DownArrow, "Próxima tarefa do dia", lambda: self.navegar(1))
        setas.addWidget(self.sobe)
        setas.addWidget(self.desce)
        ex.addLayout(setas)
        self.btn_feito = self._botao("Feito", self._feito, "Concluir a tarefa em foco (Ctrl+Enter)", "primario")
        self.btn_adiar = self._botao("Adiar", self._adiar, "Adiar a tarefa em foco (Ctrl+D)")
        ex.addWidget(self.btn_feito)
        ex.addWidget(self.btn_adiar)
        self.vazio = QLabel("Dia concluído. Bom trabalho.")
        self.vazio.setProperty("papel", "sub")
        self.vazio.setFixedWidth(300)
        ex.addWidget(self.vazio)
        self.campo = QLineEdit()
        self.campo.setPlaceholderText("+ nova tarefa e Enter")
        self.campo.setAccessibleName("Captura rápida")
        self.campo.textChanged.connect(self._previa)
        self.campo.returnPressed.connect(self._enter)
        ex.addWidget(self.campo, 1)
        ex.addWidget(self._botao("?", self._ajuda, "Atalhos e como escrever tarefas"))
        self.progresso = QLabel()
        self.progresso.setProperty("papel", "sub")
        self.progresso.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        ex.addWidget(self.progresso)
        ex.addWidget(self._icone_janela())
        ex.addWidget(self._botao("⇥", self.alternar_recolhida, "Recolher a mini barra (Ctrl+B)"))
        self.raiz.addWidget(self.expandida, 1)

        # --- parte recolhida ---
        self.recolhida = QWidget()
        rc = QHBoxLayout(self.recolhida)
        rc.setContentsMargins(0, 0, 0, 0)
        rc.setSpacing(6)
        self.btn_expandir = self._botao("⇤", self.alternar_recolhida, "Expandir a mini barra (Ctrl+B)")
        rc.addWidget(self.btn_expandir)
        rc.addWidget(self._icone_janela())
        self.raiz.addWidget(self.recolhida)

        for seq, f in [("Ctrl+Return", self._feito), ("Ctrl+Enter", self._feito), ("Ctrl+D", self._adiar),
                       ("Ctrl+Up", lambda: self.navegar(-1)), ("Ctrl+Down", lambda: self.navegar(1)),
                       ("Ctrl+J", self.janela.alternar_janela), ("Ctrl+B", self.alternar_recolhida),
                       ("Ctrl+L", self._modo_anotar), ("F1", self._ajuda)]:
            QShortcut(QKeySequence(seq), self, f)
        QShortcut(QKeySequence(Qt.Key_Escape), self, self._esc)

        self.setFixedHeight(ALTURA)
        cfg = self.sv.config()
        self._aplicar_recolhida(cfg.mini_barra_recolhida)
        self._posicao_inicial(cfg)
        self.atualizar()

    # ---------------- construção ----------------
    def _botao(self, texto, ao_clicar, dica, tipo=None) -> QPushButton:
        b = QPushButton(texto)
        if tipo:
            b.setProperty("tipo", tipo)
        b.setToolTip(dica)
        b.setAccessibleName(dica)
        b.setCursor(Qt.PointingHandCursor)
        b.clicked.connect(ao_clicar)
        return b

    def _seta(self, direcao, dica, ao_clicar) -> QToolButton:
        b = QToolButton()
        b.setArrowType(direcao)
        b.setFixedSize(26, 20)
        b.setToolTip(dica)
        b.setAccessibleName(dica)
        b.setStyleSheet("padding: 0;")
        b.clicked.connect(ao_clicar)
        return b

    def _icone_janela(self) -> QPushButton:
        b = self._botao("▭", self.janela.alternar_janela, "Mostrar ou ocultar a janela principal (Ctrl+J)")
        b.setFixedWidth(36)
        return b

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        caminho = QPainterPath()
        caminho.addRoundedRect(self.rect().adjusted(0, 0, -1, -1), 12, 12)
        p.fillPath(caminho, QColor(ESCURO))

    # ---------------- posição ----------------
    def _posicao_inicial(self, cfg):
        tela = QGuiApplication.primaryScreen().availableGeometry()
        if cfg.mini_barra_x is None or cfg.mini_barra_y is None:
            self.move(tela.right() - self.width() - 24, tela.top() + 24)
        else:
            self.mover_para(QPoint(cfg.mini_barra_x, cfg.mini_barra_y))

    def mover_para(self, ponto: QPoint):
        """Move mantendo a barra inteira dentro da tela onde o ponto está."""
        tela = QGuiApplication.screenAt(ponto) or self.screen() or QGuiApplication.primaryScreen()
        area: QRect = tela.availableGeometry()
        x = min(max(area.left(), ponto.x()), area.right() - self.width())
        y = min(max(area.top(), ponto.y()), area.bottom() - self.height())
        self.move(x, y)
        if self.balao.isVisible():
            self.balao.posicionar()

    def salvar_posicao(self):
        cfg = self.sv.config()
        cfg.mini_barra_x, cfg.mini_barra_y = self.x(), self.y()
        cfg.mini_barra_recolhida = not self.expandida.isVisible()
        self.sv.banco.salvar_config(cfg)

    def alternar_recolhida(self):
        direita = self.frameGeometry().right()
        self._aplicar_recolhida(self.expandida.isVisible())
        # recolhe/expande mantendo a borda direita no lugar
        self.mover_para(QPoint(direita - self.width() + 1, self.y()))
        self.salvar_posicao()

    def _aplicar_recolhida(self, recolher: bool):
        self.expandida.setVisible(not recolher)
        self.recolhida.setVisible(recolher)
        self.setFixedWidth(LARGURA_RECOLHIDA if recolher else LARGURA)
        self.balao.hide()

    # ---------------- dados ----------------
    def _tarefas(self):
        return tarefas_do_dia(self.sv.banco.tarefas("aberta"), self.sv.hoje_util())

    def atualizar(self):
        tarefas = self._tarefas()
        self.idx = max(0, min(self.idx, len(tarefas) - 1))
        tem = bool(tarefas)
        for w in (self.foco, self.sobe, self.desce, self.btn_feito, self.btn_adiar):
            w.setVisible(tem)
        self.vazio.setVisible(not tem)
        if tem:
            t = tarefas[self.idx]
            self.foco_sub.setText(f"Agora · {self.idx + 1} de {len(tarefas)} · {formata_minutos(t.minutos)}")
            metricas = self.foco_titulo.fontMetrics()
            self.foco_titulo.setText(metricas.elidedText(t.titulo, Qt.ElideRight, 196))
            self.sobe.setEnabled(self.idx > 0)
            self.desce.setEnabled(self.idx < len(tarefas) - 1)
        hoje = self.sv.hoje()
        feitas = sum(1 for t in self.sv.banco.tarefas("concluida") if t.concluida_em and t.concluida_em.date() == hoje)
        dia = self.sv.hoje_util()
        usado = sum(t.minutos for t in tarefas) + self.sv.reservas().get(dia, 0)
        livre = self.sv.calendario().capacidade(dia) - usado
        self.progresso.setText(f"{feitas} de {feitas + len(tarefas)} hoje\n" +
                               (f"{formata_minutos(-livre)} acima" if livre < 0 else f"{formata_minutos(livre)} livres"))
        self.btn_expandir.setText(f"⇤  {len(tarefas)} tarefa{'s' if len(tarefas) != 1 else ''}")

    def tarefa_em_foco(self):
        tarefas = self._tarefas()
        return tarefas[self.idx] if tarefas else None

    def navegar(self, passo: int):
        self.idx += passo
        self.atualizar()

    # ---------------- ações ----------------
    def avisar(self, mensagem: str, pode_desfazer: bool = True):
        linhas = mensagem.split("\n")
        self.balao.exibir(linhas[0], "\n".join(linhas[1:]), desfazer=pode_desfazer, modo="aviso", segundos=6)

    def _feito(self):
        t = self.tarefa_em_foco()
        if t:
            self.janela.executar(self.sv.concluir, t.id)

    def _adiar(self):
        t = self.tarefa_em_foco()
        if t:
            self.janela.adiar(t.id)

    def _abrir_foco(self):
        """1º clique: abre a janela nos detalhes da tarefa. 2º clique (janela já mostrando ela): minimiza."""
        t = self.tarefa_em_foco()
        self.balao.hide()
        ja_aberta = self.janela.visivel() and (t is None or self.janela.sel_id == t.id)
        if ja_aberta:
            self.janela.showMinimized()
        elif t:
            self.janela.mostrar_tarefa(t.id)
        else:
            self.janela.mostrar_janela()

    def _previa(self, texto: str):
        if self.modo_anotar:
            return
        if texto.strip():
            self.balao.exibir("Entendi: " + self.sv.prever(texto), "Enter salva · Esc limpa · ? mostra os atalhos",
                              cor=estilo.ACENTO_ESCURO, modo="previa")
        elif self.balao.modo == "previa":
            self.balao.hide()

    def _enter(self):
        texto = self.campo.text().strip()
        if not texto:
            return
        if self.modo_anotar:
            t = self.tarefa_em_foco()
            if t:
                self.sv.anotar(t.id, "Feito", texto)
                self.avisar(f"Anotado no diário de “{t.titulo}”.", False)
            self._sair_anotar()
            self.janela.recarregar()
            return
        self.campo.clear()
        self.janela.capturar(texto)

    def _modo_anotar(self):
        t = self.tarefa_em_foco()
        if not t:
            return
        self.modo_anotar = True
        self.campo.clear()
        self.campo.setPlaceholderText(f"Anotar no diário: {t.titulo[:40]}… (Enter salva, Esc cancela)")
        self.activateWindow()
        self.campo.setFocus()

    def _sair_anotar(self):
        self.modo_anotar = False
        self.campo.clear()
        self.campo.setPlaceholderText("+ nova tarefa e Enter")

    def _esc(self):
        if self.modo_anotar:
            self._sair_anotar()
        elif self.campo.text():
            self.campo.clear()
        else:
            self.balao.hide()

    def _ajuda(self):
        self.balao.exibir("Como escrever: tarefa  p|m|g ou 15min  até sex  #projeto  !  @pessoa",
                          "Ctrl+Enter conclui · Ctrl+D adia · Ctrl+↑/↓ troca a tarefa · Ctrl+L anota no diário · "
                          "Ctrl+J janela · Ctrl+B recolhe. O manual completo fica no botão Manual da janela (F1).",
                          modo="ajuda", segundos=12)

    # ---------------- balão do título ----------------
    def eventFilter(self, obj, ev):
        if obj is self.foco:
            if ev.type() == QEvent.Enter:
                t = self.tarefa_em_foco()
                if t and not self.campo.text():
                    detalhe = meta_tarefa(t) + (f" · {CONFLITOS[t.conflito]}" if t.conflito else "") + " · clique para abrir"
                    self.balao.exibir(t.titulo, detalhe, modo="dica")
            elif ev.type() == QEvent.Leave and self.balao.modo == "dica":
                self.balao.hide()
        return super().eventFilter(obj, ev)

    def hideEvent(self, ev):
        self.balao.hide()
        super().hideEvent(ev)
