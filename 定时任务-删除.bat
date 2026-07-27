@echo off
chcp 65001 >nul

:: 删除每日竞品日报定时任务
:: 注意：请右键本文件，选择"以管理员身份运行"。

net session >nul 2>&1
if %errorlevel% neq 0 (
    echo 删除定时任务需要管理员权限。
    echo 请右键本文件，选择"以管理员身份运行"。
    pause
    exit /b 1
)

set "taskName=competitor-briefing-daily"

schtasks /delete /tn "%taskName%" /f

if %errorlevel% == 0 (
    echo 已删除定时任务：%taskName%
) else (
    echo 删除失败。任务可能不存在，或权限不足。
)

pause
