"""Calendário de trabalho: feriados, ausências e capacidade de cada dia.

A capacidade de um dia é quantos minutos ficam livres para tarefas.
Fins de semana (fora dos dias úteis), feriados e ausências de dia inteiro
valem 0; meio período vale metade da capacidade base, arredondada para 15 min.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

TIPOS_AUSENCIA = ("Férias", "Feriado", "Ausência", "Meio período")


@dataclass
class Ausencia:
    tipo: str
    inicio: date
    fim: date
    descricao: str = ""
    origem: str = "manual"  # "manual" ou "feriado"
    id: int | None = None

    def cobre(self, dia: date) -> bool:
        return self.inicio <= dia <= self.fim


def pascoa(ano: int) -> date:
    """Domingo de Páscoa (algoritmo gregoriano anônimo / Meeus-Jones-Butcher)."""
    a = ano % 19
    b, c = divmod(ano, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes, dia = divmod(h + l - 7 * m + 114, 31)
    return date(ano, mes, dia + 1)


def feriados(ano: int, incluir_sp: bool = True, incluir_osasco: bool = True) -> list[tuple[date, str, str]]:
    """Feriados do ano: (data, nome, esfera). Nacionais + SP + Osasco.

    Fonte dos municipais de Osasco: Decreto nº 14.952/2025 (resumo do Sintrasp).
    """
    p = pascoa(ano)
    lista = [
        (date(ano, 1, 1), "Confraternização Universal", "Nacional"),
        (date(ano, 4, 21), "Tiradentes", "Nacional"),
        (date(ano, 5, 1), "Dia do Trabalho", "Nacional"),
        (date(ano, 9, 7), "Independência do Brasil", "Nacional"),
        (date(ano, 10, 12), "Nossa Senhora Aparecida", "Nacional"),
        (date(ano, 11, 2), "Finados", "Nacional"),
        (date(ano, 11, 15), "Proclamação da República", "Nacional"),
        (date(ano, 11, 20), "Consciência Negra", "Nacional"),
        (date(ano, 12, 25), "Natal", "Nacional"),
    ]
    if incluir_sp:
        lista.append((date(ano, 7, 9), "Revolução Constitucionalista", "Estadual (SP)"))
    if incluir_osasco:
        lista += [
            (date(ano, 2, 19), "Emancipação de Osasco", "Municipal (Osasco)"),
            (p - timedelta(days=2), "Paixão de Cristo", "Municipal (Osasco)"),
            (p + timedelta(days=60), "Corpus Christi", "Municipal (Osasco)"),
            (date(ano, 6, 13), "Santo Antônio, padroeiro de Osasco", "Municipal (Osasco)"),
        ]
    return sorted(lista)


def pontos_facultativos(ano: int) -> list[tuple[date, str]]:
    """Datas que costumam ser folga mas não são feriado (vêm desligadas)."""
    p = pascoa(ano)
    return sorted([
        (p - timedelta(days=48), "Carnaval (segunda)"),
        (p - timedelta(days=47), "Carnaval (terça)"),
        (p - timedelta(days=46), "Quarta-feira de Cinzas"),
        (date(ano, 12, 24), "Véspera de Natal"),
        (date(ano, 12, 31), "Véspera de Ano Novo"),
    ])


def ausencias_de_feriados(ano: int) -> list[Ausencia]:
    return [Ausencia("Feriado", d, d, f"{nome} ({esfera.lower()})", origem="feriado") for d, nome, esfera in feriados(ano)]


def arredonda_15(minutos: int) -> int:
    return (minutos // 15) * 15


@dataclass
class Calendario:
    horas_padrao_min: int = 300
    dias_uteis: frozenset[int] = frozenset({0, 1, 2, 3, 4})  # 0 = segunda
    capacidade_especifica: dict[date, int] = field(default_factory=dict)
    ausencias: list[Ausencia] = field(default_factory=list)

    def ausencia_em(self, dia: date) -> Ausencia | None:
        for a in self.ausencias:
            if a.cobre(dia):
                return a
        return None

    def capacidade_base(self, dia: date) -> int:
        return self.capacidade_especifica.get(dia, self.horas_padrao_min)

    def capacidade(self, dia: date) -> int:
        if dia.weekday() not in self.dias_uteis:
            return 0
        base = self.capacidade_base(dia)
        a = self.ausencia_em(dia)
        if a is None:
            return base
        if a.tipo == "Meio período":
            return arredonda_15(base // 2)
        return 0

    def eh_dia_de_trabalho(self, dia: date) -> bool:
        return self.capacidade(dia) > 0

    def motivo_folga(self, dia: date) -> str:
        if dia.weekday() not in self.dias_uteis:
            return "Dia não útil"
        a = self.ausencia_em(dia)
        return f"{a.tipo}: {a.descricao}" if a else ""

    def dias_de_trabalho(self, inicio: date, quantidade: int, limite_busca: int = 400) -> list[date]:
        """Os próximos `quantidade` dias com capacidade > 0, a partir de `inicio` (inclusive)."""
        dias, d = [], inicio
        for _ in range(limite_busca):
            if len(dias) >= quantidade:
                break
            if self.eh_dia_de_trabalho(d):
                dias.append(d)
            d += timedelta(days=1)
        return dias

    def proximo_dia_de_trabalho(self, depois_de: date) -> date:
        dias = self.dias_de_trabalho(depois_de + timedelta(days=1), 1)
        return dias[0] if dias else depois_de + timedelta(days=1)

    def dias_uteis_entre(self, inicio: date, fim: date) -> int:
        n, d = 0, inicio
        while d <= fim:
            if self.eh_dia_de_trabalho(d):
                n += 1
            d += timedelta(days=1)
        return n
