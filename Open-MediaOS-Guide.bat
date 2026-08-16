@echo off
cd /d "%~dp0"
if exist "%~dp0MediaOS-Guide.html" (
  start "" "%~dp0MediaOS-Guide.html"
) else (
  echo Missing MediaOS-Guide.html
  pause
)
exit /b 0
