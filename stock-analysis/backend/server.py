import asyncio
import importlib.util
import json
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator

try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
except ImportError:  # pragma: no cover - scheduler is optional in dev
    AsyncIOScheduler = None  # type: ignore

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"
DATA_DIR = BASE_DIR / "data"

# Environment-aware config (dev/prod separated)
APP_ENV = os.getenv("APP_ENV", "dev")
CONFIG_FILE = CONFIG_DIR / f"{APP_ENV}.json"


class ScheduleConfig(BaseModel):
    schedule_times: List[str] = Field(
        default_factory=lambda: ["09:25", "12:30", "15:10"],
        description="每天触发的时间点，24小时制 HH:MM",
    )

    @validator("schedule_times", each_item=True)
    def validate_time(cls, v: str) -> str:
        try:
            datetime.strptime(v, "%H:%M")
        except ValueError as exc:  # pragma: no cover - runtime validation
            raise ValueError(f"无效时间格式: {v}, 需使用 HH:MM") from exc
        return v


def ensure_dirs() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> ScheduleConfig:
    ensure_dirs()
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return ScheduleConfig(**json.load(f))
    cfg = ScheduleConfig()
    save_config(cfg)
    return cfg


def save_config(cfg: ScheduleConfig) -> None:
    ensure_dirs()
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg.dict(), f, ensure_ascii=False, indent=2)


def transform_analyzer_result(analyzer: Any) -> Dict[str, Any]:
    """
    将 AdvancedStockAnalyzer 的分析结果转换为前端使用的轻量 JSON。
    如果实际字段缺失，做降级处理，避免因字段不齐而报错。
    """
    result: Dict[str, Any] = analyzer.analysis_result if analyzer else {}
    liquidity = result.get("liquidity", {}) or {}
    margin = result.get("margin_trading", {}) or {}
    sentiment = result.get("sentiment", {}) or {}
    heat_map = result.get("sector_heat_map")

    strong_list: List[Dict[str, Any]] = []
    weak_list: List[Dict[str, Any]] = []
    if heat_map is not None and hasattr(heat_map, "empty") and not heat_map.empty:
        try:
            heat_sorted = heat_map.sort_values(by="热力值", ascending=False)
            strong_list = [
                {"name": row["板块名称"], "value": float(row["热力值"])}
                for _, row in heat_sorted.head(5).iterrows()
            ]
            weak_sorted = heat_sorted.sort_values(by="热力值", ascending=True)
            weak_list = [
                {"name": row["板块名称"], "value": float(row["热力值"])}
                for _, row in weak_sorted.head(5).iterrows()
            ]
        except Exception:
            pass

    # 兜底数据
    payload: Dict[str, Any] = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "index": liquidity.get("sh_index_close", 0),
        "change": liquidity.get("sh_pct_chg", 0),
        "volumeEstimate": liquidity.get("total_volume", "0"),
        "leverageRate": margin.get("leverage_ratio", 0),
        "mainFlow": liquidity.get("main_net_inflow", 0),
        "retailFlow": liquidity.get("retail_net_inflow", 0),
        "winRate": sentiment.get("赚钱效应", 0),
        "sectors": {
            "strong": strong_list,
            "weak": weak_list,
        },
        "scenarios": result.get("scenarios")
        or [
            {
                "title": "基准情景",
                "probability": 60,
                "type": "base",
                "description": "指数震荡，量能回落但未破位。",
            },
            {
                "title": "乐观情景",
                "probability": 25,
                "type": "optimistic",
                "description": "量能放大、权重修复带动反弹。",
            },
            {
                "title": "悲观情景",
                "probability": 15,
                "type": "pessimistic",
                "description": "跌破关键支撑，引发加速下探。",
            },
        ],
        "aiAdvice": result.get("aiAdvice")
        or [
            "立即将总仓位降至50%以下，停止追高。",
            "优先减持高杠杆/破位品种，回避金融和游戏权重。",
            "配置部分货币/国债类资产锁定流动性。",
        ],
    }
    return payload


def generate_report(date_str: Optional[str] = None) -> Dict[str, Any]:
    """
    调用分析逻辑并将结果写入 data/YYYY-MM-DD.json。
    如果 AdvancedStockAnalyzer 不可用，则返回示例数据。
    """
    ensure_dirs()
    date_str = date_str or date.today().strftime("%Y-%m-%d")
    filename = DATA_DIR / f"{date_str}.json"

    def load_analyzer():
        main_path = BASE_DIR / "main.py"
        if not main_path.exists():
            return None
        spec = importlib.util.spec_from_file_location("a_share_main", main_path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return getattr(module, "AdvancedStockAnalyzer", None)
        return None

    AdvancedStockAnalyzer = load_analyzer()

    payload: Dict[str, Any]
    if AdvancedStockAnalyzer is not None:
        try:
            analyzer = AdvancedStockAnalyzer()
            analyzer.run_analysis()
            payload = transform_analyzer_result(analyzer)
        except Exception as exc:  # pragma: no cover
            payload = {
                "error": f"分析失败: {exc}",
                "timestamp": datetime.now().isoformat(),
            }
    else:  # Fallback mock for environments without full deps
        payload = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "index": 4077.72,
            "change": -0.2,
            "volumeEstimate": "3.45",
            "leverageRate": 2.53,
            "mainFlow": -633.24,
            "retailFlow": 576.26,
            "winRate": 40.9,
            "sectors": {
                "strong": [
                    {"name": "煤炭行业", "value": 90.3},
                    {"name": "化学制药", "value": 89.9},
                    {"name": "汽车零部件", "value": 86.9},
                ],
                "weak": [
                    {"name": "证券", "value": 9.8},
                    {"name": "保险", "value": 17.3},
                    {"name": "游戏", "value": 21.6},
                ],
            },
            "scenarios": [
                {
                    "title": "基准情景",
                    "probability": 60,
                    "type": "base",
                    "description": "指数在4060-4085区间弱势震荡，放量滞涨。",
                },
                {
                    "title": "乐观情景",
                    "probability": 25,
                    "type": "optimistic",
                    "description": "金融小幅修复带动反弹，需量能维持。",
                },
                {
                    "title": "悲观情景",
                    "probability": 15,
                    "type": "pessimistic",
                    "description": "跌破4060引发恐慌抛售，加速回撤。",
                },
            ],
            "aiAdvice": [
                "仓位降至50%以下，停止追高。",
                "减持高杠杆及金融/游戏权重。",
                "10%-15%流动性放货币ETF或逆回购。",
            ],
        }

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return payload


def read_report(date_str: Optional[str] = None) -> Dict[str, Any]:
    date_str = date_str or date.today().strftime("%Y-%m-%d")
    filepath = DATA_DIR / f"{date_str}.json"
    if not filepath.exists():
        raise FileNotFoundError(f"未找到 {filepath.name}")
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


app = FastAPI(title="A-Share Risk Backend", version="1.0.0")
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
cors_origins = [origin.strip() for origin in cors_origins if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins or ["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
scheduler = AsyncIOScheduler() if AsyncIOScheduler else None


def schedule_jobs(cfg: ScheduleConfig) -> None:
    if scheduler is None:
        return
    scheduler.remove_all_jobs()
    for t in cfg.schedule_times:
        hh, mm = t.split(":")
        scheduler.add_job(
            generate_report,
            trigger="cron",
            hour=int(hh),
            minute=int(mm),
            id=f"job-{t}",
            replace_existing=True,
        )


@app.on_event("startup")
async def startup_event() -> None:
    cfg = load_config()
    schedule_jobs(cfg)
    if scheduler and not scheduler.running:
        scheduler.start()


class ConfigPayload(BaseModel):
    schedule_times: List[str]


class RunPayload(BaseModel):
    date: Optional[str] = None


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok", "env": APP_ENV}


@app.get("/config")
async def get_config() -> Dict[str, Any]:
    cfg = load_config()
    return {"config": cfg.dict(), "env": APP_ENV}


@app.post("/config")
async def update_config(payload: ConfigPayload) -> Dict[str, Any]:
    cfg = ScheduleConfig(schedule_times=payload.schedule_times)
    save_config(cfg)
    schedule_jobs(cfg)
    return {"message": "配置已更新", "config": cfg.dict()}


@app.post("/run")
@app.post("/api/run")
async def run_now(body: RunPayload) -> Dict[str, Any]:
    date_str = body.date
    if date_str:
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="date 格式必须为 YYYY-MM-DD")
    payload = await asyncio.to_thread(generate_report, date_str)
    return {
        "message": "生成完成",
        "date": date_str or date.today().strftime("%Y-%m-%d"),
        "data": payload,
    }


@app.get("/report")
@app.get("/api/report")
async def get_report(
    date: Optional[str] = Query(default=None, description="YYYY-MM-DD"),
) -> Dict[str, Any]:
    if date:
        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="date 格式必须为 YYYY-MM-DD")
    try:
        data = await asyncio.to_thread(read_report, date)
        return {"date": date or date.today().strftime("%Y-%m-%d"), "data": data}
    except FileNotFoundError:
        raise HTTPException(
            status_code=404, detail="指定日期的报告不存在，请手动触发生成"
        )


@app.get("/reports")
async def list_reports() -> Dict[str, Any]:
    ensure_dirs()
    files = sorted([p.name for p in DATA_DIR.glob("*.json")])
    return {"files": files}


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run("backend.server:app", host="0.0.0.0", port=8000, reload=True)
