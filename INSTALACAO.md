# Instalação no computador do trabalho

Guia passo a passo para levar o Produtividade para o computador do trabalho. Não precisa de administrador,
não instala serviço e não mexe no resto do Windows: tudo fica dentro da pasta do app.

Tempo: uns 15 minutos (a maior parte é o download do PySide6, cerca de 200 MB).

---

## Passo 1 · Python 3.11 ou superior

Abra o **PowerShell** (tecla Windows, digite `powershell`, Enter) e rode:

```
python --version
```

- Apareceu `Python 3.11` ou maior (3.12, 3.13…): pronto, vá para o passo 2.
- Apareceu outra versão, um erro ou abriu a Microsoft Store: instale o Python por uma destas opções, na ordem:
  1. **Portal da Empresa / Central de Software** da empresa, se tiver o Python 3.12 ou 3.13.
  2. **Microsoft Store**: procure "Python 3.13" (instala só para o seu usuário, sem administrador).
  3. **python.org/downloads**: no instalador, marque *Add python.exe to PATH* e use *Install Now*
     (fica na sua pasta de usuário, sem administrador).

  Feche e abra o PowerShell de novo e repita o `python --version`.

## Passo 2 · Copiar a pasta do app

1. Crie uma pasta **fora do OneDrive**, por exemplo `C:\Users\<seu usuário>\Produtividade`.

   > Por que fora do OneDrive: o `dados.db` é aberto o tempo todo pelo app, e a sincronização do OneDrive pode
   > travá-lo ou criar cópias "em conflito". A cópia de segurança vai para o OneDrive pelo backup diário (passo 4).
   > Atenção: em muitas empresas a pasta **Documentos** já é sincronizada com o OneDrive — prefira a pasta do usuário.

2. Copie para lá **todo o conteúdo** da pasta do app, **menos**:
   - `.venv` e `__pycache__` (são recriados);
   - `dados.db`, `backup` e `erros.log`, se quiser começar do zero no trabalho
     (os dados de teste ficam no computador de casa). Se quiser levar as tarefas, copie o `dados.db` também.

## Passo 3 · Instalar

Dê dois cliques em **`instalar.bat`**. Ele:

1. encontra o Python;
2. cria o ambiente `.venv` dentro da pasta do app;
3. instala o PySide6;
4. confere tudo (`app.py verificar`) e pergunta se você quer o **atalho na Área de Trabalho** e se o app deve
   **abrir sozinho ao ligar o computador**.

No fim deve aparecer `Tudo certo.`. Se aparecer `[!!]` em algum item, veja **Problemas comuns** abaixo.

### 3B · Se a rede da empresa bloquear o pip (plano B, sem internet)

Sintoma: no passo [3/4] aparece erro de conexão, `SSL`, `proxy` ou `403`.

1. Num Windows **com internet** (ex.: o de casa) e com Python 3.11+, dê dois cliques em **`baixar_pacotes.bat`**.
   Ele cria a subpasta `pacotes` com o PySide6.
2. Leve a pasta do app **com a subpasta `pacotes`** para o computador do trabalho (pendrive, OneDrive, e-mail…).
3. Rode **`instalar.bat`** de novo: ele percebe a pasta `pacotes` e instala dela, sem internet.

### 3C · Se a empresa usa proxy

Às vezes o pip funciona informando o proxy. No PowerShell, na pasta do app:

```
.venv\Scripts\python.exe -m pip install --proxy http://proxy.suaempresa:8080 -r requirements.txt
```

(peça o endereço do proxy à TI). Se não der, use o plano B.

## Passo 4 · Primeira abertura e configuração

Abra pelo atalho **Produtividade** (ou dois cliques em `iniciar.bat`). Aparecem a mini barra, a janela principal e
um ícone ao lado do relógio. Em **Configurações** (botão no topo):

1. **Dados e reuniões**
   - Seu nome como aparece nos recaps do Copilot: `FABIO KIYOSHI SATO` (já vem preenchido) e os apelidos.
   - **Backup diário**: clique em *Escolher pasta…* e escolha uma pasta dentro do OneDrive corporativo, por exemplo
     `C:\Users\<seu usuário>\OneDrive - <Empresa>\Produtividade-backup`. Clique em *Fazer backup agora* para testar.
2. **Jornada de trabalho**: início, almoço, fim, dias úteis e as horas para tarefas por dia (padrão 5h).
3. **Avisos sonoros**: ligue os avisos, escolha a antecedência e o som; use *Ver aviso da manhã* para ver como fica.
4. **Férias, feriados e ausências**: os feriados nacionais, de SP e de Osasco já estão lá; cadastre as férias e
   ausências já marcadas e, se a empresa liberar, os pontos facultativos (Carnaval, vésperas).

Pronto. O **Manual** (botão no topo ou F1) explica o resto.

---

## Uso diário

- Abrir: atalho **Produtividade** (ou ele abre sozinho com o Windows, se você escolheu).
  Abrir de novo com o app já aberto só traz a janela para a frente (nunca ficam duas cópias).
- Fechar a janela no X **não encerra** o app: a mini barra e o ícone continuam. Para sair de vez: botão direito no
  ícone ao lado do relógio › **Sair**.
- Ligar ou desligar a abertura automática depois:
  `.venv\Scripts\python.exe app.py iniciar-com-windows sim` (ou `nao`).

## Atualizar para uma versão nova

1. Saia do app (ícone › Sair).
2. Copie os arquivos novos por cima dos antigos, **mantendo** `dados.db`, `backup` e `.venv`.
3. Se a versão nova disser que mudou o `requirements.txt`, rode `instalar.bat` de novo.
4. Abra o app. Se o formato dos dados mudou, o `dados.db` é atualizado sozinho, sem perder nada, e uma
   cópia de como ele estava fica ao lado, como `dados-antes-vN.db` (pode apagar depois de conferir que está tudo certo).

## Backup e restauração

- O backup é automático, uma vez por dia, ao abrir o app: um arquivo só, `dados-backup.db`, na pasta escolhida
  (ou na subpasta `backup`), substituído a cada dia. O arquivo novo é gravado à parte e só então troca o anterior,
  então uma falha no meio não estraga o backup que já existia.
- Se a pasta for do OneDrive, ele guarda sozinho as versões anteriores do arquivo: botão direito em
  `dados-backup.db` › *Histórico de versões* (no site do OneDrive) para voltar a um dia anterior.
- Para **voltar o backup**: saia do app; na pasta do app, renomeie `dados.db` para `dados-antes.db`; copie o
  `dados-backup.db` para a pasta do app e renomeie para `dados.db`; abra o app.
- **Trocar de computador**: instale (passos 1 a 3) e copie o `dados.db` mais recente (ou o `dados-backup.db`
  renomeado para `dados.db`) para a pasta do app antes de abrir.

## Problemas comuns

| Sintoma | O que fazer |
| --- | --- |
| `Não encontrei o Python 3.11 ou superior` | Passo 1. Depois de instalar, feche e abra o PowerShell (ou reinicie a sessão) e rode `instalar.bat` de novo. |
| Erro de conexão, `SSL`, `proxy` ou `403` ao instalar | Plano B (3B) ou proxy (3C). |
| Dois cliques no atalho e nada abre | Veja se há um `erros.log` na pasta do app. Para ver a mensagem na hora: no PowerShell, na pasta do app, `.venv\Scripts\python.exe app.py`. |
| O app já estava aberto e "não abre" | Ele está aberto: procure o ícone ao lado do relógio (às vezes fica na setinha ^ dos ícones ocultos). Arraste-o para a barra para ficar sempre visível. |
| A mini barra sumiu | Ícone ao lado do relógio › *Mostrar mini barra*. Se ela ficou fora da tela (trocou de monitor): saia do app e rode `.venv\Scripts\python.exe app.py resetar-mini`. |
| O aviso aparece mas sem som | Confira o volume do Windows e, em Configurações › Avisos sonoros, se o som não está em *Desligado*. Clicar num som toca uma amostra. |
| O atalho não foi criado | O PowerShell pode estar bloqueado pela empresa. Crie à mão (abaixo). |
| O antivírus ou o SmartScreen bloqueia o `.bat` | Rode os comandos à mão no PowerShell, na pasta do app: `python -m venv .venv`, depois `.venv\Scripts\python.exe -m pip install -r requirements.txt`, depois `.venv\Scripts\python.exe app.py verificar`. |
| `Pasta do app: sem permissão de escrita` | A pasta está num lugar protegido (ex.: Arquivos de Programas). Use uma pasta dentro do seu usuário (passo 2). |
| Os testes | Dois cliques em `testar.bat` (inclui os testes da interface, sem abrir janelas). |

### Atalho manual

1. Botão direito na Área de Trabalho › **Novo › Atalho**.
2. Local do item (troque pelo caminho da sua pasta, com as aspas):
   `"C:\Users\<seu usuário>\Produtividade\.venv\Scripts\pythonw.exe" "C:\Users\<seu usuário>\Produtividade\app.py"`
3. Nome: `Produtividade`. Depois, botão direito no atalho › Propriedades › **Iniciar em**: a pasta do app.
4. Para abrir com o Windows: tecla Windows + R, digite `shell:startup`, Enter, e copie o atalho para essa pasta.

## Desinstalar

1. Saia do app (ícone › Sair).
2. `.venv\Scripts\python.exe app.py iniciar-com-windows nao` (se tinha ligado) e apague o atalho da Área de Trabalho.
3. Apague a pasta do app (guarde antes o `dados.db` ou a pasta de backup, se quiser manter o histórico).

---

## Para a equipe de TI / segurança

- **O que é**: aplicativo pessoal de tarefas, em código-fonte Python aberto na própria pasta (sem executável
  compilado). Interface com **PySide6** (Qt for Python, licença LGPL, The Qt Company), instalado via pip num
  ambiente virtual (`.venv`) dentro da pasta do app.
- **Permissões**: roda com o usuário comum; não precisa de administrador, não instala serviço, driver nem tarefa
  agendada. Opcionalmente cria um atalho na Área de Trabalho e outro na pasta Inicializar do próprio usuário.
- **Rede**: nenhuma conexão de rede durante o uso. A internet só é usada uma vez, pelo pip, para baixar o PySide6
  (`pypi.org` e `files.pythonhosted.org`); há uma alternativa sem internet (pasta `pacotes`).
  Para impedir duas cópias abertas, o app usa um *named pipe* local do Windows (QLocalServer), sem rede.
- **Dados**: um arquivo SQLite (`dados.db`) na pasta do app, com as tarefas, anotações e recaps de reunião
  colados pelo usuário. Cópia de segurança diária para uma pasta escolhida pelo usuário (ex.: OneDrive
  corporativo). Sem telemetria e sem envio de dados para terceiros.
- **Integrações**: nenhuma API externa. O recap do Teams Copilot é copiado e colado manualmente pelo usuário.
