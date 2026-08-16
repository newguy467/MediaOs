@echo off
call "%~dp0_common.bat"
echo ============================================================
echo   MediaOS - Alembic reversibility check (see docs\ALEMBIC_CI.md)
echo ============================================================
echo.
echo Proves migrations aren't one-way traps: upgrade head, downgrade -1,
echo upgrade head again, on a throwaway sqlite file.
echo.

cd /d "%REPO_ROOT%"
if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
) else (
    echo [WARN] No .venv found - run 03_install_backend.bat first if this fails.
)

set "DATABASE_URL=sqlite:///./ci-migrate.db"
if exist "ci-migrate.db" del /q "ci-migrate.db"
echo Using DATABASE_URL=%DATABASE_URL%
echo.

echo [1/3] alembic upgrade head ...
python -m alembic upgrade head
if errorlevel 1 goto :fail

echo.
echo [2/3] alembic downgrade -1 ...
python -m alembic downgrade -1
if errorlevel 1 goto :fail

echo.
echo [3/3] alembic upgrade head (re-apply) ...
python -m alembic upgrade head
if errorlevel 1 goto :fail

if exist "ci-migrate.db" del /q "ci-migrate.db"
echo.
echo [OK] Migrations are reversible.
goto :end

:fail
echo.
echo [FAILED] Alembic round-trip failed - see output above.
if exist "ci-migrate.db" del /q "ci-migrate.db"
popd
pause
exit /b 1

:end
popd
pause
exit /b 0
