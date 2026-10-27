"""Aba Reuniões: colar o recap do Teams Copilot, revisar os itens e criar tarefas; histórico com busca."""
from __future__ import annotations

from datetime import timedelta

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (QDateEdit, QFrame, QHBoxLayout, QLineEdit, QPlainTextEdit,
                               QStackedWidget, QVBoxLayout, QWidget)

from nucleo.captura import formata_dia, formata_minutos
from nucleo.recap import AGUARDANDO, DECISAO, PROMPT_COPILOT, RISCO, TAREFA

from . import estilo
from .widgets import (LinhaClicavel, area_rolavel, botao, cabecalho, campo_data, fluxo, limpar_layout, rotulo, selo,
                      texto_longo, vazio)  # noqa: F401

CORES_SUGESTAO = {
    TAREFA: ("TAREFA SUA", estilo.ACENTO_ESCURO, estilo.ACENTO_CLARO),
    AGUARDANDO: ("AGUARDANDO", estilo.AGUARDA_TEXTO, estilo.AGUARDA_CLARO),
    DECISAO: ("DECISÃO", estilo.TINTA_2, "#E7EAEE"),  # neutro: não confundir com o lilás de Aguardando
    RISCO: ("RISCO", estilo.VERMELHO_TEXTO, estilo.VERMELHO_CLARO),
}
STATUS = {"aberta": "aberta", "concluida": "concluída", "cancelada": "cancelada", "delegada": "delegada"}


class TelaReunioes(QWidget):
    LISTA, NOVA, REVISAR, DETALHE = range(4)

    def __init__(self, ctrl, parent=None):
        super().__init__(parent)
        self.ctrl = ctrl
        self.sugestoes = []
        self.reuniao_id: int | None = None
        externo = QVBoxLayout(self)
        externo.setContentsMargins(0, 0, 0, 0)
        self.paginas = QStackedWidget()
        externo.addWidget(self.paginas)
        for montar in (self._montar_lista, self._montar_nova, self._montar_revisar, self._montar_detalhe):
            pagina = QWidget()
            montar(area_rolavel(pagina))
            self.paginas.addWidget(pagina)

    @property
    def modo(self) -> int:
        return self.paginas.currentIndex()

    def ir(self, modo: int):
        self.paginas.setCurrentIndex(modo)
        self.atualizar()

    def atualizar(self):
        if self.modo == self.LISTA:
            self._preencher_lista()
        elif self.modo == self.DETALHE:
            self._preencher_detalhe()
        # NOVA e REVISAR guardam o que você digitou: não são redesenhadas por fora

    # ================================================================ lista
    def _montar_lista(self, lay):
        self.busca = QLineEdit()
        self.busca.setPlaceholderText("Buscar no título, nas decisões ou no recap")
        self.busca.setAccessibleName("Buscar reuniões")
        self.busca.setClearButtonEnabled(True)
        self.busca.textChanged.connect(lambda _: self._preencher_lista())
        nova = botao("Nova reunião", "primario", self.nova_reuniao, "Colar o recap do Teams Copilot")
        lay.addLayout(cabecalho("Reuniões", "Cole o recap do Teams Copilot e transforme em tarefas.", nova))
        lay.addWidget(self.busca)
        self.lista = QVBoxLayout()
        self.lista.setSpacing(8)
        lay.addLayout(self.lista)
        lay.addStretch(1)

    def _preencher_lista(self):
        limpar_layout(self.lista)
        filtro = self.busca.text().strip()
        resumos = self.ctrl.sv.reunioes(filtro)
        if not resumos:
            self.lista.addWidget(vazio("Nenhuma reunião encontrada." if filtro else
                                       "Nenhuma reunião ainda. Clique em Nova reunião e cole o recap do Teams Copilot."))
            return
        for rr in resumos:
            linha = LinhaClicavel()
            linha.clicada.connect(lambda i=rr.reuniao.id: self.mostrar_detalhe(i))
            h = QHBoxLayout(linha)
            h.setContentsMargins(14, 10, 14, 10)
            h.setSpacing(16)
            quando = rotulo(formata_dia(rr.reuniao.quando.date()), "meta")
            quando.setFixedWidth(80)
            textos = QVBoxLayout()
            textos.setSpacing(2)
            for w in (texto_longo(rr.reuniao.titulo, "tituloTarefa"), texto_longo(rr.legenda, "meta")):
                w.setAttribute(Qt.WA_TransparentForMouseEvents)
                textos.addWidget(w)
            quando.setAttribute(Qt.WA_TransparentForMouseEvents)
            h.addWidget(quando, 0, Qt.AlignTop)
            h.addLayout(textos, 1)
            self.lista.addWidget(linha)

    # ================================================================ nova
    def _montar_nova(self, lay):
        voltar = botao("← Reuniões", "link", lambda: self.ir(self.LISTA))
        lay.addWidget(voltar, 0, Qt.AlignLeft)
        lay.addLayout(cabecalho("Nova reunião", "Cole o recap; o app sugere tarefas suas, o que esperar dos outros e as decisões."))
        lay.addWidget(rotulo("NOME DA REUNIÃO", "rotulo"))
        self.titulo = QLineEdit()
        self.titulo.setPlaceholderText("ex.: Status Projeto Alfa")
        self.titulo.setAccessibleName("Nome da reunião")
        lay.addWidget(self.titulo)
        lay.addWidget(rotulo("DATA", "rotulo"))
        self.data = campo_data(acessivel="Data da reunião")
        lay.addWidget(self.data, 0, Qt.AlignLeft)
        lay.addWidget(rotulo("RECAP DO TEAMS COPILOT", "rotulo"))
        self.recap = QPlainTextEdit()
        self.recap.setAccessibleName("Recap do Teams Copilot")
        self.recap.setPlaceholderText(
            "Cole aqui o recap.\n\nDica: clique em “Copiar pedido para o Copilot”, cole no chat do Copilot da reunião "
            "e traga a resposta. Nesse formato a leitura é certeira:\n\n" + PROMPT_COPILOT)
        self.recap.setMinimumHeight(280)
        lay.addWidget(self.recap)
        self.erro_recap = rotulo("Cole o recap antes de ler.", "meta")
        self.erro_recap.setStyleSheet(f"color: {estilo.VERMELHO};")
        self.erro_recap.hide()
        lay.addWidget(self.erro_recap)
        lay.addWidget(fluxo(botao("Ler recap", "primario", self.ler_recap),
                            botao("Copiar pedido para o Copilot", ao_clicar=self.copiar_pedido,
                                  dica="Copia um pedido para o Copilot responder num formato fácil de ler"),
                            botao("Cancelar", ao_clicar=lambda: self.ir(self.LISTA)), espaco=8))
        lay.addStretch(1)

    def nova_reuniao(self):
        self.titulo.clear()
        self.recap.clear()
        self.erro_recap.hide()
        h = self.ctrl.sv.hoje()
        self.data.setDate(QDate(h.year, h.month, h.day))
        self.ir(self.NOVA)
        self.titulo.setFocus()

    def copiar_pedido(self):
        QGuiApplication.clipboard().setText(PROMPT_COPILOT)
        self.ctrl.avisar("Pedido copiado. Cole no chat do Copilot da reunião e traga a resposta para cá.", False)

    def ler_recap(self):
        texto = self.recap.toPlainText().strip()
        if not texto:
            self.erro_recap.show()
            self.recap.setFocus()
            return
        self.erro_recap.hide()
        self.sugestoes = self.ctrl.sv.ler_recap(texto)
        self._preencher_revisao()
        self.paginas.setCurrentIndex(self.REVISAR)

    # ================================================================ revisar
    def _montar_revisar(self, lay):
        lay.addWidget(botao("← Voltar ao recap", "link", lambda: self.paginas.setCurrentIndex(self.NOVA)), 0, Qt.AlignLeft)
        self.cab_revisar = QVBoxLayout()
        lay.addLayout(self.cab_revisar)
        self.revisao = QVBoxLayout()
        self.revisao.setSpacing(8)
        lay.addLayout(self.revisao)
        self.criar = botao("Criar", "primario", self.criar_itens)
        lay.addWidget(fluxo(self.criar, botao("Voltar ao recap", ao_clicar=lambda: self.paginas.setCurrentIndex(self.NOVA)),
                            espaco=8))
        lay.addStretch(1)

    def _titulo_reuniao(self) -> str:
        return self.titulo.text().strip() or f"Reunião de {self.data.date().toPython():%d/%m}"

    def _preencher_revisao(self):
        limpar_layout(self.cab_revisar)
        limpar_layout(self.revisao)
        self.cab_revisar.addLayout(cabecalho(
            "Revisar itens",
            f"{self._titulo_reuniao()} · nada é criado sem a sua confirmação. Tarefas aceitas entram direto no planejamento."))
        if not self.sugestoes:
            self.revisao.addWidget(vazio(
                "Não encontrei itens neste recap. Você pode salvar só o recap, ou usar “Copiar pedido para o Copilot” "
                "para receber os itens num formato que o app lê com certeza."))
        for s in self.sugestoes:
            self.revisao.addWidget(self._linha_sugestao(s))
        self._contar()

    def _linha_sugestao(self, s) -> QFrame:
        caixa = QFrame()
        caixa.setObjectName("cartao")
        v = QVBoxLayout(caixa)
        v.setContentsMargins(14, 10, 14, 10)
        v.setSpacing(6)
        nome, cor_t, cor_f = CORES_SUGESTAO[s.tipo]
        topo = QHBoxLayout()
        topo.setSpacing(8)
        topo.addWidget(selo(nome, cor_t, cor_f))
        topo.addStretch(1)
        if s.tipo in (TAREFA, AGUARDANDO):
            trocar = botao("é de outra pessoa" if s.tipo == TAREFA else "é minha", "link",
                           lambda _=False, s=s: self._trocar_tipo(s),
                           dica="Trocar entre tarefa sua e item aguardando")
            topo.addWidget(trocar)
        aceito = botao("", "chip", lambda _=False, s=s: self._alternar(s))
        aceito.setCheckable(True)
        self._pintar_aceito(aceito, s.aceita)
        topo.addWidget(aceito)
        v.addLayout(topo)

        texto = QLineEdit(s.texto)
        texto.setAccessibleName("Texto do item")
        texto.textChanged.connect(lambda t, s=s: setattr(s, "texto", t))
        v.addWidget(texto)
        if s.tipo == AGUARDANDO:
            pessoa = QLineEdit(s.responsavel or "")
            pessoa.setPlaceholderText("De quem? (obrigatório)")
            pessoa.setAccessibleName("Pessoa responsável")
            pessoa.setFixedWidth(220)
            pessoa.textChanged.connect(lambda t, s=s: setattr(s, "responsavel", t.strip() or None))
            sv = self.ctrl.sv
            cobrar = s.prazo or sv.calendario().dias_de_trabalho(sv.hoje() + timedelta(days=1), 2)[-1]
            v.addWidget(fluxo(pessoa, rotulo(f"cobrar {self.ctrl.sv.nome_dia(cobrar)}", "meta"), espaco=10))
        else:
            partes = []
            if s.tipo == TAREFA:
                if s.responsavel:
                    partes.append(f"responsável: {s.responsavel}")
                if s.prazo:
                    partes.append(f"até {formata_dia(s.prazo)}")
                if s.data_fixa:
                    partes.append(f"em {formata_dia(s.data_fixa)}")
                partes.append(formata_minutos(s.minutos or 120))
            else:
                partes.append("fica registrada na reunião")
            v.addWidget(texto_longo(" · ".join(partes), "meta"))
        if s.trecho and s.trecho.strip() != s.texto.strip():
            trecho = texto_longo(f"Trecho: “{s.trecho}”", "meta")
            trecho.setStyleSheet("font-style: italic;")
            v.addWidget(trecho)
        if not s.aceita:
            caixa.setStyleSheet(f"QFrame#cartao {{ background: {estilo.FUNDO_CINZA}; }}")
        return caixa

    def _pintar_aceito(self, b, aceito: bool):
        b.setChecked(aceito)
        b.setText("✓ Aceito" if aceito else "Descartado")
        b.setToolTip("Clique para descartar" if aceito else "Clique para aceitar")

    def _alternar(self, s):
        s.aceita = not s.aceita
        self._preencher_revisao()

    def _trocar_tipo(self, s):
        s.tipo = AGUARDANDO if s.tipo == TAREFA else TAREFA
        self._preencher_revisao()

    def _contar(self):
        n = sum(1 for s in self.sugestoes if s.aceita)
        self.criar.setText(f"Criar {n} {'item' if n == 1 else 'itens'}" if n else "Salvar só o recap")

    def criar_itens(self):
        faltando = [s for s in self.sugestoes if s.aceita and s.tipo == AGUARDANDO and not s.responsavel]
        if faltando:
            self.ctrl.avisar(f"Diga de quem você espera: {faltando[0].texto}", False)
            return
        r = self.ctrl.executar(self.ctrl.sv.criar_da_reuniao, self._titulo_reuniao(), self.recap.toPlainText(),
                               self.sugestoes, self.data.date().toPython())
        reunioes = self.ctrl.sv.banco.reunioes()
        self.sugestoes = []
        if r and reunioes:
            self.mostrar_detalhe(max(x.id for x in reunioes))  # a que acabou de ser criada

    # ================================================================ detalhe
    def _montar_detalhe(self, lay):
        lay.addWidget(botao("← Reuniões", "link", lambda: self.ir(self.LISTA)), 0, Qt.AlignLeft)
        self.det = QVBoxLayout()
        self.det.setSpacing(12)
        lay.addLayout(self.det)
        lay.addStretch(1)

    def mostrar_detalhe(self, reuniao_id: int):
        self.reuniao_id = reuniao_id
        self.ir(self.DETALHE)

    def _preencher_detalhe(self):
        limpar_layout(self.det)
        sv = self.ctrl.sv
        r = sv.banco.reuniao(self.reuniao_id) if self.reuniao_id else None
        if r is None:
            self.paginas.setCurrentIndex(self.LISTA)
            self._preencher_lista()
            return
        rr = sv.resumo_reuniao(r)
        self.det.addLayout(cabecalho(r.titulo, f"{formata_dia(r.quando.date())} {r.quando:%Y} · {rr.legenda}"))

        self.det.addWidget(rotulo("ITENS CRIADOS", "rotulo"))
        if not rr.tarefas and not rr.aguardando:
            self.det.addWidget(texto_longo("Nenhuma tarefa ou espera saiu desta reunião.", "meta"))
        for t in rr.tarefas:
            linha = LinhaClicavel()
            linha.marcar_selecionada(t.id == self.ctrl.sel_id)
            linha.clicada.connect(lambda i=t.id: self.ctrl.abrir_tarefa(i))
            h = QHBoxLayout(linha)
            h.setContentsMargins(12, 8, 12, 8)
            h.setSpacing(10)
            h.addWidget(selo("TAREFA", estilo.ACENTO_ESCURO, estilo.ACENTO_CLARO), 0, Qt.AlignTop)
            textos = QVBoxLayout()
            textos.setSpacing(2)
            quando = sv.nome_dia(t.dia_planejado) if t.status == "aberta" else STATUS.get(t.status, t.status)
            for w in (texto_longo(t.titulo, "tituloTarefa"), texto_longo(f"{quando} · {formata_minutos(t.minutos)}", "meta")):
                w.setAttribute(Qt.WA_TransparentForMouseEvents)
                textos.addWidget(w)
            h.addLayout(textos, 1)
            self.det.addWidget(linha)
        for a in rr.aguardando:
            linha = LinhaClicavel()
            if a.status == "aberto":
                linha.clicada.connect(lambda i=a.id: self.ctrl.editar_espera(i))
            else:
                linha.setCursor(Qt.ArrowCursor)
            h = QHBoxLayout(linha)
            h.setContentsMargins(12, 8, 12, 8)
            h.setSpacing(10)
            h.addWidget(selo("AGUARDANDO" if a.status == "aberto" else "RECEBIDO", estilo.AGUARDA_TEXTO, estilo.AGUARDA_CLARO), 0, Qt.AlignTop)
            textos = QVBoxLayout()
            textos.setSpacing(2)
            meta = f"{a.pessoa} · cobrar {sv.nome_dia(a.cobrar_em)}" if a.status == "aberto" else f"{a.pessoa} · recebido"
            for w in (texto_longo(a.o_que, "tituloTarefa"), texto_longo(meta, "meta")):
                w.setAttribute(Qt.WA_TransparentForMouseEvents)
                textos.addWidget(w)
            h.addLayout(textos, 1)
            self.det.addWidget(linha)

        for titulo, itens in (("DECISÕES", rr.decisoes), ("RISCOS", rr.riscos)):
            if itens:
                self.det.addWidget(rotulo(titulo, "rotulo"))
                for texto in itens:
                    self.det.addWidget(texto_longo(f"•  {texto}"))

        self.det.addWidget(rotulo("RECAP ORIGINAL", "rotulo"))
        if r.recap_original.strip():
            original = QPlainTextEdit(r.recap_original)
            original.setReadOnly(True)
            original.setAccessibleName("Recap original")
            original.setMinimumHeight(160)
            original.setMaximumHeight(320)
            self.det.addWidget(original)
        else:
            self.det.addWidget(texto_longo("(sem recap)", "meta"))

        excluir = botao("Excluir reunião", "link", lambda: self.ctrl.excluir_reuniao(r.id),
                        "Apaga a reunião; as tarefas e esperas criadas continuam")
        excluir.setStyleSheet(f"color: {estilo.VERMELHO};")
        self.det.addWidget(excluir, 0, Qt.AlignLeft)
