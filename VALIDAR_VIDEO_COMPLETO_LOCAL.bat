@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" VALIDAR_VIDEO_COMPLETO_LOCAL.py
) else (
  python VALIDAR_VIDEO_COMPLETO_LOCAL.py
)
pause
