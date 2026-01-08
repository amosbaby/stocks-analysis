#!/usr/bin/env bash
set -euo pipefail

# 一键部署脚本：创建虚拟环境、安装后端依赖、构建前端、用 pm2 拉起 uvicorn。

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT"
FRONT_DIR="$ROOT/preact-terminal"
VENV_DIR="$ROOT/.venv"
APP_ENV="${APP_ENV:-prod}"
PORT="${PORT:-8000}"
PM2_NAME="${PM2_NAME:-a-share-api}"

echo ">>> 部署环境: APP_ENV=${APP_ENV}, PORT=${PORT}"

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || { echo "缺少依赖: $1" >&2; exit 1; }
}

need_cmd python3
need_cmd node
need_cmd npm
need_cmd pm2

echo ">>> 建立/激活虚拟环境"
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"
pip install --upgrade pip
pip install fastapi uvicorn[standard] apscheduler pydantic

echo ">>> 构建前端 (Vite + Preact)"
cd "$FRONT_DIR"
npm install
npm run build
cd "$BACKEND_DIR"

echo ">>> 启动/重启后端 (pm2 + uvicorn)"
# 使用 --interpreter none 让 pm2 直接执行 uvicorn 二进制
APP_ENV="$APP_ENV" PORT="$PORT" pm2 delete "$PM2_NAME" >/dev/null 2>&1 || true
APP_ENV="$APP_ENV" PORT="$PORT" pm2 start "$VENV_DIR/bin/uvicorn" \
  --name "$PM2_NAME" \
  --cwd "$BACKEND_DIR" \
  --interpreter none \
  -- backend.server:app --host 0.0.0.0 --port "$PORT"

echo ">>> pm2 列表"
pm2 ls
echo ">>> pm2 日志 (按 Ctrl+C 退出查看)"
pm2 logs "$PM2_NAME" --lines 20

cat <<'NOTE'
---------------------------------------------------------
Nginx 静态目录: stock-analysis/preact-terminal/dist
反代 /api 到 http://127.0.0.1:PORT
示例配置详见 stock-analysis/DEPLOYMENT.md
---------------------------------------------------------
NOTE
