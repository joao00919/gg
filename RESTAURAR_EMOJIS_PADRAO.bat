@echo off
setlocal
cd /d "%~dp0"
title ZYNEX Systems 4.2.6 - Restaurar Emojis Padrao
set SYNC_APPLICATION_EMOJIS=true
echo Restaurando e sincronizando os emojis padrao do bot...
echo O bot podera reiniciar automaticamente ao concluir a sincronizacao.
python bot.py
pause
