@echo off
cd /d "%~dp0"
python -c "import imapclient, requests, pystray, PIL" 2>nul || python -m pip install -r requirements.txt
start "" pythonw mail_bot_tray.py
