"""Leitura do recap de reunião (Teams Copilot) e geração de sugestões.

Aceita dois formatos:
1. Estruturado (pedido copiado pelo botão "Copiar pedido para o Copilot"):
       TAREFA: enviar ata | RESPONSÁVEL: Fabio | PRAZO: 28/10
       AGUARDANDO: plano de migração | RESPONSÁVEL: Marcos | PRAZO: 28/10
       DECISÃO: manter go-live em 30/11
       RISCO: atraso do fornecedor
2. Livre (recap padrão), com linhas do tipo "Nome: ação até 28/10" em seções como
   "Itens de ação" / "Próximos passos", e "Decisões".

Itens cujo responsável bate com o seu nome ou apelidos viram tarefas suas; os de
outras pessoas viram Aguardando. Nada é criado sem revisão: isto só gera sugestões.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Callable

from .captura import le_dia, le_duracao, normaliza

TAREFA, AGUARDANDO, DECISAO, RISCO = "TAREFA", "AGUARDANDO", "DECISÃO", "RISCO"

PROMPT_COPILOT = (
    "Com base nesta reunião, responda só neste formato, uma linha por item:\n"
    "DECISÃO: <texto>\n"
    "TAREFA: <o quê> | RESPONSÁVEL: <quem> | PRAZO: <dd/mm>\n"
    "AGUARDANDO: <o que outra pessoa entrega> | RESPONSÁVEL: <quem> | PRAZO: <dd/mm>\n"
    "RISCO: <texto>"
)

_SECOES_ACAO = ("itens de acao", "acoes", "proximos passos", "tarefas", "action items", "pendencias")
_SECOES_DECISAO = ("decisoes", "decisao", "definicoes")
_SECOES_RISCO = ("riscos", "pontos de atencao", "atencao")


@dataclass
class Sugestao:
    tipo: str            # TAREFA | AGUARDANDO | DECISÃO | RISCO
    texto: str
    responsavel: str | None = None
    prazo: date | None = None
    data_fixa: date | None = None
    minutos: int | None = None
    trecho: str = ""
    aceita: bool = True


def eh_comigo(responsavel: str | None, meu_nome: str, apelidos: list[str]) -> bool:
    """True se o responsável sou eu: nome completo, primeiro+último nome, apelidos ou 'você'."""
    if not responsavel:
        return False
    r = normaliza(responsavel).strip()
    nome = normaliza(meu_nome).strip()
    partes = nome.split()
    candidatos = {nome}
    if partes:
        candidatos.add(partes[0])
        candidatos.add(f"{partes[0]} {partes[-1]}")
    candidatos |= {normaliza(a).strip() for a in apelidos if a.strip()}
    candidatos |= {"voce", "eu"}
    return r in candidatos or any(re.search(rf"\b{re.escape(c)}\b", r) for c in candidatos if len(c) > 2)


def _extrai_datas(texto: str, hoje: date, proximo_util) -> tuple[str, date | None, date | None]:
    """Remove 'até X' (prazo) e 'hoje/amanhã' (data fixa) do texto e devolve (texto_limpo, prazo, data_fixa)."""
    prazo = fixa = None
    m = re.search(r"\b(?:at[ée]|para|prazo:?)\s+(?:o\s+dia\s+|dia\s+)?(\S+)", texto, flags=re.IGNORECASE)
    if m and (d := le_dia(m.group(1), hoje, proximo_util)):
        prazo = d
        texto = (texto[:m.start()] + texto[m.end():]).strip()
    m = re.search(r"\b(hoje|amanh[ãa])\b", texto, flags=re.IGNORECASE)
    if m and prazo is None:
        fixa = le_dia(m.group(1), hoje, proximo_util)
        texto = (texto[:m.start()] + texto[m.end():]).strip()
    return re.sub(r"\s{2,}", " ", texto).strip(" .;,-"), prazo, fixa


def _estruturada(linha: str, hoje: date, proximo_util) -> Sugestao | None:
    m = re.match(r"^\s*[-•*]?\s*(TAREFA|AGUARDANDO|DECIS[ÃA]O|RISCO)\s*:\s*(.+)$", linha, flags=re.IGNORECASE)
    if not m:
        return None
    tipo = normaliza(m.group(1)).upper()
    tipo = {"DECISAO": DECISAO}.get(tipo, tipo)
    campos = [c.strip() for c in m.group(2).split("|")]
    texto, resp, prazo, minutos = campos[0], None, None, None
    for c in campos[1:]:
        k, _, v = c.partition(":")
        k = normaliza(k).strip()
        if k.startswith("respons"):
            resp = v.strip()
        elif k.startswith("prazo"):
            prazo = le_dia(v.strip(), hoje, proximo_util)
        elif k.startswith("tempo") or k.startswith("tamanho"):
            minutos = le_duracao(v.strip(), aceitar_numero=True)
    return Sugestao(tipo, texto, resp, prazo, None, minutos, trecho=linha.strip())


def le_recap(texto: str, hoje: date, meu_nome: str, apelidos: list[str],
             proximo_util: Callable[[date], date] | None = None) -> list[Sugestao]:
    sugestoes: list[Sugestao] = []
    secao = ""
    for bruta in (texto or "").splitlines():
        linha = bruta.strip()
        if not linha:
            continue
        estruturada = _estruturada(linha, hoje, proximo_util)
        if estruturada:
            sugestoes.append(estruturada)
            continue
        cab = normaliza(linha).rstrip(":").strip()
        if linha.endswith(":") or cab in _SECOES_ACAO + _SECOES_DECISAO + _SECOES_RISCO:
            secao = ("acao" if any(cab.startswith(s) for s in _SECOES_ACAO)
                     else "decisao" if any(cab.startswith(s) for s in _SECOES_DECISAO)
                     else "risco" if any(cab.startswith(s) for s in _SECOES_RISCO) else "")
            continue
        corpo = re.sub(r"^[-•*\d.)\s]+", "", linha).strip()
        if not corpo:
            continue
        if secao == "decisao":
            sugestoes.append(Sugestao(DECISAO, corpo.rstrip("."), trecho=linha))
        elif secao == "risco":
            sugestoes.append(Sugestao(RISCO, corpo.rstrip("."), trecho=linha, aceita=False))
        elif secao == "acao":
            m = re.match(r"^([^:]{2,60}):\s*(.+)$", corpo)
            resp, acao = (m.group(1).strip(), m.group(2).strip()) if m else (None, corpo)
            acao, prazo, fixa = _extrai_datas(acao, hoje, proximo_util)
            acao = acao[:1].upper() + acao[1:] if acao else acao
            sugestoes.append(Sugestao(TAREFA, acao, resp, prazo, fixa, trecho=linha))

    # tarefas de outras pessoas viram Aguardando
    for s in sugestoes:
        if s.tipo == TAREFA and s.responsavel and not eh_comigo(s.responsavel, meu_nome, apelidos):
            s.tipo = AGUARDANDO
        if s.tipo == AGUARDANDO and s.responsavel and eh_comigo(s.responsavel, meu_nome, apelidos):
            s.tipo = TAREFA
    return sugestoes
