"""Diálogos: decisão do 3º adiamento, item recebido e edição de um item de Aguardando."""
from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (QDateEdit, QDialog, QGridLayout, QHBoxLayout, QLineEdit, QPushButton,
                               QVBoxLayout)

from . import estilo
from .widgets import botao, campo_data, rotulo


class DialogoDecisao(QDialog):
    """Na 3ª tentativa de adiar: fazer hoje, quebrar, delegar ou cancelar (ou adiar mesmo assim)."""
    OPCOES = [
        ("fazer_hoje", "Fazer hoje", "Fixa em hoje"),
        ("quebrar", "Quebrar em 2", "Duas partes menores"),
        ("delegar", "Delegar", "Vai para Aguardando"),
        ("cancelar", "Cancelar", "Fica no histórico"),
    ]

    def __init__(self, titulo_tarefa: str, adiamentos: int, parent=None):
        super().__init__(parent)
        self.escolha: str | None = None
        self.setWindowTitle("Decidir tarefa adiada")
        self.setMinimumWidth(480)
        v = QVBoxLayout(self)
        v.setContentsMargins(24, 22, 24, 22)
        v.setSpacing(14)
        r = rotulo("3º ADIAMENTO", "rotulo")
        r.setStyleSheet(f"color: {estilo.LARANJA_TEXTO};")
        v.addWidget(r)
        t = rotulo(titulo_tarefa, quebra=True)
        t.setStyleSheet("font-size: 17px; font-weight: 700;")
        v.addWidget(t)
        v.addWidget(rotulo(f"Esta tarefa já foi adiada {adiamentos} vezes. Em vez de empurrar de novo, decida:", quebra=True))
        grade = QGridLayout()
        grade.setSpacing(8)
        for i, (chave, nome, desc) in enumerate(self.OPCOES):
            b = QPushButton(f"{nome}\n{desc}")
            b.setMinimumHeight(56)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet("text-align: left; padding: 8px 12px;" + (f" color: {estilo.VERMELHO};" if chave == "cancelar" else ""))
            b.clicked.connect(lambda _=False, c=chave: self._escolher(c))
            grade.addWidget(b, i // 2, i % 2)
        v.addLayout(grade)
        baixo = QHBoxLayout()
        baixo.addWidget(botao("Adiar mesmo assim", "link", lambda: self._escolher("adiar_mesmo")))
        baixo.addStretch(1)
        baixo.addWidget(botao("Voltar", ao_clicar=self.reject))
        v.addLayout(baixo)

    def _escolher(self, chave: str):
        self.escolha = chave
        self.accept()


class DialogoRecebi(QDialog):
    """Ao marcar 'Recebi': pergunta se isso gera algo para você fazer."""

    def __init__(self, ctrl, pessoa: str, o_que: str, parent=None):
        super().__init__(parent)
        self.ctrl = ctrl
        self.texto_tarefa: str | None = None
        self.setWindowTitle("Item recebido")
        self.setMinimumWidth(520)
        v = QVBoxLayout(self)
        v.setContentsMargins(24, 22, 24, 22)
        v.setSpacing(12)
        r = rotulo(f"RECEBIDO DE {pessoa.upper()}", "rotulo")
        r.setStyleSheet(f"color: {estilo.VERDE};")
        v.addWidget(r)
        t = rotulo(o_que, quebra=True)
        t.setStyleSheet("font-size: 17px; font-weight: 700;")
        v.addWidget(t)
        v.addWidget(rotulo("Isso gera algo para você fazer?"))
        self.campo = QLineEdit()
        self.campo.setPlaceholderText("ex.: revisar o plano de migração m até qui")
        self.campo.setAccessibleName("Tarefa gerada pelo item recebido")
        self.campo.textChanged.connect(self._previa)
        self.campo.returnPressed.connect(self._criar)
        v.addWidget(self.campo)
        self.previa = rotulo("", "previa")
        self.previa.hide()
        v.addWidget(self.previa)
        v.addWidget(rotulo("O item fica registrado em Concluídas, com as datas em que você cobrou.", "meta", quebra=True))
        baixo = QHBoxLayout()
        baixo.addStretch(1)
        baixo.addWidget(botao("Não gera nada", ao_clicar=self.accept))
        baixo.addWidget(botao("Criar tarefa", "primario", self._criar))
        v.addLayout(baixo)

    def _previa(self, texto: str):
        if texto.strip():
            self.previa.setText("Entendi: " + self.ctrl.sv.prever(texto))
            self.previa.show()
        else:
            self.previa.hide()

    def _criar(self):
        self.texto_tarefa = self.campo.text().strip() or None
        self.accept()


class DialogoEspera(QDialog):
    """Editar um item de Aguardando (quem, o quê, quando cobrar) ou excluí-lo."""

    def __init__(self, pessoa: str, o_que: str, cobrar_em: date, parent=None, eventos: list[dict] | None = None):
        super().__init__(parent)
        self.acao: str | None = None  # "salvar" | "excluir"
        self.setWindowTitle("Item aguardado")
        self.setMinimumWidth(460)
        v = QVBoxLayout(self)
        v.setContentsMargins(24, 22, 24, 22)
        v.setSpacing(8)
        v.addWidget(rotulo("DE QUEM VOCÊ ESPERA", "rotulo"))
        self.pessoa = QLineEdit(pessoa)
        self.pessoa.setAccessibleName("Pessoa")
        v.addWidget(self.pessoa)
        v.addSpacing(4)
        v.addWidget(rotulo("O QUÊ", "rotulo"))
        self.o_que = QLineEdit(o_que)
        self.o_que.setAccessibleName("O que você espera")
        v.addWidget(self.o_que)
        v.addSpacing(4)
        v.addWidget(rotulo("COBRAR EM", "rotulo"))
        self.data = campo_data(cobrar_em, "Data da cobrança")
        v.addWidget(self.data, 0, Qt.AlignLeft)
        if eventos:
            v.addSpacing(8)
            cob = sum(1 for e in eventos if e.get("tipo") == "Cobrado")
            adi = sum(1 for e in eventos if e.get("tipo") == "Adiado")
            v.addWidget(rotulo(f"HISTÓRICO · cobrado {cob}x · adiado {adi}x", "rotulo"))
            for e in reversed(eventos[-12:]):
                quando = e.get("quando", "")
                data = f"{quando[8:10]}/{quando[5:7]} {quando[11:16]}".strip()
                linha = rotulo(f"{data} · {e.get('tipo', '')}" + (f" · {e['texto']}" if e.get("texto") else ""), "meta", quebra=True)
                if e.get("tipo") in ("Adiado", "Cobrado"):
                    linha.setStyleSheet(f"color: {estilo.AGUARDA_TEXTO};")
                v.addWidget(linha)
            if len(eventos) > 12:
                v.addWidget(rotulo(f"… e mais {len(eventos) - 12} registros antigos", "meta"))
        self.erro = rotulo("Preencha quem e o quê.", "meta")
        self.erro.setStyleSheet(f"color: {estilo.VERMELHO};")
        self.erro.hide()
        v.addWidget(self.erro)
        v.addSpacing(10)
        baixo = QHBoxLayout()
        excluir = botao("Excluir", "link", self._excluir, "Apagar este item (Ctrl+Z desfaz)")
        excluir.setStyleSheet(f"color: {estilo.VERMELHO};")
        baixo.addWidget(excluir)
        baixo.addStretch(1)
        baixo.addWidget(botao("Cancelar", ao_clicar=self.reject))
        salvar = botao("Salvar", "primario", self._salvar)
        salvar.setDefault(True)
        baixo.addWidget(salvar)
        v.addLayout(baixo)
        self.pessoa.returnPressed.connect(self._salvar)
        self.o_que.returnPressed.connect(self._salvar)

    @property
    def cobrar_em(self) -> date:
        return self.data.date().toPython()

    def _salvar(self):
        if not self.pessoa.text().strip() or not self.o_que.text().strip():
            self.erro.show()
            return
        self.acao = "salvar"
        self.accept()

    def _excluir(self):
        self.acao = "excluir"
        self.accept()
