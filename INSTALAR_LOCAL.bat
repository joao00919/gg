@echo off
setlocal
cd /d "%~dp0"
title ZYNEX Systems 4.3.18 - Instalacao Local

echo ==============================================
echo ZYNEX SYSTEMS 4.3.18 - INSTALACAO LOCAL
echo ==============================================
echo.

where py >nul 2>nul
if errorlevel 1 goto use_python

py -3.11 --version >nul 2>nul
if errorlevel 1 goto use_python
set "PYTHON_CMD=py -3.11"
goto python_ready

:use_python
where python >nul 2>nul
if errorlevel 1 (
  echo ERRO: Python nao foi encontrado.
  echo Instale o Python 3.11 e marque Add Python to PATH.
  pause
  exit /b 1
)
set "PYTHON_CMD=python"

:python_ready
if not exist ".venv\Scripts\python.exe" (
  echo [1/4] Criando ambiente virtual...
  %PYTHON_CMD% -m venv .venv
  if errorlevel 1 goto failed
) else (
  echo [1/4] Ambiente virtual ja existe.
)

call ".venv\Scripts\activate.bat"

echo [2/4] Atualizando pip...
python -m pip install --upgrade pip
if errorlevel 1 goto failed

echo [3/4] Instalando dependencias...
python -m pip install -r requirements.txt
if errorlevel 1 goto failed

if not exist ".env" (
  echo [4/4] Criando arquivo .env...
  copy /y ".env.example" ".env" >nul
) else (
  echo [4/4] Arquivo .env ja existe e foi preservado.
)

echo.
echo Executando diagnostico sem Discord e sem MongoDB...
python bot.py --check
if errorlevel 1 goto failed

echo.
echo INSTALACAO CONCLUIDA.
echo Agora abra o arquivo .env e preencha DISCORD_TOKEN, MAIN_GUILD_ID e BOT_OWNER_IDS.
echo Depois execute INICIAR_LOCAL.bat.
pause
exit /b 0

:failed
echo.
echo A instalacao falhou. Verifique o erro exibido acima.
pause
exit /b 1
