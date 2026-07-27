@echo off
chcp 65001 >nul

:: Check admin rights
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo ============================================================
    echo 创建定时任务需要管理员权限。
    echo 请右键本文件，选择"以管理员身份运行"。
    echo ============================================================
    pause
    exit /b 1
)

set "taskName=competitor-briefing-daily"
set "taskDir=C:\Users\dengyufan\Documents\Default Project\competitor_briefing"
set "runner=%taskDir%\run_task.bat"
:: Change this time if you want another schedule, e.g. 15:30
set "triggerTime=10:00"

:: Detect Python
set "pythonPath="
if exist "%~dp0python\python.exe" (
    set "pythonPath=%~dp0python\python.exe"
)
if not defined pythonPath if exist "C:\Program Files\Python3.14\python.exe" (
    set "pythonPath=C:\Program Files\Python3.14\python.exe"
)
if not defined pythonPath (
    for /f "delims=" %%i in ('where python 2^>nul') do (
        if not defined pythonPath set "pythonPath=%%i"
    )
)

if not defined pythonPath (
    echo ============================================================
    echo 未检测到 Python。
    echo 本项目已自带便携 Python，请确认项目目录下的 python\python.exe 存在。
    echo 或从 https://www.python.org/downloads/ 安装 Python 3.x。
    echo ============================================================
    pause
    exit /b 1
)

echo 已找到 Python：%pythonPath%
echo.

:: Generate run_task.bat
echo 正在生成 run_task.bat...
(
    echo @echo off
    echo chcp 65001 ^>nul
    echo cd /d "%~dp0"
    echo "%%~dp0python\python.exe" "%%~dp0main.py" ^>^> "%%~dp0task.log" 2^>^&1
) > "%runner%"

if %errorlevel% neq 0 (
    echo 生成 run_task.bat 失败。
    pause
    exit /b 1
)

:: Create scheduled task via PowerShell (supports StartWhenAvailable)
echo 正在创建定时任务：%taskName%，执行时间 %triggerTime%
powershell -ExecutionPolicy Bypass -File "%taskDir%\create_task.ps1" -TaskDir "%taskDir%" -Runner "%runner%" -TriggerTime "%triggerTime%"

if %errorlevel% equ 0 (
    echo.
    echo ============================================================
    echo 定时任务创建成功。
    echo 每天 %triggerTime% 自动生成简报；若电脑关机，开机后会自动补跑。
    echo.
    echo 下一步：
    echo 1. 打开 Edge，访问 edge://extensions/
    echo 2. 开启"开发人员模式"
    echo 3. 点击"加载解压缩的扩展"，选择：
    echo    %taskDir%\edge-extension
    echo ============================================================
) else (
    echo.
    echo ============================================================
    echo 定时任务创建失败。
    echo 请确认已使用管理员身份运行本脚本。
    echo ============================================================
)

pause
