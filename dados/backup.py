"""Backup diário do dados.db, num arquivo só.

Usa a API de backup do SQLite (cópia consistente mesmo com o app aberto).
O destino é a pasta configurada (ex.: OneDrive corporativo) ou a subpasta backup/.
Fica sempre um único arquivo, dados-backup.db, substituído uma vez por dia. A cópia nova é gravada
primeiro num arquivo temporário e só então troca a antiga: se algo falhar no meio, o backup anterior continua lá.
"""
from __future__ import annotations

import os
import sqlite3
from datetime import date, datetime
from pathlib import Path

NOME_BACKUP = "dados-backup.db"


def arquivo_backup(pasta: str | Path) -> Path:
    return Path(pasta) / NOME_BACKUP


def data_do_backup(pasta: str | Path) -> datetime | None:
    try:
        return datetime.fromtimestamp(arquivo_backup(pasta).stat().st_mtime)
    except OSError:
        return None


def fazer_backup(arquivo_db: str | Path, pasta_destino: str | Path, hoje: date, forcar: bool = False) -> Path | None:
    """Substitui o backup no máximo uma vez por dia (forcar=True refaz agora). Retorna o arquivo, ou None se já era de hoje."""
    pasta = Path(pasta_destino)
    pasta.mkdir(parents=True, exist_ok=True)
    alvo = arquivo_backup(pasta)
    feito = data_do_backup(pasta)
    if feito is not None and feito.date() >= hoje and not forcar:
        return None
    temporario = pasta / (NOME_BACKUP + ".novo")
    origem = sqlite3.connect(arquivo_db)
    destino = sqlite3.connect(temporario)
    try:
        origem.backup(destino)
    finally:
        destino.close()
        origem.close()
    os.replace(temporario, alvo)
    _apagar_backups_antigos(pasta)
    return alvo


def _apagar_backups_antigos(pasta: Path):
    """Versões anteriores do app guardavam um arquivo por dia (dados-AAAA-MM-DD.db): agora fica só o arquivo único."""
    for velho in pasta.glob("dados-????-??-??.db"):
        try:
            velho.unlink()
        except OSError:
            pass  # em uso ou sem permissão: tenta de novo no próximo backup


def pasta_backup_efetiva(pasta_configurada: str, pasta_app: Path) -> Path:
    return Path(pasta_configurada) if pasta_configurada.strip() else pasta_app / "backup"
