@echo off
setlocal
cd /d "%~dp0"
title ZYNEX Systems 4.3.18 - Local

if not exist ".venv\Scripts\python.exe" (
  echo O ambiente virtual ainda nao foi criado.
  echo Execute primeiro: INSTALAR_LOCAL.bat
  pause
  exit /b 1
)

if not exist ".env" (
  copy /y ".env.example" ".env" >nul
  echo O arquivo .env foi criado.
  echo Preencha DISCORD_TOKEN, MAIN_GUILD_ID e BOT_OWNER_IDS antes de continuar.
  notepad .env
  pause
  exit /b 1
)

call ".venv\Scripts\activate.bat"
python bot.py
set "EXIT_CODE=%ERRORLEVEL%"

echo.
echo O ZYNEX Systems foi encerrado com codigo %EXIT_CODE%.
pause
exit /b %EXIT_CODE%
