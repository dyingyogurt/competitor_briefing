@echo off
chcp 65001 >nul

:: 一键把本地仓库推到 GitHub
:: 运行前请先到 https://github.com/settings/tokens/new 创建 Token，只勾选 repo 即可。

set "repoUrl=https://github.com/dyingyogurt/competitor_briefing.git"

echo 仓库地址：%repoUrl%
echo.
set /p token="请输入 GitHub Personal Access Token："

if "%token%"=="" (
    echo Token 不能为空。
    pause
    exit /b 1
)

git branch -M main 2>nul
git remote remove origin 2>nul
git remote add origin https://dyingyogurt:%token%@github.com/dyingyogurt/competitor_briefing.git

echo.
echo 正在推送...
git push -u origin main

if %errorlevel% == 0 (
    echo.
    echo 推送成功。
    git remote set-url origin %repoUrl%
) else (
    echo.
    echo 推送失败，请检查 Token 是否正确，以及仓库是否已创建。
    git remote set-url origin %repoUrl%
)

pause
