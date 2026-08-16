@echo off
call "%~dp0_common.bat"
cd /d "%REPO_ROOT%"

set "PORT=8787"
if exist ".env" (
    for /f "tokens=2 delims==" %%P in ('findstr /b "MEDIAOS_HOST_PORT=" ".env" 2^>nul') do (
        if not "%%P"=="" set "PORT=%%P"
    )
)

echo Opening http://localhost:%PORT% ...
start "" "http://localhost:%PORT%"
popd
exit /b 0
