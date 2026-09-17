@echo off
REM 一键启动前后端（开发模式）
REM 需要另开 Docker Desktop 并确保 TikTokDownloader / RapidOCRAPI 容器已启动

start "anan-backend" cmd /k "cd /d %~dp0backend && .venv\Scripts\activate && python run.py"
start "anan-frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo 前端: http://localhost:5173
echo 后端: http://localhost:8000/docs
