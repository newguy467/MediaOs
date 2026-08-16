@echo off
setlocal EnableExtensions
title MediaOS - Control Panel
cd /d "%~dp0"
color 0D

REM Direct launch into the GUI Control Panel (all day-to-day actions live
REM there: start/stop/restart, open UI, health check, logs, backup, update).
REM For building/testing from source, see scripts\windows\dashboard.bat instead.

if not exist "%~dp0MediaOS-Control-Panel.hta" (
  echo Missing MediaOS-Control-Panel.hta next to this launcher.
  pause
  exit /b 1
)

start "" mshta.exe "%~dp0MediaOS-Control-Panel.hta"
exit /b 0
