"""Operações do app: o que a interface chama. Junta banco, planejador e diário.

Toda operação que mexe no planejamento:
  1. guarda um retrato para o Desfazer;
  2. roda o planejador;
  3. grava as tarefas e registra no diário as que mudaram de dia;
  4. devolve um Resultado com a mensagem para o aviso.
"""
from __future__ import annotations

import copy
import sqlite3
from dataclasses import asdict, dataclass, field, fields, replace
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Callable

from dados.backup import data_do_backup, fazer_backup, pasta_backup_efetiva
from dados.banco import Banco
from .calendario import TIPOS_AUSENCIA, Ausencia, Calendario, pontos_facultativos
from .captura import formata_dia, formata_minutos, le_captura, normaliza
from .modelos import (ABERTA, CANCELADA, CONCLUIDA, DELEGADA, Aguardando, Registro,
                      Reuniao, Tarefa)
from .planejador import Movimento, ResultadoPlano, planejar
from .sons import SONS
from .recap import AGUARDANDO, DECISAO, RISCO, TAREFA, Sugestao, eh_comigo, le_recap

MINUTOS_COBRANCA = 5
AVISO_CONFLITO = {
    "nao_cabe": "não cabe antes do prazo",
    "prazo_vencido": "vai passar do prazo combinado",
    "maior_que_dia": "maior que um dia de trabalho: quebre em partes",
}
LIMITE_ADIAMENTOS = 2  # na 3ª tentativa de adiar, o app pede uma decisão


@dataclass
class ItemHistorico:
    """Uma linha da aba Concluídas: tarefa concluída ou entrega recebida de outra pessoa."""
    tipo: str            # "tarefa" | "recebido"
    dia: date
    titulo: str
    detalhe: str
    tarefa: Tarefa | None = None
    aguardando: Aguardando | None = None


@dataclass
class ResumoReuniao:
    reuniao: Reuniao
    tarefas: list[Tarefa]
    aguardando: list[Aguardando]
    decisoes: list[str]
    riscos: list[str]

    @property
    def legenda(self) -> str:
        partes = []
        for n, um, varios in [(len(self.tarefas), "tarefa", "tarefas"), (len(self.aguardando), "aguardando", "aguardando"),
                              (len(self.decisoes), "decisão", "decisões"), (len(self.riscos), "risco", "riscos")]:
            if n:
                partes.append(f"{n} {um if n == 1 else varios}")
        return " · ".join(partes) or "só o recap"


@dataclass
class Resultado:
    mensagem: str
    tarefa: Tarefa | None = None
    movidas: list[Movimento] = field(default_factory=list)
    precisa_decisao: bool = False
    pode_desfazer: bool = True
    ok: bool = True  # False quando a operação foi recusada (ex.: valor inválido)


@dataclass
class Aviso:
    """Aviso de horário (antes do almoço ou do fim da jornada)."""
    tipo: str          # "manha" | "fim"
    hora: datetime
    titulo: str
    mensagem: str
    acao: str          # "ver_hoje" | "replanejar" | "ok"
    acao_rotulo: str


def le_hora(texto: str) -> time | None:
    """'9', '9:00', '09h30', '18:00' → time; inválido → None."""
    t = (texto or "").strip().lower().replace("h", ":").rstrip(":")
    try:
        if ":" in t:
            h, m = t.split(":", 1)
            return time(int(h), int(m or 0))
        return time(int(t), 0)
    except (ValueError, TypeError):
        return None


def _min(t: time) -> int:
    return t.hour * 60 + t.minute


def _hhmm(minutos: int) -> str:
    minutos %= 24 * 60
    return f"{minutos // 60:02d}:{minutos % 60:02d}"


def _erro(msg: str) -> "Resultado":
    return Resultado(msg, pode_desfazer=False, ok=False)


class Servico:
    def __init__(self, banco: Banco, pasta_app: Path | None = None, hoje: Callable[[], date] = date.today):
        self.banco = banco
        self.pasta_app = Path(pasta_app) if pasta_app else banco.caminho.parent
        self._hoje = hoje
        self._desfazer: list[dict] = []
        for ano in (self.hoje().year, self.hoje().year + 1):
            banco.garantir_feriados(ano)

    # ---------- utilitários ----------
    def hoje(self) -> date:
        return self._hoje()

    def hoje_util(self) -> date:
        """Hoje, ou o próximo dia de trabalho se hoje for fim de semana, feriado ou ausência."""
        h = self.hoje()
        return h if self.calendario().eh_dia_de_trabalho(h) else self._proximo_util(h)

    def config(self):
        return self.banco.config()

    def calendario(self) -> Calendario:
        cfg = self.config()
        return Calendario(horas_padrao_min=cfg.horas_padrao_min, dias_uteis=frozenset(cfg.dias_uteis),
                          capacidade_especifica=self.banco.capacidades_especificas(),
                          ausencias=self.banco.ausencias())

    def reservas(self) -> dict[date, int]:
        r: dict[date, int] = {}
        for a in self.banco.aguardando("aberto"):
            d = max(a.cobrar_em, self.hoje())
            r[d] = r.get(d, 0) + MINUTOS_COBRANCA
        return r

    def _proximo_util(self, d: date) -> date:
        return self.calendario().proximo_dia_de_trabalho(d)

    def _registrar(self, tarefa_id: int, tipo: str, texto: str, **extra) -> Registro:
        return self.banco.registrar(Registro(tarefa_id=tarefa_id, tipo=tipo, texto=texto, **extra))

    def _retrato(self):
        maior = self.banco.con.execute("SELECT COALESCE(MAX(id), 0) FROM registro").fetchone()[0]
        self._desfazer.append({
            "tarefas": copy.deepcopy(self.banco.tarefas()),
            "aguardando": copy.deepcopy(self.banco.aguardando()),
            "reunioes": copy.deepcopy(self.banco.reunioes()),
            "registro_max": maior,
            "dias": [tuple(r) for r in self.banco.con.execute("SELECT data, minutos_disponiveis, observacao FROM dia")],
            "ausencias": [tuple(r) for r in self.banco.con.execute("SELECT id, tipo, inicio, fim, descricao, origem FROM ausencia")],
        })
        del self._desfazer[:-20]

    def desfazer(self) -> Resultado:
        if not self._desfazer:
            return Resultado("Nada para desfazer.", pode_desfazer=False)
        r = self._desfazer.pop()
        ids_antes = {t.id for t in r["tarefas"]}
        if "excluida" in r:  # volta antes de tudo: o diário dela depende da tarefa existir
            self.banco.restaurar_tarefa(*r["excluida"])
        with self.banco.con:
            self.banco.con.execute("DELETE FROM registro WHERE id > ?", (r["registro_max"],))
            for t in self.banco.tarefas():
                if t.id not in ids_antes:  # tarefas criadas depois do retrato
                    self.banco.con.execute("DELETE FROM tarefa WHERE id = ?", (t.id,))
            self.banco.con.execute("DELETE FROM dia")
            self.banco.con.executemany("INSERT INTO dia(data, minutos_disponiveis, observacao) VALUES (?, ?, ?)", r["dias"])
            self.banco.con.execute("DELETE FROM ausencia")
            self.banco.con.executemany("INSERT INTO ausencia(id, tipo, inicio, fim, descricao, origem) VALUES (?, ?, ?, ?, ?, ?)", r["ausencias"])
        self.banco.salvar_tarefas(r["tarefas"])
        self.banco.substituir_tabela("aguardando", r["aguardando"])
        self.banco.substituir_tabela("reuniao", r["reunioes"])
        return Resultado("Desfeito.", pode_desfazer=False)

    @staticmethod
    def texto_movidas(movidas: list[Movimento]) -> str:
        if not movidas:
            return ""
        m = movidas[0]
        para = formata_dia(m.para) if m.para else "sem data"
        if len(movidas) == 1:
            return f"\n1 outra replanejada: {m.titulo} ({formata_dia(m.de)} → {para})"
        return f"\n{len(movidas)} outras replanejadas, ex.: {m.titulo} → {para}"

    def nome_dia(self, d: date | None) -> str:
        if d is None:
            return "sem data por enquanto"
        h = self.hoje()
        if d == h:
            return "Hoje"
        if d == self._proximo_util(h):
            return "Amanhã" if d == h + timedelta(days=1) else f"{formata_dia(d)} (próximo dia útil)"
        return formata_dia(d)

    # ---------- planejamento ----------
    def replanejar(self, motivo: str, ignorar: set[int] | None = None, tarefas: list[Tarefa] | None = None) -> ResultadoPlano:
        base = tarefas if tarefas is not None else self.banco.tarefas()
        res = planejar(base, self.calendario(), self.hoje(), self.config().horizonte_dias, self.reservas(), ignorar)
        self.banco.salvar_tarefas(res.tarefas)
        for m in res.movidas:
            de = formata_dia(m.de) if m.de else "sem data"
            para = formata_dia(m.para) if m.para else "sem data"
            self._registrar(m.tarefa_id, "Replanejada", f"{de} → {para} · {motivo}")
        if res.movidas:
            self.banco.registrar_replanejamento(motivo, [{"tarefa": m.tarefa_id, "de": m.de, "para": m.para} for m in res.movidas])
        return res

    def _tarefa(self, tarefa_id: int) -> Tarefa:
        t = self.banco.tarefa(tarefa_id)
        if t is None:
            raise KeyError(f"tarefa {tarefa_id} não existe")
        return t

    def _aplicar(self, alterada: Tarefa, motivo: str, ignorar_ids: set[int] | None = None) -> tuple[Tarefa, ResultadoPlano]:
        tarefas = [alterada if t.id == alterada.id else t for t in self.banco.tarefas()]
        if alterada.id is None:
            tarefas.append(alterada)
        res = self.replanejar(motivo, ignorar_ids or ({alterada.id} if alterada.id else set()), tarefas)
        nova = next(t for t in res.tarefas if t is alterada or (alterada.id and t.id == alterada.id))
        return nova, res

    # ---------- captura ----------
    def prever(self, texto: str) -> str:
        return le_captura(texto, self.hoje(), self._proximo_util).descricao()

    def capturar(self, texto: str) -> Resultado:
        c = le_captura(texto, self.hoje(), self._proximo_util)
        if not c.titulo:
            return Resultado("Escreva o que precisa ser feito.", pode_desfazer=False)
        self._retrato()
        if c.eh_aguardando:
            cobrar = c.prazo or self.calendario().dias_de_trabalho(self.hoje() + timedelta(days=1), 2)[-1]
            pessoa = c.pessoa if c.pessoa != c.pessoa.lower() else c.pessoa.replace(".", " ").replace("_", " ").title()
            a = Aguardando(pessoa=pessoa, o_que=c.titulo, cobrar_em=cobrar)
            self._evento(a, "Criado", f"cobrar {self.nome_dia(cobrar)}")
            self.banco.salvar_aguardando(a)
            res = self.replanejar("cobrança reservada")
            return Resultado(f"Em Aguardando: {pessoa} · cobrar {self.nome_dia(cobrar)}" + self.texto_movidas(res.movidas))
        t = Tarefa(titulo=c.titulo, minutos=c.minutos or 120, importancia=c.importancia, prazo=c.prazo,
                   data_fixa=c.data_fixa, projeto=c.projeto)
        self.banco.salvar_tarefa(t)
        self._registrar(t.id, "Criada", "Criada pela captura rápida.")
        nova, res = self._aplicar(t, "nova tarefa")
        if nova.dia_planejado is None:
            msg = f"Sem data por enquanto (não coube nas próximas 4 semanas) · {formata_minutos(nova.minutos)}"
        else:
            msg = f"Encaixada em {self.nome_dia(nova.dia_planejado)} · {formata_minutos(nova.minutos)}"
        if nova.conflito:
            msg += f" · {AVISO_CONFLITO[nova.conflito]}"
        return Resultado(msg + self.texto_movidas(res.movidas), nova, res.movidas)

    # ---------- ações sobre tarefas ----------
    def concluir(self, tarefa_id: int) -> Resultado:
        self._retrato()
        t = self._tarefa(tarefa_id)
        t.status, t.concluida_em = CONCLUIDA, datetime.now()
        self.banco.salvar_tarefa(t)
        self._registrar(t.id, "Concluída", "Tarefa finalizada.")
        return Resultado("Concluída.", t)

    def reabrir(self, tarefa_id: int) -> Resultado:
        self._retrato()
        t = self._tarefa(tarefa_id)
        t.status, t.concluida_em, t.dia_planejado, t.nao_antes_de = ABERTA, None, None, self.hoje()
        self.banco.salvar_tarefa(t)
        self._registrar(t.id, "Reaberta", "Tarefa reaberta.")
        nova, res = self._aplicar(t, "tarefa reaberta")
        return Resultado(f"Reaberta e encaixada em {self.nome_dia(nova.dia_planejado)}" + self.texto_movidas(res.movidas), nova, res.movidas)

    def adiar(self, tarefa_id: int, motivo: str | None = None, forcar: bool = False) -> Resultado:
        t = self._tarefa(tarefa_id)
        if not forcar and t.adiamentos >= LIMITE_ADIAMENTOS:
            return Resultado(f"“{t.titulo}” já foi adiada {t.adiamentos} vezes. Decida: fazer hoje, quebrar, delegar ou cancelar.",
                             t, precisa_decisao=True, pode_desfazer=False)
        self._retrato()
        de = t.dia_planejado
        t.adiamentos += 1
        # adiar = "não no dia em que está": vai para depois do dia planejado (ou de hoje)
        t.nao_antes_de = self._proximo_util(max(self.hoje(), de or self.hoje()))
        t.data_fixa = None
        nova, res = self._aplicar(t, "adiamento de outra tarefa")
        texto = f"{formata_dia(de) if de else 'sem data'} → {formata_dia(nova.dia_planejado) if nova.dia_planejado else 'sem data'}"
        self._registrar(t.id, "Adiamento", texto + (f" · {motivo}" if motivo else ""))
        msg = f"Adiada para {self.nome_dia(nova.dia_planejado)}"
        if nova.conflito:
            msg += f" · {AVISO_CONFLITO[nova.conflito]}"
        return Resultado(msg + self.texto_movidas(res.movidas), nova, res.movidas)

    def anotar_motivo_adiamento(self, tarefa_id: int, motivo: str):
        regs = [r for r in self.banco.registros(tarefa_id) if r.tipo == "Adiamento"]
        if regs:
            r = regs[-1]
            r.texto = f"{r.texto} · {motivo}"
            self.banco.registrar(r)

    def decidir(self, tarefa_id: int, opcao: str) -> Resultado:
        """Decisão do 3º adiamento (e saídas de conflito): fazer_hoje | quebrar | delegar | cancelar."""
        self._retrato()
        t = self._tarefa(tarefa_id)
        if opcao == "fazer_hoje":
            t.data_fixa = self.hoje_util()
            nova, res = self._aplicar(t, "tarefa fixada em hoje")
            return Resultado(f"Fixada em {self.nome_dia(nova.dia_planejado).lower() if nova.dia_planejado == self.hoje() else self.nome_dia(nova.dia_planejado)}." + self.texto_movidas(res.movidas), nova, res.movidas)
        if opcao == "quebrar":
            metade = max(15, round(t.minutos / 2 / 15) * 15)
            t.status = CANCELADA
            self.banco.salvar_tarefa(t)
            self._registrar(t.id, "Decisão", "Quebrada em 2 partes.")
            partes = []
            for n in (1, 2):
                p = Tarefa(titulo=f"{t.titulo} (parte {n})", minutos=metade, importancia=t.importancia,
                           prazo=t.prazo, projeto=t.projeto, nao_antes_de=self.hoje())
                self.banco.salvar_tarefa(p)
                self._registrar(p.id, "Criada", f"Parte {n} de “{t.titulo}”.")
                partes.append(p.id)
            res = self.replanejar("tarefa quebrada", set(partes))
            dias = [next(x for x in res.tarefas if x.id == pid).dia_planejado for pid in partes]
            return Resultado(f"Quebrada em 2 partes de {formata_minutos(metade)}: {self.nome_dia(dias[0])} e {self.nome_dia(dias[1])}.", movidas=res.movidas)
        if opcao == "delegar":
            t.status = DELEGADA
            self.banco.salvar_tarefa(t)
            cobrar = self.calendario().dias_de_trabalho(self.hoje() + timedelta(days=1), 2)[-1]
            a = Aguardando(pessoa="(definir pessoa)", o_que=t.titulo, cobrar_em=cobrar, tarefa_origem_id=t.id)
            self._evento(a, "Criado", f"delegada da tarefa “{t.titulo}”")
            self.banco.salvar_aguardando(a)
            self._registrar(t.id, "Decisão", "Delegada: foi para Aguardando.")
            res = self.replanejar("tarefa delegada")
            return Resultado(f"Delegada: foi para Aguardando, cobrar {self.nome_dia(cobrar)}." + self.texto_movidas(res.movidas), movidas=res.movidas)
        if opcao == "cancelar":
            t.status = CANCELADA
            self.banco.salvar_tarefa(t)
            self._registrar(t.id, "Decisão", "Cancelada.")
            return Resultado("Cancelada (fica no histórico).")
        raise ValueError(f"opção desconhecida: {opcao}")

    def alterar(self, tarefa_id: int, **campos) -> Resultado:
        """Muda tamanho, prazo, data fixa etc. e replaneja (usado pelas saídas de conflito e pelo painel)."""
        self._retrato()
        t = replace(self._tarefa(tarefa_id), **campos)
        nova, res = self._aplicar(t, "tarefa alterada", set())
        res.movidas = [m for m in res.movidas if m.tarefa_id != tarefa_id]
        msg = f"Planejada para {self.nome_dia(nova.dia_planejado)}"
        if nova.conflito:
            msg += " · ainda em conflito"
        return Resultado(msg + self.texto_movidas(res.movidas), nova, res.movidas)

    def renomear(self, tarefa_id: int, titulo: str) -> Resultado:
        """Corrige o texto da tarefa. Não mexe no planejamento; fica registrado no diário."""
        novo = " ".join(titulo.split())
        if not novo:
            return Resultado("O texto da tarefa não pode ficar vazio.", pode_desfazer=False)
        t = self._tarefa(tarefa_id)
        if novo == t.titulo:
            return Resultado("Texto sem mudanças.", t, pode_desfazer=False)
        self._retrato()
        antigo, t.titulo = t.titulo, novo
        self.banco.salvar_tarefa(t)
        self._registrar(t.id, "Ocorrência", f"Texto alterado. Antes: “{antigo}”")
        return Resultado("Texto da tarefa atualizado.", t)

    def excluir(self, tarefa_id: int) -> Resultado:
        """Apaga de vez (para tarefas criadas por engano ou de teste). Dá para desfazer nesta sessão."""
        t = self._tarefa(tarefa_id)
        regs = self.banco.registros(tarefa_id)
        self._retrato()
        self._desfazer[-1]["excluida"] = (copy.deepcopy(t), copy.deepcopy(regs))
        self.banco.excluir_tarefa(tarefa_id)
        res = self.replanejar("tarefa excluída")
        return Resultado(f"“{t.titulo}” excluída." + self.texto_movidas(res.movidas), movidas=res.movidas)

    def adiantar(self, tarefa_id: int) -> Resultado:
        self._retrato()
        t = self._tarefa(tarefa_id)
        t.dia_planejado = self.hoje()
        nova, res = self._aplicar(t, "tarefa adiantada")
        return Resultado(f"“{t.titulo}” adiantada para hoje.", nova, res.movidas)

    def definir_capacidade(self, dia: date, minutos: int) -> Resultado:
        self._retrato()
        self.banco.definir_capacidade(dia, max(0, min(600, minutos)))
        res = self.replanejar(f"horas de {formata_dia(dia)} alteradas")
        msg = f"{self.nome_dia(dia)} agora com {formata_minutos(minutos)} disponíveis"
        msg += self.texto_movidas(res.movidas) if res.movidas else " · nada precisou mudar"
        if res.conflitos:
            msg += f"\n{len(res.conflitos)} em conflito com o prazo"
        return Resultado(msg, movidas=res.movidas)

    def replanejar_resto_do_dia(self) -> Resultado:
        """Botão do aviso de fim de jornada: empurra o que sobrou de hoje (sem contar como adiamento)."""
        self._retrato()
        amanha = self._proximo_util(self.hoje())
        tarefas = self.banco.tarefas()
        for t in tarefas:
            if t.aberta and t.dia_planejado == self.hoje() and t.data_fixa is None:
                t.nao_antes_de = amanha
        res = self.replanejar("fim da jornada", tarefas=tarefas)
        return Resultado(f"{len(res.movidas)} tarefa(s) de hoje replanejadas para os próximos dias.", movidas=res.movidas)

    def abrir_o_dia(self) -> Resultado | None:
        """Chamado ao iniciar o app: replaneja o que ficou para trás e faz o backup do dia."""
        try:
            fazer_backup(self.banco.caminho, pasta_backup_efetiva(self.config().pasta_backup, self.pasta_app), self.hoje())
        except OSError:
            pass  # pasta de backup indisponível (ex.: OneDrive offline); tenta na próxima abertura
        atrasadas = [t for t in self.banco.tarefas(ABERTA) if t.dia_planejado and t.dia_planejado < self.hoje()]
        if not atrasadas:
            self.replanejar("abertura do dia")
            return None
        res = self.replanejar("virada do dia")
        return Resultado(f"Bom dia! {len(atrasadas)} tarefa(s) de dias anteriores reencaixadas automaticamente.", movidas=res.movidas)

    # ---------- diário ----------
    def anotar(self, tarefa_id: int, tipo: str, texto: str) -> Registro:
        return self._registrar(tarefa_id, tipo, texto.strip())

    def marcar_passo(self, registro: Registro, feito: bool = True) -> Registro:
        registro.feito, registro.feito_em = feito, (datetime.now() if feito else None)
        return self.banco.registrar(registro)

    # ---------- aguardando ----------
    @staticmethod
    def _evento(a: Aguardando, tipo: str, texto: str = ""):
        a.eventos = [*a.eventos, {"quando": datetime.now().isoformat(timespec="minutes"), "tipo": tipo, "texto": texto}]

    def cobrei(self, aguardando_id: int) -> Resultado:
        self._retrato()
        a = next(x for x in self.banco.aguardando() if x.id == aguardando_id)
        a.cobrancas = [*a.cobrancas, self.hoje()]
        a.cobrar_em = self.calendario().dias_de_trabalho(self.hoje() + timedelta(days=1), 2)[-1]
        self._evento(a, "Cobrado", f"próxima cobrança: {self.nome_dia(a.cobrar_em)}")
        self.banco.salvar_aguardando(a)
        self.replanejar("cobrança remarcada")
        return Resultado(f"Cobrado. Próxima cobrança: {self.nome_dia(a.cobrar_em)}.")

    def recebi(self, aguardando_id: int, texto_tarefa: str | None = None) -> Resultado:
        self._retrato()
        a = next(x for x in self.banco.aguardando() if x.id == aguardando_id)
        a.status, a.recebido_em = "recebido", self.hoje()
        self._evento(a, "Recebido", f"gerou a tarefa “{texto_tarefa.strip()}”" if texto_tarefa and texto_tarefa.strip() else "")
        nova = None
        if texto_tarefa and texto_tarefa.strip():
            c = le_captura(texto_tarefa, self.hoje(), self._proximo_util)
            t = Tarefa(titulo=c.titulo or texto_tarefa.strip(), minutos=c.minutos or 120, importancia=c.importancia,
                       prazo=c.prazo, data_fixa=c.data_fixa, projeto=c.projeto, aguardando_id=a.id)
            self.banco.salvar_tarefa(t)
            self._registrar(t.id, "Criada", f"Criada ao receber “{a.o_que}” de {a.pessoa}.")
            a.tarefa_gerada_id = t.id
            self.banco.salvar_aguardando(a)
            nova, res = self._aplicar(t, "nova tarefa")
            return Resultado(f"Recebido de {a.pessoa}. Nova tarefa encaixada em {self.nome_dia(nova.dia_planejado)}" + self.texto_movidas(res.movidas), nova, res.movidas)
        self.banco.salvar_aguardando(a)
        self.replanejar("cobrança liberada")
        return Resultado(f"Recebido de {a.pessoa}. Registrado em Concluídas.")

    def _espera(self, aguardando_id: int) -> Aguardando:
        a = next((x for x in self.banco.aguardando() if x.id == aguardando_id), None)
        if a is None:
            raise KeyError(f"aguardando {aguardando_id} não existe")
        return a

    def capturar_espera(self, texto: str) -> Resultado:
        """Campo da aba Aguardando: exige @pessoa."""
        c = le_captura(texto, self.hoje(), self._proximo_util)
        if not c.eh_aguardando:
            return Resultado("Inclua @pessoa: de quem você está esperando?", pode_desfazer=False)
        return self.capturar(texto)

    def editar_espera(self, aguardando_id: int, pessoa: str, o_que: str, cobrar_em: date) -> Resultado:
        pessoa, o_que = " ".join(pessoa.split()), " ".join(o_que.split())
        if not pessoa or not o_que:
            return Resultado("Preencha quem e o quê.", pode_desfazer=False)
        self._retrato()
        a = self._espera(aguardando_id)
        if cobrar_em > a.cobrar_em:
            self._evento(a, "Adiado", f"{formata_dia(a.cobrar_em)} → {formata_dia(cobrar_em)}")
        elif cobrar_em < a.cobrar_em:
            self._evento(a, "Antecipado", f"{formata_dia(a.cobrar_em)} → {formata_dia(cobrar_em)}")
        mudou = [f"{nome}: “{antes}” → “{depois}”" for nome, antes, depois in
                 (("pessoa", a.pessoa, pessoa), ("texto", a.o_que, o_que)) if antes != depois]
        if mudou:
            self._evento(a, "Editado", " · ".join(mudou))
        a.pessoa, a.o_que, a.cobrar_em = pessoa, o_que, cobrar_em
        self.banco.salvar_aguardando(a)
        self.replanejar("cobrança remarcada")
        return Resultado(f"Atualizado: {pessoa} · cobrar {self.nome_dia(cobrar_em)}.")

    def adiar_espera(self, aguardando_id: int) -> Resultado:
        """Empurra a cobrança para o próximo dia útil (depois de hoje e da data atual)."""
        self._retrato()
        a = self._espera(aguardando_id)
        novo = self._proximo_util(max(self.hoje(), a.cobrar_em))
        self._evento(a, "Adiado", f"{formata_dia(a.cobrar_em)} → {formata_dia(novo)}")
        a.cobrar_em = novo
        self.banco.salvar_aguardando(a)
        self.replanejar("cobrança adiada")
        n = a.contar("Adiado")
        return Resultado(f"Cobrança de {a.pessoa} adiada para {self.nome_dia(novo)}" + (f" · já adiada {n}x" if n > 1 else "") + ".")

    def excluir_espera(self, aguardando_id: int) -> Resultado:
        self._retrato()
        a = self._espera(aguardando_id)
        self.banco.excluir_aguardando(aguardando_id)
        self.replanejar("cobrança excluída")
        return Resultado(f"Excluído: {a.pessoa}: {a.o_que}.")

    def reabrir_espera(self, aguardando_id: int) -> Resultado:
        """Recebido por engano ou veio incompleto: volta para Aguardando, com cobrança no próximo dia útil."""
        self._retrato()
        a = self._espera(aguardando_id)
        a.status, a.recebido_em, a.cobrar_em = "aberto", None, self.hoje_util()
        self._evento(a, "Reaberto", f"cobrar {self.nome_dia(a.cobrar_em)}")
        self.banco.salvar_aguardando(a)
        self.replanejar("cobrança reaberta")
        return Resultado(f"Voltou para Aguardando: cobrar {a.pessoa} {self.nome_dia(a.cobrar_em)}.")

    # ---------- concluídas ----------
    def historico(self, filtro: str = "") -> list[ItemHistorico]:
        """Tarefas concluídas e entregas recebidas, das mais recentes para as mais antigas."""
        itens = []
        for t in self.banco.tarefas(CONCLUIDA):
            dia = t.concluida_em.date() if t.concluida_em else t.criada_em.date()
            partes = [formata_minutos(t.minutos)]
            if t.projeto:
                partes.append(f"#{t.projeto}")
            partes.append(f"adiada {t.adiamentos}x antes de concluir" if t.adiamentos else "sem adiamentos")
            itens.append((t.concluida_em or datetime.combine(dia, datetime.min.time()),
                          ItemHistorico("tarefa", dia, t.titulo, " · ".join(partes), tarefa=t)))
        for a in self.banco.aguardando("recebido"):
            dia = a.recebido_em or a.cobrar_em
            n = len(a.cobrancas)
            cobr = f"cobrado {n}x ({', '.join(f'{d:%d/%m}' for d in a.cobrancas)})" if n else "sem cobranças"
            if (adi := a.contar("Adiado")):
                cobr += f" · adiado {adi}x"
            itens.append((datetime.combine(dia, datetime.max.time()),
                          ItemHistorico("recebido", dia, a.o_que, f"de {a.pessoa} · {cobr}", aguardando=a)))
        itens.sort(key=lambda x: x[0], reverse=True)
        termos = normaliza(filtro).split()
        if termos:
            def combina(i: ItemHistorico) -> bool:
                alvo = normaliza(" ".join([i.titulo, i.detalhe, f"#{i.tarefa.projeto}" if i.tarefa and i.tarefa.projeto else ""]))
                return all(t in alvo for t in termos)
            itens = [x for x in itens if combina(x[1])]
        return [i for _, i in itens]

    # ---------- reuniões ----------
    def ler_recap(self, texto: str) -> list[Sugestao]:
        cfg = self.config()
        return le_recap(texto, self.hoje(), cfg.meu_nome, cfg.apelidos, self._proximo_util)

    def resumo_reuniao(self, r: Reuniao) -> ResumoReuniao:
        tarefas = [t for t in self.banco.tarefas() if t.reuniao_id == r.id and t.status != CANCELADA]
        esperas = [a for a in self.banco.aguardando() if a.reuniao_id == r.id]
        dec = [n.split(":", 1)[1].strip() for n in r.notas if n.startswith(DECISAO + ":")]
        ris = [n.split(":", 1)[1].strip() for n in r.notas if n.startswith(RISCO + ":")]
        return ResumoReuniao(r, tarefas, esperas, dec, ris)

    def reunioes(self, filtro: str = "") -> list[ResumoReuniao]:
        termos = normaliza(filtro).split()
        saida = []
        for r in self.banco.reunioes():
            if termos:
                alvo = normaliza(" ".join([r.titulo, r.recap_original, *r.notas]))
                if not all(t in alvo for t in termos):
                    continue
            saida.append(self.resumo_reuniao(r))
        return saida

    def excluir_reuniao(self, reuniao_id: int) -> Resultado:
        r = self.banco.reuniao(reuniao_id)
        if r is None:
            return Resultado("Reunião não encontrada.", pode_desfazer=False)
        self._retrato()
        self.banco.excluir_reuniao(reuniao_id)
        return Resultado(f"Reunião “{r.titulo}” excluída. As tarefas criadas por ela continuam.")

    def criar_da_reuniao(self, titulo: str, recap: str, sugestoes: list[Sugestao], dia: date | None = None) -> Resultado:
        titulo = " ".join(titulo.split()) or "Reunião sem título"
        quando = datetime.combine(dia, datetime.now().time()) if dia else datetime.now()
        notas = [f"{s.tipo}: {s.texto}" for s in sugestoes if s.aceita and s.tipo in (DECISAO, RISCO) and s.texto.strip()]
        self._retrato()
        r = self.banco.salvar_reuniao(Reuniao(titulo=titulo, quando=quando, recap_original=recap, notas=notas))
        criadas = 0
        for s in sugestoes:
            if not s.aceita:
                continue
            if not s.texto.strip():
                continue
            if s.tipo == TAREFA:
                t = Tarefa(titulo=s.texto, minutos=s.minutos or 120, prazo=s.prazo, data_fixa=s.data_fixa, reuniao_id=r.id)
                self.banco.salvar_tarefa(t)
                self._registrar(t.id, "Criada", f"Criada a partir da reunião {titulo}. Trecho: “{s.trecho}”")
                criadas += 1
            elif s.tipo == AGUARDANDO:
                cobrar = s.prazo or self.calendario().dias_de_trabalho(self.hoje() + timedelta(days=1), 2)[-1]
                a = Aguardando(pessoa=s.responsavel or "(definir pessoa)", o_que=s.texto, cobrar_em=cobrar, reuniao_id=r.id)
                self._evento(a, "Criado", f"da reunião {titulo}")
                self.banco.salvar_aguardando(a)
                criadas += 1
        res = self.replanejar("itens da reunião", ignorar={t.id for t in self.banco.tarefas() if t.reuniao_id == r.id})
        msg = f"Reunião salva e {criadas} {'item criado' if criadas == 1 else 'itens criados'}." if criadas else "Reunião salva."
        if notas:
            msg += f" {len(notas)} {'decisão/risco registrado' if len(notas) == 1 else 'decisões/riscos registrados'}."
        return Resultado(msg + self.texto_movidas(res.movidas), movidas=res.movidas)

    # ---------- configurações ----------
    CAMPOS_QUE_REPLANEJAM = ("horas_padrao_min", "dias_uteis")

    def salvar_configuracao(self, **campos) -> Resultado:
        """Valida e grava. Mudou horas por dia ou dias úteis: replaneja na hora."""
        cfg = self.config()
        validos = {f.name for f in fields(cfg)}
        desconhecidos = set(campos) - validos
        if desconhecidos:
            return _erro(f"Campo desconhecido: {', '.join(sorted(desconhecidos))}")
        novo = replace(cfg, **campos)
        novo.meu_nome = " ".join(novo.meu_nome.split())
        novo.apelidos = [a.strip() for a in novo.apelidos if a.strip()]
        novo.pasta_backup = novo.pasta_backup.strip()
        if not novo.meu_nome:
            return _erro("Informe seu nome como aparece nos recaps.")
        horas = {}
        for chave in ("jornada_inicio", "almoco_inicio", "almoco_fim", "jornada_fim"):
            t = le_hora(getattr(novo, chave))
            if t is None:
                return _erro("Horário inválido. Use o formato 09:00.")
            horas[chave] = t
            setattr(novo, chave, t.strftime("%H:%M"))
        if not (_min(horas["jornada_inicio"]) < _min(horas["almoco_inicio"]) <= _min(horas["almoco_fim"]) < _min(horas["jornada_fim"])):
            return _erro("A jornada precisa seguir a ordem: início, almoço, volta do almoço, fim.")
        if not 15 <= novo.horas_padrao_min <= 720:
            return _erro("As horas para tarefas por dia vão de 15min a 12h.")
        novo.dias_uteis = sorted({int(d) for d in novo.dias_uteis if 0 <= int(d) <= 6})
        if not novo.dias_uteis:
            return _erro("Deixe pelo menos um dia útil.")
        if not 5 <= novo.aviso_antecedencia_min <= 120:
            return _erro("A antecedência do aviso vai de 5 a 120 minutos.")
        if novo.aviso_som not in SONS:
            return _erro("Som desconhecido.")
        if novo.pasta_backup:
            try:
                Path(novo.pasta_backup).mkdir(parents=True, exist_ok=True)
            except OSError:
                return _erro("Não consegui usar essa pasta de backup. Confira se o OneDrive está disponível.")
        if asdict(novo) == asdict(cfg):
            return Resultado("Sem mudanças.", pode_desfazer=False)
        self.banco.salvar_config(novo)
        if any(getattr(novo, c) != getattr(cfg, c) for c in self.CAMPOS_QUE_REPLANEJAM):
            res = self.replanejar("configuração alterada")
            return Resultado("Configuração salva e semana replanejada." + self.texto_movidas(res.movidas),
                             movidas=res.movidas, pode_desfazer=False)
        return Resultado("Configuração salva.", pode_desfazer=False)

    def resumo_jornada(self) -> str:
        cfg = self.config()
        ini, ai, af, fim = (_min(le_hora(x)) for x in (cfg.jornada_inicio, cfg.almoco_inicio, cfg.almoco_fim, cfg.jornada_fim))
        total = (fim - ini) - (af - ai)
        n = len(cfg.dias_uteis)
        return (f"Jornada de {formata_minutos(total)} por dia, {n} {'dia' if n == 1 else 'dias'} por semana. "
                f"Dessas horas, {formata_minutos(cfg.horas_padrao_min)} ficam para tarefas por padrão; o resto é para "
                f"reuniões e imprevistos (ajuste dia a dia com − e + em Hoje ou Semana).")

    # ---------- avisos de horário ----------
    def horarios_avisos(self, dia: date | None = None) -> list[tuple[str, datetime]]:
        """Avisos ligados para o dia (só em dia de trabalho), em ordem."""
        dia = dia or self.hoje()
        cfg = self.config()
        if not self.calendario().eh_dia_de_trabalho(dia):
            return []
        saida = []
        if cfg.aviso_manha:
            saida.append(("manha", _min(le_hora(cfg.almoco_inicio)) - cfg.aviso_antecedencia_min))
        if cfg.aviso_fim:
            saida.append(("fim", _min(le_hora(cfg.jornada_fim)) - cfg.aviso_antecedencia_min))
        return [(tipo, datetime.combine(dia, time(m // 60, m % 60))) for tipo, m in sorted(saida, key=lambda x: x[1]) if m >= 0]

    def resumo_avisos(self) -> str:
        nomes = {"manha": "Aviso da manhã", "fim": "aviso do fim do dia"}
        cfg = self.config()
        partes = []
        if cfg.aviso_manha:
            partes.append(f"{nomes['manha']} às {_hhmm(_min(le_hora(cfg.almoco_inicio)) - cfg.aviso_antecedencia_min)}")
        if cfg.aviso_fim:
            partes.append(f"{nomes['fim']} às {_hhmm(_min(le_hora(cfg.jornada_fim)) - cfg.aviso_antecedencia_min)}")
        texto = " · ".join(partes) or "Nenhum aviso ligado"
        if partes and cfg.aviso_som == "Desligado":
            texto += " (sem som)"
        return texto[:1].upper() + texto[1:]

    def montar_aviso(self, tipo: str) -> Aviso:
        cfg = self.config()
        dia = self.hoje()
        abertas = [t for t in self.banco.tarefas(ABERTA) if t.dia_planejado == dia]
        minutos = sum(t.minutos for t in abertas)
        cobrar = sum(1 for a in self.banco.aguardando("aberto") if a.cobrar_em <= dia)
        antes = cfg.aviso_antecedencia_min
        if tipo == "manha":
            hora = datetime.combine(dia, le_hora(cfg.almoco_inicio)) - timedelta(minutes=antes)
            if abertas:
                msg = f"{len(abertas)} {'tarefa aberta' if len(abertas) == 1 else 'tarefas abertas'} hoje ({formata_minutos(minutos)})."
                cabe = [t for t in abertas if t.minutos <= antes]
                if cabe:
                    msg += f"\nDá tempo de fechar: {cabe[0].titulo}"
            else:
                msg = "Tudo de hoje está concluído. Bom almoço!"
            if cobrar:
                msg += f"\n{cobrar} {'cobrança pendente' if cobrar == 1 else 'cobranças pendentes'}."
            return Aviso("manha", hora, f"Faltam {antes} min para o almoço", msg, "ver_hoje" if abertas or cobrar else "ok",
                         "Ver Hoje" if abertas or cobrar else "Ok")
        hora = datetime.combine(dia, le_hora(cfg.jornada_fim)) - timedelta(minutes=antes)
        if abertas:
            msg = (f"{len(abertas)} {'tarefa ainda aberta' if len(abertas) == 1 else 'tarefas ainda abertas'} ({formata_minutos(minutos)}).\n"
                   "O que não terminar será replanejado sozinho amanhã cedo, ou replaneje agora e feche o dia tranquilo.")
        else:
            msg = "Nada pendente para hoje. Até amanhã!"
        if cobrar:
            msg += f"\n{cobrar} {'cobrança pendente' if cobrar == 1 else 'cobranças pendentes'}."
        return Aviso("fim", hora, f"Faltam {antes} min para o fim da jornada", msg,
                     "replanejar" if abertas else "ok", "Replanejar o resto agora" if abertas else "Ok")

    # ---------- backup ----------
    def pasta_backup(self) -> Path:
        return pasta_backup_efetiva(self.config().pasta_backup, self.pasta_app)

    def ultimo_backup(self) -> datetime | None:
        return data_do_backup(self.pasta_backup())

    def backup_agora(self) -> Resultado:
        try:
            alvo = fazer_backup(self.banco.caminho, self.pasta_backup(), self.hoje(), forcar=True)
        except (OSError, sqlite3.Error) as e:
            return _erro(f"Não consegui fazer o backup: {e}")
        return Resultado(f"Backup feito: {alvo}", pode_desfazer=False)

    # ---------- ausências (listas para a tela) ----------
    def ausencias_futuras(self) -> list[Ausencia]:
        """Ausências e feriados que ainda não terminaram, em ordem de data."""
        h = self.hoje()
        return sorted((a for a in self.banco.ausencias() if a.fim >= h), key=lambda a: (a.inicio, a.fim))

    def pontos_facultativos_pendentes(self) -> list[tuple[date, str]]:
        """Carnaval, Cinzas e vésperas que ainda não viraram folga (para cadastrar com um clique)."""
        h = self.hoje()
        cal = self.calendario()
        saida = []
        for ano in (h.year, h.year + 1):
            for d, nome in pontos_facultativos(ano):
                if d >= h and d.weekday() in cal.dias_uteis and cal.ausencia_em(d) is None:
                    saida.append((d, nome))
        return saida

    # ---------- ausências ----------
    def adicionar_ausencia(self, tipo: str, inicio: date, fim: date, descricao: str = "") -> Resultado:
        if tipo not in TIPOS_AUSENCIA:
            return _erro(f"Tipo desconhecido: {tipo}")
        inicio, fim = min(inicio, fim), max(inicio, fim)
        cfg = self.config()
        d, uteis = inicio, 0
        while d <= fim:
            uteis += d.weekday() in cfg.dias_uteis
            d += timedelta(days=1)
        if not uteis:
            return _erro("O período escolhido não tem dia útil.")
        self._retrato()
        self.banco.salvar_ausencia(Ausencia(tipo, inicio, fim, descricao))
        res = self.replanejar(f"{tipo.lower()} cadastrado(a)")
        periodo = formata_dia(inicio) if fim <= inicio else f"{formata_dia(inicio)} a {formata_dia(fim)}"
        msg = f"{tipo} cadastrado(a): {periodo}" + (self.texto_movidas(res.movidas) if res.movidas else " · nada precisou mudar")
        if res.conflitos:
            msg += f"\n{len(res.conflitos)} em conflito com o prazo"
        return Resultado(msg, movidas=res.movidas)

    def remover_ausencia(self, ausencia_id: int) -> Resultado:
        self._retrato()
        self.banco.remover_ausencia(ausencia_id)
        res = self.replanejar("ausência removida")
        return Resultado("Removida." + self.texto_movidas(res.movidas), movidas=res.movidas)
