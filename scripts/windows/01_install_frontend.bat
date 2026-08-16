@echo off
call "%~dp0_common.bat"
echo ============================================================
echo   MediaOS - Install frontend dependencies (npm install)
echo ============================================================
echo.
echo NOTE: package.json lives at the repo root (vite's "root: ui" option
echo just points at the source folder) - so this runs from %REPO_ROOT%,
echo NOT from ui\.
echo.

where npm >nul 2>nul
if errorlevel 1 (
    echo [ERROR] npm was not found on PATH. Install Node.js LTS first:
    echo         https://nodejs.org/
    goto :fail
)

cd /d "%REPO_ROOT%"
echo Running npm install in %CD% ...
call npm install
if errorlevel 1 goto :fail

echo.
echo [OK] Frontend dependencies installed.
goto :end

:fail
echo.
echo [FAILED] npm install did not complete successfully.
popd
pause
exit /b 1

:end
popd
pause
exit /b 0
