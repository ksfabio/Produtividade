# Produtividade

App desktop pessoal de tarefas com replanejamento automático: você anota a tarefa, o app encaixa no dia certo
dentro das horas livres e, quando você adia ou não termina, replaneja sozinho as próximas 4 semanas.

Especificação completa: documento "Especificação v2 — App desktop de produtividade" (Claude Docs).

## Situação

| Etapa | Conteúdo | Status |
| --- | --- | --- |
| 1 | Núcleo: banco SQLite, planejador, captura rápida, recap do Copilot, feriados, backup, testes | **pronta** |
| 2 | Janela principal (Hoje, Semana, painel da tarefa, diário) em PySide6 | **pronta** |
| 3 | Mini barra (arrastar, recolher, navegar) e ícone na bandeja | **pronta** |
| 4 | Abas Aguardando, Concluídas e Reuniões | **pronta** |
| 5 | Configurações, avisos sonoros, ausências com calendário, manual | **pronta** |
| 6 | Instalação no computador do trabalho (guia, scripts, atalhos, instância única) | **pronta** |

## Instalar

Windows com Python 3.11 ou superior. Dois cliques em **`instalar.bat`**: cria o ambiente `.venv` nesta pasta,
instala o PySide6, confere tudo e oferece o atalho na Área de Trabalho e a abertura com o Windows.
Passo a passo completo, plano B sem internet, atualização, backup e problemas comuns: **[INSTALACAO.md](INSTALACAO.md)**.

## Abrir o app

Atalho **Produtividade**, dois cliques em `iniciar.bat` (abre sem janela de terminal) ou `python app.py`.
Se o app já estiver aberto, abrir de novo só traz a janela para a frente.

Ao abrir, aparecem a **mini barra** (sempre por cima das outras janelas), a janela principal e um ícone
ao lado do relógio do Windows.

Na mini barra:
- arraste pela alça pontilhada (a posição fica salva); ⇥ recolhe e ⇤ expande;
- a tarefa em foco aparece com "2 de 5"; passe o mouse para ver o texto completo, clique para abrir os detalhes (clique de novo para minimizar a janela);
- ▲▼ trocam a tarefa em foco; Feito e Adiar valem para ela;
- o campo captura novas tarefas (mesma sintaxe); Ctrl+L anota no diário da tarefa em foco;
- ▭ mostra ou oculta a janela principal.

Fechar a janela no X não encerra o app: a mini barra e o ícone continuam. Para sair de vez,
clique com o botão direito no ícone ao lado do relógio › Sair.

Na janela principal:
- **Hoje**: campo "Nova tarefa" com prévia do que o app entendeu; barra de horas do dia com − e +;
  cobranças em lilás (Cobrei / Recebi); clique em qualquer parte da tarefa para abrir o painel.
- **Semana**: segunda a sexta em colunas (esta semana e as 3 seguintes), horas ajustáveis por dia,
  feriados e ausências coloridos e a lista "Sem data por enquanto".
- **Painel da tarefa**: abre por cima, à direita, em qualquer aba (trocar de aba fecha). Clique no título para
  editar o texto (ou F2; Enter salva, Esc cancela), tamanho (P/M/G ou tempo livre),
  prazo, saídas de conflito, Feito/Adiar/Reabrir e o diário (Feito, Próximo passo, Ocorrência, Bloqueio,
  Decisão), com a lista Falta fazer. No fim do painel, **Excluir tarefa** apaga de vez (pede confirmação;
  Ctrl+Z desfaz logo em seguida).
- **Aguardando**: o que você espera de outras pessoas. Campo próprio (`plano @marcos até 28/10`), seção
  "Cobrar hoje" em lilás, Cobrei / Adiar / Recebi, e clique no item para ver o histórico (quando foi criado,
  cobrado, adiado, editado, recebido) e editar quem, o quê e quando cobrar (ou excluir).
- **Reuniões**: Nova reunião › nome, data e o recap do Teams Copilot › Ler recap › revise cada item (aceitar ou
  descartar, corrigir o texto, trocar "é minha" / "é de outra pessoa", dizer de quem você espera) › Criar.
  "Copiar pedido para o Copilot" copia um pedido que faz o Copilot responder num formato que o app lê com certeza.
  A lista tem busca (título, decisões, recap); o detalhe mostra itens criados, decisões, riscos e o recap original.
- **Concluídas**: tarefas concluídas e entregas recebidas, por mês (o atual aberto) e por dia, com filtro por
  texto, #projeto ou pessoa, e Reabrir.
- Atalhos: Ctrl+N nova tarefa · Ctrl+Enter concluir · Ctrl+D adiar · Ctrl+Z desfazer ·
  Ctrl+1…5 abas · F1 manual · Ctrl+, configurações · F2 edita o texto da tarefa aberta · Ctrl+J janela · Ctrl+B recolhe a mini barra · Esc limpa o campo ou fecha o painel.
  Na mini barra também: Ctrl+↑/↓ troca a tarefa em foco · Ctrl+L anota no diário · F1 ajuda rápida.
- Se algo der errado, o detalhe fica em `erros.log` nesta pasta (seus dados continuam salvos).

- **Configurações** (botão no topo ou Ctrl+,): seu nome e apelidos nos recaps, pasta de backup (OneDrive) e
  "Fazer backup agora"; jornada (início, almoço, fim), dias úteis e horas para tarefas por dia; avisos sonoros
  (antes do fim da manhã e do fim da jornada, antecedência e som); férias, feriados, ausências e meio período
  num calendário colorido, com a lista do que vem pela frente e os pontos facultativos (Carnaval, vésperas).
- **Avisos**: no horário, toca o som e aparece um cartão no canto da tela, por cima de tudo, com "Ver Hoje" ou
  "Replanejar o resto agora". Só em dias de trabalho; se o app abrir mais de 15 min depois, não avisa atrasado.
- **Manual** (botão no topo ou F1): 11 tópicos com passo a passo, exemplos e dicas. **? Atalhos**: a cola da
  sintaxe e dos atalhos.

## Testes

Dois cliques em `testar.bat`, ou no terminal (PowerShell) nesta pasta:

```
python -m unittest discover -s testes -t .
```

Ou, com pytest instalado (`pip install -r requirements-testes.txt`): `python -m pytest`. Com o PySide6 instalado, `testes/test_interface.py`
abre a janela sem mostrá-la, testa os fluxos e salva capturas de tela em `testes/capturas/`.

Linha de comando (sem interface):

```
python app.py verificar       (confere Python, PySide6, pasta, dados e backup)
python app.py atalho          (cria o atalho na Área de Trabalho)
python app.py iniciar-com-windows sim|nao
python app.py resetar-mini    (mini barra de volta à posição padrão)
python app.py nova "consolidar riscos #alfa g até qui !"
python app.py nova "e-mail para Ana 15min"
python app.py nova "plano de migração @marcos até 28/10"
python app.py hoje            (hoje e os próximos 2 dias)
python app.py semana          (as próximas 4 semanas)
python app.py adiar 1 bloqueio
python app.py horas 29/10 2h  (quinta com reuniões: só 2h livres)
python app.py feito 2
```

## Sintaxe da captura

| Você escreve | O app entende |
| --- | --- |
| `p` · `m` · `g` | tamanho 30min · 2h · 4h (padrão: 2h) |
| `15min` · `1h` · `1h30` | tempo exato |
| `até sex` · `até 30/10` | prazo final: o planejador nunca passa dele |
| `hoje` · `amanhã` · `qua` · `30/10` | data fixa: a tarefa fica nesse dia |
| `!` · `!!` | importante · muito importante |
| `#projeto` | projeto |
| `@pessoa` | não é sua: vai para Aguardando, com cobrança |

## Estrutura

```
app.py                 ponto de entrada (sem argumentos abre a interface)
instalacao.py          verificação do ambiente, atalhos do Windows, resetar a mini barra
instalar.bat           instala (Python 3.11+, .venv, PySide6) · iniciar.bat abre · testar.bat roda os testes
baixar_pacotes.bat     plano B: baixa o PySide6 num PC com internet para instalar sem internet
INSTALACAO.md          guia de instalação no computador do trabalho
ui/                    interface PySide6: janela, mini barra, bandeja, Hoje, Semana, painel, diálogos, estilo
nucleo/
  calendario.py        feriados (nacionais, SP, Osasco), ausências, capacidade de cada dia
  sons.py              sons dos avisos (gerados na hora, sem arquivos de áudio)
  captura.py           leitura da captura rápida e das datas em português
  planejador.py        encaixe automático com estabilidade, conflitos e "sem data"
  recap.py             leitura do recap do Teams Copilot (formato pedido e livre)
  servico.py           operações do app (capturar, adiar, concluir, cobrar, receber, desfazer...)
  modelos.py           Tarefa, Registro, Aguardando, Reuniao, Configuracao
dados/
  banco.py             SQLite (dados.db ao lado do app), esquema versionado
  backup.py            backup diário num arquivo só, dados-backup.db (pasta backup/ ou OneDrive)
testes/                testes automáticos (unittest; também rodam com pytest)
```

## Dados

- `dados.db` fica nesta pasta. O backup diário vai para `backup/` ou para a pasta do OneDrive corporativo
  definida em Configurações (campo `pasta_backup`), num arquivo só, `dados-backup.db`, substituído uma vez por dia.
- Seu nome nos recaps do Copilot é configurável (padrão: FABIO KIYOSHI SATO, apelidos "Fabio" e "você").
