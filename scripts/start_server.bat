@echo off
setlocal
cd /d "%~dp0.."
python -m uvicorn api_fastapi:app --host 127.0.0.1 --port 8000 --reload
endlocal
