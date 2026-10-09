@echo off
cd /d C:\Users\HP\Desktop\Football_fantasy
C:\Users\HP\anaconda3\python.exe manage.py import_data
C:\Users\HP\anaconda3\python.exe manage.py import_stats
C:\Users\HP\anaconda3\python.exe manage.py update_points
C:\Users\HP\anaconda3\python.exe manage.py backup_db