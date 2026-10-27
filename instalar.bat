@echo off
rem ============================================================
rem  Produtividade - instalacao (uma vez por computador)
rem  - procura o Python 3.11 ou superior
rem  - cria o ambiente .venv dentro desta pasta (nao mexe no resto do Windows)
rem  - instala o PySide6 (da internet, ou da pasta "pacotes" se ela existir)
rem  - confere tudo e oferece criar o atalho
rem  Nao precisa de administrador. Pode rodar de novo quando quiser.
rem ============================================================
setlocal
cd /d "%~dp0"
title Produtividade - instalacao
echo.
echo  Produtividade - instalacao
echo  Pasta: %CD%
echo.

set "PY="
where py >nul 2>nul && py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul && set "PY=py -3"
if not defined PY (
    where python >nul 2>nul && python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul && set "PY=python"
)
if not defined PY (
    echo  [ERRO] Nao encontrei o Python 3.11 ou superior.
    echo         Instale pelo Portal da Empresa / Microsoft Store ^(Python 3.12^) ou por python.org
    echo         e rode este arquivo de novo. Detalhes: INSTALACAO.md, passo 1.
    echo.
    pause
    exit /b 1
)
for /f "delims=" %%v in ('%PY% -c "import sys; print(sys.version.split()[0])"') do set "VERSAO=%%v"
echo  [1/4] Python %VERSAO% encontrado ^(%PY%^)

if exist ".venv\Scripts\python.exe" (
    echo  [2/4] Ambiente .venv ja existe
) else (
    echo  [2/4] Criando o ambiente .venv ...
    %PY% -m venv .venv
    if errorlevel 1 (
        echo  [ERRO] Nao consegui criar o .venv. Veja INSTALACAO.md, Problemas comuns.
        pause
        exit /b 1
    )
)
set "VPY=%CD%\.venv\Scripts\python.exe"

if exist "pacotes\*.whl" (
    echo  [3/4] Instalando o PySide6 da pasta "pacotes" ^(sem internet^) ...
    "%VPY%" -m pip install --no-index --find-links pacotes -r requirements.txt
) else (
    echo  [3/4] Instalando o PySide6 pela internet ^(uns 200 MB, pode demorar^) ...
    "%VPY%" -m pip install --disable-pip-version-check -r requirements.txt
)
if errorlevel 1 (
    echo.
    echo  [ERRO] A instalacao do PySide6 falhou.
    echo         Se a rede da empresa bloqueia o pip, use o plano B: INSTALACAO.md, passo 3B.
    pause
    exit /b 1
)

echo  [4/4] Conferindo ...
echo.
"%VPY%" app.py verificar
echo.
choice /c SN /n /m " Criar o atalho na Area de Trabalho? [S/N] "
if errorlevel 2 goto inicializar
"%VPY%" app.py atalho

:inicializar
choice /c SN /n /m " Abrir o app sozinho ao ligar o computador? [S/N] "
if errorlevel 2 goto fim
"%VPY%" app.py iniciar-com-windows sim

:fim
echo.
echo  Pronto. Para abrir: atalho "Produtividade" ou dois cliques em iniciar.bat
echo.
pause
