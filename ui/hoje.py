"""Aba Hoje: captura, capacidade do dia, cobranças, tarefas, sugestão de adiantar, concluídas."""
from __future__ import annotations

from datetime import date, datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QLineEdit, QScrollArea, QVBoxLayout,
                               QWidget)

from nucleo.captura import formata_dia, formata_minutos
from nucleo.planejador import proxima_que_cabe, tarefas_do_dia

from . import estilo
from .widgets import BarraCapacidade, LinhaClicavel, ao_focar, botao, limpar_layout, rotulo, selo

DIAS_LONGOS = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
CONFLITOS = {"nao_cabe": "não cabe até o prazo", "prazo_vencido": "passou do prazo", "maior_que_dia": "maior que um dia"}


def meta_tarefa(t, registros_pendentes: int = 0) -> str:
    partes = [formata_minutos(t.minutos)]
    if t.prazo:
        partes.append(f"até {formata_dia(t.prazo)}")
    if t.data_fixa:
        partes.append("data fixa")
    if t.projeto:
        partes.append(f"#{t.projeto}")
    if t.adiamentos:
        partes.append(f"adiada {t.adiamentos}x")
    if registros_pendentes:
        partes.append(f"{registros_pendentes} passo{'s' if registros_pendentes > 1 else ''} pendente{'s' if registros_pendentes > 1 else ''}")
    return " · ".join(partes)


class CampoCaptura(QWidget):
    """Campo 'Nova tarefa' com a prévia do que o app entendeu."""

    def __init__(self, ctrl, parent=None):
        super().__init__(parent)
        self.ctrl = ctrl
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        self.campo = QLineEdit()
        self.campo.setObjectName("captura")
        self.campo.setPlaceholderText("Nova tarefa… ex.: e-mail para Ana 15min · consolidar riscos g até qui ! · plano @marcos até 28/10")
        self.campo.setAccessibleName("Nova tarefa")
        self.campo.textChanged.connect(self._previa)
        self.campo.returnPressed.connect(self._salvar)
        ao_focar(self.campo, self._fechar_painel)  # quem vai anotar algo novo não precisa do detalhe aberto
        lay.addWidget(self.campo)
        self.previa = rotulo("", "previa")
        self.previa.hide()
        lay.addWidget(self.previa)

    def _fechar_painel(self):
        if self.ctrl.sel_id is not None:
            self.ctrl.fechar_painel()

    def _previa(self, texto: str):
        if texto.strip():
            self.previa.setText("Entendi: " + self.ctrl.sv.prever(texto) + " · Enter para salvar · Esc limpa")
            self.previa.show()
        else:
            self.previa.hide()

    def _salvar(self):
        texto = self.campo.text().strip()
        if texto:
            self.ctrl.capturar(texto)
            self.campo.clear()


class TelaHoje(QWidget):
    def __init__(self, ctrl, parent=None):
        super().__init__(parent)
        self.ctrl = ctrl
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
        self.lay.setSpacing(16)
        self.captura = CampoCaptura(ctrl)
        self.lay.addWidget(self.captura)
        self.dinamico = QVBoxLayout()
        self.dinamico.setSpacing(16)
        self.lay.addLayout(self.dinamico)
        self.lay.addStretch(1)

    def focar_captura(self):
        self.captura.campo.setFocus()
        self.captura.campo.selectAll()

    # ----------------------------------------------------------------
    def atualizar(self):
        sv = self.ctrl.sv
        limpar_layout(self.dinamico)
        dia = sv.hoje_util()
        cal = sv.calendario()
        abertas = sv.banco.tarefas("aberta")
        do_dia = tarefas_do_dia(abertas, dia)
        reservas = sv.reservas()
        usado = sum(t.minutos for t in do_dia) + reservas.get(dia, 0)
        cap = cal.capacidade(dia)
        concluidas = [t for t in sv.banco.tarefas("concluida") if t.concluida_em and t.concluida_em.date() == sv.hoje()]

        # cabeçalho
        cab = QHBoxLayout()
        textos = QVBoxLayout()
        textos.setSpacing(2)
        eh_hoje = dia == sv.hoje()
        textos.addWidget(rotulo("Hoje" if eh_hoje else f"{DIAS_LONGOS[dia.weekday()]} (próximo dia útil)", "titulo"))
        resumo = f"{DIAS_LONGOS[dia.weekday()]}, {dia:%d/%m} · {len(do_dia)} tarefas · {formata_minutos(usado)} planejadas"
        if concluidas:
            resumo += f" · {len(concluidas)} concluídas"
        textos.addWidget(rotulo(resumo, "subtitulo"))
        cab.addLayout(textos, 1)
        capbox = QVBoxLayout()
        capbox.setSpacing(4)
        livre = cap - usado
        capbox.addWidget(rotulo(f"{formata_minutos(usado)} de {formata_minutos(cap)} · " +
                                (f"{formata_minutos(-livre)} acima" if livre < 0 else f"{formata_minutos(livre)} livres"), "meta"))
        barra = BarraCapacidade()
        barra.setFixedWidth(220)
        barra.definir(usado, cap)
        capbox.addWidget(barra)
        cab.addLayout(capbox)
        menos = botao("−", ao_clicar=lambda: self.ctrl.definir_capacidade(dia, cal.capacidade_base(dia) - 30),
                      dica="Menos 30 minutos disponíveis neste dia")
        mais = botao("+", ao_clicar=lambda: self.ctrl.definir_capacidade(dia, cal.capacidade_base(dia) + 30),
                     dica="Mais 30 minutos disponíveis neste dia")
        for b in (menos, mais):
            b.setFixedWidth(34)
            cab.addWidget(b)
        self.dinamico.addLayout(cab)

        # cobranças do dia
        for a in sv.banco.aguardando("aberto"):
            if max(a.cobrar_em, sv.hoje()) <= dia:
                self.dinamico.addWidget(self._linha_cobranca(a))

        # tarefas
        lista = QVBoxLayout()
        lista.setSpacing(6)
        for t in do_dia:
            lista.addWidget(self._linha_tarefa(t))
        if not do_dia:
            vazio = rotulo("Nada pendente para este dia.", "subtitulo")
            vazio.setAlignment(Qt.AlignCenter)
            vazio.setStyleSheet(f"padding: 24px; border: 1px dashed {estilo.BORDA_FORTE}; border-radius: 10px;")
            lista.addWidget(vazio)
        self.dinamico.addLayout(lista)

        # sugestão de adiantar
        cand = proxima_que_cabe(abertas, dia, livre) if livre >= 15 else None
        if cand:
            caixa = QFrame()
            caixa.setObjectName("sugestao")
            h = QHBoxLayout(caixa)
            h.setContentsMargins(14, 10, 14, 10)
            txt = rotulo(f"Sobrou {formata_minutos(livre)} hoje. Adiantar “{cand.titulo}” "
                         f"({formata_minutos(cand.minutos)}, planejada para {sv.nome_dia(cand.dia_planejado)})?", quebra=True)
            txt.setStyleSheet(f"color: {estilo.ACENTO_ESCURO};")
            h.addWidget(txt, 1)
            h.addWidget(botao("Adiantar", "primario", lambda: self.ctrl.executar(sv.adiantar, cand.id)))
            self.dinamico.addWidget(caixa)

        # concluídas hoje
        if concluidas:
            self.dinamico.addWidget(rotulo("CONCLUÍDAS HOJE", "rotulo"))
            for t in concluidas:
                b = botao(t.titulo, "link", lambda _=False, i=t.id: self.ctrl.abrir_tarefa(i))
                b.setStyleSheet(f"color: {estilo.MUTED}; text-decoration: line-through; text-align: left;")
                self.dinamico.addWidget(b)

        # próximo dia
        prox = sv.calendario().proximo_dia_de_trabalho(dia)
        do_prox = tarefas_do_dia(abertas, prox)
        linha = rotulo(f"Depois: {sv.nome_dia(prox)} · {len(do_prox)} tarefas · "
                       f"{formata_minutos(sum(t.minutos for t in do_prox) + reservas.get(prox, 0))} de "
                       f"{formata_minutos(cal.capacidade(prox))}", "subtitulo")
        linha.setStyleSheet(f"border-top: 1px solid {estilo.BORDA}; padding-top: 12px;")
        self.dinamico.addWidget(linha)

    # ----------------------------------------------------------------
    def _linha_tarefa(self, t) -> QFrame:
        sv = self.ctrl.sv
        pend = sum(1 for r in sv.banco.registros(t.id) if r.tipo == "Próximo passo" and not r.feito)
        linha = LinhaClicavel()
        linha.marcar_selecionada(t.id == self.ctrl.sel_id)
        linha.clicada.connect(lambda i=t.id: self.ctrl.abrir_tarefa(i))
        h = QHBoxLayout(linha)
        h.setContentsMargins(12, 10, 12, 10)
        h.setSpacing(12)
        h.addWidget(botao("", "concluir", lambda _=False, i=t.id: self.ctrl.executar(sv.concluir, i), "Concluir tarefa"))
        textos = QVBoxLayout()
        textos.setSpacing(2)
        titulo = rotulo(t.titulo, "tituloTarefa", quebra=True)
        titulo.setAttribute(Qt.WA_TransparentForMouseEvents)
        meta = rotulo(meta_tarefa(t, pend), "meta")
        meta.setAttribute(Qt.WA_TransparentForMouseEvents)
        textos.addWidget(titulo)
        textos.addWidget(meta)
        h.addLayout(textos, 1)
        if t.conflito:
            h.addWidget(selo(CONFLITOS.get(t.conflito, "conflito"), estilo.VERMELHO, estilo.VERMELHO_CLARO))
        if t.importancia:
            h.addWidget(selo("muito importante" if t.importancia == 2 else "importante", estilo.LARANJA_TEXTO, estilo.LARANJA_CLARO))
        h.addWidget(botao("Adiar", ao_clicar=lambda _=False, i=t.id: self.ctrl.adiar(i)))
        return linha

    def _linha_cobranca(self, a) -> QFrame:
        sv = self.ctrl.sv
        caixa = QFrame()
        caixa.setObjectName("linhaCobranca")
        h = QHBoxLayout(caixa)
        h.setContentsMargins(12, 10, 12, 10)
        h.setSpacing(12)
        h.addWidget(selo("COBRAR HOJE", "white", estilo.COBRAR))
        textos = QVBoxLayout()
        textos.setSpacing(1)
        textos.addWidget(rotulo(f"{a.pessoa}: {a.o_que}", "tituloTarefa", quebra=True))
        n = len(a.cobrancas)
        info = f"Já cobrado {n} {'vez' if n == 1 else 'vezes'} (última: {a.cobrancas[-1]:%d/%m})" if n else "Primeira cobrança"
        if (adi := a.contar("Adiado")):
            info += f" · adiado {adi}x"
        m = rotulo(info, "meta")
        m.setStyleSheet(f"color: {estilo.AGUARDA_TEXTO};")
        textos.addWidget(m)
        h.addLayout(textos, 1)
        cinco = rotulo("5min", "meta")
        cinco.setStyleSheet(f"color: {estilo.AGUARDA_TEXTO}; font-weight: 600;")
        h.addWidget(cinco)
        h.addWidget(botao("Cobrei", ao_clicar=lambda _=False, i=a.id: self.ctrl.executar(sv.cobrei, i)))
        h.addWidget(botao("Adiar", ao_clicar=lambda _=False, i=a.id: self.ctrl.executar(sv.adiar_espera, i),
                          dica="Passa a cobrança para o próximo dia útil"))
        h.addWidget(botao("Recebi", "primario", lambda _=False, i=a.id: self.ctrl.recebi(i)))
        return caixa
