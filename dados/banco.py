"""Persistência em SQLite (arquivo único dados.db, ao lado do app).

Datas são gravadas como texto ISO (AAAA-MM-DD) e listas como JSON.
O esquema tem versão (tabela meta) para permitir migrações futuras.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, fields
from datetime import date, datetime
from pathlib import Path

from nucleo.calendario import Ausencia, ausencias_de_feriados
from nucleo.modelos import Aguardando, Configuracao, Registro, Reuniao, Tarefa

VERSAO_ESQUEMA = 3

ESQUEMA = """
CREATE TABLE IF NOT EXISTS meta (chave TEXT PRIMARY KEY, valor TEXT);
CREATE TABLE IF NOT EXISTS tarefa (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo TEXT NOT NULL, minutos INTEGER NOT NULL, importancia INTEGER NOT NULL DEFAULT 0,
    prazo TEXT, data_fixa TEXT, dia_planejado TEXT, nao_antes_de TEXT,
    status TEXT NOT NULL DEFAULT 'aberta', adiamentos INTEGER NOT NULL DEFAULT 0,
    projeto TEXT, reuniao_id INTEGER, aguardando_id INTEGER,
    criada_em TEXT NOT NULL, concluida_em TEXT,
    ordem_manual INTEGER, ordem_manual_dia TEXT, conflito TEXT
);
CREATE TABLE IF NOT EXISTS registro (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tarefa_id INTEGER NOT NULL REFERENCES tarefa(id),
    tipo TEXT NOT NULL, texto TEXT NOT NULL, quando TEXT NOT NULL,
    feito INTEGER NOT NULL DEFAULT 0, feito_em TEXT
);
CREATE TABLE IF NOT EXISTS aguardando (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pessoa TEXT NOT NULL, o_que TEXT NOT NULL, cobrar_em TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'aberto', cobrancas TEXT NOT NULL DEFAULT '[]',
    recebido_em TEXT, reuniao_id INTEGER, tarefa_origem_id INTEGER, tarefa_gerada_id INTEGER,
    eventos TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS reuniao (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo TEXT NOT NULL, quando TEXT NOT NULL, recap_original TEXT NOT NULL DEFAULT '',
    notas TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS dia (
    data TEXT PRIMARY KEY, minutos_disponiveis INTEGER NOT NULL, observacao TEXT
);
CREATE TABLE IF NOT EXISTS ausencia (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo TEXT NOT NULL, inicio TEXT NOT NULL, fim TEXT NOT NULL,
    descricao TEXT NOT NULL DEFAULT '', origem TEXT NOT NULL DEFAULT 'manual'
);
CREATE TABLE IF NOT EXISTS replanejamento (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quando TEXT NOT NULL, motivo TEXT NOT NULL, mudancas TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS config (chave TEXT PRIMARY KEY, valor TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_tarefa_status ON tarefa(status);
CREATE INDEX IF NOT EXISTS ix_registro_tarefa ON registro(tarefa_id);
"""

_CAMPOS_DATA = {"prazo", "data_fixa", "dia_planejado", "nao_antes_de", "ordem_manual_dia",
                "cobrar_em", "recebido_em", "inicio", "fim"}
_CAMPOS_DATAHORA = {"criada_em", "concluida_em", "quando", "feito_em"}


def _para_db(nome: str, valor):
    if valor is None:
        return None
    if isinstance(valor, bool):
        return int(valor)
    if isinstance(valor, datetime):
        return valor.isoformat(timespec="seconds")
    if isinstance(valor, date):
        return valor.isoformat()
    if isinstance(valor, list):
        return json.dumps([v.isoformat() if isinstance(v, date) else v for v in valor], ensure_ascii=False)
    return valor


def _de_db(nome: str, valor):
    if valor is None:
        return None
    if nome in _CAMPOS_DATA:
        return date.fromisoformat(valor)
    if nome in _CAMPOS_DATAHORA:
        return datetime.fromisoformat(valor)
    if nome == "feito":
        return bool(valor)
    if nome == "cobrancas":
        return [date.fromisoformat(v) for v in json.loads(valor)]
    if nome in ("notas", "eventos"):
        return json.loads(valor)
    return valor


class Banco:
    def __init__(self, caminho: str | Path):
        self.caminho = Path(caminho)
        self.con = sqlite3.connect(self.caminho)
        self.con.row_factory = sqlite3.Row
        self.con.execute("PRAGMA foreign_keys = ON")
        self.con.executescript(ESQUEMA)
        self._migrar()
        self.con.commit()

    def _migrar(self):
        """Atualiza bancos criados por versões anteriores do app, sem perder dados."""
        versao = int(self._meta("versao") or VERSAO_ESQUEMA)
        if versao < VERSAO_ESQUEMA:
            # guarda uma cópia do arquivo como estava, antes de mudar o formato
            copia = self.caminho.with_name(f"{self.caminho.stem}-antes-v{VERSAO_ESQUEMA}.db")
            if not copia.exists():
                destino = sqlite3.connect(copia)
                try:
                    self.con.backup(destino)
                finally:
                    destino.close()
        if versao < 2:
            colunas = {r["name"] for r in self.con.execute("PRAGMA table_info(reuniao)")}
            if "notas" not in colunas:
                self.con.execute("ALTER TABLE reuniao ADD COLUMN notas TEXT NOT NULL DEFAULT '[]'")
        if versao < 3:
            colunas = {r["name"] for r in self.con.execute("PRAGMA table_info(aguardando)")}
            if "eventos" not in colunas:
                self.con.execute("ALTER TABLE aguardando ADD COLUMN eventos TEXT NOT NULL DEFAULT '[]'")
                # histórico inicial a partir das datas de cobrança já registradas
                for r in self.con.execute("SELECT id, cobrancas FROM aguardando").fetchall():
                    eventos = [{"quando": f"{d}T00:00", "tipo": "Cobrado", "texto": ""} for d in json.loads(r["cobrancas"] or "[]")]
                    self.con.execute("UPDATE aguardando SET eventos = ? WHERE id = ?", (json.dumps(eventos, ensure_ascii=False), r["id"]))
        self._meta("versao", str(VERSAO_ESQUEMA))

    def fechar(self):
        self.con.close()

    # --- meta ---
    def _meta(self, chave: str, valor: str | None = None):
        if valor is None:
            row = self.con.execute("SELECT valor FROM meta WHERE chave = ?", (chave,)).fetchone()
            return row["valor"] if row else None
        self.con.execute("INSERT OR REPLACE INTO meta(chave, valor) VALUES (?, ?)", (chave, valor))

    # --- genéricos ---
    def _salvar(self, tabela: str, obj):
        dados = {f.name: _para_db(f.name, getattr(obj, f.name)) for f in fields(obj) if f.name != "id"}
        if obj.id is None:
            cols = ", ".join(dados)
            marcas = ", ".join("?" for _ in dados)
            cur = self.con.execute(f"INSERT INTO {tabela} ({cols}) VALUES ({marcas})", list(dados.values()))
            obj.id = cur.lastrowid
        else:
            sets = ", ".join(f"{k} = ?" for k in dados)
            self.con.execute(f"UPDATE {tabela} SET {sets} WHERE id = ?", [*dados.values(), obj.id])
        self.con.commit()
        return obj

    def _listar(self, tabela: str, classe, onde: str = "", args: tuple = ()):
        nomes = {f.name for f in fields(classe)}
        rows = self.con.execute(f"SELECT * FROM {tabela} {onde}", args).fetchall()
        return [classe(**{k: _de_db(k, r[k]) for k in r.keys() if k in nomes}) for r in rows]

    # --- tarefas ---
    def salvar_tarefa(self, t: Tarefa) -> Tarefa:
        return self._salvar("tarefa", t)

    def salvar_tarefas(self, tarefas: list[Tarefa]):
        with self.con:
            for t in tarefas:
                dados = {f.name: _para_db(f.name, getattr(t, f.name)) for f in fields(t) if f.name != "id"}
                if t.id is None:
                    cur = self.con.execute(f"INSERT INTO tarefa ({', '.join(dados)}) VALUES ({', '.join('?' for _ in dados)})", list(dados.values()))
                    t.id = cur.lastrowid
                else:
                    self.con.execute(f"UPDATE tarefa SET {', '.join(f'{k} = ?' for k in dados)} WHERE id = ?", [*dados.values(), t.id])

    def tarefas(self, status: str | None = None) -> list[Tarefa]:
        if status:
            return self._listar("tarefa", Tarefa, "WHERE status = ? ORDER BY id", (status,))
        return self._listar("tarefa", Tarefa, "ORDER BY id")

    def tarefa(self, tarefa_id: int) -> Tarefa | None:
        r = self._listar("tarefa", Tarefa, "WHERE id = ?", (tarefa_id,))
        return r[0] if r else None

    def excluir_tarefa(self, tarefa_id: int):
        """Apaga a tarefa e o diário dela; itens de Aguardando ligados a ela perdem só a ligação."""
        with self.con:
            self.con.execute("DELETE FROM registro WHERE tarefa_id = ?", (tarefa_id,))
            self.con.execute("UPDATE aguardando SET tarefa_origem_id = NULL WHERE tarefa_origem_id = ?", (tarefa_id,))
            self.con.execute("UPDATE aguardando SET tarefa_gerada_id = NULL WHERE tarefa_gerada_id = ?", (tarefa_id,))
            self.con.execute("DELETE FROM tarefa WHERE id = ?", (tarefa_id,))

    def _inserir_com_id(self, tabela: str, obj):
        dados = {f.name: _para_db(f.name, getattr(obj, f.name)) for f in fields(obj)}
        self.con.execute(f"INSERT OR REPLACE INTO {tabela} ({', '.join(dados)}) VALUES ({', '.join('?' for _ in dados)})",
                         list(dados.values()))

    def restaurar_tarefa(self, t: Tarefa, registros: list[Registro]):
        """Volta uma tarefa excluída com o mesmo id e o mesmo diário (usado pelo Desfazer)."""
        with self.con:
            self._inserir_com_id("tarefa", t)
            for r in registros:
                self._inserir_com_id("registro", r)

    def substituir_tabela(self, tabela: str, objetos: list):
        """Troca todo o conteúdo de uma tabela sem dependentes (aguardando, reuniao) — usado pelo Desfazer."""
        assert tabela in ("aguardando", "reuniao")
        with self.con:
            self.con.execute(f"DELETE FROM {tabela}")
            for o in objetos:
                self._inserir_com_id(tabela, o)

    # --- diário ---
    def registrar(self, r: Registro) -> Registro:
        return self._salvar("registro", r)

    def registros(self, tarefa_id: int) -> list[Registro]:
        return self._listar("registro", Registro, "WHERE tarefa_id = ? ORDER BY quando, id", (tarefa_id,))

    # --- aguardando ---
    def salvar_aguardando(self, a: Aguardando) -> Aguardando:
        return self._salvar("aguardando", a)

    def excluir_aguardando(self, aguardando_id: int):
        with self.con:
            self.con.execute("UPDATE tarefa SET aguardando_id = NULL WHERE aguardando_id = ?", (aguardando_id,))
            self.con.execute("DELETE FROM aguardando WHERE id = ?", (aguardando_id,))

    def aguardando(self, status: str | None = None) -> list[Aguardando]:
        if status:
            return self._listar("aguardando", Aguardando, "WHERE status = ? ORDER BY cobrar_em", (status,))
        return self._listar("aguardando", Aguardando, "ORDER BY cobrar_em")

    # --- reuniões ---
    def salvar_reuniao(self, r: Reuniao) -> Reuniao:
        return self._salvar("reuniao", r)

    def reunioes(self) -> list[Reuniao]:
        return self._listar("reuniao", Reuniao, "ORDER BY quando DESC, id DESC")

    def reuniao(self, reuniao_id: int) -> Reuniao | None:
        r = self._listar("reuniao", Reuniao, "WHERE id = ?", (reuniao_id,))
        return r[0] if r else None

    def excluir_reuniao(self, reuniao_id: int):
        """Apaga a reunião; as tarefas e esperas criadas por ela continuam, só sem a ligação."""
        with self.con:
            self.con.execute("UPDATE tarefa SET reuniao_id = NULL WHERE reuniao_id = ?", (reuniao_id,))
            self.con.execute("UPDATE aguardando SET reuniao_id = NULL WHERE reuniao_id = ?", (reuniao_id,))
            self.con.execute("DELETE FROM reuniao WHERE id = ?", (reuniao_id,))

    # --- ausências e feriados ---
    def salvar_ausencia(self, a: Ausencia) -> Ausencia:
        return self._salvar("ausencia", a)

    def remover_ausencia(self, ausencia_id: int):
        with self.con:
            self.con.execute("DELETE FROM ausencia WHERE id = ?", (ausencia_id,))

    def ausencias(self) -> list[Ausencia]:
        return self._listar("ausencia", Ausencia, "ORDER BY inicio")

    def garantir_feriados(self, ano: int):
        """Cadastra os feriados do ano uma única vez (o usuário pode remover depois)."""
        chave = f"feriados_{ano}"
        if self._meta(chave):
            return
        for a in ausencias_de_feriados(ano):
            self._salvar("ausencia", a)
        self._meta(chave, "1")
        self.con.commit()

    # --- capacidade por dia ---
    def capacidades_especificas(self) -> dict[date, int]:
        rows = self.con.execute("SELECT data, minutos_disponiveis FROM dia").fetchall()
        return {date.fromisoformat(r["data"]): r["minutos_disponiveis"] for r in rows}

    def definir_capacidade(self, dia: date, minutos: int, observacao: str = ""):
        with self.con:
            self.con.execute("INSERT OR REPLACE INTO dia(data, minutos_disponiveis, observacao) VALUES (?, ?, ?)",
                             (dia.isoformat(), minutos, observacao))

    # --- replanejamentos (base do Desfazer) ---
    def registrar_replanejamento(self, motivo: str, mudancas: list[dict]) -> int:
        with self.con:
            cur = self.con.execute("INSERT INTO replanejamento(quando, motivo, mudancas) VALUES (?, ?, ?)",
                                   (datetime.now().isoformat(timespec="seconds"), motivo, json.dumps(mudancas, default=str, ensure_ascii=False)))
            return cur.lastrowid

    # --- configuração ---
    def config(self) -> Configuracao:
        rows = {r["chave"]: json.loads(r["valor"]) for r in self.con.execute("SELECT chave, valor FROM config")}
        padrao = Configuracao()
        validos = {f.name for f in fields(Configuracao)}
        return Configuracao(**{**asdict(padrao), **{k: v for k, v in rows.items() if k in validos}})

    def salvar_config(self, cfg: Configuracao):
        with self.con:
            for k, v in asdict(cfg).items():
                self.con.execute("INSERT OR REPLACE INTO config(chave, valor) VALUES (?, ?)", (k, json.dumps(v, ensure_ascii=False)))
