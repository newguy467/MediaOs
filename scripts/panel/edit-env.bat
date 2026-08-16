@echo off
call "%~dp0_common.bat"
cd /d "%REPO_ROOT%"

if not exist ".env" (
    echo No .env found - creating one from .env.example ...
    copy /y ".env.example" ".env" >nul
)

start "" notepad ".env"
popd
exit /b 0
