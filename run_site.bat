@echo off
cd /d C:\Users\HP\Desktop\Football_fantasy
set DEBUG=False
C:\Users\HP\anaconda3\python.exe manage.py collectstatic --noinput
C:\Users\HP\anaconda3\python.exe -m waitress --listen=127.0.0.1:8000 config.wsgi:application
pause