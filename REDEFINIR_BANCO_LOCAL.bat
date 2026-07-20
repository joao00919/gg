@echo off
setlocal
cd /d "%~dp0"
title ZYNEX Systems 3.8.1 - Redefinir Banco Local

echo ATENCAO: isso apagara as configuracoes salvas no modo local.
choice /c SN /n /m "Deseja continuar? [S/N]: "
if errorlevel 2 exit /b 0

if not exist ".venv\Scripts\python.exe" (
  echo Execute primeiro: INSTALAR_LOCAL.bat
  pause
  exit /b 1
)

call ".venv\Scripts\activate.bat"
python bot.py --reset-local-data --check
pause
