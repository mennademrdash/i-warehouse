@echo off

cd /d "E:\dema D\i warehouse"

start "Flask 5001" cmd /k "call venv\Scripts\activate && set PORT=5001 && python app.py"

timeout /t 2 /nobreak >nul

start "Flask 5002" cmd /k "call venv\Scripts\activate && set PORT=5002 && python app.py"

timeout /t 2 /nobreak >nul

start "Flask 5003" cmd /k "call venv\Scripts\activate && set PORT=5003 && python app.py"

timeout /t 3 /nobreak >nul

start "Nginx" cmd /k "cd /d C:\nginx-1.30.4 && nginx.exe"

echo.
echo ==============================
echo   i-Warehouse Server Started
echo ==============================
echo Flask 1: http://127.0.0.1:5001
echo Flask 2: http://127.0.0.1:5002
echo Flask 3: http://127.0.0.1:5003
echo Load Balancer: http://127.0.0.1:8088
echo ==============================

pause