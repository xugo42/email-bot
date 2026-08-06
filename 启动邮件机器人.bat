@echo off
chcp 65001 >nul
cd /d "%~dp0"
python -c "import imapclient, requests" 2>nul || python -m pip install -r requirements.txt
python mail_bot.py
pause
