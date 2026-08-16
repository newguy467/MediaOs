@echo off
call "%~dp0_common.bat"
echo ============================================================
echo   MediaOS - Run backend dev server (uvicorn, no Docker)
echo ============================================================
echo.
echo app\config.py has no sqlite default (Postgres only) - this uses a local
echo sqlite file so you can smoke-test without standing up Postgres. For a
echo production-like run with Postgres + all sidecar services, use
echo 08_docker_up.bat instead.
echo.

cd /d "%REPO_ROOT%"
if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
) else (
    echo [WARN] No .venv found - run 03_install_backend.bat first if this fails.
)

if not exist "app\static\index.html" (
    echo [WARN] app\static\index.html not found - the UI hasn't been built yet.
    echo        Run 02_build_frontend.bat first, or this will serve API-only.
    echo.
)

if not defined DATABASE_URL set "DATABASE_URL=sqlite:///./dev.db"
echo Using DATABASE_URL=%DATABASE_URL%
echo Once it starts, open http://127.0.0.1:8000 in your browser.
echo Press Ctrl+C in this window to stop the server.
echo.

python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

popd
pause
exit /b 0
