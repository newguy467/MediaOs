@echo off
call "%~dp0_common.bat"
echo ============================================================
echo   MediaOS - Docker Compose up (full stack, Postgres included)
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
    echo [WARN] .env needs a real POSTGRES_PASSWORD before this will start.
    echo        scripts\generate_secrets.sh is a POSIX script (needs WSL /
    echo        git-bash on Windows^). Generating one right here instead:
    for /f "delims=" %%P in ('python -c "import secrets; print(secrets.token_hex(32))"') do set "GEN_PW=%%P"
    if defined GEN_PW (
        powershell -NoProfile -Command "(Get-Content '.env') -replace 'POSTGRES_PASSWORD=.*', 'POSTGRES_PASSWORD=%GEN_PW%' | Set-Content '.env'"
        echo        Generated POSTGRES_PASSWORD and wrote it into .env.
    ) else (
        echo        Could not generate one automatically - edit .env by hand
        echo        and set POSTGRES_PASSWORD before continuing.
        goto :fail
    )
    echo.
)

echo Which compose file?
echo   1^) docker-compose.yml            (default)
echo   2^) docker-compose.standalone.yml (all-in-one, no external *arr apps)
echo   3^) docker-compose.nvidia.yml     (NVIDIA GPU transcode)
echo   4^) docker-compose.amd.yml        (AMD GPU transcode)
echo   5^) docker-compose.intel.yml      (Intel QSV transcode)
set /p COMPOSE_CHOICE="Choice [1-5, default 1]: "
if "%COMPOSE_CHOICE%"=="2" set "COMPOSE_FILE=docker-compose.standalone.yml"
if "%COMPOSE_CHOICE%"=="3" set "COMPOSE_FILE=docker-compose.nvidia.yml"
if "%COMPOSE_CHOICE%"=="4" set "COMPOSE_FILE=docker-compose.amd.yml"
if "%COMPOSE_CHOICE%"=="5" set "COMPOSE_FILE=docker-compose.intel.yml"
if not defined COMPOSE_FILE set "COMPOSE_FILE=docker-compose.yml"

echo.
echo Using %COMPOSE_FILE% ...
docker compose -f %COMPOSE_FILE% up --build
if errorlevel 1 goto :fail

goto :end

:fail
echo.
echo [FAILED] docker compose did not start successfully.
popd
pause
exit /b 1

:end
popd
pause
exit /b 0
