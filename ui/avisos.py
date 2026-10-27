"""Avisos de horário: som + janelinha no canto da tela, antes do almoço e do fim da jornada."""
from __future__ import annotations

import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QVBoxLayout, QWidget

from nucleo.sons import gerar_wav

from . import estilo
from .widgets import botao, rotulo, texto_longo

JANELA_DISPARO = timedelta(minutes=15)  # se o app abrir até 15 min depois do horário, ainda avisa


def tocar(nome: str):
    """Toca o som escolhido. No Windows usa o winsound (padrão do Python); fora dele, um bipe do sistema."""
    if nome == "Desligado":
        return
    pasta = Path(tempfile.gettempdir()) / "produtividade-sons"
    arquivo = pasta / f"{nome.lower()}.wav"
    try:
        if not arquivo.exists():
            pasta.mkdir(parents=True, exist_ok=True)
            arquivo.write_bytes(gerar_wav(nome))
        if sys.platform == "win32":
            import winsound
            winsound.PlaySound(str(arquivo), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
            return
    except (OSError, RuntimeError):
        pass
    QApplication.beep()


class JanelaAvisoHora(QWidget):
    """Cartão no canto inferior direito, sempre por cima, até você responder."""
    acao = Signal(str)  # "ver_hoje" | "replanejar" | "ok"

    def __init__(self, parent=None):
        super().__init__(parent, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFixedWidth(400)
        externo = QVBoxLayout(self)
        externo.setContentsMargins(8, 8, 8, 8)
        self.cartao = QFrame()
        self.cartao.setObjectName("avisoHora")
        externo.addWidget(self.cartao)
        v = QVBoxLayout(self.cartao)
        v.setContentsMargins(18, 14, 18, 14)
        v.setSpacing(6)
        self.quando = rotulo("", "rotulo")
        self.titulo = texto_longo("")
        self.titulo.setStyleSheet("font-size: 16px; font-weight: 700;")
        self.mensagem = texto_longo("")
        v.addWidget(self.quando)
        v.addWidget(self.titulo)
        v.addWidget(self.mensagem)
        baixo = QHBoxLayout()
        baixo.addStretch(1)
        self.fechar = botao("Fechar", ao_clicar=lambda: self._responder("ok"))
        self.principal = botao("Ok", "primario")
        self.principal.clicked.connect(lambda: self._responder(self._acao))
        baixo.addWidget(self.fechar)
        baixo.addWidget(self.principal)
        v.addSpacing(4)
        v.addLayout(baixo)
        self._acao = "ok"

    def mostrar(self, aviso):
        cor, fundo = (estilo.LARANJA, "#FFF8EE") if aviso.tipo == "manha" else (estilo.ACENTO, "#F3F6FD")
        self.cartao.setStyleSheet(f"QFrame#avisoHora {{ background: {fundo}; border: 2px solid {cor}; border-radius: 12px; }}")
        self.quando.setText(f"{aviso.hora:%H:%M} · {'ANTES DO FIM DA MANHÃ' if aviso.tipo == 'manha' else 'ANTES DO FIM DO DIA'}")
        self.quando.setStyleSheet(f"color: {cor};")
        self.titulo.setText(aviso.titulo)
        self.mensagem.setText(aviso.mensagem)
        self._acao = aviso.acao
        self.principal.setText(aviso.acao_rotulo)
        self.fechar.setVisible(aviso.acao != "ok")
        self.adjustSize()
        tela = QGuiApplication.primaryScreen()
        if tela is not None:
            area = tela.availableGeometry()
            self.move(area.right() - self.width() - 16, area.bottom() - self.height() - 16)
        self.show()
        self.raise_()

    def _responder(self, acao: str):
        self.hide()
        self.acao.emit(acao)


class AgendadorAvisos(QObject):
    """Confere o relógio a cada 20 s e dispara cada aviso uma vez por dia."""
    disparar = Signal(str)  # tipo do aviso

    def __init__(self, sv, agora=datetime.now, parent=None):
        super().__init__(parent)
        self.sv = sv
        self.agora = agora
        self.disparados: set[tuple] = set()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.verificar)
        self.timer.start(20_000)

    def verificar(self) -> list[str]:
        agora = self.agora()
        saida = []
        for tipo, hora in self.sv.horarios_avisos(agora.date()):
            chave = (agora.date(), tipo)
            if chave in self.disparados:
                continue
            if hora <= agora < hora + JANELA_DISPARO:
                self.disparados.add(chave)
                saida.append(tipo)
                self.disparar.emit(tipo)
            elif agora >= hora + JANELA_DISPARO:
                self.disparados.add(chave)  # passou do horário com o app fechado: não avisa atrasado
        return saida
