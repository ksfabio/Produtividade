"""Ícone ao lado do relógio do Windows (bandeja do sistema)."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from . import estilo


def icone_app(tamanho: int = 64) -> QIcon:
    """Quadrado azul arredondado com um visto branco (desenhado, sem arquivo de imagem)."""
    pix = QPixmap(tamanho, tamanho)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    caminho = QPainterPath()
    caminho.addRoundedRect(QRectF(2, 2, tamanho - 4, tamanho - 4), tamanho * 0.22, tamanho * 0.22)
    p.fillPath(caminho, QColor(estilo.ACENTO))
    caneta = QPen(QColor("white"), tamanho * 0.11, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(caneta)
    s = tamanho
    p.drawPolyline([QPointF(s * 0.28, s * 0.52), QPointF(s * 0.44, s * 0.68), QPointF(s * 0.74, s * 0.34)])
    p.end()
    return QIcon(pix)


class Bandeja(QSystemTrayIcon):
    def __init__(self, janela, mini):
        super().__init__(icone_app())
        self.janela = janela
        self.mini = mini
        self._avisou_fechar = False
        menu = QMenu()
        self.acao_janela = QAction("Abrir janela principal", menu, triggered=janela.mostrar_janela)
        self.acao_mini = QAction("Ocultar mini barra", menu, triggered=self.alternar_mini)
        self.acao_recolher = QAction("Recolher / expandir mini barra", menu, triggered=mini.alternar_recolhida)
        self.acao_sair = QAction("Sair", menu, triggered=janela.sair)
        menu.addAction(self.acao_janela)
        menu.addAction(self.acao_mini)
        menu.addAction(self.acao_recolher)
        menu.addSeparator()
        menu.addAction(self.acao_sair)
        self.menu = menu
        self.setContextMenu(menu)
        self.activated.connect(self._ativado)
        self.atualizar()

    def _ativado(self, motivo):
        if motivo in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.janela.alternar_janela()

    def alternar_mini(self):
        if self.mini.isVisible():
            self.mini.hide()
        else:
            self.mini.show()
            self.mini.raise_()
        self.atualizar()

    def atualizar(self):
        self.acao_mini.setText("Ocultar mini barra" if self.mini.isVisible() else "Mostrar mini barra")
        n = len(self.mini._tarefas())
        self.setToolTip(f"Produtividade · {n} tarefa{'s' if n != 1 else ''} para hoje")

    def avisar_que_continua(self):
        """Na primeira vez que a janela é fechada, explica que o app continua rodando."""
        if self._avisou_fechar or not self.supportsMessages():
            return
        self._avisou_fechar = True
        self.showMessage("Produtividade continua rodando",
                         "A mini barra segue ativa e o ícone fica aqui. Para sair de vez: clique com o botão direito › Sair.",
                         QSystemTrayIcon.Information, 6000)
