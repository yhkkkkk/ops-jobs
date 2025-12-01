@echo off
echo ========================================
echo Stop Django Services
echo ========================================
echo.

echo Stopping services on ports 8000 and 8001...

for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING') do (
    echo Killing process %%a on port 8000
    taskkill /PID %%a /F >nul 2>&1
)

for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8001 ^| findstr LISTENING') do (
    echo Killing process %%a on port 8001
    taskkill /PID %%a /F >nul 2>&1
)

echo Stopping Celery workers...
wmic process where "commandline like '%%celery%%worker%%'" delete >nul 2>&1

echo Closing service windows...
taskkill /FI "WINDOWTITLE eq Django WSGI*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Django ASGI*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Celery Worker*" /F >nul 2>&1

echo.
echo All services stopped!
echo.
pause
