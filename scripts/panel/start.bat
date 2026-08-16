@echo off
call "%~dp0_common.bat"
set "COMPOSE_FILE=%~1"
if "%COMPOSE_FILE%"=="" set "COMPOSE_FILE=docker-compose.yml"
echo ============================================================
echo   MediaOS - Start   (%COMPOSE_FILE%)
echo ============================================================
echo.

where docker >nul 2>nul
if errorlevel 1 (
    echo [ERROR] docker was not found on PATH. Install Docker Desktop first:
    echo         https://www.docker.com/products/docker-desktop/
    goto :fail
)

cd /d "%REPO_ROOT%"

if not exist ".env" (
    echo No .env found - creating one from .env.example ...
    copy /y ".env.example" ".env" >nul
    echo.
    echo [INFO] Generating a POSTGRES_PASSWORD for you ...
    for /f "delims=" %%P in ('python -c "import secrets; print(secrets.token_hex(32))" 2^>nul') do set "GEN_PW=%%P"
    if defined GEN_PW (
        powershell -NoProfile -Command "(Get-Content '.env') -replace 'POSTGRES_PASSWORD=.*', 'POSTGRES_PASSWORD=%GEN_PW%' | Set-Content '.env'"
        echo        Generated POSTGRES_PASSWORD and wrote it into .env.
    ) else (
        echo        [WARN] Could not auto-generate one - edit .env by hand and
        echo               set POSTGRES_PASSWORD before continuing.
        goto :fail
    )
    echo.
)

echo Starting %COMPOSE_FILE% in the background ...
docker compose -f %COMPOSE_FILE% up -d
if errorlevel 1 goto :fail

echo.
echo MediaOS is starting. Give it a few seconds, then click
echo "Open MediaOS UI" or "Health Check" in the control panel.
goto :end

:fail
echo.
echo [FAILED] docker compose did not start successfully - see errors above.
popd
pause
exit /b 1

:end
popd
pause
exit /b 0
