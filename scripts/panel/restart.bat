@echo off
call "%~dp0_common.bat"
set "COMPOSE_FILE=%~1"
if "%COMPOSE_FILE%"=="" set "COMPOSE_FILE=docker-compose.yml"
cd /d "%REPO_ROOT%"

echo ============================================================
echo   MediaOS - Restart   (%COMPOSE_FILE%)
echo ============================================================
echo.
docker compose -f %COMPOSE_FILE% restart
if errorlevel 1 goto :fail

echo.
echo Restarted.
goto :end

:fail
echo.
echo [FAILED] see errors above.

:end
popd
pause
exit /b 0
