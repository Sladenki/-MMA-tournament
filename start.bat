@echo off
chcp 65001 >nul
cd /d "%~dp0"
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":8765" ^| findstr "LISTENING"') do taskkill /F /PID %%P >nul 2>&1
python -m pip install -q -r requirements.txt
python run.py
pause
