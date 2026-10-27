@echo off
rem Roda os testes automaticos (inclusive os da interface, sem abrir janelas)
cd /d "%~dp0"
set "VPY=python"
if exist ".venv\Scripts\python.exe" set "VPY=.venv\Scripts\python.exe"
"%VPY%" -m unittest discover -s testes -t .
echo.
pause
