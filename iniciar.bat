@echo off
rem Abre o app sem janela de terminal (usa o .venv criado pelo instalar.bat, se existir)
cd /d "%~dp0"
if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" app.py
) else (
    start "" pythonw app.py
)
