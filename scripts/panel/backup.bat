@echo off
call "%~dp0_common.bat"
set "COMPOSE_FILE=%~1"
if "%COMPOSE_FILE%"=="" set "COMPOSE_FILE=docker-compose.yml"
cd /d "%REPO_ROOT%"

if not exist "backups" mkdir "backups"
for /f "delims=" %%T in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HHmmss"') do set "STAMP=%%T"
set "OUTDIR=backups\%STAMP%"
mkdir "%OUTDIR%"

echo ============================================================
echo   MediaOS - Backup   (%STAMP%)
echo ============================================================
echo.
echo Dumping Postgres database ...
docker compose -f %COMPOSE_FILE% exec -T mediaos-db pg_dump -U mediaos mediaos > "%OUTDIR%\mediaos-db.sql"
if errorlevel 1 (
    echo [WARN] Database dump failed - is MediaOS running? Continuing with
    echo        a config-only backup ^(.env^).
)

if exist ".env" copy /y ".env" "%OUTDIR%\.env" >nul

echo Zipping into backups\%STAMP%.zip ...
powershell -NoProfile -Command "Compress-Archive -Path '%OUTDIR%\*' -DestinationPath '%OUTDIR%.zip' -Force"
if errorlevel 1 goto :fail
rmdir /s /q "%OUTDIR%"

echo.
echo Backup saved to backups\%STAMP%.zip
goto :end

:fail
echo.
echo [FAILED] backup did not complete - see errors above. Raw files (if any)
echo          are left in %OUTDIR%.

:end
popd
pause
exit /b 0
