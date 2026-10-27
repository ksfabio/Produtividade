"""Configurações: dados e reuniões, jornada, avisos sonoros e férias/feriados/ausências (com calendário)."""
from __future__ import annotations

import calendar as _cal
from datetime import date, timedelta

from PySide6.QtCore import QTime, Qt, Signal
from PySide6.QtWidgets import (QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLineEdit, QPushButton,
                               QTimeEdit, QVBoxLayout, QWidget)

from nucleo.calendario import TIPOS_AUSENCIA
from nucleo.captura import formata_dia, formata_minutos, le_duracao
from nucleo.sons import SONS

from . import estilo
from .avisos import tocar
from .widgets import (area_rolavel, botao, cabecalho, fluxo, limpar_layout, rotulo, selo, texto_longo)

DIAS_CURTOS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto",
         "Setembro", "Outubro", "Novembro", "Dezembro"]


def periodo(a) -> str:
    if a.inicio == a.fim:
        return f"{formata_dia(a.inicio)}/{a.inicio:%Y}"
    return f"{formata_dia(a.inicio)} a {formata_dia(a.fim)}/{a.fim:%Y}"


def _chip(texto: str, marcado: bool, ao_clicar) -> QPushButton:
    b = botao(texto, "chip", ao_clicar)
    b.setCheckable(True)
    b.setChecked(marcado)
    return b


class CalendarioAusencias(QWidget):
    """Mês em grade: clique no primeiro e no último dia. Dias já cadastrados aparecem na cor do tipo."""
    mudou = Signal()

    def __init__(self, hoje: date, parent=None):
        super().__init__(parent)
        self.hoje = hoje
        self.mes = hoje.replace(day=1)
        self.de: date | None = None
        self.ate: date | None = None
        self.tipo = "Férias"
        self.ausencias = []
        self.dias_uteis = {0, 1, 2, 3, 4}
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(6)
        topo = QHBoxLayout()
        self.anterior = botao("‹", ao_clicar=lambda: self.navegar(-1), dica="Mês anterior")
        self.proximo = botao("›", ao_clicar=lambda: self.navegar(1), dica="Próximo mês")
        for b in (self.anterior, self.proximo):
            b.setFixedWidth(34)
        self.titulo = rotulo("", "secao")
        self.titulo.setAlignment(Qt.AlignCenter)
        topo.addWidget(self.anterior)
        topo.addWidget(self.titulo, 1)
        topo.addWidget(self.proximo)
        v.addLayout(topo)
        self.grade = QGridLayout()
        self.grade.setSpacing(3)
        for i, nome in enumerate(DIAS_CURTOS):
            lb = rotulo(nome, "meta")
            lb.setAlignment(Qt.AlignCenter)
            self.grade.addWidget(lb, 0, i)
        self.dias: list[QPushButton] = []
        for k in range(42):
            b = QPushButton()
            b.setFixedSize(42, 34)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=k: self._clicar(k))
            self.grade.addWidget(b, 1 + k // 7, k % 7)
            self.dias.append(b)
        v.addLayout(self.grade)
        self._datas: list[date] = []
        self.desenhar()

    def definir(self, ausencias, dias_uteis, tipo: str):
        self.ausencias = ausencias
        self.dias_uteis = set(dias_uteis)
        self.tipo = tipo
        self.desenhar()

    def navegar(self, delta: int):
        m = self.mes.month - 1 + delta
        novo = date(self.mes.year + m // 12, m % 12 + 1, 1)
        if novo < self.hoje.replace(day=1):
            return
        self.mes = novo
        self.desenhar()

    def limpar(self):
        self.de = self.ate = None
        self.desenhar()
        self.mudou.emit()

    def selecionar(self, de: date, ate: date | None = None):
        self.de, self.ate = de, ate
        self.mes = de.replace(day=1)
        self.desenhar()
        self.mudou.emit()

    def _clicar(self, k: int):
        d = self._datas[k]
        if d < self.hoje or d.weekday() not in self.dias_uteis:
            return
        if self.de is None or self.ate is not None:
            self.de, self.ate = d, None
        elif d < self.de:
            self.de = d
        else:
            self.ate = d
        self.desenhar()
        self.mudou.emit()

    def _ausencia(self, d: date):
        for a in self.ausencias:
            if a.inicio <= d <= a.fim:
                return a
        return None

    def desenhar(self):
        self.titulo.setText(f"{MESES[self.mes.month - 1]} de {self.mes.year}")
        self.anterior.setEnabled(self.mes > self.hoje.replace(day=1))
        primeiro = self.mes - timedelta(days=self.mes.weekday())
        self._datas = [primeiro + timedelta(days=k) for k in range(42)]
        forte, _, _ = estilo.CORES_AUSENCIA[self.tipo]
        fim_sel = self.ate or self.de
        for b, d in zip(self.dias, self._datas):
            b.setText(str(d.day))
            fora = d.month != self.mes.month
            bloqueado = d < self.hoje or d.weekday() not in self.dias_uteis
            selecionado = self.de is not None and self.de <= d <= fim_sel
            a = self._ausencia(d)
            css = ["border-radius: 6px; padding: 0; font-size: 13px;"]
            dica = ""
            if selecionado:
                css.append(f"background: {forte}; color: white; font-weight: 700; border: none;")
            elif a is not None:
                _, claro, texto = estilo.CORES_AUSENCIA.get(a.tipo, estilo.CORES_AUSENCIA["Ausência"])
                css.append(f"background: {claro}; color: {texto}; font-weight: 600; border: none;")
                dica = f"{a.tipo}" + (f": {a.descricao}" if a.descricao else "")
            elif bloqueado:
                css.append(f"background: transparent; color: #B0B6BE; border: none;")
            else:
                css.append(f"background: {estilo.FUNDO}; border: 1px solid {estilo.BORDA};")
            if d == self.hoje and not selecionado:
                css.append(f"border: 2px solid {estilo.ACENTO};")
            if fora and not selecionado:
                css.append("color: #C9CED6;")
            b.setStyleSheet("QPushButton { " + " ".join(css) + " }")
            b.setToolTip(dica)
            b.setEnabled(not bloqueado or a is not None)
            b.setCursor(Qt.ArrowCursor if bloqueado else Qt.PointingHandCursor)
            b.setAccessibleName(f"{d:%d/%m/%Y}" + (f", {dica}" if dica else ""))

    def dias_uteis_selecionados(self) -> int:
        if self.de is None:
            return 0
        fim = self.ate or self.de
        n, d = 0, self.de
        while d <= fim:
            n += d.weekday() in self.dias_uteis and self._ausencia(d) is None
            d += timedelta(days=1)
        return n


class TelaConfiguracoes(QWidget):
    def __init__(self, ctrl, parent=None):
        super().__init__(parent)
        self.ctrl = ctrl
        self._carregando = False
        self.tipo_ausencia = "Férias"
        self.mostrar_feriados = False
        lay = area_rolavel(self, espaco=18)
        lay.addLayout(cabecalho("Configurações",
                                "Jornada, avisos sonoros e dias sem trabalho. O planejador usa tudo isso para encaixar as tarefas."))
        lay.addWidget(self._secao_dados())
        lay.addWidget(self._secao_jornada())
        lay.addWidget(self._secao_avisos())
        lay.addWidget(self._secao_ausencias())
        lay.addStretch(1)

    # ---------------------------------------------------------------- utilitários
    @staticmethod
    def _cartao(titulo: str, *direita) -> tuple[QFrame, QVBoxLayout]:
        caixa = QFrame()
        caixa.setObjectName("cartao")
        v = QVBoxLayout(caixa)
        v.setContentsMargins(20, 16, 20, 18)
        v.setSpacing(10)
        topo = QHBoxLayout()
        topo.addWidget(rotulo(titulo, "secao"))
        topo.addStretch(1)
        for w in direita:
            topo.addWidget(w)
        v.addLayout(topo)
        return caixa, v

    def _salvar(self, **campos):
        if self._carregando:
            return
        r = self.ctrl.sv.salvar_configuracao(**campos)
        if r.mensagem != "Sem mudanças.":
            self.ctrl.avisar(r.mensagem, False)
        self.ctrl.recarregar()  # também recarrega esta tela (volta ao valor salvo se foi recusado)

    # ---------------------------------------------------------------- dados e reuniões
    def _secao_dados(self) -> QFrame:
        caixa, v = self._cartao("Dados e reuniões")
        g = QGridLayout()
        g.setHorizontalSpacing(14)
        g.setVerticalSpacing(10)
        g.setColumnStretch(1, 1)
        self.nome = QLineEdit()
        self.nome.setAccessibleName("Seu nome nos recaps")
        self.nome.editingFinished.connect(lambda: self._salvar(meu_nome=self.nome.text()))
        self.apelidos = QLineEdit()
        self.apelidos.setAccessibleName("Apelidos")
        self.apelidos.setPlaceholderText("separe por vírgula, ex.: Fabio, Kiyoshi, você")
        self.apelidos.editingFinished.connect(
            lambda: self._salvar(apelidos=[a.strip() for a in self.apelidos.text().split(",")]))
        self.backup = QLineEdit()
        self.backup.setAccessibleName("Pasta de backup")
        self.backup.editingFinished.connect(lambda: self._salvar(pasta_backup=self.backup.text()))
        self.arquivo = rotulo("", "meta")
        self.arquivo.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.info_backup = texto_longo("", "meta")
        linhas = [
            ("Seu nome nos recaps do Copilot", self.nome),
            ("Outros jeitos de se referirem a você", self.apelidos),
            ("Arquivo de dados", self.arquivo),
            ("Backup diário", fluxo(self.backup, botao("Escolher pasta…", ao_clicar=self._escolher_pasta),
                                    botao("Fazer backup agora", ao_clicar=self._backup_agora), espaco=8)),
        ]
        self.backup.setMinimumWidth(320)
        for i, (nome, w) in enumerate(linhas):
            g.addWidget(rotulo(nome, "meta"), i, 0, Qt.AlignLeft | Qt.AlignVCenter)
            g.addWidget(w, i, 1)
        g.addWidget(self.info_backup, len(linhas), 1)
        v.addLayout(g)
        return caixa

    def _escolher_pasta(self):
        pasta = QFileDialog.getExistingDirectory(self, "Pasta para o backup diário", self.backup.text() or str(self.ctrl.sv.pasta_backup()))
        if pasta:
            self.backup.setText(pasta)
            self._salvar(pasta_backup=pasta)

    def _backup_agora(self):
        r = self.ctrl.sv.backup_agora()
        self.ctrl.avisar(r.mensagem, False)
        self.atualizar()

    # ---------------------------------------------------------------- jornada
    def _hora(self, nome: str, campo: str) -> QTimeEdit:
        t = QTimeEdit()
        t.setDisplayFormat("HH:mm")
        t.setAccessibleName(nome)
        t.setMinimumWidth(t.fontMetrics().horizontalAdvance(" 00:00 ") + 48)
        t.editingFinished.connect(lambda: self._salvar(**{campo: t.time().toString("HH:mm")}))
        return t

    def _secao_jornada(self) -> QFrame:
        caixa, v = self._cartao("Jornada de trabalho")
        self.h_inicio = self._hora("Início", "jornada_inicio")
        self.h_alm_ini = self._hora("Almoço de", "almoco_inicio")
        self.h_alm_fim = self._hora("Volta do almoço", "almoco_fim")
        self.h_fim = self._hora("Fim", "jornada_fim")
        g = QGridLayout()
        g.setHorizontalSpacing(14)
        g.setVerticalSpacing(10)
        g.setColumnStretch(1, 1)
        g.addWidget(rotulo("Horário", "meta"), 0, 0)
        g.addWidget(fluxo(rotulo("Início"), self.h_inicio, rotulo("  Almoço de"), self.h_alm_ini, rotulo("até"),
                          self.h_alm_fim, rotulo("  Fim"), self.h_fim, espaco=8), 0, 1)
        self.chips_dias = []
        for i, nome in enumerate(DIAS_CURTOS):
            self.chips_dias.append(_chip(nome, False, lambda _=False: self._salvar(
                dias_uteis=[k for k, c in enumerate(self.chips_dias) if c.isChecked()])))
        g.addWidget(rotulo("Dias úteis", "meta"), 1, 0)
        g.addWidget(fluxo(*self.chips_dias, espaco=4), 1, 1)
        self.horas = QLineEdit()
        self.horas.setAccessibleName("Horas para tarefas por dia")
        self.horas.setFixedWidth(110)
        self.erro_horas = rotulo("Use de 15min a 12h, ex.: 5h, 4h30.", "meta")
        self.erro_horas.setStyleSheet(f"color: {estilo.VERMELHO};")
        self.erro_horas.hide()
        self.horas.editingFinished.connect(self._salvar_horas)
        g.addWidget(rotulo("Horas para tarefas", "meta"), 2, 0)
        g.addWidget(fluxo(self.horas, rotulo("por dia (o padrão de cada dia; ajuste dia a dia com − e +)", "meta"), self.erro_horas, espaco=8), 2, 1)
        for r in range(3):
            g.itemAtPosition(r, 0).setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        v.addLayout(g)
        self.resumo_jornada = texto_longo("")
        self.resumo_jornada.setStyleSheet(f"color: {estilo.ACENTO_ESCURO}; font-weight: 600;")
        v.addWidget(self.resumo_jornada)
        return caixa

    def _salvar_horas(self):
        if self._carregando:
            return
        m = le_duracao(self.horas.text(), aceitar_numero=True)
        if not m or not 15 <= m <= 720:
            self.erro_horas.show()
            return
        self.erro_horas.hide()
        self._salvar(horas_padrao_min=m)

    # ---------------------------------------------------------------- avisos
    def _secao_avisos(self) -> QFrame:
        caixa, v = self._cartao(
            "Avisos sonoros",
            botao("Ver aviso da manhã", ao_clicar=lambda: self.ctrl.mostrar_aviso_hora("manha")),
            botao("Ver aviso do fim do dia", ao_clicar=lambda: self.ctrl.mostrar_aviso_hora("fim")))
        g = QGridLayout()
        g.setHorizontalSpacing(14)
        g.setVerticalSpacing(10)
        g.setColumnStretch(1, 1)
        self.chip_manha = _chip("Antes do fim da manhã", False, lambda _=False: self._salvar(aviso_manha=self.chip_manha.isChecked()))
        self.chip_fim = _chip("Antes do fim da jornada", False, lambda _=False: self._salvar(aviso_fim=self.chip_fim.isChecked()))
        self.chips_antes = {m: _chip(f"{m} min", False, lambda _=False, m=m: self._salvar(aviso_antecedencia_min=m)) for m in (15, 30, 45, 60)}
        self.chips_som = {s: _chip(s, False, lambda _=False, s=s: self._escolher_som(s)) for s in SONS}
        for i, (nome, w) in enumerate([("Avisar", fluxo(self.chip_manha, self.chip_fim)),
                                       ("Com antecedência de", fluxo(*self.chips_antes.values())),
                                       ("Som", fluxo(*self.chips_som.values()))]):
            g.addWidget(rotulo(nome, "meta"), i, 0, Qt.AlignLeft | Qt.AlignVCenter)
            g.addWidget(w, i, 1)
        v.addLayout(g)
        self.resumo_avisos = texto_longo("")
        self.resumo_avisos.setStyleSheet(f"color: {estilo.ACENTO_ESCURO}; font-weight: 600;")
        v.addWidget(self.resumo_avisos)
        v.addWidget(texto_longo("O aviso aparece no canto da tela, por cima das outras janelas, só em dias de trabalho. "
                                "Clicar num som toca uma amostra.", "meta"))
        return caixa

    def _escolher_som(self, som: str):
        tocar(som)
        self._salvar(aviso_som=som)

    # ---------------------------------------------------------------- ausências
    def _secao_ausencias(self) -> QFrame:
        caixa, v = self._cartao("Férias, feriados e ausências")
        v.addWidget(texto_longo("Nesses dias o planejador não encaixa tarefas; em meio período, usa metade das horas. "
                                "Feriados nacionais, de SP e de Osasco já vêm cadastrados.", "meta"))
        self.lista_ausencias = QVBoxLayout()
        self.lista_ausencias.setSpacing(6)
        v.addLayout(self.lista_ausencias)

        v.addSpacing(6)
        v.addWidget(rotulo("ADICIONAR", "rotulo"))
        self.chips_tipo = {}
        for t in TIPOS_AUSENCIA:
            forte, claro, texto = estilo.CORES_AUSENCIA[t]
            b = _chip(f"●  {t}", False, lambda _=False, t=t: self._escolher_tipo(t))
            b.setStyleSheet(f"QPushButton {{ color: {texto}; }} QPushButton:checked {{ background: {claro}; border: 1px solid {forte}; color: {texto}; font-weight: 700; }}")
            self.chips_tipo[t] = b
        v.addWidget(fluxo(*self.chips_tipo.values()))
        corpo = QHBoxLayout()
        corpo.setSpacing(24)
        self.calendario = CalendarioAusencias(self.ctrl.sv.hoje())
        self.calendario.mudou.connect(self._dica_selecao)
        corpo.addWidget(self.calendario, 0, Qt.AlignTop)
        lado = QVBoxLayout()
        lado.setSpacing(10)
        self.dica_sel = texto_longo("")
        self.dica_sel.setStyleSheet(f"color: {estilo.ACENTO_ESCURO}; font-weight: 600; font-size: 14px;")
        lado.addWidget(self.dica_sel)
        self.limpar_sel = botao("Limpar seleção", "link", lambda: self.calendario.limpar())
        lado.addWidget(self.limpar_sel, 0, Qt.AlignLeft)
        lado.addWidget(rotulo("Descrição", "meta"))
        self.descricao = QLineEdit()
        self.descricao.setPlaceholderText("ex.: viagem, médico, curso")
        self.descricao.setAccessibleName("Descrição da ausência")
        lado.addWidget(self.descricao)
        self.adicionar = botao("Adicionar e replanejar", "primario", self._adicionar)
        lado.addWidget(self.adicionar, 0, Qt.AlignLeft)
        legenda = [selo(t, estilo.CORES_AUSENCIA[t][2], estilo.CORES_AUSENCIA[t][1]) for t in TIPOS_AUSENCIA]
        lado.addWidget(fluxo(*legenda, espaco=6))
        lado.addWidget(texto_longo("Clique no primeiro e no último dia. Fins de semana e dias passados não são selecionáveis; "
                                   "os dias já cadastrados aparecem na cor do tipo (passe o mouse para ver).", "meta"))
        lado.addStretch(1)
        corpo.addLayout(lado, 1)
        v.addLayout(corpo)

        self.facultativos = QVBoxLayout()
        self.facultativos.setSpacing(6)
        v.addLayout(self.facultativos)
        return caixa

    def _escolher_tipo(self, tipo: str):
        self.tipo_ausencia = tipo
        for t, b in self.chips_tipo.items():
            b.setChecked(t == tipo)
        self.calendario.definir(self.ctrl.sv.banco.ausencias(), self.ctrl.sv.config().dias_uteis, tipo)
        self._dica_selecao()

    def _dica_selecao(self):
        c = self.calendario
        if c.de is None:
            self.dica_sel.setText("Clique no primeiro dia.")
        elif c.ate is None:
            self.dica_sel.setText(f"Selecionado: {formata_dia(c.de)}. Clique no último dia, ou adicione só este dia.")
        else:
            n = c.dias_uteis_selecionados()
            self.dica_sel.setText(f"Selecionado: {formata_dia(c.de)} a {formata_dia(c.ate)} · {n} {'dia útil' if n == 1 else 'dias úteis'}")
        self.limpar_sel.setVisible(c.de is not None)
        self.adicionar.setEnabled(c.de is not None)
        self.adicionar.setText(f"Adicionar {self.tipo_ausencia.lower()} e replanejar")

    def _adicionar(self):
        c = self.calendario
        if c.de is None:
            return
        r = self.ctrl.executar(self.ctrl.sv.adicionar_ausencia, self.tipo_ausencia, c.de, c.ate or c.de, self.descricao.text().strip())
        if r.ok:
            self.descricao.clear()
            c.de = c.ate = None
            self.atualizar()

    def _preencher_ausencias(self):
        sv = self.ctrl.sv
        limpar_layout(self.lista_ausencias)
        futuras = sv.ausencias_futuras()
        minhas = [a for a in futuras if a.origem != "feriado"]
        feriados = [a for a in futuras if a.origem == "feriado"]
        if not minhas:
            self.lista_ausencias.addWidget(rotulo("Nenhuma férias ou ausência cadastrada daqui para a frente.", "meta"))
        for a in minhas:
            self.lista_ausencias.addWidget(self._linha_ausencia(a))
        ver = botao(("Ocultar" if self.mostrar_feriados else "Mostrar") + f" os {len(feriados)} próximos feriados", "link",
                    self._alternar_feriados)
        self.lista_ausencias.addWidget(ver, 0, Qt.AlignLeft)
        if self.mostrar_feriados:
            for a in feriados:
                self.lista_ausencias.addWidget(self._linha_ausencia(a))

        limpar_layout(self.facultativos)
        pend = sv.pontos_facultativos_pendentes()
        if pend:
            self.facultativos.addSpacing(6)
            self.facultativos.addWidget(rotulo("PONTOS FACULTATIVOS (NÃO SÃO FERIADO)", "rotulo"))
            self.facultativos.addWidget(texto_longo("Se a empresa liberar, cadastre com um clique:", "meta"))
            botoes = [botao(f"+ {nome} · {formata_dia(d)}/{d:%y}", ao_clicar=lambda _=False, d=d, n=nome:
                            self.ctrl.executar(sv.adicionar_ausencia, "Feriado", d, d, f"{n} (ponto facultativo)"))
                      for d, nome in pend]
            self.facultativos.addWidget(fluxo(*botoes, espaco=6))

    def _alternar_feriados(self):
        self.mostrar_feriados = not self.mostrar_feriados
        self._preencher_ausencias()

    def _linha_ausencia(self, a) -> QFrame:
        linha = QFrame()
        linha.setObjectName("linhaTarefa")
        h = QHBoxLayout(linha)
        h.setContentsMargins(12, 8, 12, 8)
        h.setSpacing(12)
        forte, claro, texto = estilo.CORES_AUSENCIA.get(a.tipo, estilo.CORES_AUSENCIA["Ausência"])
        tipo = selo(a.tipo.upper(), texto, claro)
        tipo.setFixedWidth(118)
        tipo.setAlignment(Qt.AlignCenter)
        h.addWidget(tipo)
        textos = QVBoxLayout()
        textos.setSpacing(1)
        textos.addWidget(texto_longo(periodo(a), "tituloTarefa"))
        if a.descricao:
            textos.addWidget(texto_longo(a.descricao, "meta"))
        h.addLayout(textos, 1)
        h.addWidget(botao("Ver no calendário", "link", lambda _=False, a=a: self._ver(a)))
        h.addWidget(botao("Remover", ao_clicar=lambda _=False, i=a.id: self.ctrl.executar(self.ctrl.sv.remover_ausencia, i),
                          dica="Remove e replaneja (Ctrl+Z desfaz)"))
        return linha

    def _ver(self, a):
        self.calendario.mes = max(a.inicio, self.ctrl.sv.hoje()).replace(day=1)
        self.calendario.desenhar()

    # ---------------------------------------------------------------- carregar
    def atualizar(self):
        sv = self.ctrl.sv
        cfg = sv.config()
        self._carregando = True
        try:
            self.nome.setText(cfg.meu_nome)
            self.apelidos.setText(", ".join(cfg.apelidos))
            self.backup.setText(cfg.pasta_backup)
            self.backup.setPlaceholderText(str(sv.pasta_backup()) + "  (padrão)")
            self.arquivo.setText(str(sv.banco.caminho))
            ultimo = sv.ultimo_backup()
            self.info_backup.setText(
                (f"Último backup: {formata_dia(ultimo.date())} às {ultimo:%H:%M}" if ultimo else "Ainda sem backup")
                + f" · um arquivo só (dados-backup.db), substituído uma vez por dia, em {sv.pasta_backup()}")
            for campo, w in ((cfg.jornada_inicio, self.h_inicio), (cfg.almoco_inicio, self.h_alm_ini),
                             (cfg.almoco_fim, self.h_alm_fim), (cfg.jornada_fim, self.h_fim)):
                w.setTime(QTime.fromString(campo, "HH:mm"))
            for i, c in enumerate(self.chips_dias):
                c.setChecked(i in cfg.dias_uteis)
            self.horas.setText(formata_minutos(cfg.horas_padrao_min))
            self.erro_horas.hide()
            self.resumo_jornada.setText(sv.resumo_jornada())
            self.chip_manha.setChecked(cfg.aviso_manha)
            self.chip_fim.setChecked(cfg.aviso_fim)
            for m, c in self.chips_antes.items():
                c.setChecked(m == cfg.aviso_antecedencia_min)
            for s, c in self.chips_som.items():
                c.setChecked(s == cfg.aviso_som)
            self.resumo_avisos.setText(sv.resumo_avisos())
        finally:
            self._carregando = False
        self._escolher_tipo(self.tipo_ausencia)
        self._preencher_ausencias()
