@echo off
REM Buduje samodzielny KN5Converter.exe w folderze dist\
cd /d "%~dp0"
if not exist .venv python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-build.txt
.venv\Scripts\pyinstaller --noconfirm --clean --onefile --windowed --name KN5Converter gui.py
echo.
echo Gotowe: dist\KN5Converter.exe
