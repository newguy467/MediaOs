@echo off
REM -------------------------------------------------------------------------
REM dashboard.bat - double-click this to open the MediaOS Build Tools
REM dashboard: a red/black themed window with a button for every script in
REM this folder. It's a thin launcher for dashboard.hta (an "HTA" - a real
REM Windows GUI window, not a browser tab - .bat files alone can't draw
REM clickable buttons).
REM -------------------------------------------------------------------------
start "" mshta.exe "%~dp0dashboard.hta"
exit /b 0
