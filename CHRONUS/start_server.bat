@echo off
rem Start CHRONUS (API + website on http://127.0.0.1:8001) from wherever this file lives.
cd /d "%~dp0"
set "PY=python"
if exist "%~dp0..\venv\Scripts\python.exe" set "PY=%~dp0..\venv\Scripts\python.exe"
if exist "%~dp0venv\Scripts\python.exe" set "PY=%~dp0venv\Scripts\python.exe"
"%PY%" run_server.py %*
