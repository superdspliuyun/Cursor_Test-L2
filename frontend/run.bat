@echo off
REM 启动前端服务
cd /d %~dp0

echo Installing dependencies...
call npm install

echo Starting Vite dev server...
call npm run dev

pause
