@echo off
call "%~dp0_common.bat"
set "COMPOSE_FILE=%~1"
if "%COMPOSE_FILE%"=="" set "COMPOSE_FILE=docker-compose.yml"
cd /d "%REPO_ROOT%"

set "PORT=8787"
if exist ".env" (
    for /f "tokens=2 delims==" %%P in ('findstr /b "MEDIAOS_HOST_PORT=" ".env" 2^>nul') do (
        if not "%%P"=="" set "PORT=%%P"
    )
)

echo ============================================================
echo   MediaOS - Health Check
echo ============================================================
echo.
echo Container status (%COMPOSE_FILE%):
docker compose -f %COMPOSE_FILE% ps
echo.
echo API health check - http://localhost:%PORT%/api/health
echo.
where curl >nul 2>nul
if errorlevel 1 (
    powershell -NoProfile -Command "try { (Invoke-WebRequest -UseBasicParsing -Uri 'http://localhost:%PORT%/api/health').Content } catch { Write-Host '[UNREACHABLE] MediaOS did not respond - is it running? Try Start first.' }"
) else (
    curl -s http://localhost:%PORT%/api/health
    if errorlevel 1 echo [UNREACHABLE] MediaOS did not respond - is it running? Try Start first.
)
echo.
echo.
popd
pause
exit /b 0
