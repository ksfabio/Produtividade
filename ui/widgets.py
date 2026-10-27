"""Componentes reutilizáveis da interface."""
from __future__ import annotations

from PySide6.QtCore import QDate, QEvent, QObject, QPoint, QRect, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (QDateEdit, QFrame, QHBoxLayout, QLabel, QLayout, QPushButton, QScrollArea,
                               QSizePolicy, QVBoxLayout, QWidget)

from . import estilo


def botao(texto: str, tipo: str | None = None, ao_clicar=None, dica: str | None = None) -> QPushButton:
    b = QPushButton(texto)
    if tipo:
        b.setProperty("tipo", tipo)
    if ao_clicar:
        b.clicked.connect(ao_clicar)
    if dica:
        b.setToolTip(dica)
        b.setAccessibleName(dica)
    b.setCursor(Qt.PointingHandCursor)
    return b


def rotulo(texto: str = "", papel: str | None = None, quebra: bool = False) -> QLabel:
    lb = QLabel(texto)
    if papel:
        lb.setProperty("papel", papel)
    lb.setWordWrap(quebra)
    lb.setTextInteractionFlags(Qt.NoTextInteraction)
    return lb


def selo(texto: str, cor_texto: str, cor_fundo: str, borda: str | None = None) -> QLabel:
    lb = QLabel(texto)
    lb.setStyleSheet(estilo.selo(texto, cor_texto, cor_fundo, borda))
    lb.setAttribute(Qt.WA_TransparentForMouseEvents)
    return lb


def texto_longo(texto: str, papel: str | None = None) -> QLabel:
    """Rótulo que quebra linha e nunca alarga o layout: ocupa a largura que houver e cresce para baixo."""
    lb = rotulo(texto, papel, quebra=True)
    pol = lb.sizePolicy()
    pol.setHorizontalPolicy(QSizePolicy.Ignored)
    lb.setSizePolicy(pol)
    lb.setMinimumWidth(40)
    return lb


class TextoClicavel(QLabel):
    """Texto que quebra linha e, ao ser clicado, emite `clicado` (ex.: título da tarefa → editar)."""
    clicado = Signal()

    def __init__(self, texto: str, parent=None):
        super().__init__(texto, parent)
        self.setWordWrap(True)
        pol = self.sizePolicy()
        pol.setHorizontalPolicy(QSizePolicy.Ignored)
        self.setSizePolicy(pol)
        self.setMinimumWidth(40)
        self.setCursor(Qt.IBeamCursor)
        self.setAttribute(Qt.WA_Hover)

    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.LeftButton and self.rect().contains(ev.position().toPoint()):
            self.clicado.emit()
        super().mouseReleaseEvent(ev)


class _FiltroFoco(QObject):
    def __init__(self, alvo, funcao):
        super().__init__(alvo)
        self._funcao = funcao
        alvo.installEventFilter(self)

    def eventFilter(self, obj, ev):
        # ignora o foco que volta sozinho ao reativar a janela (ex.: abrir uma tarefa pela mini barra)
        if ev.type() == QEvent.FocusIn and ev.reason() not in (Qt.ActiveWindowFocusReason, Qt.PopupFocusReason):
            self._funcao()
        return False


def ao_focar(widget: QWidget, funcao):
    """Chama `funcao` sempre que o widget ganha o foco (clique, Tab ou atalho)."""
    return _FiltroFoco(widget, funcao)


def campo_data(dia=None, acessivel: str = "Data") -> QDateEdit:
    """Seletor de data com calendário, largo o bastante para 'seg 26/10/2026' inteiro."""
    d = QDateEdit()
    d.setCalendarPopup(True)
    d.setDisplayFormat("ddd dd/MM/yyyy")
    d.setMinimumWidth(d.fontMetrics().horizontalAdvance("  qua. 30/09/2026  ") + 56)
    d.setAccessibleName(acessivel)
    if dia is not None:
        d.setDate(QDate(dia.year, dia.month, dia.day))
    return d


def vazio(texto: str) -> QLabel:
    """Caixa tracejada para listas vazias."""
    lb = texto_longo(texto, "subtitulo")
    lb.setAlignment(Qt.AlignCenter)
    lb.setStyleSheet(f"padding: 24px; border: 1px dashed {estilo.BORDA_FORTE}; border-radius: 10px;")
    return lb


def area_rolavel(tela: QWidget, margens=(24, 20, 24, 32), espaco: int = 16) -> QVBoxLayout:
    """Põe uma área com rolagem vertical (nunca lateral) dentro da tela e devolve o layout do conteúdo."""
    externo = QVBoxLayout(tela)
    externo.setContentsMargins(0, 0, 0, 0)
    rolagem = QScrollArea()
    rolagem.setWidgetResizable(True)
    rolagem.setFrameShape(QFrame.NoFrame)
    rolagem.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    externo.addWidget(rolagem)
    conteudo = QWidget()
    conteudo.setObjectName("fundo")
    rolagem.setWidget(conteudo)
    lay = QVBoxLayout(conteudo)
    lay.setContentsMargins(*margens)
    lay.setSpacing(espaco)
    return lay


def cabecalho(titulo: str, subtitulo: str = "", *direita: QWidget) -> QHBoxLayout:
    """Título grande + subtítulo à esquerda; botões ou campos à direita."""
    cab = QHBoxLayout()
    cab.setSpacing(12)
    textos = QVBoxLayout()
    textos.setSpacing(2)
    textos.addWidget(rotulo(titulo, "titulo"))
    if subtitulo:
        textos.addWidget(texto_longo(subtitulo, "subtitulo"))
    cab.addLayout(textos, 1)
    for w in direita:
        cab.addWidget(w, 0, Qt.AlignVCenter)
    return cab


class Fluxo(QLayout):
    """Põe os itens lado a lado e passa para a linha de baixo quando não cabem (como texto).

    Assim uma fileira de botões nunca alarga o painel, qualquer que seja a fonte ou o tema do Windows.
    """

    def __init__(self, parent=None, espaco: int = 6):
        super().__init__(parent)
        self._itens = []
        self._espaco = espaco
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item):
        self._itens.append(item)

    def count(self):
        return len(self._itens)

    def itemAt(self, i):
        return self._itens[i] if 0 <= i < len(self._itens) else None

    def takeAt(self, i):
        return self._itens.pop(i) if 0 <= i < len(self._itens) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, largura):
        return self._arranjar(QRect(0, 0, largura, 0), apenas_medir=True)

    def setGeometry(self, ret):
        super().setGeometry(ret)
        self._arranjar(ret, apenas_medir=False)

    def sizeHint(self):
        visiveis = [i for i in self._itens if not i.isEmpty()]
        largura = sum(i.sizeHint().width() for i in visiveis) + self._espaco * max(0, len(visiveis) - 1)
        altura = max((i.sizeHint().height() for i in visiveis), default=0)
        m = self.contentsMargins()
        return QSize(largura + m.left() + m.right(), altura + m.top() + m.bottom())

    def minimumSize(self):
        tam = QSize(0, 0)
        for i in self._itens:
            if not i.isEmpty():
                tam = tam.expandedTo(i.minimumSize())
        m = self.contentsMargins()
        return QSize(tam.width() + m.left() + m.right(), tam.height() + m.top() + m.bottom())

    def _arranjar(self, ret, apenas_medir: bool) -> int:
        m = self.contentsMargins()
        area = ret.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x, y, altura_linha = area.x(), area.y(), 0
        for item in self._itens:
            if item.isEmpty():
                continue
            tam = item.sizeHint().boundedTo(QSize(max(area.width(), 1), 10_000))
            if x > area.x() and x + tam.width() > area.x() + area.width():
                x = area.x()
                y += altura_linha + self._espaco
                altura_linha = 0
            if not apenas_medir:
                item.setGeometry(QRect(QPoint(x, y), tam))
            x += tam.width() + self._espaco
            altura_linha = max(altura_linha, tam.height())
        return y + altura_linha - ret.y() + m.bottom()


def fluxo(*widgets, espaco: int = 6) -> QWidget:
    """Container com Fluxo: use para fileiras de botões ou chips que precisam caber em pouco espaço."""
    caixa = QWidget()
    lay = Fluxo(caixa, espaco)
    for w in widgets:
        lay.addWidget(w)
    return caixa


def limpar_layout(layout: QLayout):
    """Remove e apaga todos os itens de um layout (inclusive sublayouts).

    Esconde antes de apagar e NÃO usa setParent(None): no Windows, um widget sem pai vira por um
    instante uma janela solta, e o redesenho das listas fazia piscar várias janelinhas.
    """
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w is not None:
            w.hide()
            w.deleteLater()
        elif item.layout() is not None:
            limpar_layout(item.layout())


class BarraCapacidade(QWidget):
    """Barra horizontal 'usado / disponível'; fica laranja quando estoura."""

    def __init__(self, altura: int = 8, parent=None):
        super().__init__(parent)
        self.usado, self.total = 0, 1
        self.setFixedHeight(altura)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

    def definir(self, usado: int, total: int):
        self.usado, self.total = usado, total
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect())
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#E6E9ED"))
        p.drawRoundedRect(r, 3, 3)
        frac = 1.0 if self.total <= 0 else min(1.0, self.usado / self.total)
        if frac > 0:
            cor = estilo.LARANJA if self.usado > self.total else estilo.ACENTO
            p.setBrush(QColor(cor))
            p.drawRoundedRect(QRectF(r.x(), r.y(), r.width() * frac, r.height()), 3, 3)


class LinhaClicavel(QFrame):
    """Moldura que inteira é clicável (exceto os botões dentro dela, que tratam o próprio clique)."""
    clicada = Signal()

    def __init__(self, nome_objeto: str = "linhaTarefa", parent=None):
        super().__init__(parent)
        self.setObjectName(nome_objeto)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)

    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.LeftButton and self.rect().contains(ev.position().toPoint()):
            self.clicada.emit()
        super().mouseReleaseEvent(ev)

    def keyPressEvent(self, ev):
        if ev.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.clicada.emit()
        else:
            super().keyPressEvent(ev)

    def marcar_selecionada(self, sim: bool):
        self.setProperty("selecionada", "true" if sim else "false")
        self.style().unpolish(self)
        self.style().polish(self)


class Aviso(QFrame):
    """Aviso flutuante no rodapé da janela (com Desfazer e, ao adiar, os motivos)."""
    desfazer = Signal()
    motivo = Signal(str)

    MOTIVOS = ("Falta de tempo", "Bloqueio", "Prioridade mudou", "Aguardando alguém")

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("aviso")
        self.hide()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 12, 12)
        lay.setSpacing(8)
        topo = QHBoxLayout()
        self.texto = QLabel()
        self.texto.setWordWrap(True)
        self.texto.setMaximumWidth(620)
        topo.addWidget(self.texto, 1)
        self.btn_desfazer = botao("Desfazer", ao_clicar=self._desfazer)
        topo.addWidget(self.btn_desfazer)
        fechar = botao("×", ao_clicar=self.hide, dica="Fechar aviso")
        fechar.setFixedWidth(30)
        topo.addWidget(fechar)
        lay.addLayout(topo)
        self.linha_motivos = QWidget()
        lm = QHBoxLayout(self.linha_motivos)
        lm.setContentsMargins(0, 0, 0, 0)
        lm.setSpacing(6)
        rot = QLabel("Motivo (opcional):")
        rot.setStyleSheet("color: #C9D1D9; font-size: 12px;")
        lm.addWidget(rot)
        for m in self.MOTIVOS:
            b = botao(m, ao_clicar=lambda _=False, m=m: self._motivo(m))
            b.setStyleSheet("font-size: 12px; padding: 3px 10px; border-radius: 12px;")
            lm.addWidget(b)
        lm.addStretch(1)
        lay.addWidget(self.linha_motivos)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.hide)
        parent.installEventFilter(self)

    def mostrar(self, texto: str, pode_desfazer: bool = True, pedir_motivo: bool = False):
        self.texto.setText(texto)
        self.btn_desfazer.setVisible(pode_desfazer)
        self.linha_motivos.setVisible(pedir_motivo)
        self.adjustSize()
        self._posicionar()
        self.show()
        self.raise_()
        self.timer.start(9000 if pedir_motivo else 6000)

    def _posicionar(self):
        pai = self.parentWidget()
        self.adjustSize()
        x = max(16, (pai.width() - self.width()) // 2)
        self.move(QPoint(x, pai.height() - self.height() - 24))

    def eventFilter(self, obj, ev):
        if obj is self.parentWidget() and ev.type() == QEvent.Resize and self.isVisible():
            self._posicionar()
        return False

    def _desfazer(self):
        self.hide()
        self.desfazer.emit()

    def _motivo(self, m: str):
        self.linha_motivos.hide()
        self.texto.setText(self.texto.text().split("\n")[0] + f" · motivo: {m.lower()}")
        self.adjustSize()
        self._posicionar()
        self.motivo.emit(m)
