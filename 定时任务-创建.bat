@echo off
chcp 65001 >nul

:: Create a daily scheduled task at 10:00 to generate the competitor briefing.
:: IMPORTANT: Right-click this file and choose "Run as administrator".

net session >nul 2>&1
if %errorlevel% neq 0 (
    echo This file must be run as administrator.
    echo Right-click it and choose "Run as administrator".
    pause
    exit /b 1
)

set "taskDir=C:\Users\dengyufan\Documents\Default Project\competitor_briefing"
set "runner=%taskDir%\run_task.bat"
set "triggerTime=10:00"

powershell -ExecutionPolicy Bypass -File "%taskDir%\create_task.ps1" -TaskDir "%taskDir%" -Runner "%runner%" -TriggerTime "%triggerTime%"

pause
