@echo off
call "%~dp0_common.bat"
echo ============================================================
echo   MediaOS - Run backend tests (pytest)
echo ============================================================
echo.

cd /d "%REPO_ROOT%"
if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
) else (
    echo [WARN] No .venv found - run 03_install_backend.bat first if this fails.
)

REM Same DATABASE_URL pattern .github\workflows\ci.yml uses for the unit
REM test job - an isolated on-disk sqlite file, not the dev Postgres DB.
if not defined DATABASE_URL set "DATABASE_URL=sqlite:///./mediaos-test.db"
echo Using DATABASE_URL=%DATABASE_URL%
echo.

python -m pytest tests\ -q --tb=short
if errorlevel 1 goto :fail

echo.
echo [OK] Tests passed.
goto :end

:fail
echo.
echo [FAILED] One or more tests failed - see output above.
popd
pause
exit /b 1

:end
popd
pause
exit /b 0
