@echo off
rem ============================================================
rem  Plano B (sem pip na rede da empresa):
rem  rode ESTE arquivo num Windows com internet e Python 3.11+.
rem  Ele baixa o PySide6 para a pasta "pacotes". Copie a pasta do app
rem  inteira (com "pacotes") para o computador do trabalho e rode instalar.bat.
rem ============================================================
setlocal
cd /d "%~dp0"
set "PY=python"
where py >nul 2>nul && set "PY=py -3"
echo Baixando PySide6 para a pasta "pacotes" ...
%PY% -m pip download -r requirements.txt -d pacotes --only-binary=:all: --platform win_amd64 --python-version 3.11
if errorlevel 1 (
    echo [ERRO] O download falhou. Confira a internet e o Python.
    pause
    exit /b 1
)
echo.
echo Pronto. Leve a pasta inteira do app, com a subpasta "pacotes", para o computador do trabalho.
pause
