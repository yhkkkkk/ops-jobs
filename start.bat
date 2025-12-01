@echo off
echo ========================================
echo Django Services Launcher
echo ========================================
echo.

if not exist "manage.py" (
    echo Error: Please run in project root directory
    pause
    exit /b 1
)

echo Starting Django WSGI Server on port 8000...
start "Django WSGI" cmd /k "uv run python manage.py runserver 127.0.0.1:8000"

timeout /t 3 /nobreak >nul

echo Starting Django ASGI Server on port 8001...
start "Django ASGI" cmd /k "uv run python -m daphne -b 127.0.0.1 -p 8001 ops_job.asgi:application"

timeout /t 3 /nobreak >nul

echo Starting Celery Worker...
start "Celery Worker" cmd /k "uv run celery -A ops_job worker --loglevel=info --pool=threads --concurrency=2 --without-gossip --without-mingle --without-heartbeat"

echo.
echo All services started in separate windows!
echo.
echo Services:
echo - Django WSGI: http://127.0.0.1:8000
echo - Django ASGI: http://127.0.0.1:8001
echo - Admin Panel: http://127.0.0.1:8000/admin/
echo - API Docs: http://127.0.0.1:8000/docs/swagger/
echo.
echo To stop services: close the command windows or run stop.bat
echo.
pause
