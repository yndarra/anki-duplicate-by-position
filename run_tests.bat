@echo off
chcp 65001 >nul
rem Тесты логики на временной коллекции Anki (нужна .venv с пакетом anki)
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    py -3.12 -m venv .venv
    .venv\Scripts\python -m pip install anki
)
.venv\Scripts\python -m unittest discover -s tests -v
pause
