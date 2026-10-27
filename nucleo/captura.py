"""Leitura da captura rápida.

Exemplo: "consolidar riscos #alfa g até qui !"
    -> título "consolidar riscos", 4 h, projeto "alfa", prazo na quinta, importante.

Regras (todas opcionais, em qualquer ordem):
    p | m | g                tamanho 30 min | 2 h | 4 h
    15min, 1h, 1h30, 90min   tempo exato
    até <dia>                prazo final (o planejador nunca passa dele)
    <dia> sem "até"          data fixa (a tarefa fica nesse dia)
    ! | !!                   importante | muito importante
    #projeto                 projeto
    @pessoa                  não é sua: vai para Aguardando
<dia> = hoje, amanhã, seg..sex (ou segunda..sexta), dd/mm, dd/mm/aaaa.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Callable

from .modelos import TAMANHOS

DIAS_SEMANA = {
    "seg": 0, "segunda": 0, "segunda-feira": 0,
    "ter": 1, "terca": 1, "terca-feira": 1,
    "qua": 2, "quarta": 2, "quarta-feira": 2,
    "qui": 3, "quinta": 3, "quinta-feira": 3,
    "sex": 4, "sexta": 4, "sexta-feira": 4,
    "sab": 5, "sabado": 5, "dom": 6, "domingo": 6,
}
NOMES_CURTOS = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]


def normaliza(texto: str) -> str:
    """Minúsculas e sem acentos."""
    sem = unicodedata.normalize("NFD", texto or "")
    return "".join(c for c in sem if unicodedata.category(c) != "Mn").lower()


def formata_dia(d: date) -> str:
    return f"{NOMES_CURTOS[d.weekday()].capitalize()} {d:%d/%m}"


def formata_minutos(m: int) -> str:
    if m < 60:
        return f"{m}min"
    h, r = divmod(m, 60)
    return f"{h}h{r:02d}" if r else f"{h}h"


def le_duracao(token: str, aceitar_numero: bool = False) -> int | None:
    """'15min', '1h', '1h30', '1h30min', '1,5h'. None se não for duração.

    Com aceitar_numero=True, um número sozinho ('20') vale minutos; usado no campo
    de tempo do painel da tarefa, não na captura (onde '3' pode fazer parte do título).
    """
    t = normaliza(token).replace(" ", "").replace(",", ".")
    if aceitar_numero and t.isdigit():
        return int(t)
    if t in TAMANHOS:
        return TAMANHOS[t]
    m = re.fullmatch(r"(\d+)(?:min|m)", t)
    if m:
        return int(m.group(1))
    m = re.fullmatch(r"(\d+)h(\d{1,2})?(?:min)?", t)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2) or 0)
    m = re.fullmatch(r"(\d+\.\d+)h", t)
    if m:
        return round(float(m.group(1)) * 60)
    return None


def le_dia(token: str, hoje: date, proximo_util: Callable[[date], date] | None = None) -> date | None:
    """Converte 'hoje', 'amanhã', 'qui', '30/10', '30/10/2026' em data. None se não for dia."""
    t = normaliza(token).strip(".,;")
    if t == "hoje":
        return hoje
    if t == "amanha":
        return proximo_util(hoje) if proximo_util else hoje + timedelta(days=1)
    if t in DIAS_SEMANA:
        alvo = DIAS_SEMANA[t]
        return hoje + timedelta(days=(alvo - hoje.weekday()) % 7)
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?", t)
    if m:
        dia, mes = int(m.group(1)), int(m.group(2))
        ano = m.group(3)
        try:
            if ano:
                a = int(ano)
                return date(a + 2000 if a < 100 else a, mes, dia)
            d = date(hoje.year, mes, dia)
            # data que já passou há mais de 30 dias é do ano seguinte (ex.: "05/01" digitado em dezembro)
            if d < hoje - timedelta(days=30):
                d = date(hoje.year + 1, mes, dia)
            return d
        except ValueError:
            return None
    return None


@dataclass
class Captura:
    titulo: str
    minutos: int | None = None
    importancia: int = 0
    prazo: date | None = None
    data_fixa: date | None = None
    projeto: str | None = None
    pessoa: str | None = None

    @property
    def eh_aguardando(self) -> bool:
        return self.pessoa is not None

    def descricao(self) -> str:
        """Prévia do que foi entendido, para mostrar enquanto a pessoa digita."""
        partes = [f"“{self.titulo}”"] if self.titulo else []
        if self.pessoa:
            partes.append(f"aguardando {self.pessoa} (vai para Aguardando)")
            if self.prazo:
                partes.append(f"cobrar em {formata_dia(self.prazo)}")
        else:
            partes.append("tamanho " + (formata_minutos(self.minutos) if self.minutos else "2h (padrão)"))
            if self.prazo:
                partes.append(f"prazo até {formata_dia(self.prazo)}")
        if self.data_fixa:
            partes.append(f"data fixa {formata_dia(self.data_fixa)}")
        if self.projeto:
            partes.append(f"projeto {self.projeto}")
        if self.importancia:
            partes.append("muito importante" if self.importancia == 2 else "importante")
        if not self.pessoa and not self.prazo and not self.data_fixa:
            partes.append("encaixe automático")
        return " · ".join(partes)


def le_captura(texto: str, hoje: date, proximo_util: Callable[[date], date] | None = None) -> Captura:
    tokens = (texto or "").split()
    palavras: list[str] = []
    c = Captura(titulo="")
    i = 0
    while i < len(tokens):
        tk = tokens[i]
        baixo = normaliza(tk)
        if re.fullmatch(r"#\S+", tk):
            c.projeto = tk[1:]
        elif re.fullmatch(r"@\S+", tk):
            c.pessoa = tk[1:]
        elif tk == "!!":
            c.importancia = 2
        elif tk == "!":
            c.importancia = max(c.importancia, 1)
        elif (dur := le_duracao(tk)) is not None and not re.fullmatch(r"\d+", baixo):
            c.minutos = dur
        elif baixo == "ate" and i + 1 < len(tokens) and (d := le_dia(tokens[i + 1], hoje, proximo_util)):
            c.prazo = d
            i += 1
        elif (d := le_dia(tk, hoje, proximo_util)) is not None:
            c.data_fixa = d
        else:
            palavras.append(tk)
        i += 1
    c.titulo = " ".join(palavras).strip()
    return c
