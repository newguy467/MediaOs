@echo off
REM -------------------------------------------------------------------------
REM _common.bat - shared header, `call`-ed at the top of every script in this
REM folder. NOT meant to be run directly.
REM
REM Sets:
REM   REPO_ROOT   - absolute path to the repo root (this folder is
REM                 <repo>\scripts\windows\, so it's two levels up)
REM   Console theme - black background, bright red text, matching the
REM                   dashboard.
REM -------------------------------------------------------------------------
color 0C
pushd "%~dp0..\.."
set "REPO_ROOT=%CD%"
title MediaOS Build Tools
exit /b 0
