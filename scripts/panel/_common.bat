@echo off
REM -------------------------------------------------------------------------
REM _common.bat - shared header, `call`-ed at the top of every script in this
REM folder. NOT meant to be run directly.
REM
REM Sets:
REM   REPO_ROOT     - absolute path to the repo root (this folder is
REM                   <repo>\scripts\panel\, so it's two levels up)
REM   Console theme - black background, bright purple/magenta text, matching
REM                   MediaOS-Control-Panel.hta.
REM -------------------------------------------------------------------------
color 0D
pushd "%~dp0..\.."
set "REPO_ROOT=%CD%"
title MediaOS Control Panel
exit /b 0
