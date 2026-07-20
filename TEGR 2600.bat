@echo off
title TEGR 2600
cd /d "%~dp0"
python tegr2600_ui.py
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] TEGR 2600 failed to launch. Check Python/PyQt6 installation.
    pause
)
