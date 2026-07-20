@echo off
setlocal
cd /d "%~dp0"
title ZYNEX Systems 4.2.6 - Diagnostico

if not exist ".venv\Scripts\python.exe" (
  echo Execute primeiro: INSTALAR_LOCAL.bat
  pause
  exit /b 1
)

call ".venv\Scripts\activate.bat"
python bot.py --check
set "EXIT_CODE=%ERRORLEVEL%"
pause
exit /b %EXIT_CODE%
