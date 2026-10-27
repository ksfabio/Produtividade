"""Aba Aguardando: o que você espera de outras pessoas, com Cobrei, Recebi e edição."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QVBoxLayout, QWidget

from . import estilo
from .widgets import (LinhaClicavel, ao_focar, area_rolavel, botao, cabecalho, limpar_layout, rotulo, selo,
                      texto_longo, vazio)


def meta_espera(sv, a) -> str:
    partes = [a.pessoa, f"cobrar {sv.nome_dia(a.cobrar_em)}"]
    n = len(a.cobrancas)
    if n:
        partes.append(f"cobrado {n}x (última {a.cobrancas[-1]:%d/%m})")
    if (adi := a.contar("Adiado")):
        partes.append(f"adiado {adi}x")
    if a.reuniao_id and (r := sv.banco.reuniao(a.reuniao_id)):
        partes.append(f"da reunião {r.titulo}")
    if a.tarefa_origem_id and (t := sv.banco.tarefa(a.tarefa_origem_id)):
        partes.append(f"delegada de “{t.titulo}”")
    return " · ".join(partes)


class TelaAguardando(QWidget):
    def __init__(self, ctrl, parent=None):
        super().__init__(parent)
        self.ctrl = ctrl
        self.lay = area_rolavel(self)
        self.lay.addLayout(cabecalho(
            "Aguardando",
            "O que você espera de outras pessoas. No dia de cobrar, o item aparece em lilás em Hoje e reserva 5 min."))

        self.campo = QLineEdit()
        self.campo.setObjectName("captura")
        self.campo.setPlaceholderText("Nova espera… ex.: plano de migração @marcos até 28/10")
        self.campo.setAccessibleName("Nova espera")
        self.campo.textChanged.connect(self._previa)
        self.campo.returnPressed.connect(self._salvar)
        ao_focar(self.campo, lambda: self.ctrl.sel_id is not None and self.ctrl.fechar_painel())
        self.lay.addWidget(self.campo)
        self.previa = rotulo("", "previa")
        self.previa.hide()
        self.lay.addWidget(self.previa)

        self.dinamico = QVBoxLayout()
        self.dinamico.setSpacing(8)
        self.lay.addLayout(self.dinamico)
        self.lay.addStretch(1)

    # ----------------------------------------------------------------
    def _previa(self, texto: str):
        if not texto.strip():
            self.previa.hide()
            return
        if "@" not in texto:
            self.previa.setText("Inclua @pessoa: de quem você está esperando? · até dd/mm define quando cobrar")
        else:
            self.previa.setText("Entendi: " + self.ctrl.sv.prever(texto) + " · Enter para salvar · Esc limpa")
        self.previa.show()

    def _salvar(self):
        texto = self.campo.text().strip()
        if not texto:
            return
        r = self.ctrl.executar(self.ctrl.sv.capturar_espera, texto)
        if r.pode_desfazer:  # salvou
            self.campo.clear()

    def focar_captura(self):
        self.campo.setFocus()

    # ----------------------------------------------------------------
    def atualizar(self):
        sv = self.ctrl.sv
        limpar_layout(self.dinamico)
        abertos = sv.banco.aguardando("aberto")
        hoje = sv.hoje()
        cobrar = [a for a in abertos if a.cobrar_em <= hoje]
        depois = [a for a in abertos if a.cobrar_em > hoje]
        if not abertos:
            self.dinamico.addWidget(vazio("Ninguém te devendo nada. Use @pessoa no campo acima ou em qualquer captura."))
        if cobrar:
            self.dinamico.addWidget(rotulo(f"COBRAR HOJE · {len(cobrar)}", "rotulo"))
            for a in cobrar:
                self.dinamico.addWidget(self._linha(a, atrasado=True))
        if depois:
            if cobrar:
                self.dinamico.addSpacing(8)
            self.dinamico.addWidget(rotulo(f"PRÓXIMAS COBRANÇAS · {len(depois)}", "rotulo"))
            for a in depois:
                self.dinamico.addWidget(self._linha(a, atrasado=False))
        n_rec = len(sv.banco.aguardando("recebido"))
        if n_rec:
            self.dinamico.addSpacing(8)
            ver = botao(f"Ver {n_rec} {'item recebido' if n_rec == 1 else 'itens recebidos'} em Concluídas", "link",
                        lambda: self.ctrl.ir_para("concluidas"))
            self.dinamico.addWidget(ver, 0, Qt.AlignLeft)

    def _linha(self, a, atrasado: bool) -> LinhaClicavel:
        sv = self.ctrl.sv
        linha = LinhaClicavel("linhaCobranca" if atrasado else "linhaTarefa")
        linha.setToolTip("Clique para ver o histórico, editar ou excluir")
        linha.clicada.connect(lambda i=a.id: self.ctrl.editar_espera(i))
        h = QHBoxLayout(linha)
        h.setContentsMargins(12, 10, 12, 10)
        h.setSpacing(12)
        if atrasado:
            atraso = (sv.hoje() - a.cobrar_em).days
            h.addWidget(selo("COBRAR HOJE" if atraso <= 0 else f"ATRASADO {atraso}d", "white", estilo.COBRAR), 0, Qt.AlignTop)
        textos = QVBoxLayout()
        textos.setSpacing(2)
        titulo = texto_longo(a.o_que, "tituloTarefa")
        meta = texto_longo(meta_espera(sv, a), "meta")
        if atrasado:
            meta.setStyleSheet(f"color: {estilo.AGUARDA_TEXTO};")
        for w in (titulo, meta):
            w.setAttribute(Qt.WA_TransparentForMouseEvents)
            textos.addWidget(w)
        h.addLayout(textos, 1)
        h.addWidget(botao("Cobrei", ao_clicar=lambda _=False, i=a.id: self.ctrl.executar(sv.cobrei, i),
                          dica="Registra a cobrança e marca a próxima para 2 dias úteis depois"))
        h.addWidget(botao("Adiar", ao_clicar=lambda _=False, i=a.id: self.ctrl.executar(sv.adiar_espera, i),
                          dica="Passa a cobrança para o próximo dia útil (fica no histórico)"))
        h.addWidget(botao("Recebi", "primario", lambda _=False, i=a.id: self.ctrl.recebi(i)))
        return linha
