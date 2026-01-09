# 部署指南（Linux / pm2 / Nginx）

## 目录结构
- `backend/server.py`：FastAPI + APScheduler，写每日 JSON（`data/YYYY-MM-DD.json`）
- `config/`：按环境分离的配置文件（`dev.json` / `prod.json`），已被 `.gitignore` 忽略
- `data/`：生成的日报 JSON（日期命名）
- `preact-terminal/`：前端工程（Vite + Preact）

## 依赖
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cd stock-analysis/preact-terminal
npm install
```

## 一键部署脚本（deploy.sh）
脚本会缓存依赖指纹，避免重复安装；缓存目录为 `.deploy-cache/`。
常用环境变量：
- `SKIP_FRONTEND_BUILD=1`：跳过前端依赖安装与构建
- `VITE_API_BASE_URL=...`：注入前端 API 基地址
- `APP_ENV=prod`：选择配置文件（默认 `dev`）
- `LOG_ALL_PRINTS=1`：将 print 输出写入 `logs/YYYY-MM-DD.debug.log`
- `DEPLOY_NGINX=0`：服务器部署时跳过复制前端构建产物到 Nginx
- `NGINX_ROOT_DIR=...`：前端构建产物目标目录（默认 `/usr/share/nginx/html/stock-analysis`）
如需强制重装依赖，可删除 `.deploy-cache/` 与对应的 `.venv/` 或 `preact-terminal/node_modules/`。
pm2 启动参数不会随 `restart --update-env` 变化；脚本会记录上次端口到 `.deploy-cache/pm2.port`，端口变更时自动重建进程。
如需清理端口记录：删除 `.deploy-cache/pm2.port` 后重新运行 `./deploy.sh`。

## 快速使用
- 开发环境（默认）：`./deploy.sh`
- 线上环境：`./deploy.sh prod`

## 后端运行（pm2 管理）
假设代码路径 `/opt/a-share/stock-analysis`，监听 3008 端口：
```bash
cd /opt/a-share/stock-analysis
APP_ENV=prod pm2 start ".venv/bin/uvicorn backend.server:app --host 0.0.0.0 --port 3008" \
  --name a-share-api --interpreter /bin/bash --cwd /opt/a-share/stock-analysis

# 查看日志
pm2 logs a-share-api
```

## 前端构建 & 部署
```bash
cd stock-analysis/preact-terminal
npm run build   # 输出到 dist
```
前端构建时可通过环境变量指定 API 基地址：
```bash
VITE_API_BASE_URL=https://api.example.com ./deploy.sh
```
示例文件：
- `preact-terminal/.env.production`（生产默认）
- `preact-terminal/.env.staging`（预发示例）
- `preact-terminal/.env.example`（模板）
将 `dist/` 作为 Nginx 静态目录。示例 Nginx 配置（`/etc/nginx/conf.d/a-share.conf`）：
```
server {
    listen 80;
    server_name your.domain.com;

    root /opt/a-share/stock-analysis/preact-terminal/dist;
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:3008/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```
重载：`sudo nginx -t && sudo nginx -s reload`

## 配置与调度
- 环境变量：`APP_ENV=dev|prod`（默认 dev），决定读取 `config/{env}.json`
- 可选：`LOG_ALL_PRINTS=1` 时，将所有 `print(...)` 输出写入 `logs/YYYY-MM-DD.debug.log`
- 配置示例（`config/prod.json`，被忽略不随代码更新覆盖）：
```json
{
  "schedule_times": ["09:25", "12:30", "15:10"]
}
```
示例：开启全量日志输出
```bash
LOG_ALL_PRINTS=1 ./deploy.sh
```
- 修改调度（两种方式）：
  1) 直接编辑 `config/{env}.json` 并重启/重载服务（pm2 restart a-share-api）
  2) API：`POST /config`，Body: `{ "schedule_times": ["09:25","12:30"] }`
- 调度任务会在指定时间调用 `generate_report`，写入 `data/YYYY-MM-DD.json`

## 接口
- `GET /health`：健康检查
- `GET /report?date=YYYY-MM-DD`：读取指定日期 JSON；若不存在返回 404，前端提示手动触发
- `GET /report/raw?date=YYYY-MM-DD`：返回报告 JSON 原文（SSE/前端查看用）
- `GET /report/debug?date=YYYY-MM-DD`：返回调试日志原文（DEBUG_MODE 开启时生成）
- `GET /reports`：列出可用 JSON 文件名
- `POST /run`：手动触发生成（可带 `{ "date": "2026-01-08" }`），生成完即返回内容
- `GET /run/stream`：SSE 推送进度与结果（参数 `date=YYYY-MM-DD`）
- `GET /config` / `POST /config`：查看或更新调度时间

## 手动执行（不通过 API）
```bash
APP_ENV=prod python - <<'PY'
from backend.server import generate_report
generate_report()  # 默认当天
PY
```

## 运行策略与注意事项
- JSON 按日期命名保存在 `data/`，访问页面默认读取当天；若不存在提示手动触发
- `config/*.json` 与 `data/*.json` 已在 `.gitignore` 中，避免代码更新覆盖生产配置/数据
- 如果未安装 APScheduler，调度不会启用，但手动触发与 API 依旧可用
- 如需 HTTPS，在 Nginx 上加证书与 `listen 443 ssl` 配置
