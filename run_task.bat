@echo off
chcp 65001 >nul
cd /d "%~dp0"

"%~dp0python\python.exe" "%~dp0main.py" >> "%~dp0task.log" 2>&1
