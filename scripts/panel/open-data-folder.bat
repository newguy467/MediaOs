@echo off
call "%~dp0_common.bat"
cd /d "%REPO_ROOT%"

if not exist "data" mkdir "data"
start "" explorer "%REPO_ROOT%\data"
popd
exit /b 0
