#!/usr/bin/env bash
set -euo pipefail

# 一键部署脚本：创建虚拟环境、安装后端依赖、构建前端、用 pm2 拉起 uvicorn。

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT"
FRONT_DIR="$ROOT/preact-terminal"
VENV_DIR="$ROOT/.venv"
CACHE_DIR="$ROOT/.deploy-cache"
APP_ENV="${APP_ENV:-prod}"
LOG_ALL_PRINTS="${LOG_ALL_PRINTS:-0}"
PORT="${PORT:-3008}"
PM2_NAME="${PM2_NAME:-a-share-api}"
TARGET_ENV="${TARGET_ENV:-server}"
LOCAL_PYTHON_BIN="${LOCAL_PYTHON_BIN:-python3.13}"
SERVER_PYTHON_BIN="${SERVER_PYTHON_BIN:-/usr/local/python3.10/bin/python3.10}"
PYTHON_BIN="${PYTHON_BIN:-}"
SKIP_FRONTEND_BUILD="${SKIP_FRONTEND_BUILD:-0}"

if [[ -z "$PYTHON_BIN" ]]; then
  if [[ "$TARGET_ENV" == "local" ]]; then
    PYTHON_BIN="$LOCAL_PYTHON_BIN"
  else
    PYTHON_BIN="$SERVER_PYTHON_BIN"
  fi
fi

echo ">>> 部署环境: TARGET_ENV=${TARGET_ENV}, APP_ENV=${APP_ENV}, PORT=${PORT}, LOG_ALL_PRINTS=${LOG_ALL_PRINTS}"

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || { echo "缺少依赖: $1" >&2; exit 1; }
}

need_cmd "$PYTHON_BIN"
need_cmd node
need_cmd npm
need_cmd pm2

hash_file() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  else
    shasum -a 256 "$1" | awk '{print $1}'
  fi
}

get_py_ver() {
  "$1" - <<'PY'
import sys
print(f"{sys.version_info[0]}.{sys.version_info[1]}")
PY
}

ensure_cache_dir() {
  mkdir -p "$CACHE_DIR"
}

"$PYTHON_BIN" - <<'PY'
import sys
if sys.version_info < (3, 8):
    ver = ".".join(map(str, sys.version_info[:3]))
    raise SystemExit(f"Python 版本过低: {ver}，需 3.8+")
PY

echo ">>> 建立/激活虚拟环境"
FORCE_PIP_INSTALL="0"
DESIRED_PY_VER="$(get_py_ver "$PYTHON_BIN")"
if [[ -d "$VENV_DIR" && -x "$VENV_DIR/bin/python" ]]; then
  VENV_PY_VER="$(get_py_ver "$VENV_DIR/bin/python")"
  if [[ "$VENV_PY_VER" != "$DESIRED_PY_VER" ]]; then
    echo ">>> 虚拟环境 Python 版本不匹配: ${VENV_PY_VER} -> ${DESIRED_PY_VER}，重建 .venv"
    rm -rf "$VENV_DIR"
    FORCE_PIP_INSTALL="1"
  fi
fi
if [[ ! -d "$VENV_DIR" ]]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
  FORCE_PIP_INSTALL="1"
fi
source "$VENV_DIR/bin/activate"
pip install --upgrade pip
ensure_cache_dir
REQ_HASH_FILE="$CACHE_DIR/requirements.sha256"
NEW_REQ_HASH="$(hash_file "$BACKEND_DIR/requirements.txt")"
OLD_REQ_HASH=""
if [[ -f "$REQ_HASH_FILE" ]]; then
  OLD_REQ_HASH="$(cat "$REQ_HASH_FILE")"
fi
if [[ "$FORCE_PIP_INSTALL" == "1" || "$NEW_REQ_HASH" != "$OLD_REQ_HASH" ]]; then
  echo ">>> 安装后端依赖 (requirements 变更)"
  pip install -r "$BACKEND_DIR/requirements.txt"
  echo "$NEW_REQ_HASH" > "$REQ_HASH_FILE"
else
  echo ">>> 后端依赖无变化，跳过 pip install"
fi
if [[ ! -x "$VENV_DIR/bin/uvicorn" ]]; then
  echo ">>> 未发现 uvicorn，可执行文件，重新安装依赖"
  pip install -r "$BACKEND_DIR/requirements.txt"
fi

echo ">>> 构建前端 (Vite + Preact)"
if [[ "$SKIP_FRONTEND_BUILD" != "1" ]]; then
  cd "$FRONT_DIR"
  ensure_cache_dir
  PKG_HASH_FILE="$CACHE_DIR/package-lock.sha256"
  NEW_PKG_HASH="$(hash_file "$FRONT_DIR/package-lock.json")"
  OLD_PKG_HASH=""
  if [[ -f "$PKG_HASH_FILE" ]]; then
    OLD_PKG_HASH="$(cat "$PKG_HASH_FILE")"
  fi
  if [[ "$NEW_PKG_HASH" != "$OLD_PKG_HASH" || ! -d "$FRONT_DIR/node_modules" ]]; then
    echo ">>> 安装前端依赖 (lock 变更)"
    npm ci
    echo "$NEW_PKG_HASH" > "$PKG_HASH_FILE"
  else
    echo ">>> 前端依赖无变化，跳过 npm ci"
  fi
  if [[ -n "${VITE_API_BASE_URL:-}" ]]; then
    echo ">>> 前端 API 基地址: ${VITE_API_BASE_URL}"
    export VITE_API_BASE_URL
  fi
  npm run build
  cd "$BACKEND_DIR"
else
  echo ">>> 跳过前端构建 (SKIP_FRONTEND_BUILD=1)"
fi

echo ">>> 启动/重启后端 (pm2 + uvicorn)"
# 使用 --interpreter none 让 pm2 直接执行 uvicorn 二进制
if pm2 describe "$PM2_NAME" >/dev/null 2>&1; then
  ensure_cache_dir
  PM2_PORT_FILE="$CACHE_DIR/pm2.port"
  OLD_PM2_PORT=""
  if [[ -f "$PM2_PORT_FILE" ]]; then
    OLD_PM2_PORT="$(cat "$PM2_PORT_FILE")"
  fi
  if [[ "$OLD_PM2_PORT" != "$PORT" ]]; then
    echo ">>> 端口变化: ${OLD_PM2_PORT:-<empty>} -> ${PORT}，重建 pm2 进程"
    pm2 delete "$PM2_NAME" >/dev/null 2>&1 || true
    APP_ENV="$APP_ENV" PORT="$PORT" LOG_ALL_PRINTS="$LOG_ALL_PRINTS" pm2 start "$VENV_DIR/bin/uvicorn" \
      --name "$PM2_NAME" \
      --cwd "$BACKEND_DIR" \
      --interpreter none \
      -- backend.server:app --host 0.0.0.0 --port "$PORT"
    echo "$PORT" > "$PM2_PORT_FILE"
  else
    APP_ENV="$APP_ENV" PORT="$PORT" LOG_ALL_PRINTS="$LOG_ALL_PRINTS" pm2 restart "$PM2_NAME" --update-env
  fi
else
  APP_ENV="$APP_ENV" PORT="$PORT" LOG_ALL_PRINTS="$LOG_ALL_PRINTS" pm2 start "$VENV_DIR/bin/uvicorn" \
    --name "$PM2_NAME" \
    --cwd "$BACKEND_DIR" \
    --interpreter none \
    -- backend.server:app --host 0.0.0.0 --port "$PORT"
  ensure_cache_dir
  echo "$PORT" > "$CACHE_DIR/pm2.port"
fi

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
