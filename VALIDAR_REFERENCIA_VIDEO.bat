@echo off
setlocal
cd /d "%~dp0"
echo ==============================================
echo ZENYX 4.3.18 - VALIDACAO DA REFERENCIA EM VIDEO
echo ==============================================
python -m pytest -q
if errorlevel 1 goto :erro
python bot.py --check
if errorlevel 1 goto :erro
echo.
echo VALIDACAO CONCLUIDA COM SUCESSO.
pause
exit /b 0
:erro
echo.
echo A VALIDACAO ENCONTROU UM ERRO. CONSULTE A MENSAGEM ACIMA.
pause
exit /b 1
