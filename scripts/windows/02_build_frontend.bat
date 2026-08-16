@echo off
call "%~dp0_common.bat"
echo ============================================================
echo   MediaOS - Build frontend (vite build -^> app\static\)
echo ============================================================
echo.

where npm >nul 2>nul
if errorlevel 1 (
    echo [ERROR] npm was not found on PATH. Install Node.js LTS first:
    echo         https://nodejs.org/
    goto :fail
)

cd /d "%REPO_ROOT%"
if not exist "node_modules" (
    echo [WARN] node_modules not found - run 01_install_frontend.bat first.
    echo        Attempting npm install now...
    call npm install
    if errorlevel 1 goto :fail
)

echo Running npm run build in %CD% ...
echo (vite.config.js build.outDir points at app\static, emptyOutDir: true -
echo  it wipes and refreshes that folder every run)
call npm run build
if errorlevel 1 goto :fail

echo.
echo Newest files in app\static\assets\ (should all be from just now):
dir /o-d /b "%REPO_ROOT%\app\static\assets" 2>nul | more +0

echo.
echo [OK] Frontend build complete.
goto :end

:fail
echo.
echo [FAILED] vite build did not complete successfully.
popd
pause
exit /b 1

:end
popd
pause
exit /b 0
