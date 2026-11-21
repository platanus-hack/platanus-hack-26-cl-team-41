@echo off
cd /d "%~dp0"
.venv\Scripts\python.exe obstacle_curriculum.py --tests 2 --view
pause
