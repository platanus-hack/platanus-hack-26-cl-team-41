@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" arm_sim.py
if errorlevel 1 pause
