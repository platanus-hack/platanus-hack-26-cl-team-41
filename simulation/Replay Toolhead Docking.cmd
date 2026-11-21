@echo off
cd /d "%~dp0"
.venv\Scripts\python.exe dock_curriculum.py --tests 1 --view
pause
