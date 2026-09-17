#!/usr/bin/env bash
# 一键启动前后端（开发模式，Git Bash 用）
cd "$(dirname "$0")"

(cd backend && ./.venv/Scripts/python.exe run.py) &
(cd frontend && npm run dev) &

echo "前端: http://localhost:5173"
echo "后端: http://localhost:8000/docs"
wait
