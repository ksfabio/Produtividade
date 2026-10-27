"""Aba Semana: segunda a sexta em colunas, com capacidade ajustável e 'sem data por enquanto'."""
from __future__ import annotations

from datetime import timedelta

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QButtonGroup, QFrame, QGridLayout, QHBoxLayout, QScrollArea,
                               QVBoxLayout, QWidget)

from nucleo.captura import formata_dia, formata_minutos
from nucleo.planejador import tarefas_do_dia

from . import estilo
from .hoje import CONFLITOS, meta_tarefa
from .widgets import BarraCapacidade, LinhaClicavel, botao, limpar_layout, rotulo, selo


class TelaSemana(QWidget):
    SEMANAS = 4

    def __init__(self, ctrl, parent=None):
        super().__init__(parent)
        self.ctrl = ctrl
        self.semana = 0
        externo = QVBoxLayout(self)
        externo.setContentsMargins(0, 0, 0, 0)
        rolagem = QScrollArea()
        rolagem.setWidgetResizable(True)
        rolagem.setFrameShape(QFrame.NoFrame)
        externo.addWidget(rolagem)
        conteudo = QWidget()
        conteudo.setObjectName("fundo")
        rolagem.setWidget(conteudo)
        self.lay = QVBoxLayout(conteudo)
        self.lay.setContentsMargins(24, 20, 24, 32)
        self.lay.setSpacing(14)

        cab = QHBoxLayout()
        textos = QVBoxLayout()
        textos.setSpacing(2)
        textos.addWidget(rotulo("Semana", "titulo"))
        textos.addWidget(rotulo("Montada pelo planejador. Ajuste as horas de cada dia e ele reencaixa.", "subtitulo"))
        cab.addLayout(textos, 1)
        self.grupo = QButtonGroup(self)
        self.grupo.setExclusive(True)
        for i, nome in enumerate(["Esta semana", "Próxima", "+2", "+3"]):
            b = botao(nome, "chip", lambda _=False, i=i: self._escolher(i))
            b.setCheckable(True)
            b.setChecked(i == 0)
            self.grupo.addButton(b, i)
            cab.addWidget(b)
        self.lay.addLayout(cab)
        self.grade = QGridLayout()
        self.grade.setSpacing(10)
        for c in range(5):
            self.grade.setColumnStretch(c, 1)
        self.lay.addLayout(self.grade)
        self.sem_data = QVBoxLayout()
        self.sem_data.setSpacing(6)
        self.lay.addLayout(self.sem_data)
        self.lay.addStretch(1)

    def _escolher(self, i: int):
        self.semana = i
        self.atualizar()

    def atualizar(self):
        sv = self.ctrl.sv
        limpar_layout(self.grade)
        limpar_layout(self.sem_data)
        hoje = sv.hoje()
        segunda = hoje - timedelta(days=hoje.weekday()) + timedelta(weeks=self.semana)
        cal = sv.calendario()
        abertas = sv.banco.tarefas("aberta")
        reservas = sv.reservas()
        for c in range(5):
            dia = segunda + timedelta(days=c)
            self.grade.addWidget(self._coluna(dia, cal, abertas, reservas, hoje), 0, c, Qt.AlignTop)

        sem = [t for t in abertas if t.dia_planejado is None]
        if sem:
            self.sem_data.addWidget(rotulo(f"SEM DATA POR ENQUANTO · {len(sem)}", "rotulo"))
            self.sem_data.addWidget(rotulo("Não couberam nas próximas 4 semanas. Libere horas ou ajuste prazos e tamanhos.", "meta"))
            for t in sem:
                self.sem_data.addWidget(self._cartao(t, largo=True))

    def _coluna(self, dia, cal, abertas, reservas, hoje) -> QFrame:
        sv = self.ctrl.sv
        col = QFrame()
        col.setObjectName("colunaHoje" if dia == hoje else "colunaDia")
        col.setMinimumHeight(420)
        v = QVBoxLayout(col)
        v.setContentsMargins(10, 10, 10, 10)
        v.setSpacing(8)
        nome = sv.nome_dia(dia)
        titulo = rotulo(nome if nome.startswith(formata_dia(dia)) else f"{nome} · {dia:%d/%m}", "secao")
        if dia == hoje:
            titulo.setStyleSheet(f"color: {estilo.ACENTO_ESCURO};")
        v.addWidget(titulo)
        passado = dia < hoje
        motivo = cal.motivo_folga(dia)
        cap = cal.capacidade(dia)
        do_dia = tarefas_do_dia(abertas, dia)
        usado = sum(t.minutos for t in do_dia) + reservas.get(dia, 0)
        if passado:
            v.addWidget(rotulo("Dia encerrado", "meta"))
        else:
            v.addWidget(rotulo(f"{formata_minutos(usado)} de {formata_minutos(cap)}", "meta"))
            barra = BarraCapacidade(6)
            barra.definir(usado, cap)
            v.addWidget(barra)
            if motivo and "Meio período" not in motivo:
                tipo = motivo.split(":")[0]
                forte, claro, texto = estilo.CORES_AUSENCIA.get(tipo, estilo.CORES_AUSENCIA["Dia não útil"])
                faixa = selo(motivo, texto, claro, forte)
                faixa.setWordWrap(True)
                v.addWidget(faixa)
            else:
                if motivo:
                    forte, claro, texto = estilo.CORES_AUSENCIA["Meio período"]
                    v.addWidget(selo(motivo, texto, claro, forte))
                linha = QHBoxLayout()
                linha.setSpacing(4)
                base = cal.capacidade_base(dia)
                linha.addWidget(botao("− 30min", ao_clicar=lambda _=False, d=dia, b=base: self.ctrl.definir_capacidade(d, b - 30),
                                      dica="Menos 30 minutos neste dia"))
                linha.addWidget(botao("+ 30min", ao_clicar=lambda _=False, d=dia, b=base: self.ctrl.definir_capacidade(d, b + 30),
                                      dica="Mais 30 minutos neste dia"))
                v.addLayout(linha)
            for a in sv.banco.aguardando("aberto"):
                if max(a.cobrar_em, hoje) == dia:
                    v.addWidget(selo(f"Cobrar {a.pessoa} · 5min", "white", estilo.COBRAR))
            for t in do_dia:
                v.addWidget(self._cartao(t))
        v.addStretch(1)
        return col

    def _cartao(self, t, largo: bool = False) -> QFrame:
        c = LinhaClicavel()
        c.marcar_selecionada(t.id == self.ctrl.sel_id)
        if t.conflito:
            c.setStyleSheet(f"QFrame#linhaTarefa {{ border: 2px solid {estilo.VERMELHO}; background: {estilo.VERMELHO_CLARO}; }}")
        c.clicada.connect(lambda i=t.id: self.ctrl.abrir_tarefa(i))
        v = QVBoxLayout(c)
        v.setContentsMargins(9, 7, 9, 7)
        v.setSpacing(2)
        titulo = rotulo(t.titulo, quebra=True)
        titulo.setStyleSheet("font-weight: 600;")
        titulo.setAttribute(Qt.WA_TransparentForMouseEvents)
        v.addWidget(titulo)
        detalhe = meta_tarefa(t) if largo else formata_minutos(t.minutos) + (
            f" · até {formata_dia(t.prazo).lower()}" if t.prazo else "") + (" · fixa" if t.data_fixa else "")
        if t.conflito:
            detalhe += f" · {CONFLITOS.get(t.conflito, 'conflito')}"
        m = rotulo(detalhe, "meta", quebra=True)
        if t.conflito:
            m.setStyleSheet(f"color: {estilo.VERMELHO_TEXTO};")
        m.setAttribute(Qt.WA_TransparentForMouseEvents)
        v.addWidget(m)
        return c
