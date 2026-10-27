"""Objetos de domínio do app. Sem dependência de interface nem de banco."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

# status da tarefa
ABERTA, CONCLUIDA, CANCELADA, DELEGADA = "aberta", "concluida", "cancelada", "delegada"

# tipos de registro no diário
TIPOS_REGISTRO = ("Criada", "Feito", "Próximo passo", "Ocorrência", "Bloqueio", "Decisão",
                  "Adiamento", "Replanejada", "Reaberta", "Concluída")
TIPOS_QUE_O_USUARIO_ESCREVE = ("Feito", "Próximo passo", "Ocorrência", "Bloqueio", "Decisão")

# conflitos marcados pelo planejador
CONFLITO_NAO_CABE = "nao_cabe"            # não há espaço antes do prazo
CONFLITO_PRAZO_VENCIDO = "prazo_vencido"  # o prazo já passou
CONFLITO_MAIOR_QUE_DIA = "maior_que_dia"  # tamanho maior que qualquer dia

TAMANHOS = {"p": 30, "m": 120, "g": 240}
TAMANHO_PADRAO = 120


@dataclass
class Tarefa:
    titulo: str
    minutos: int = TAMANHO_PADRAO
    importancia: int = 0  # 0 normal, 1 importante, 2 muito importante
    prazo: date | None = None          # prazo combinado: nunca muda com adiamentos
    data_fixa: date | None = None      # se definida, a tarefa fica nesse dia
    dia_planejado: date | None = None  # calculado pelo planejador
    nao_antes_de: date | None = None   # usado ao adiar: só a partir deste dia
    status: str = ABERTA
    adiamentos: int = 0
    projeto: str | None = None
    reuniao_id: int | None = None
    aguardando_id: int | None = None   # item recebido que gerou esta tarefa
    criada_em: datetime = field(default_factory=datetime.now)
    concluida_em: datetime | None = None
    ordem_manual: int | None = None    # ordem definida arrastando, válida só em ordem_manual_dia
    ordem_manual_dia: date | None = None
    conflito: str | None = None        # preenchido pelo planejador
    id: int | None = None

    @property
    def aberta(self) -> bool:
        return self.status == ABERTA


@dataclass
class Registro:
    tarefa_id: int
    tipo: str
    texto: str
    quando: datetime = field(default_factory=datetime.now)
    feito: bool = False                # só para "Próximo passo"
    feito_em: datetime | None = None
    id: int | None = None


@dataclass
class Aguardando:
    pessoa: str
    o_que: str
    cobrar_em: date
    status: str = "aberto"  # aberto | recebido
    cobrancas: list[date] = field(default_factory=list)
    recebido_em: date | None = None
    reuniao_id: int | None = None
    tarefa_origem_id: int | None = None  # tarefa delegada que virou este item
    tarefa_gerada_id: int | None = None  # tarefa criada ao receber
    eventos: list[dict] = field(default_factory=list)  # histórico: {"quando", "tipo", "texto"}
    id: int | None = None

    def contar(self, tipo: str) -> int:
        return sum(1 for e in self.eventos if e.get("tipo") == tipo)


@dataclass
class Reuniao:
    titulo: str
    quando: datetime
    recap_original: str = ""
    notas: list[str] = field(default_factory=list)  # decisões e riscos aceitos, ex.: "DECISÃO: go-live em 30/11"
    id: int | None = None


@dataclass
class Configuracao:
    meu_nome: str = "FABIO KIYOSHI SATO"
    apelidos: list[str] = field(default_factory=lambda: ["Fabio", "você"])
    horas_padrao_min: int = 300
    dias_uteis: list[int] = field(default_factory=lambda: [0, 1, 2, 3, 4])
    jornada_inicio: str = "09:00"
    almoco_inicio: str = "12:00"
    almoco_fim: str = "13:00"
    jornada_fim: str = "18:00"
    aviso_manha: bool = True
    aviso_fim: bool = True
    aviso_antecedencia_min: int = 30
    aviso_som: str = "Suave"  # Suave | Sino | Bipe | Desligado
    pasta_backup: str = ""     # vazio = subpasta backup/ ao lado do app
    horizonte_dias: int = 20   # 4 semanas de dias úteis
    mini_barra_x: int | None = None
    mini_barra_y: int | None = None
    mini_barra_recolhida: bool = False
