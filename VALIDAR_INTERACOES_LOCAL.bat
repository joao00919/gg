@echo off
setlocal
cd /d "%~dp0"
title ZENYX 4.3.18 - Validacao de Interacoes

if exist ".venv\Scripts\python.exe" (
  call ".venv\Scripts\activate.bat"
  python VALIDAR_INTERACOES_LOCAL.py
) else (
  python VALIDAR_INTERACOES_LOCAL.py
)

set "EXIT_CODE=%ERRORLEVEL%"
echo.
if "%EXIT_CODE%"=="0" (
  echo VALIDACAO CONCLUIDA SEM ERROS.
) else (
  echo A VALIDACAO FALHOU. Veja o erro acima.
)
pause
exit /b %EXIT_CODE%
