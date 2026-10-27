"""Ajuda de instalação: diagnóstico do ambiente e atalhos do Windows (Área de Trabalho e inicializar com o Windows).

Usado por `python app.py verificar | atalho | iniciar-com-windows sim|nao` e pelo instalar.bat.
Nada aqui acessa a rede nem pede permissão de administrador.
"""
from __future__ import annotations

import base64
import json
import os
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

NOME_ATALHO = "Produtividade"
PYTHON_MINIMO = (3, 11)


@dataclass
class Item:
    ok: bool
    nome: str
    detalhe: str


# ---------------------------------------------------------------- diagnóstico
def verificar(pasta_app: Path) -> list[Item]:
    itens = []
    v = sys.version_info
    itens.append(Item(v >= PYTHON_MINIMO, "Python", f"{v.major}.{v.minor}.{v.micro} em {sys.executable}"
                      + ("" if v >= PYTHON_MINIMO else f" (precisa de {PYTHON_MINIMO[0]}.{PYTHON_MINIMO[1]} ou superior)")))
    try:
        import PySide6
        itens.append(Item(True, "PySide6 (interface)", PySide6.__version__))
    except ImportError:
        itens.append(Item(False, "PySide6 (interface)", "não instalado: rode instalar.bat"))
    if os.access(pasta_app, os.W_OK):
        itens.append(Item(True, "Pasta do app", f"{pasta_app} (com permissão de escrita)"))
    else:
        itens.append(Item(False, "Pasta do app", f"{pasta_app}: sem permissão de escrita"))
    db = pasta_app / "dados.db"
    pasta_cfg = ""
    if db.exists():
        try:  # só leitura: a verificação nunca altera os dados
            con = sqlite3.connect(f"{db.resolve().as_uri()}?mode=ro", uri=True)
            n = con.execute("SELECT COUNT(*) FROM tarefa").fetchone()[0]
            versao = con.execute("SELECT valor FROM meta WHERE chave = 'versao'").fetchone()
            linha = con.execute("SELECT valor FROM config WHERE chave = 'pasta_backup'").fetchone()
            con.close()
            pasta_cfg = json.loads(linha[0]) if linha else ""
            itens.append(Item(True, "Dados", f"dados.db com {n} tarefas (esquema {versao[0] if versao else '?'})"))
        except (sqlite3.Error, ValueError) as e:
            itens.append(Item(False, "Dados", f"dados.db não abriu: {e}"))
    else:
        itens.append(Item(True, "Dados", "dados.db ainda não existe (é criado ao abrir o app)"))
    pasta = Path(pasta_cfg) if str(pasta_cfg).strip() else pasta_app / "backup"
    if pasta.exists():
        from dados.backup import arquivo_backup, data_do_backup
        feito = data_do_backup(pasta)
        itens.append(Item(True, "Backup", f"{arquivo_backup(pasta)}" + (f" · feito em {feito:%d/%m/%Y %H:%M}" if feito else " · ainda não feito")))
    elif pasta_cfg:
        itens.append(Item(False, "Backup", f"{pasta} não está acessível (OneDrive desconectado?)"))
    else:
        itens.append(Item(True, "Backup", f"{pasta} (criada no primeiro backup)"))
    if sys.platform == "win32":
        pw = pythonw()
        itens.append(Item(pw.name.lower() == "pythonw.exe", "Abrir sem terminal",
                          str(pw) if pw.name.lower() == "pythonw.exe" else "pythonw.exe não encontrado; o app abre com janela de terminal"))
    return itens


def texto_verificacao(itens: list[Item]) -> str:
    linhas = ["Produtividade · verificação do ambiente", ""]
    for i in itens:
        linhas.append(f"  [{'OK' if i.ok else '!!'}] {i.nome}: {i.detalhe}")
    problemas = sum(not i.ok for i in itens)
    linhas += ["", "Tudo certo." if not problemas else f"{problemas} ponto(s) para resolver (veja INSTALACAO.md › Problemas comuns)."]
    return "\n".join(linhas)


# ---------------------------------------------------------------- atalhos
def pythonw() -> Path:
    """O pythonw.exe ao lado do Python atual (abre o app sem janela de terminal)."""
    exe = Path(sys.executable)
    candidato = exe.with_name("pythonw.exe")
    return candidato if candidato.exists() else exe


def _ps(texto: str) -> str:
    """Texto entre aspas simples do PowerShell (aspas simples dobradas)."""
    return "'" + texto.replace("'", "''") + "'"


def script_atalho(pasta_especial: str, alvo: Path, app_py: Path, pasta_app: Path, icone: Path | None) -> str:
    """Script PowerShell que cria <pasta especial>/Produtividade.lnk. pasta_especial: 'Desktop' ou 'Startup'."""
    linhas = [
        f"$pasta = [Environment]::GetFolderPath({_ps(pasta_especial)})",
        f"$lnk = Join-Path $pasta {_ps(NOME_ATALHO + '.lnk')}",
        "$s = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk)",
        f"$s.TargetPath = {_ps(str(alvo))}",
        f"$s.Arguments = {_ps(chr(34) + str(app_py) + chr(34))}",
        f"$s.WorkingDirectory = {_ps(str(pasta_app))}",
        f"$s.Description = {_ps('Produtividade: tarefas com replanejamento automático')}",
    ]
    if icone is not None:
        linhas.append(f"$s.IconLocation = {_ps(str(icone))}")
    linhas += ["$s.Save()", "Write-Output $lnk"]
    return "\n".join(linhas)


def _rodar_powershell(script: str) -> tuple[bool, str]:
    codificado = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand", codificado],
                           capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, str(e)
    return r.returncode == 0, (r.stdout or r.stderr).strip()


def gerar_icone(pasta_app: Path) -> Path | None:
    """Salva icone.ico (o mesmo ícone da bandeja) para o atalho. Sem PySide6, o atalho fica com o ícone do Python."""
    destino = pasta_app / "icone.ico"
    try:
        if sys.platform != "win32":
            os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtGui import QGuiApplication
        app = QGuiApplication.instance() or QGuiApplication([])  # noqa: F841 - precisa existir para desenhar
        from ui.bandeja import icone_app
        if icone_app(256).pixmap(256, 256).save(str(destino), "ICO"):
            return destino
    except Exception:  # noqa: BLE001
        return None
    return None


def pasta_inicializar() -> Path:
    return Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def criar_atalho(pasta_app: Path, onde: str = "Desktop") -> tuple[bool, str]:
    """Cria o atalho na Área de Trabalho ('Desktop') ou para iniciar com o Windows ('Startup')."""
    if sys.platform != "win32":
        return False, "Atalhos só no Windows."
    script = script_atalho(onde, pythonw(), pasta_app / "app.py", pasta_app, gerar_icone(pasta_app))
    ok, saida = _rodar_powershell(script)
    if ok:
        return True, f"Atalho criado: {saida}"
    if onde == "Startup":  # plano B sem PowerShell: um .cmd na pasta Inicializar
        try:
            cmd = pasta_inicializar() / f"{NOME_ATALHO}.cmd"
            cmd.write_text(f'@echo off\r\ncd /d "{pasta_app}"\r\nstart "" "{pythonw()}" "{pasta_app / "app.py"}"\r\n', encoding="ascii")
            return True, f"Atalho criado (modo simples): {cmd}"
        except OSError as e:
            saida += f" / {e}"
    return False, f"Não consegui criar o atalho ({saida}). Veja INSTALACAO.md › Atalho manual."


def remover_inicializar() -> tuple[bool, str]:
    removidos = []
    for nome in (f"{NOME_ATALHO}.lnk", f"{NOME_ATALHO}.cmd"):
        alvo = pasta_inicializar() / nome
        if alvo.exists():
            try:
                alvo.unlink()
                removidos.append(str(alvo))
            except OSError as e:
                return False, f"Não consegui remover {alvo}: {e}"
    return True, ("Removido: " + ", ".join(removidos)) if removidos else "O app não estava configurado para iniciar com o Windows."


def inicia_com_windows() -> bool:
    return any((pasta_inicializar() / n).exists() for n in (f"{NOME_ATALHO}.lnk", f"{NOME_ATALHO}.cmd"))


# ---------------------------------------------------------------- mini barra
def resetar_mini_barra(arquivo_db: Path) -> str:
    """Volta a mini barra para a posição padrão (útil se ela ficou fora da tela, ex.: após trocar de monitor)."""
    from dados.banco import Banco
    b = Banco(arquivo_db)
    cfg = b.config()
    cfg.mini_barra_x = cfg.mini_barra_y = None
    cfg.mini_barra_recolhida = False
    b.salvar_config(cfg)
    b.fechar()
    return "Mini barra volta para a posição padrão na próxima vez que o app abrir."
