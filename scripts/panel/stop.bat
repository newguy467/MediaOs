@echo off
call "%~dp0_common.bat"
set "COMPOSE_FILE=%~1"
if "%COMPOSE_FILE%"=="" set "COMPOSE_FILE=docker-compose.yml"
cd /d "%REPO_ROOT%"

echo ============================================================
echo   MediaOS - Stop   (%COMPOSE_FILE%)
echo ============================================================
echo.
echo Stopping MediaOS ...
docker compose -f %COMPOSE_FILE% down
if errorlevel 1 goto :fail

echo.
echo Stopped. Your data (Postgres volume, media paths) is untouched.
goto :end

:fail
echo.
echo [FAILED] see errors above.

:end
popd
pause
exit /b 0
