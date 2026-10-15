@echo off
REM Buduje samodzielny KN5Converter.exe w folderze dist\
if not exist .venv python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\pyinstaller --noconfirm --clean --onefile --windowed --name KN5Converter gui.py
