@echo off
call "%~dp0_common.bat"
echo ============================================================
echo   MediaOS - Push current branch to origin
echo ============================================================
echo.

where git >nul 2>nul
if errorlevel 1 (
    echo [ERROR] git was not found on PATH. Install Git for Windows first:
    echo         https://git-scm.com/download/win
    goto :fail
)

cd /d "%REPO_ROOT%"

for /f "delims=" %%B in ('git rev-parse --abbrev-ref HEAD') do set "BRANCH=%%B"
echo Current branch: %BRANCH%
echo.

git status --short
echo.

set /p CONFIRM="Push '%BRANCH%' to origin now? [y/N]: "
if /i not "%CONFIRM%"=="y" (
    echo Cancelled - nothing pushed.
    goto :end
)

git push -u origin %BRANCH%
if errorlevel 1 goto :fail

echo.
echo [OK] Pushed. Open a PR at:
for /f "delims=" %%U in ('git remote get-url origin') do set "REMOTE_URL=%%U"
echo   %REMOTE_URL%
echo (compare/pull-request link depends on your host - GitHub shows one
echo  automatically in the push output above, or use the "Compare ^&
echo  pull request" button on the repo page.)
goto :end

:fail
echo.
echo [FAILED] git push did not complete successfully.
popd
pause
exit /b 1

:end
popd
pause
exit /b 0
