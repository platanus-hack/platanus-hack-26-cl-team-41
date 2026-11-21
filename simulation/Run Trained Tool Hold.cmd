@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" run_trained_skill.py --task tool-hold --view
if errorlevel 1 pause
