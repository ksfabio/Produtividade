"""Inicialização da interface gráfica."""
from __future__ import annotations

import hashlib
import sys
import traceback
from datetime import datetime
from pathlib import Path

from PySide6.QtGui import QFont
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMessageBox

from dados.banco import Banco
from nucleo.servico import Servico

from .estilo import QSS
from .bandeja import Bandeja, icone_app
from .janela import JanelaPrincipal
from .mini_barra import MiniBarra


def criar_app(argv: list[str] | None = None) -> QApplication:
    app = QApplication.instance() or QApplication(argv or sys.argv)
    app.setApplicationName("Produtividade")
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(QSS)
    app.setQuitOnLastWindowClosed(False)  # fechar a janela não encerra: a mini barra continua
    app.setWindowIcon(icone_app())
    return app


def _registrar_erros(pasta_app: Path):
    """Sem terminal (pythonw), erros iriam para lugar nenhum: grava em erros.log e avisa."""
    log = pasta_app / "erros.log"

    def gancho(tipo, valor, tb):
        texto = "".join(traceback.format_exception(tipo, valor, tb))
        try:
            with open(log, "a", encoding="utf-8") as f:
                f.write(f"\n--- {datetime.now():%Y-%m-%d %H:%M:%S} ---\n{texto}")
        except OSError:
            pass
        QMessageBox.warning(None, "Produtividade", f"Algo deu errado: {valor}\n\nDetalhes em {log}. Seus dados estão salvos.")

    sys.excepthook = gancho


def _nome_instancia(pasta_app: Path) -> str:
    return "produtividade-" + hashlib.md5(str(pasta_app).lower().encode("utf-8")).hexdigest()[:12]


def avisar_instancia_aberta(nome: str) -> bool:
    """Se o app já está aberto (ex.: dois cliques no atalho), pede para ele mostrar a janela e devolve True."""
    s = QLocalSocket()
    s.connectToServer(nome)
    if not s.waitForConnected(400):
        return False
    s.write(b"mostrar")
    s.flush()
    s.waitForBytesWritten(400)
    s.disconnectFromServer()
    return True


def _identificar_no_windows():
    """Faz a barra de tarefas mostrar o ícone do app (e não o do Python)."""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Produtividade.App")
        except (AttributeError, OSError):
            pass


def iniciar(arquivo_dados: Path, pasta_app: Path) -> int:
    _identificar_no_windows()
    app = criar_app()
    nome = _nome_instancia(pasta_app)
    if avisar_instancia_aberta(nome):
        return 0  # só uma cópia aberta por vez: a outra mostra a janela
    _registrar_erros(pasta_app)
    banco = Banco(arquivo_dados)
    sv = Servico(banco, pasta_app)
    abertura = sv.abrir_o_dia()
    janela = JanelaPrincipal(sv)
    mini = MiniBarra(janela)
    bandeja = Bandeja(janela, mini)
    janela.conectar_mini(mini, bandeja)
    servidor = QLocalServer(janela)
    QLocalServer.removeServer(nome)  # sobra de um encerramento inesperado
    if servidor.listen(nome):
        def outra_copia():
            conexao = servidor.nextPendingConnection()
            if conexao is not None:
                conexao.disconnectFromServer()
            janela.mostrar_janela()
        servidor.newConnection.connect(outra_copia)
    bandeja.show()
    mini.show()
    janela.show()
    janela.recarregar()
    if abertura:
        janela.avisar(abertura.mensagem)
    codigo = app.exec()
    banco.fechar()
    return codigo
