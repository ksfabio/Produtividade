"""Planejador: encaixa as tarefas abertas nos dias de trabalho.

Regras (as mesmas do protótipo):
1. Tarefas com data fixa ficam no seu dia, mesmo que ele estoure.
2. As demais seguem a ordem: prazo mais próximo, depois a mais importante, depois a mais antiga.
3. Estabilidade: quem já está planejado num dia válido e ainda cabe, fica onde está.
4. Quem precisa de lugar vai para o primeiro dia com espaço, a partir de max(hoje, nao_antes_de),
   sem passar do prazo.
5. Sem espaço antes do prazo: fica no próprio dia do prazo, marcada com conflito.
   Prazo já vencido: primeiro dia com espaço, marcada com conflito.
6. Sem prazo e sem espaço no horizonte (4 semanas): fica "sem data por enquanto".
Cobranças de Aguardando reservam minutos nos seus dias antes de tudo.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date

from .calendario import Calendario
from .modelos import (ABERTA, CONFLITO_MAIOR_QUE_DIA, CONFLITO_NAO_CABE,
                      CONFLITO_PRAZO_VENCIDO, Tarefa)

_SEM_PRAZO = date.max


def chave_prioridade(t: Tarefa):
    return (t.prazo or _SEM_PRAZO, -t.importancia, t.criada_em, t.id or 0)


@dataclass
class Movimento:
    tarefa_id: int | None
    titulo: str
    de: date | None
    para: date | None


@dataclass
class ResultadoPlano:
    tarefas: list[Tarefa]
    movidas: list[Movimento] = field(default_factory=list)
    sem_data: list[Tarefa] = field(default_factory=list)
    uso: dict[date, int] = field(default_factory=dict)

    @property
    def conflitos(self) -> list[Tarefa]:
        return [t for t in self.tarefas if t.aberta and t.conflito]


def planejar(tarefas: list[Tarefa], calendario: Calendario, hoje: date,
             horizonte_dias: int = 20, reservas: dict[date, int] | None = None,
             ignorar_movimento_de: set[int] | None = None) -> ResultadoPlano:
    """Retorna cópias das tarefas com dia_planejado e conflito recalculados.

    `ignorar_movimento_de`: ids que mudaram de dia por ação direta do usuário (ex.: a tarefa
    adiada); não entram na lista de "outras replanejadas".
    """
    dias = calendario.dias_de_trabalho(hoje, horizonte_dias)
    dias_set = set(dias)
    cap = {d: calendario.capacidade(d) for d in dias}
    uso: dict[date, int] = {d: 0 for d in dias}
    for d, m in (reservas or {}).items():
        alvo = max(d, hoje)
        if alvo in uso:
            uso[alvo] += m
    maior_dia = max(cap.values(), default=0)
    ignorar = ignorar_movimento_de or set()

    antes = {t.id: t.dia_planejado for t in tarefas if t.id is not None}
    copias = [replace(t, conflito=None) for t in tarefas]
    abertas = [t for t in copias if t.status == ABERTA]

    def cabe(t: Tarefa, d: date) -> bool:
        return uso[d] + t.minutos <= cap[d]

    # 1. fixas
    for t in abertas:
        if t.data_fixa is not None:
            if t.data_fixa < hoje:
                t.data_fixa = hoje
            t.dia_planejado = t.data_fixa
            uso[t.data_fixa] = uso.get(t.data_fixa, 0) + t.minutos

    flexiveis = sorted((t for t in abertas if t.data_fixa is None), key=chave_prioridade)

    def limites(t: Tarefa) -> tuple[date, date | None]:
        inicio = max(hoje, t.nao_antes_de or hoje)
        return inicio, t.prazo

    # 2. estabilidade: mantém quem ainda é válido onde está
    pendentes: list[Tarefa] = []
    for t in flexiveis:
        inicio, prazo = limites(t)
        d = t.dia_planejado
        if d in dias_set and d >= inicio and (prazo is None or d <= prazo) and cabe(t, d):
            uso[d] += t.minutos
        else:
            pendentes.append(t)

    # 3. encaixa só quem precisa
    sem_data: list[Tarefa] = []
    for t in pendentes:
        inicio, prazo = limites(t)
        if t.minutos > maior_dia:
            # nunca cabe em dia nenhum: aparece logo, marcada, para a pessoa quebrar em partes
            t.conflito = CONFLITO_MAIOR_QUE_DIA
            t.dia_planejado = next((d for d in dias if d >= inicio), None)
            if t.dia_planejado is None:
                sem_data.append(t)
            else:
                uso[t.dia_planejado] += t.minutos
            continue
        candidatos = [d for d in dias if d >= inicio and (prazo is None or d <= prazo)]
        escolhido = next((d for d in candidatos if cabe(t, d)), None)
        if escolhido is None and prazo is not None:
            ate_prazo = [d for d in dias if inicio <= d <= prazo]
            if prazo < inicio or not ate_prazo:
                # prazo vencido, ou nenhum dia de trabalho até ele (ex.: prazo num sábado ou feriado):
                # vai para o primeiro dia com espaço, marcada
                t.conflito = CONFLITO_PRAZO_VENCIDO if prazo < inicio else CONFLITO_NAO_CABE
                escolhido = next((d for d in dias if d >= inicio and cabe(t, d)), None)
            elif dias and prazo <= dias[-1]:
                # há dias até o prazo, mas sem espaço: fica no último deles, mesmo estourando
                t.conflito = CONFLITO_NAO_CABE
                escolhido = ate_prazo[-1]
            # prazo além do horizonte: espera por espaço (sem data por enquanto)
        t.dia_planejado = escolhido
        if escolhido is None:
            sem_data.append(t)
        else:
            uso[escolhido] += t.minutos

    movidas = []
    for t in abertas:
        de = antes.get(t.id)
        if t.id in ignorar or de is None:
            continue
        if de != t.dia_planejado:
            movidas.append(Movimento(t.id, t.titulo, de, t.dia_planejado))
    return ResultadoPlano(copias, movidas, sem_data, uso)


def tarefas_do_dia(tarefas: list[Tarefa], dia: date) -> list[Tarefa]:
    """Ordem de exibição de um dia: ordem manual (se definida para esse dia), depois fixas, depois prioridade."""
    do_dia = [t for t in tarefas if t.aberta and t.dia_planejado == dia]

    def chave(t: Tarefa):
        manual = t.ordem_manual if t.ordem_manual_dia == dia and t.ordem_manual is not None else 10**6
        return (manual, 0 if t.data_fixa else 1, chave_prioridade(t))

    return sorted(do_dia, key=chave)


def proxima_que_cabe(tarefas: list[Tarefa], hoje: date, livre_min: int) -> Tarefa | None:
    """Sugestão de 'adiantar': a primeira tarefa futura, não fixa, que cabe no tempo livre de hoje."""
    futuras = [t for t in tarefas if t.aberta and t.dia_planejado and t.dia_planejado > hoje
               and t.data_fixa is None and t.minutos <= livre_min]
    return min(futuras, key=lambda t: (t.dia_planejado, chave_prioridade(t)), default=None)
