@echo off
chcp 65001 >nul
cd /d "%~dp0"
python -m pip install -q -r requirements.txt pyinstaller pillow
python tools\make_icon.py
python -m PyInstaller --noconfirm --clean secretary.spec
echo.
echo Готово: dist\Секретарь ММА.exe
echo Рядом с программой появится папка data — там хранится турнир.
pause
