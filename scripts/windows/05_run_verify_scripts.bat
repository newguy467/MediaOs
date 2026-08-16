@echo off
call "%~dp0_common.bat"
echo ============================================================
echo   MediaOS - Verify scripts (version / UI static / lazy exports)
echo ============================================================
echo.
echo NOTE: package.json's own "verify"/"ci:local" npm scripts shell out to
echo "python3", which usually isn't on PATH on Windows (only "python" is).
echo This script calls the same three checks directly with "python"/"node"
echo instead, so it works out of the box on Windows.
echo.

cd /d "%REPO_ROOT%"
if exist ".venv\Scripts\activate.bat" call ".venv\Scripts\activate.bat"

echo [1/3] check_version.py ...
python scripts\check_version.py
if errorlevel 1 goto :fail

echo.
echo [2/3] check_ui_static.py ...
python scripts\check_ui_static.py
if errorlevel 1 goto :fail

echo.
echo [3/3] check_lazy_exports.mjs ...
where node >nul 2>nul
if errorlevel 1 (
    echo [WARN] node not found on PATH - skipping check_lazy_exports.mjs.
    goto :end
)
node scripts\check_lazy_exports.mjs
if errorlevel 1 goto :fail

echo.
echo [OK] All verify scripts passed.
goto :end

:fail
echo.
echo [FAILED] One or more verify scripts failed - see output above.
popd
pause
exit /b 1

:end
popd
pause
exit /b 0
