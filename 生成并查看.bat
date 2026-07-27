@echo off
chcp 65001 >nul
cd /d "C:\Users\dengyufan\Documents\Default Project\competitor_briefing"

python main.py

:: 运行完成后用 Edge 打开简报页面。
start msedge "file:///%CD%\edge-extension\briefing.html"

pause
