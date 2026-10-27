"""Manual de uso (dentro do app) e a cola de atalhos e sintaxe."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QFrame, QGridLayout, QHBoxLayout, QPushButton, QVBoxLayout,
                               QWidget)

from . import estilo
from .widgets import area_rolavel, botao, limpar_layout, rotulo, texto_longo

TOPICOS = [
    {"titulo": "Primeiros passos",
     "intro": "O app tem duas partes: a mini barra, sempre visível por cima das outras janelas, e a janela principal. "
              "Você anota as tarefas, o app encaixa cada uma num dia com horas livres e replaneja sozinho quando algo muda.",
     "passos": ["Em Configurações, confira sua jornada, os dias úteis e as horas para tarefas por dia (padrão 5h).",
                "Anote tarefas na mini barra ou no campo Nova tarefa da aba Hoje: escreva e aperte Enter.",
                "Trabalhe pela mini barra: a tarefa em foco tem Feito e Adiar; as setas ▲▼ trocam de tarefa.",
                "Na janela principal: Hoje, Semana, Aguardando (o que você espera dos outros), Reuniões e Concluídas."],
     "dica": "Fechar a janela no X não encerra o app: a mini barra e o ícone ao lado do relógio continuam. "
             "Para sair de vez, clique com o botão direito no ícone › Sair."},
    {"titulo": "Captura rápida",
     "intro": "Toda tarefa nasce de uma linha de texto. Só o texto já basta; algumas palavras, em qualquer ordem, "
              "dizem o tamanho, o prazo e a importância.",
     "passos": ["Tamanho: p (30min), m (2h), g (4h) ou o tempo exato (15min, 1h30). Sem nada, vale 2h.",
                "Prazo: até sex, até 30/10, até amanhã. O planejador nunca passa do prazo.",
                "Data fixa: hoje, amanhã, qua ou 30/10 sem o “até”. A tarefa fica nesse dia e não é movida.",
                "Importância: ! (importante) ou !! (muito importante). Projeto: #nome. "
                "Coisa de outra pessoa: @nome (vai para Aguardando)."],
     "exemplo": "consolidar riscos #alfa g até qui !\n→ tarefa de 4h do projeto alfa, importante, no primeiro dia com 4h livres antes de quinta.",
     "dica": "Enquanto você digita, a linha “Entendi: …” mostra o que o app entendeu. O botão “? Atalhos” mostra a cola completa."},
    {"titulo": "Como o planejador decide",
     "intro": "Cada dia útil tem um número de horas livres para tarefas. O planejador ocupa essas horas na ordem certa "
              "e mexe o mínimo possível no que já estava planejado.",
     "passos": ["Tarefas com data fixa entram primeiro no seu dia.",
                "As demais seguem a ordem: prazo mais próximo, depois a mais importante, depois a mais antiga.",
                "Cada tarefa vai para o primeiro dia com espaço, sem passar do prazo; o horizonte é de 4 semanas. "
                "O que não couber fica em “Sem data por enquanto”.",
                "O que já estava planejado só muda de dia se não couber mais. Toda mudança aparece num aviso com Desfazer."],
     "exemplo": "Quinta ganhou 3 reuniões: diminua as horas de quinta para 2h em Semana (−). O app move o que não cabe e avisa quantas tarefas mudaram.",
     "dica": "Cada cobrança de Aguardando reserva 5 min no dia em que deve ser feita."},
    {"titulo": "Adiar, conflitos e decisões",
     "intro": "Adiar é um clique: o app encontra o próximo dia com espaço. Ele também avisa quando algo não cabe "
              "antes do prazo e não deixa uma tarefa ser empurrada para sempre.",
     "passos": ["Adiar leva a tarefa para o próximo dia útil com espaço; o motivo é opcional, num clique no aviso.",
                "Sem espaço antes do prazo, a tarefa fica em vermelho com saídas: reduzir pela metade, prazo +2 dias úteis, "
                "delegar ou forçar no prazo (e quebrar em 2, se for maior que um dia).",
                "Na 3ª tentativa de adiar, o app pede uma decisão: fazer hoje, quebrar em 2, delegar ou cancelar.",
                "Ao abrir o app num dia novo, o que ficou para trás é reencaixado sozinho (sem contar como adiamento)."],
     "dica": "Errou? Ctrl+Z ou o Desfazer do aviso voltam a última ação (vale enquanto o app estiver aberto)."},
    {"titulo": "Mini barra",
     "intro": "A mini barra fica sempre por cima das outras janelas e mostra a tarefa em foco agora.",
     "passos": ["Arraste pela alça pontilhada para qualquer lugar da tela; a posição é lembrada.",
                "Passe o mouse no título para ver o texto completo; clique para abrir os detalhes da tarefa e clique de novo para minimizar a janela.",
                "▲▼ (ou Ctrl+↑/↓) trocam a tarefa em foco; Feito e Adiar valem para ela.",
                "O campo da mini barra captura tarefas novas; Ctrl+L anota no diário da tarefa em foco.",
                "⇥ recolhe a mini barra (fica só a alça e os botões de expandir e da janela); ⇤ expande."]},
    {"titulo": "Detalhes e diário da tarefa",
     "intro": "Clique em qualquer tarefa para abrir os detalhes, que aparecem por cima, à direita. "
              "Trocar de aba ou clicar no campo de nova tarefa fecha os detalhes.",
     "passos": ["Clique no título para corrigir o texto (ou F2); Enter salva, Esc cancela.",
                "Tamanho (P, M, G ou Tempo Livre) e Prazo combinado mudam o planejamento na hora.",
                "No diário, escolha o tipo: Feito, Próximo passo, Ocorrência, Bloqueio ou Decisão. "
                "Cada Próximo passo entra na lista Falta fazer, que você vai marcando.",
                "Criação, adiamentos, replanejamentos e conclusão entram no diário sozinhos.",
                "Excluir tarefa (no fim do painel) apaga de vez o que foi criado por engano; Ctrl+Z desfaz logo em seguida."],
     "dica": "O diário é a melhor evidência para feedback e avaliação: anote o resultado ao concluir."},
    {"titulo": "Aguardando",
     "intro": "O que você espera de outras pessoas fica separado das suas tarefas, com data para cobrar e histórico.",
     "passos": ["Crie com @pessoa (na captura ou no campo da aba Aguardando), delegando uma tarefa ou pela revisão de uma reunião.",
                "No dia da cobrança, o item aparece em lilás em Hoje e em Aguardando e reserva 5 min.",
                "Cobrei registra a data e marca a próxima cobrança para 2 dias úteis depois. "
                "Adiar passa a cobrança para o próximo dia útil.",
                "Recebi pergunta se isso gera algo para você fazer e manda o item para Concluídas.",
                "Clique no item para ver o histórico (criado, cobrado, adiado, editado, recebido) e para editar ou excluir."]},
    {"titulo": "Reuniões",
     "intro": "Transforme o recap do Teams Copilot em tarefas sem digitar tudo de novo.",
     "passos": ["Em Reuniões › Nova reunião, preencha o nome e a data e cole o recap.",
                "Opcional: “Copiar pedido para o Copilot” copia um pedido; cole no chat do Copilot da reunião e traga a resposta. "
                "Nesse formato a leitura é certeira.",
                "Ler recap: revise cada item — aceite ou descarte, corrija o texto, troque “é minha” / “é de outra pessoa” "
                "e diga de quem você espera.",
                "Criar: as tarefas entram direto no planejamento; decisões, riscos e o recap original ficam guardados na reunião.",
                "A lista de reuniões tem busca pelo título, decisões e texto do recap."],
     "dica": "Seu nome nos recaps (ex.: FABIO KIYOSHI SATO) e os apelidos ficam em Configurações › Dados e reuniões."},
    {"titulo": "Concluídas",
     "intro": "O histórico de tudo que você concluiu e recebeu, para consultar e para o levantamento do ano.",
     "passos": ["Agrupado por mês e por dia; o mês atual abre expandido. Clique no mês para abrir ou fechar.",
                "Filtre por texto, #projeto ou nome da pessoa (com filtro, todos os meses abrem).",
                "Clique numa tarefa para ver o diário; Reabrir devolve ao planejamento (ou, para um item recebido, a Aguardando)."]},
    {"titulo": "Configurações",
     "intro": "Mudanças nas horas por dia ou nos dias úteis fazem o planejador recalcular as semanas na hora.",
     "passos": ["Dados e reuniões: seu nome nos recaps, apelidos e a pasta de backup (ex.: OneDrive corporativo).",
                "Jornada: início, almoço, fim, dias úteis e horas para tarefas por dia.",
                "Avisos sonoros: antes do fim da manhã e do fim da jornada, com antecedência e som escolhidos.",
                "Férias, feriados e ausências: escolha no calendário; cada tipo tem sua cor. "
                "Feriados nacionais, de SP e de Osasco já vêm cadastrados."],
     "dica": "Os dados ficam em dados.db, na pasta do app. O backup é um arquivo só (dados-backup.db), atualizado uma vez por dia."},
    {"titulo": "Atalhos de teclado",
     "intro": "Os atalhos funcionam com o app em foco (mini barra ou janela principal).",
     "passos": ["Enter salva a tarefa digitada; Esc limpa o campo ou fecha os detalhes.",
                "Ctrl+N nova tarefa · Ctrl+Enter conclui · Ctrl+D adia · Ctrl+Z desfaz · F2 edita o texto da tarefa aberta.",
                "Ctrl+1…5 trocam de aba · Ctrl+J mostra ou oculta a janela · Ctrl+B recolhe a mini barra.",
                "Na mini barra: Ctrl+↑/↓ troca a tarefa em foco · Ctrl+L anota no diário · F1 ajuda rápida.",
                "Na janela: F1 abre este manual."]},
]

SINTAXE = [
    ("p · m · g", "tamanho 30min · 2h · 4h (sem nada: 2h)", "relatório m"),
    ("15min · 1h · 1h30", "tempo exato", "e-mail para Ana 15min"),
    ("até sex · até 30/10", "prazo final (o planejador nunca passa dele)", "proposta até sex"),
    ("hoje · amanhã · qua · 30/10", "data fixa: a tarefa fica nesse dia", "ligar para o banco amanhã"),
    ("! · !!", "importante · muito importante", "auditoria g até qui !!"),
    ("#projeto", "projeto", "consolidar riscos #alfa"),
    ("@pessoa", "não é sua: vai para Aguardando", "plano @marcos até 28/10"),
]
ATALHOS = [
    ("Enter", "salvar a tarefa digitada"), ("Esc", "limpar o campo ou fechar os detalhes"),
    ("Ctrl+N", "nova tarefa"), ("Ctrl+Enter", "concluir a tarefa aberta / em foco"),
    ("Ctrl+D", "adiar a tarefa aberta / em foco"), ("Ctrl+Z", "desfazer"),
    ("F2", "editar o texto da tarefa aberta"), ("Ctrl+1…5", "trocar de aba"),
    ("Ctrl+J", "mostrar ou ocultar a janela"), ("Ctrl+B", "recolher ou expandir a mini barra"),
    ("Ctrl+↑ / Ctrl+↓", "trocar a tarefa em foco (mini barra)"), ("Ctrl+L", "anotar no diário (mini barra)"),
    ("F1", "manual (janela) · ajuda rápida (mini barra)"),
]


class TelaManual(QWidget):
    def __init__(self, ctrl, parent=None):
        super().__init__(parent)
        self.ctrl = ctrl
        self.atual = 0
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        nav = QFrame()
        nav.setObjectName("navManual")
        nav.setStyleSheet(f"QFrame#navManual {{ border: none; border-right: 1px solid {estilo.BORDA}; background: {estilo.FUNDO_SUAVE}; }}")
        nav.setFixedWidth(250)
        nv = QVBoxLayout(nav)
        nv.setContentsMargins(12, 18, 12, 18)
        nv.setSpacing(2)
        nv.addWidget(rotulo("MANUAL DE USO", "rotulo"))
        nv.addSpacing(6)
        self.botoes = []
        for i, tp in enumerate(TOPICOS):
            b = QPushButton(f"{i + 1}. {tp['titulo']}")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(f"QPushButton {{ text-align: left; border: none; border-radius: 6px; padding: 8px 10px; background: transparent; }}"
                            f"QPushButton:hover {{ background: {estilo.FUNDO_CINZA}; }}"
                            f"QPushButton:checked {{ background: {estilo.ACENTO_CLARO}; color: {estilo.ACENTO_ESCURO}; font-weight: 600; }}")
            b.clicked.connect(lambda _=False, k=i: self.mostrar(k))
            nv.addWidget(b)
            self.botoes.append(b)
        nv.addStretch(1)
        h.addWidget(nav)
        corpo = QWidget()
        self.lay = area_rolavel(corpo, margens=(32, 24, 32, 32), espaco=14)
        h.addWidget(corpo, 1)
        self.mostrar(0)

    def atualizar(self):
        pass

    def mostrar(self, indice: int):
        self.atual = max(0, min(indice, len(TOPICOS) - 1))
        for i, b in enumerate(self.botoes):
            b.setChecked(i == self.atual)
        tp = TOPICOS[self.atual]
        limpar_layout(self.lay)
        self.lay.addWidget(rotulo(f"Tópico {self.atual + 1} de {len(TOPICOS)}", "meta"))
        self.lay.addWidget(rotulo(tp["titulo"], "titulo"))
        intro = texto_longo(tp["intro"])
        intro.setStyleSheet("font-size: 14px;")
        self.lay.addWidget(intro)
        self.lay.addWidget(rotulo("Como funciona", "secao"))
        for n, passo in enumerate(tp["passos"], start=1):
            linha = QHBoxLayout()
            linha.setSpacing(10)
            num = rotulo(str(n))
            num.setFixedWidth(24)
            num.setAlignment(Qt.AlignRight | Qt.AlignTop)
            num.setStyleSheet(f"color: {estilo.ACENTO}; font-weight: 700;")
            linha.addWidget(num, 0, Qt.AlignTop)
            linha.addWidget(texto_longo(passo), 1)
            self.lay.addLayout(linha)
        for chave, nome, cor, fundo in (("exemplo", "EXEMPLO", estilo.TINTA_2, estilo.FUNDO_CINZA),
                                        ("dica", "DICA", estilo.ACENTO_ESCURO, "#F3F6FD")):
            if tp.get(chave):
                caixa = QFrame()
                caixa.setObjectName("caixaManual")
                caixa.setStyleSheet(f"QFrame#caixaManual {{ background: {fundo}; border-radius: 8px; }}")
                v = QVBoxLayout(caixa)
                v.setContentsMargins(14, 10, 14, 10)
                v.setSpacing(4)
                r = rotulo(nome, "rotulo")
                r.setStyleSheet(f"color: {cor};")
                v.addWidget(r)
                t = texto_longo(tp[chave])
                if chave == "exemplo":
                    t.setStyleSheet("font-family: Consolas, 'Cascadia Mono', monospace;")
                v.addWidget(t)
                self.lay.addWidget(caixa)
        nav = QHBoxLayout()
        if self.atual > 0:
            nav.addWidget(botao(f"← {TOPICOS[self.atual - 1]['titulo']}", ao_clicar=lambda: self.mostrar(self.atual - 1)))
        nav.addStretch(1)
        if self.atual < len(TOPICOS) - 1:
            nav.addWidget(botao(f"{TOPICOS[self.atual + 1]['titulo']} →", "primario", lambda: self.mostrar(self.atual + 1)))
        self.lay.addSpacing(8)
        self.lay.addLayout(nav)
        self.lay.addStretch(1)


class DialogoAtalhos(QDialog):
    """Cola rápida: como escrever uma tarefa e os atalhos."""

    def __init__(self, parent=None, abrir_manual=None):
        super().__init__(parent)
        self.setWindowTitle("Atalhos e sintaxe")
        self.setMinimumWidth(640)
        v = QVBoxLayout(self)
        v.setContentsMargins(24, 20, 24, 20)
        v.setSpacing(10)
        v.addWidget(rotulo("COMO ESCREVER UMA TAREFA", "rotulo"))
        g = QGridLayout()
        g.setHorizontalSpacing(16)
        g.setVerticalSpacing(6)
        for i, (token, sentido, exemplo) in enumerate(SINTAXE):
            t = rotulo(token)
            t.setStyleSheet(f"font-family: Consolas, monospace; font-weight: 700; color: {estilo.ACENTO_ESCURO};")
            g.addWidget(t, i, 0)
            g.addWidget(rotulo(sentido), i, 1)
            e = rotulo(exemplo, "meta")
            e.setStyleSheet("font-family: Consolas, monospace;")
            g.addWidget(e, i, 2)
        v.addLayout(g)
        v.addSpacing(6)
        v.addWidget(rotulo("ATALHOS (COM O APP EM FOCO)", "rotulo"))
        g2 = QGridLayout()
        g2.setHorizontalSpacing(16)
        g2.setVerticalSpacing(4)
        for i, (tecla, oque) in enumerate(ATALHOS):
            t = rotulo(tecla)
            t.setStyleSheet(f"font-weight: 700; background: {estilo.FUNDO_CINZA}; border: 1px solid {estilo.BORDA}; "
                            "border-radius: 4px; padding: 1px 6px;")
            g2.addWidget(t, i // 2, (i % 2) * 2, Qt.AlignLeft)
            g2.addWidget(rotulo(oque), i // 2, (i % 2) * 2 + 1)
        v.addLayout(g2)
        baixo = QHBoxLayout()
        if abrir_manual:
            baixo.addWidget(botao("Abrir o manual completo", "link", lambda: (self.accept(), abrir_manual())))
        baixo.addStretch(1)
        ok = botao("Fechar", "primario", self.accept)
        ok.setDefault(True)
        baixo.addWidget(ok)
        v.addSpacing(6)
        v.addLayout(baixo)
