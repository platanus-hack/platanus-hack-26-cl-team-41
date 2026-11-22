@echo off
where py >nul 2>nul
if errorlevel 1 (
    python "%~dp0camera_relay.py" %*
) else (
    py -3 "%~dp0camera_relay.py" %*
)
if errorlevel 1 pause
