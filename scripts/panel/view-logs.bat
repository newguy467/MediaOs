@echo off
call "%~dp0_common.bat"
set "COMPOSE_FILE=%~1"
if "%COMPOSE_FILE%"=="" set "COMPOSE_FILE=docker-compose.yml"
cd /d "%REPO_ROOT%"

echo ============================================================
echo   MediaOS - Live Logs   (%COMPOSE_FILE%, Ctrl+C to stop)
echo ============================================================
echo.
docker compose -f %COMPOSE_FILE% logs -f --tail=200 mediaos

popd
pause
exit /b 0
