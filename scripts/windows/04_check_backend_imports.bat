@echo off
call "%~dp0_common.bat"
echo ============================================================
echo   MediaOS - Backend import check
echo ============================================================
echo.
echo py_compile only checks syntax. This actually imports app.main,
echo which catches missing packages, circular imports, and typos in
echo import paths that syntax checking alone can't see.
echo.

cd /d "%REPO_ROOT%"

if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
) else (
    echo [WARN] No .venv found - run 03_install_backend.bat first if this fails.
)

REM app/config.py has no sqlite default (postgres only) - override so this
REM check works without a running Postgres container, same pattern CI uses
REM (see .github/workflows/ci.yml, docs/ALEMBIC_CI.md).
if not defined DATABASE_URL set "DATABASE_URL=sqlite:///./dev.db"
echo Using DATABASE_URL=%DATABASE_URL%
echo.

python -c "import app.main; print('app.main imported OK')"
if errorlevel 1 goto :fail

echo.
echo [OK] Backend imports cleanly.
goto :end

:fail
echo.
echo [FAILED] app.main failed to import - see the traceback above.
popd
pause
exit /b 1

:end
popd
pause
exit /b 0
