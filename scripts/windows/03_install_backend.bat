@echo off
call "%~dp0_common.bat"
echo ============================================================
echo   MediaOS - Install backend dependencies (pip)
echo ============================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] python was not found on PATH. Install Python 3.12 first:
    echo         https://www.python.org/downloads/
    goto :fail
)

cd /d "%REPO_ROOT%"

if defined VIRTUAL_ENV (
    echo Using already-active virtual environment: %VIRTUAL_ENV%
) else (
    if exist ".venv\Scripts\activate.bat" (
        echo Found existing .venv - activating it...
        call ".venv\Scripts\activate.bat"
    ) else (
        echo No .venv found - creating one now...
        python -m venv .venv
        if errorlevel 1 goto :fail
        call ".venv\Scripts\activate.bat"
    )
)

echo Installing requirements.txt + requirements-dev.txt ...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r requirements-dev.txt
if errorlevel 1 goto :fail

echo.
echo [OK] Backend dependencies installed into %VIRTUAL_ENV%
echo      Run 04_check_backend_imports.bat next.
goto :end

:fail
echo.
echo [FAILED] pip install did not complete successfully.
popd
pause
exit /b 1

:end
popd
pause
exit /b 0
