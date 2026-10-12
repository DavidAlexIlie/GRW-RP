@echo off
rem Build GRWRP from source (Windows, Python 3.10+).
cd /d "%~dp0"
python -m pip install -r requirements.txt || exit /b 1
python make_icon.py . || exit /b 1
python -m PyInstaller --noconfirm --onedir --windowed --name GRWRP --icon icon.ico ^
  --add-data "icon.ico;." --add-data "holster_cache.json;." --add-data "logos;logos" ^
  --hidden-import render_thumbs --exclude-module tkinter --exclude-module PySide6.QtNetwork ^
  --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.QtQml --exclude-module PySide6.QtQuick ^
  --exclude-module PySide6.Qt3DCore --exclude-module PySide6.QtMultimedia app.py || exit /b 1
echo.
echo Built: dist\GRWRP\GRWRP.exe
rem Run without building:  python app.py
