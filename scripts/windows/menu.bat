@echo off
call "%~dp0_common.bat"
popd

:menu
cls
color 0C
echo ============================================================
echo             M E D I A O S   B U I L D   T O O L S
echo                  (console fallback menu)
echo ============================================================
echo.
echo   -- Frontend --
echo   [1] Install frontend dependencies      (npm install)
echo   [2] Build frontend                     (vite build)
echo.
echo   -- Backend --
echo   [3] Install backend dependencies       (pip install)
echo   [4] Check backend imports              (import app.main)
echo.
echo   -- Verify ^& Test --
echo   [5] Run verify scripts                 (version/UI-static/lazy)
echo   [6] Run tests                          (pytest)
echo   [9] Alembic reversibility check
echo.
echo   -- Run --
echo   [7] Run dev server                     (uvicorn, no Docker)
echo   [8] Docker Compose up                  (full stack)
echo.
echo   -- Ship --
echo   [10] Push branch to origin
echo.
echo   -- Everything --
echo   [99] Full build ^& verify pipeline      (01 -^> 06 in order)
echo.
echo   [D] Open the graphical dashboard instead (dashboard.hta)
echo   [Q] Quit
echo ============================================================
set "CHOICE="
set /p CHOICE="Choice: "

if /i "%CHOICE%"=="1"  (call "%~dp001_install_frontend.bat" & goto :menu)
if /i "%CHOICE%"=="2"  (call "%~dp002_build_frontend.bat" & goto :menu)
if /i "%CHOICE%"=="3"  (call "%~dp003_install_backend.bat" & goto :menu)
if /i "%CHOICE%"=="4"  (call "%~dp004_check_backend_imports.bat" & goto :menu)
if /i "%CHOICE%"=="5"  (call "%~dp005_run_verify_scripts.bat" & goto :menu)
if /i "%CHOICE%"=="6"  (call "%~dp006_run_tests.bat" & goto :menu)
if /i "%CHOICE%"=="7"  (call "%~dp007_run_dev_server.bat" & goto :menu)
if /i "%CHOICE%"=="8"  (call "%~dp008_docker_up.bat" & goto :menu)
if /i "%CHOICE%"=="9"  (call "%~dp009_alembic_ci_check.bat" & goto :menu)
if /i "%CHOICE%"=="10" (call "%~dp010_git_push_branch.bat" & goto :menu)
if /i "%CHOICE%"=="99" (call "%~dp099_full_build_all.bat" & goto :menu)
if /i "%CHOICE%"=="D"  (start "" mshta.exe "%~dp0dashboard.hta" & goto :menu)
if /i "%CHOICE%"=="Q"  exit /b 0

echo Unrecognized choice.
pause
goto :menu
