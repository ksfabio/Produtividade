"""Painel da tarefa: tamanho, prazo, conflitos, ações e diário."""
from __future__ import annotations

from datetime import timedelta

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (QCheckBox, QDateEdit, QFrame, QGridLayout, QHBoxLayout, QLineEdit,
                               QPlainTextEdit, QScrollArea, QVBoxLayout, QWidget)

from nucleo.captura import formata_dia, formata_minutos, le_duracao
from nucleo.modelos import TIPOS_QUE_O_USUARIO_ESCREVE

from . import estilo
from .widgets import TextoClicavel, botao, campo_data, fluxo, limpar_layout, rotulo, selo, texto_longo

TAMANHOS = [("P · 30min", 30), ("M · 2h", 120), ("G · 4h", 240)]
DICAS_REGISTRO = {
    "Feito": "O que você fez?",
    "Próximo passo": "O que falta fazer? Vira item da lista Falta fazer.",
    "Ocorrência": "O que aconteceu?",
    "Bloqueio": "O que está impedindo? De quem você depende?",
    "Decisão": "O que foi decidido, por quem?",
}
CORES_TIPO = {
    "Feito": (estilo.VERDE_TEXTO, estilo.VERDE_CLARO), "Concluída": (estilo.VERDE_TEXTO, estilo.VERDE_CLARO),
    "Próximo passo": (estilo.ACENTO_ESCURO, estilo.ACENTO_CLARO),
    "Bloqueio": (estilo.LARANJA_TEXTO, estilo.LARANJA_CLARO), "Ocorrência": (estilo.LARANJA_TEXTO, estilo.LARANJA_CLARO),
}
TEXTO_CONFLITO = {
    "nao_cabe": "Não cabe até o prazo com as horas atuais.",
    "prazo_vencido": "Vai ficar para depois do prazo combinado.",
    "maior_que_dia": "Maior que as horas de qualquer dia. Que tal quebrar em partes?",
}


class PainelTarefa(QFrame):
    LARGURA = 580  # cabe a fileira de tipos do diário numa linha só

    def __init__(self, ctrl, parent=None):
        super().__init__(parent)
        self.ctrl = ctrl
        self.tarefa_id: int | None = None
        self.tipo_registro = "Feito"
        self.editando_titulo = False
        self.setObjectName("painel")
        self.setFixedWidth(self.LARGURA)
        externo = QVBoxLayout(self)
        externo.setContentsMargins(0, 0, 0, 0)
        rolagem = QScrollArea()
        rolagem.setWidgetResizable(True)
        rolagem.setFrameShape(QFrame.NoFrame)
        rolagem.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)  # tudo cabe na largura do painel
        externo.addWidget(rolagem)
        self.rolagem = rolagem
        corpo = QWidget()
        corpo.setObjectName("fundo")
        rolagem.setWidget(corpo)
        self.corpo = corpo
        self.lay = QVBoxLayout(corpo)
        self.lay.setContentsMargins(20, 18, 20, 28)
        self.lay.setSpacing(14)

    # ----------------------------------------------------------------
    def mostrar(self, tarefa_id: int):
        mudou = tarefa_id != self.tarefa_id
        self.tarefa_id = tarefa_id
        if mudou:
            self.tipo_registro = "Feito"
            self.editando_titulo = False
        self.atualizar()
        self.show()

    def atualizar(self):
        if self.tarefa_id is None:
            return
        sv = self.ctrl.sv
        t = sv.banco.tarefa(self.tarefa_id)
        limpar_layout(self.lay)
        if t is None:
            self.ctrl.fechar_painel()
            return

        # cabeçalho
        cab = QHBoxLayout()
        textos = QVBoxLayout()
        textos.setSpacing(4)
        if t.status == "aberta":
            status = f"Planejada para {sv.nome_dia(t.dia_planejado)}" if t.dia_planejado else "Sem data por enquanto"
        else:
            status = {"concluida": "Concluída", "cancelada": "Cancelada", "delegada": "Delegada"}.get(t.status, t.status)
            if t.concluida_em:
                status += f" · {formata_dia(t.concluida_em.date())}"
        textos.addWidget(rotulo(status.upper(), "rotulo"))
        if self.editando_titulo:
            self._editor_titulo(t, textos)
        else:
            titulo = TextoClicavel(t.titulo)
            titulo.setStyleSheet("QLabel { font-size: 18px; font-weight: 700; border-radius: 4px; padding: 2px 4px; margin-left: -4px; }"
                                 f"QLabel:hover {{ background: {estilo.FUNDO_CINZA}; }}")
            titulo.setToolTip("Clique para editar o texto (F2)")
            titulo.clicado.connect(self.editar_titulo)
            textos.addWidget(titulo)
        cab.addLayout(textos, 1)
        fechar = botao("×", ao_clicar=self.ctrl.fechar_painel, dica="Fechar painel da tarefa")
        fechar.setFixedWidth(34)
        cab.addWidget(fechar, 0, Qt.AlignTop)
        self.lay.addLayout(cab)

        aberta = t.status == "aberta"
        if aberta:
            grade = QGridLayout()
            grade.setHorizontalSpacing(14)
            grade.setVerticalSpacing(10)
            grade.setColumnStretch(1, 1)
            self._tamanho(t, grade)
            self._prazo(t, grade)
            self.lay.addLayout(grade)
        infos = [self._info("Adiamentos", str(t.adiamentos)), self._info("Projeto", f"#{t.projeto}" if t.projeto else "—")]
        if not aberta:
            infos.append(self._info("Tamanho", formata_minutos(t.minutos)))
        self.lay.addWidget(fluxo(*infos, espaco=28))
        if t.reuniao_id and (reuniao := sv.banco.reuniao(t.reuniao_id)):
            origem = botao(f"Da reunião: {reuniao.titulo} ({reuniao.quando:%d/%m})", "link",
                           lambda _=False, i=reuniao.id: self.ctrl.abrir_reuniao(i), "Abrir a reunião")
            origem.setStyleSheet("text-align: left;")
            self.lay.addWidget(origem, 0, Qt.AlignLeft)

        if aberta and t.conflito:
            self._conflito(t)

        acoes = []
        if aberta:
            acoes.append(botao("Feito", "primario", lambda: self.ctrl.executar(sv.concluir, t.id), "Concluir (Ctrl+Enter)"))
            acoes.append(botao("Adiar", ao_clicar=lambda: self.ctrl.adiar(t.id), dica="Adiar (Ctrl+D)"))
        elif t.status == "concluida":
            acoes.append(botao("Reabrir tarefa", ao_clicar=lambda: self.ctrl.executar(sv.reabrir, t.id)))
        if acoes:
            self.lay.addWidget(fluxo(*acoes, espaco=8))

        self._diario(t)

        fim = QFrame()
        fim.setFrameShape(QFrame.HLine)
        fim.setStyleSheet(f"color: {estilo.BORDA};")
        self.lay.addWidget(fim)
        excluir = botao("Excluir tarefa", "link", lambda: self.ctrl.excluir(t.id),
                        "Apagar de vez (para tarefas criadas por engano ou de teste)")
        excluir.setStyleSheet(f"color: {estilo.VERMELHO};")
        self.lay.addWidget(excluir, 0, Qt.AlignLeft)
        self.lay.addStretch(1)

    # ---------------- texto da tarefa ----------------
    def editar_titulo(self):
        if self.tarefa_id is None:
            return
        self.editando_titulo = True
        self.atualizar()

    def cancelar_edicao(self) -> bool:
        """Esc durante a edição: volta ao texto original. Devolve True se havia edição aberta."""
        if not self.editando_titulo:
            return False
        self.editando_titulo = False
        self.atualizar()
        return True

    def _editor_titulo(self, t, lay):
        campo = QLineEdit(t.titulo)
        campo.setAccessibleName("Texto da tarefa")
        campo.setStyleSheet("font-size: 15px; font-weight: 600;")
        campo.selectAll()
        aviso = texto_longo("O texto não pode ficar vazio.", "meta")
        aviso.setStyleSheet(f"color: {estilo.VERMELHO};")
        aviso.hide()

        def salvar():
            if not campo.text().strip():
                aviso.show()
                campo.setFocus()
                return
            self.editando_titulo = False
            self.ctrl.executar(self.ctrl.sv.renomear, t.id, campo.text())

        campo.returnPressed.connect(salvar)
        lay.addWidget(campo)
        lay.addWidget(aviso)
        lay.addWidget(fluxo(botao("Salvar", "primario", salvar, "Salvar (Enter)"),
                            botao("Cancelar", ao_clicar=self.cancelar_edicao, dica="Cancelar (Esc)")))
        self._campo_titulo = campo
        campo.setFocus()

    # ----------------------------------------------------------------
    def _info(self, nome: str, valor: str) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(2)
        v.addWidget(rotulo(nome, "meta"))
        lb = rotulo(valor)
        lb.setStyleSheet("font-size: 14px; font-weight: 600;")
        v.addWidget(lb)
        return w

    @staticmethod
    def _linha_grade(grade, texto: str, widget, linha: int):
        """Uma linha 'rótulo | controles' da grade, com todos os rótulos alinhados à esquerda."""
        lb = rotulo(texto, "meta")
        grade.addWidget(lb, linha, 0, Qt.AlignLeft | Qt.AlignVCenter)
        grade.addWidget(widget, linha, 1)

    def _tamanho(self, t, grade):
        sv = self.ctrl.sv
        chips = []
        for nome, minutos in TAMANHOS:
            b = botao(nome, "chip", lambda _=False, m=minutos: self.ctrl.executar(sv.alterar, t.id, minutos=m))
            b.setCheckable(True)
            b.setChecked(t.minutos == minutos)
            chips.append(b)
        self._linha_grade(grade, "Tamanho", fluxo(*chips), 0)
        personalizado = t.minutos not in (30, 120, 240)
        campo = QLineEdit()
        campo.setPlaceholderText(formata_minutos(t.minutos) if personalizado else "ex.: 45min")
        campo.setAccessibleName("Tempo personalizado")
        campo.setFixedWidth(120)
        if personalizado:
            campo.setStyleSheet(f"QLineEdit {{ border: 1px solid {estilo.ACENTO}; background: {estilo.ACENTO_CLARO}; }}")
        erro = texto_longo("Use de 1min a 10h, ex.: 2min, 45min, 1h, 1h30.", "meta")
        erro.setStyleSheet(f"color: {estilo.VERMELHO};")
        erro.hide()

        def aplicar():
            m = le_duracao(campo.text(), aceitar_numero=True)
            if not m or m < 1 or m > 600:
                erro.show()
                return
            self.ctrl.executar(sv.alterar, t.id, minutos=m)

        campo.returnPressed.connect(aplicar)
        self._linha_grade(grade, "Tempo Livre", fluxo(campo, botao("Aplicar", ao_clicar=aplicar)), 1)
        grade.addWidget(erro, 2, 1)

    def _prazo(self, t, grade):
        sv = self.ctrl.sv
        sem = QCheckBox("Sem prazo")
        sem.setChecked(t.prazo is None)
        data = campo_data(t.prazo or sv.hoje_util())
        data.setEnabled(t.prazo is not None)

        def mudou_data(qd: QDate):
            if not sem.isChecked():
                self.ctrl.executar(sv.alterar, t.id, prazo=qd.toPython())

        def mudou_sem(marcado: bool):
            data.setEnabled(not marcado)
            self.ctrl.executar(sv.alterar, t.id, prazo=None if marcado else data.date().toPython())

        data.dateChanged.connect(mudou_data)
        sem.toggled.connect(mudou_sem)
        self._linha_grade(grade, "Prazo combinado", fluxo(data, sem, espaco=10), 3)

    def _conflito(self, t):
        sv = self.ctrl.sv
        caixa = QFrame()
        caixa.setObjectName("conflito")
        v = QVBoxLayout(caixa)
        v.setContentsMargins(14, 12, 14, 12)
        v.setSpacing(8)
        txt = texto_longo(TEXTO_CONFLITO.get(t.conflito, "Conflito com o prazo."))
        txt.setStyleSheet(f"color: {estilo.VERMELHO_TEXTO}; font-weight: 700; font-size: 14px;")
        v.addWidget(txt)
        metade = max(15, round(t.minutos / 2 / 15) * 15)
        novo_prazo = sv.calendario().dias_de_trabalho((t.prazo or sv.hoje()) + timedelta(days=1), 2)[-1]
        botoes = [
            botao("Reduzir pela metade", ao_clicar=lambda: self.ctrl.executar(sv.alterar, t.id, minutos=metade)),
            botao("Prazo +2 dias úteis", ao_clicar=lambda: self.ctrl.executar(sv.alterar, t.id, prazo=novo_prazo)),
            botao("Delegar", ao_clicar=lambda: self.ctrl.executar(sv.decidir, t.id, "delegar")),
        ]
        alvo = t.prazo if t.prazo and t.prazo >= sv.hoje() else sv.hoje_util()
        botoes.append(botao("Forçar no prazo", ao_clicar=lambda: self.ctrl.executar(sv.alterar, t.id, data_fixa=alvo)))
        if t.conflito == "maior_que_dia":
            botoes.append(botao("Quebrar em 2", ao_clicar=lambda: self.ctrl.executar(sv.decidir, t.id, "quebrar")))
        v.addWidget(fluxo(*botoes))
        self.lay.addWidget(caixa)

    # ----------------------------------------------------------------
    def _diario(self, t):
        sv = self.ctrl.sv
        regs = sv.banco.registros(t.id)
        passos = [r for r in regs if r.tipo == "Próximo passo"]
        abertos = [r for r in passos if not r.feito]
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color: {estilo.BORDA};")
        self.lay.addWidget(sep)
        cab = QHBoxLayout()
        cab.addWidget(rotulo("Diário", "secao"))
        cab.addStretch(1)
        cab.addWidget(rotulo(f"{len(passos) - len(abertos)} de {len(passos)} passos" if passos else f"{len(regs)} registros", "meta"))
        self.lay.addLayout(cab)

        if abertos:
            caixa = QFrame()
            caixa.setObjectName("faltaFazer")
            v = QVBoxLayout(caixa)
            v.setContentsMargins(12, 10, 12, 10)
            v.setSpacing(6)
            tit = rotulo("Falta fazer")
            tit.setStyleSheet(f"color: {estilo.ACENTO_ESCURO}; font-weight: 700; font-size: 12px;")
            v.addWidget(tit)
            for r in abertos:
                item = QHBoxLayout()
                item.setSpacing(6)
                cb = QCheckBox()
                cb.setAccessibleName(r.texto)
                cb.toggled.connect(lambda marcado, r=r: self._marcar(r, marcado))
                item.addWidget(cb, 0, Qt.AlignTop)
                item.addWidget(texto_longo(r.texto), 1)
                v.addLayout(item)
            self.lay.addWidget(caixa)

        self._chips_tipo = {}
        for tipo in TIPOS_QUE_O_USUARIO_ESCREVE:
            b = botao(tipo, "chip", lambda _=False, tp=tipo: self._escolher_tipo(tp))
            b.setCheckable(True)
            b.setChecked(tipo == self.tipo_registro)
            self._chips_tipo[tipo] = b
        self.lay.addWidget(fluxo(*self._chips_tipo.values(), espaco=6))
        self.texto = QPlainTextEdit()
        self.texto.setPlaceholderText(DICAS_REGISTRO[self.tipo_registro])
        self.texto.setAccessibleName("O que aconteceu?")
        self.texto.setFixedHeight(64)
        self.lay.addWidget(self.texto)
        reg = botao("Registrar", "primario", self._registrar)
        self.lay.addWidget(reg, 0, Qt.AlignLeft)

        for r in reversed(regs):
            self.lay.addWidget(self._registro(r))

    def _registro(self, r) -> QWidget:
        w = QFrame()
        w.setObjectName("registro")
        w.setStyleSheet("QFrame#registro { border: none; border-bottom: 1px solid #EEF0F3; }")
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 8, 0, 8)
        v.setSpacing(3)
        quando = rotulo(r.quando.strftime("%d/%m %H:%M"), "meta")
        quando.setStyleSheet("font-size: 11px;")
        cor_t, cor_f = CORES_TIPO.get(r.tipo, (estilo.TINTA_2, "#EEF0F3"))
        topo = [quando, selo(r.tipo, cor_t, cor_f)]
        if r.tipo == "Próximo passo":
            topo.append(botao("Reabrir" if r.feito else "Marcar feito", "link", lambda _=False, r=r: self._marcar(r, not r.feito)))
        v.addWidget(fluxo(*topo, espaco=8))
        texto = texto_longo(r.texto)
        if r.tipo == "Próximo passo" and r.feito:
            texto.setStyleSheet("color: #57606A; text-decoration: line-through;")
        v.addWidget(texto)
        return w

    def _escolher_tipo(self, tipo: str):
        self.tipo_registro = tipo
        for tp, b in getattr(self, "_chips_tipo", {}).items():
            b.setChecked(tp == tipo)
        if hasattr(self, "texto"):
            self.texto.setPlaceholderText(DICAS_REGISTRO[tipo])
            self.texto.setFocus()

    def _registrar(self):
        txt = self.texto.toPlainText().strip()
        if not txt or self.tarefa_id is None:
            self.texto.setFocus()
            return
        self.ctrl.sv.anotar(self.tarefa_id, self.tipo_registro, txt)
        self.ctrl.recarregar()

    def _marcar(self, registro, feito: bool):
        self.ctrl.sv.marcar_passo(registro, feito)
        self.ctrl.recarregar()
