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
pip install fastapi uvicorn[standard] apscheduler pydantic

cd stock-analysis/preact-terminal
npm install
```

## 后端运行（pm2 管理）
假设代码路径 `/opt/a-share/stock-analysis`，监听 8000 端口：
```bash
cd /opt/a-share/stock-analysis
APP_ENV=prod pm2 start ".venv/bin/uvicorn backend.server:app --host 0.0.0.0 --port 8000" \
  --name a-share-api --interpreter /bin/bash --cwd /opt/a-share/stock-analysis

# 查看日志
pm2 logs a-share-api
```

## 前端构建 & 部署
```bash
cd stock-analysis/preact-terminal
npm run build   # 输出到 dist
```
将 `dist/` 作为 Nginx 静态目录。示例 Nginx 配置（`/etc/nginx/conf.d/a-share.conf`）：
```
server {
    listen 80;
    server_name your.domain.com;

    root /opt/a-share/stock-analysis/preact-terminal/dist;
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:8000/;
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
- 配置示例（`config/prod.json`，被忽略不随代码更新覆盖）：
```json
{
  "schedule_times": ["09:25", "12:30", "15:10"]
}
```
- 修改调度（两种方式）：
  1) 直接编辑 `config/{env}.json` 并重启/重载服务（pm2 restart a-share-api）
  2) API：`POST /config`，Body: `{ "schedule_times": ["09:25","12:30"] }`
- 调度任务会在指定时间调用 `generate_report`，写入 `data/YYYY-MM-DD.json`

## 接口
- `GET /health`：健康检查
- `GET /report?date=YYYY-MM-DD`：读取指定日期 JSON；若不存在返回 404，前端提示手动触发
- `GET /reports`：列出可用 JSON 文件名
- `POST /run`：手动触发生成（可带 `{ "date": "2026-01-08" }`），生成完即返回内容
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
