@echo off
cd /d "%~dp0"
echo Open http://127.0.0.1:8765/web/ after the server starts.
if exist "D:\DevTools\Miniconda3\python.exe" (
  "D:\DevTools\Miniconda3\python.exe" serve.py
) else (
  python serve.py
)
pause
