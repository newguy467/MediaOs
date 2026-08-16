@echo off
call "%~dp0_common.bat"
echo ============================================================
echo   MediaOS - Full local build ^& verify pipeline
echo ============================================================
echo   1. Install frontend deps    (01)
echo   2. Build frontend           (02)
echo   3. Install backend deps     (03)
echo   4. Check backend imports    (04)
echo   5. Run verify scripts       (05)
echo   6. Run tests                (06)
echo.
echo   Each step opens below and pauses when it finishes so you can read
echo   its output - press any key to move to the next step. Stops
echo   immediately if any step fails.
echo ============================================================
popd
pause

call "%~dp001_install_frontend.bat"
if errorlevel 1 goto :halted

call "%~dp002_build_frontend.bat"
if errorlevel 1 goto :halted

call "%~dp003_install_backend.bat"
if errorlevel 1 goto :halted

call "%~dp004_check_backend_imports.bat"
if errorlevel 1 goto :halted

call "%~dp005_run_verify_scripts.bat"
if errorlevel 1 goto :halted

call "%~dp006_run_tests.bat"
if errorlevel 1 goto :halted

color 0A
echo.
echo ============================================================
echo   [OK] Full pipeline passed - build is ready to ship.
echo ============================================================
pause
exit /b 0

:halted
color 0C
echo.
echo ============================================================
echo   [HALTED] Pipeline stopped - fix the error above and re-run.
echo ============================================================
pause
exit /b 1
