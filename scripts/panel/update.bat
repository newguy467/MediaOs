@echo off
call "%~dp0_common.bat"
set "COMPOSE_FILE=%~1"
if "%COMPOSE_FILE%"=="" set "COMPOSE_FILE=docker-compose.yml"
cd /d "%REPO_ROOT%"

echo ============================================================
echo   MediaOS - Update   (%COMPOSE_FILE%)
echo ============================================================
echo.

where git >nul 2>nul
if not errorlevel 1 (
    echo Pulling latest source ...
    git pull
    echo.
) else (
    echo [INFO] git not found on PATH - skipping source pull.
    echo.
)

echo Rebuilding and restarting containers ...
docker compose -f %COMPOSE_FILE% up -d --build
if errorlevel 1 goto :fail

echo.
echo Update complete.
goto :end

:fail
echo.
echo [FAILED] update did not complete - see errors above.

:end
popd
pause
exit /b 0
