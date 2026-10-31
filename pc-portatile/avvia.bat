@echo off
rem Avvio di Portatile con doppio clic (Windows).
chcp 65001 >nul
title Portatile
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 goto senza_python

python pc.py
pause
exit /b

:senza_python
echo Python non trovato.
echo Installalo da python.org e, nella prima schermata, spunta "Add Python to PATH".
pause
exit /b 1
