"""Aba Concluídas: histórico por mês e por dia (tarefas concluídas e entregas recebidas), com filtro e Reabrir."""
from __future__ import annotations

from itertools import groupby

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QPushButton, QVBoxLayout, QWidget

from nucleo.captura import formata_dia, formata_minutos

from . import estilo
from .widgets import LinhaClicavel, area_rolavel, botao, limpar_layout, rotulo, selo, texto_longo, vazio

MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto",
         "Setembro", "Outubro", "Novembro", "Dezembro"]


def _plural(n: int, um: str, varios: str) -> str:
    return f"{n} {um if n == 1 else varios}"


class TelaConcluidas(QWidget):
    def __init__(self, ctrl, parent=None):
        super().__init__(parent)
        self.ctrl = ctrl
        hoje = ctrl.sv.hoje()
        self.abertos: set[tuple[int, int]] = {(hoje.year, hoje.month)}  # mês atual aberto por padrão
        self.lay = area_rolavel(self)
        self.filtro = QLineEdit()
        self.filtro.setPlaceholderText("Filtrar por texto, #projeto ou pessoa")
        self.filtro.setAccessibleName("Filtrar concluídas")
        self.filtro.setClearButtonEnabled(True)
        self.filtro.setMinimumWidth(180)
        self.filtro.setMaximumWidth(280)
        self.filtro.textChanged.connect(lambda _: self.atualizar())
        self.resumo = texto_longo("", "subtitulo")
        cab = QHBoxLayout()
        textos = QVBoxLayout()
        textos.setSpacing(2)
        textos.addWidget(rotulo("Concluídas", "titulo"))
        textos.addWidget(self.resumo)
        cab.addLayout(textos, 1)
        cab.addWidget(self.filtro, 0, Qt.AlignVCenter)
        self.lay.addLayout(cab)
        self.dinamico = QVBoxLayout()
        self.dinamico.setSpacing(10)
        self.lay.addLayout(self.dinamico)
        self.lay.addStretch(1)

    # ----------------------------------------------------------------
    def atualizar(self):
        sv = self.ctrl.sv
        limpar_layout(self.dinamico)
        todos = sv.historico()
        n_t = sum(1 for i in todos if i.tipo == "tarefa")
        n_r = len(todos) - n_t
        minutos = sum(i.tarefa.minutos for i in todos if i.tarefa)
        self.resumo.setText(f"{_plural(n_t, 'tarefa concluída', 'tarefas concluídas')} · "
                            f"{_plural(n_r, 'entrega recebida', 'entregas recebidas')} de outras pessoas · "
                            f"{formata_minutos(minutos) if minutos else '0min'} de trabalho registrado")
        filtro = self.filtro.text().strip()
        itens = sv.historico(filtro) if filtro else todos
        if not itens:
            self.dinamico.addWidget(vazio("Nenhum item encontrado." if filtro else
                                          "Nada concluído ainda. O que você terminar aparece aqui, por mês e por dia."))
            return
        for (ano, mes), grupo in groupby(itens, key=lambda i: (i.dia.year, i.dia.month)):
            grupo = list(grupo)
            aberto = bool(filtro) or (ano, mes) in self.abertos
            self.dinamico.addWidget(self._cabecalho_mes(ano, mes, grupo, aberto))
            if aberto:
                for dia, do_dia in groupby(grupo, key=lambda i: i.dia):
                    do_dia = list(do_dia)
                    lb = rotulo(f"{formata_dia(dia).upper()} · {_plural(len(do_dia), 'ITEM', 'ITENS')}", "rotulo")
                    lb.setContentsMargins(4, 6, 0, 0)
                    self.dinamico.addWidget(lb)
                    for item in do_dia:
                        self.dinamico.addWidget(self._linha(item))

    def _cabecalho_mes(self, ano: int, mes: int, grupo, aberto: bool) -> QPushButton:
        minutos = sum(i.tarefa.minutos for i in grupo if i.tarefa)
        partes = [_plural(len(grupo), "item", "itens")]
        if minutos:
            partes.append(formata_minutos(minutos))
        b = QPushButton(f"{'▾' if aberto else '▸'}  {MESES[mes - 1]} de {ano}     {' · '.join(partes)}")
        b.setCursor(Qt.PointingHandCursor)
        b.setAccessibleName(f"{MESES[mes - 1]} de {ano}, {'recolher' if aberto else 'expandir'}")
        b.setStyleSheet(f"QPushButton {{ text-align: left; font-size: 15px; font-weight: 700; padding: 10px 12px;"
                        f" border: 1px solid {estilo.BORDA}; border-radius: 8px; background: {estilo.FUNDO_SUAVE}; }}"
                        f"QPushButton:hover {{ background: {estilo.FUNDO_CINZA}; }}")
        b.clicked.connect(lambda _=False, k=(ano, mes): self._alternar(k))
        return b

    def _alternar(self, chave):
        if self.filtro.text().strip():
            return  # com filtro, todos os meses ficam abertos
        self.abertos ^= {chave}
        self.atualizar()

    def _linha(self, item) -> QWidget:
        sv = self.ctrl.sv
        if item.tipo == "tarefa":
            linha = LinhaClicavel()
            linha.marcar_selecionada(item.tarefa.id == self.ctrl.sel_id)
            linha.clicada.connect(lambda i=item.tarefa.id: self.ctrl.abrir_tarefa(i))
            marca = selo("✓", estilo.VERDE_TEXTO, estilo.VERDE_CLARO)
            reabrir = botao("Reabrir", ao_clicar=lambda _=False, i=item.tarefa.id: self.ctrl.executar(sv.reabrir, i),
                            dica="Volta para as tarefas abertas e é replanejada")
        else:
            linha = LinhaClicavel()
            linha.setCursor(Qt.ArrowCursor)
            marca = selo("RECEBIDO", estilo.ACENTO_ESCURO, estilo.ACENTO_CLARO)
            reabrir = botao("Reabrir", ao_clicar=lambda _=False, i=item.aguardando.id: self.ctrl.executar(sv.reabrir_espera, i),
                            dica="Volta para Aguardando, com cobrança no próximo dia útil")
        h = QHBoxLayout(linha)
        h.setContentsMargins(12, 8, 12, 8)
        h.setSpacing(12)
        h.addWidget(marca, 0, Qt.AlignTop)
        textos = QVBoxLayout()
        textos.setSpacing(2)
        for w in (texto_longo(item.titulo, "tituloTarefa"), texto_longo(item.detalhe, "meta")):
            w.setAttribute(Qt.WA_TransparentForMouseEvents)
            textos.addWidget(w)
        h.addLayout(textos, 1)
        h.addWidget(reabrir)
        return linha
