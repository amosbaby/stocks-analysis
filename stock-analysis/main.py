import os
import pickle
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

import akshare as ak
import numpy as np
import pandas as pd

try:
    from volces_chat import chat_volces

    AI_TOOL_AVAILABLE = True
except ImportError:
    AI_TOOL_AVAILABLE = False

# 关闭不必要的警告
import warnings

from tqdm import tqdm

warnings.filterwarnings("ignore")

DEBUG_MODE = True  # 开启调试模式，会打印每个接口的返回列名


def debug_print(df, name):
    if DEBUG_MODE:
        print(f"\n--- 调试信息: {name} ---")
        if df is not None and not df.empty:
            print("列名:", df.columns.tolist())
            print("数据预览:")
            print(df.head(3))
        else:
            print("数据为空或不存在。")
        print("-" * (20 + len(name)))


_cache = {}


def _safe_ak_call(func_names, *args, **kwargs):
    """尝试调用多个 akshare 接口，返回第一个非空 DataFrame。"""
    for name in func_names:
        func = getattr(ak, name, None)
        if func is None:
            continue
        try:
            df = func(*args, **kwargs)
            if df is not None and not df.empty:
                return df
        except Exception:
            continue
    return pd.DataFrame()


def _pick_col(df, candidates):
    """从候选列名中选出第一个存在的列。"""
    for col in candidates:
        if col in df.columns:
            return col
    return None


def _normalize_flow_value(value):
    """将资金流数值尽量归一到“亿元”口径。"""
    if value is None:
        return np.nan
    try:
        val = float(value)
    except (TypeError, ValueError):
        val = pd.to_numeric(value, errors="coerce")
    if pd.isna(val):
        return np.nan
    # 经验判断：若数值极大，可能为“元”，则换算为亿元
    if abs(val) > 1e6:
        return val / 1e8
    return val


def _fetch_trade_calendar():
    """获取交易日历数据。"""
    return _safe_ak_call(
        [
            "tool_trade_date_hist_sina",
            "tool_trade_date_hist_sse",
            "tool_trade_date_hist",
        ]
    )


def cache_data(filename, data_func, *args, frequency="hourly", **kwargs):
    """
    缓存函数，支持小时级或天级缓存。
    frequency: 'hourly' 或 'daily'
    """
    if frequency == "hourly":
        time_str = datetime.now().strftime("%Y%m%d%H")
    else:  # daily
        time_str = datetime.now().strftime("%Y%m%d")

    params_str = "_".join(map(str, args)) + "_".join(
        f"{k}_{v}" for k, v in kwargs.items()
    )
    unique_filename = f"{filename}_{params_str}_{time_str}.pkl"
    filepath = os.path.join("../cache", unique_filename)

    if filepath in _cache:
        return _cache[filepath]

    if not os.path.exists("../cache"):
        os.makedirs("../cache")
    if os.path.exists(filepath):
        with open(filepath, "rb") as f:
            data = pickle.load(f)
            _cache[filepath] = data
            return data

    try:
        data = data_func(*args, **kwargs)
        with open(filepath, "wb") as f:
            pickle.dump(data, f)
        _cache[filepath] = data
        return data
    except Exception as e:
        print(f"  - 获取 {filename} 数据失败: {e}，返回空DataFrame")
        return pd.DataFrame()


def get_incremental_daily_data(
    base_filename, data_func, date_col_name, *args, **kwargs
):
    """
    为日线历史数据提供增量更新的缓存策略。
    """
    base_filepath = os.path.join("../cache", f"{base_filename}_base.pkl")

    if not os.path.exists("../cache"):
        os.makedirs("../cache")

    if os.path.exists(base_filepath):
        with open(base_filepath, "rb") as f:
            df_base = pickle.load(f)

        last_date = pd.to_datetime(df_base[date_col_name]).max()
        start_date = (last_date + timedelta(days=1)).strftime("%Y%m%d")
        today_str = datetime.now().strftime("%Y%m%d")

        if start_date <= today_str:
            print(f"  - 增量更新 {base_filename} 数据从 {start_date} 开始...")
            try:
                # 传递 start_date 给 akshare 函数
                kwargs["start_date"] = start_date
                df_new = data_func(*args, **kwargs)
                if not df_new.empty:
                    df_updated = pd.concat([df_base, df_new]).drop_duplicates(
                        subset=[date_col_name], keep="last"
                    )
                    with open(base_filepath, "wb") as f:
                        pickle.dump(df_updated, f)
                    return df_updated
            except Exception as e:
                print(f"  - 增量更新失败: {e}")
        return df_base
    else:
        print(f"  - 未找到基底文件，首次全量获取 {base_filename} 数据...")
        try:
            # 首次获取，从一个较早的日期开始
            kwargs["start_date"] = "19900101"
            df_full = data_func(*args, **kwargs)
            with open(base_filepath, "wb") as f:
                pickle.dump(df_full, f)
            return df_full
        except Exception as e:
            print(f"  - 全量获取失败: {e}")
            return pd.DataFrame()


def clean_old_cache():
    """清理过期的小时级和天级缓存文件，保留基底文件。"""
    if not os.path.exists("../cache"):
        return

    print("步骤 0/13: 清理过期缓存...")
    current_hour_str = datetime.now().strftime("%Y%m%d%H")
    current_day_str = datetime.now().strftime("%Y%m%d")

    for filename in os.listdir("../cache"):
        if "_base.pkl" in filename:
            continue
        match_hourly = re.search(r"_(\d{10})\.pkl$", filename)
        if match_hourly and match_hourly.group(1) != current_hour_str:
            os.remove(os.path.join("../cache", filename))
            if DEBUG_MODE:
                print(f"  - 已删除过期小时缓存: {filename}")
            continue
        match_daily = re.search(r"_(\d{8})\.pkl$", filename)
        if match_daily and match_daily.group(1) != current_day_str:
            os.remove(os.path.join("../cache", filename))
            if DEBUG_MODE:
                print(f"  - 已删除过期每日缓存: {filename}")
    print("  - 缓存清理完成。")


class AdvancedStockAnalyzer:
    SECTOR_THEMES = [
        "大新能源",
        "半导体",
        "人工智能",
        "软件",
        "消费电子",
        "有色金属",
        "芯片",
        "机器人",
        "国防军工",
        "脑机接口",
        "云计算",
        "大消费",
        "大农业",
        "医疗健康",
        "大金融",
        "房地产",
        "港股",
        "周期/材料",
        "高端制造",
        "交通运输",
        "传媒/游戏",
        "军工",
        "其他",
    ]

    def __init__(self):
        self.data = {}
        self.analysis_result = {}
        self.stock_to_industry_map = {}
        self.run_mode = None
        self.is_trading_day = None

    def _build_stock_industry_map(self):
        """构建股票代码到行业名称的精确映射字典"""
        print("步骤 1/13: 构建股票与行业的精确映射...")
        try:
            self.stock_to_industry_map = cache_data(
                "stock_industry_map", self._fetch_full_industry_map, frequency="daily"
            )
            print(
                f"  - 股票行业映射构建完成，共映射 {len(self.stock_to_industry_map)} 只股票。"
            )
        except Exception as e:
            print(f"  - 构建股票行业映射失败: {e}")

    def _get_trade_calendar(self):
        """获取交易日历（缓存）。"""
        return cache_data("trade_calendar", _fetch_trade_calendar, frequency="daily")

    def _is_trade_day(self, date_obj):
        """判断指定日期是否为交易日。"""
        try:
            df = self._get_trade_calendar()
            if df is None or df.empty:
                return None
            date_col = _pick_col(df, ["trade_date", "日期", "date"])
            if not date_col:
                return None
            date_series = pd.to_datetime(df[date_col], errors="coerce").dt.date
            return date_obj in set(date_series.dropna().tolist())
        except Exception:
            return None

    def _fetch_full_industry_map(self):
        """遍历所有行业板块获取其成分股，构建完整映射"""
        all_industries = ak.stock_board_industry_name_em()
        full_map = {}
        for industry_name in tqdm(
            all_industries["板块名称"], desc="  - 正在遍历行业板块"
        ):
            try:
                cons_df = ak.stock_board_industry_cons_em(symbol=industry_name)
                for code in cons_df["代码"]:
                    full_map[code] = industry_name
            except Exception:
                time.sleep(0.5)
                continue
        return full_map

    def fetch_data(self):
        """获取所有需要的基础数据"""
        print("开始获取基础数据...")
        try:
            self._build_stock_industry_map()

            print("步骤 2/13: 获取市场总体资金流历史...")
            self.data["market_fund_flow"] = ak.stock_market_fund_flow()
            debug_print(self.data["market_fund_flow"], "市场总体资金流")

            print("步骤 3/13: 获取行业板块当日资金流...")
            self.data["industry_fund_flow"] = ak.stock_sector_fund_flow_rank(
                indicator="今日", sector_type="行业资金流"
            )

            print("步骤 4/13: 获取北向资金数据...")

            def fetch_northbound_flow():
                return _safe_ak_call(
                    ["stock_hsgt_flow_em", "stock_hsgt_flow_xq", "stock_hsgt_flow"],
                )

            def fetch_northbound_top():
                return _safe_ak_call(
                    [
                        "stock_hsgt_hold_stock_em",
                        "stock_hsgt_north_hold_stock_em",
                        "stock_hk_stock_connect_detail_em",
                    ],
                )

            self.data["northbound_flow"] = cache_data(
                "northbound_flow", fetch_northbound_flow, frequency="hourly"
            )
            self.data["northbound_top"] = cache_data(
                "northbound_top", fetch_northbound_top, frequency="daily"
            )
            debug_print(self.data["northbound_flow"], "北向资金流")
            debug_print(self.data["northbound_top"], "北向资金持仓/净买入明细")

            print("步骤 5/13: 获取大盘与国债历史行情 (增量更新)...")
            # 上证指数
            sh_index_df = get_incremental_daily_data(
                "sh_index", ak.index_zh_a_hist, "日期", symbol="000001", period="daily"
            )
            sh_index_df.rename(
                columns={
                    "收盘": "close",
                    "开盘": "open",
                    "最高": "high",
                    "最低": "low",
                    "成交额": "amount",
                    "涨跌幅": "pct_chg",
                },
                inplace=True,
            )
            self.data["sh_index"] = sh_index_df

            # 深证成指
            sz_index_df = get_incremental_daily_data(
                "sz_index", ak.index_zh_a_hist, "日期", symbol="399001", period="daily"
            )
            sz_index_df.rename(
                columns={
                    "收盘": "close",
                    "开盘": "open",
                    "最高": "high",
                    "最低": "low",
                    "成交额": "amount",
                    "涨跌幅": "pct_chg",
                },
                inplace=True,
            )
            self.data["sz_index"] = sz_index_df

            # 风格与分市场指数
            style_indices = {
                "csi300": "000300",  # 沪深300
                "zz1000": "000852",  # 中证1000
                "cyb": "399006",  # 创业板指
                "kcb50": "000688",  # 科创50
                "bj50": "899050",  # 北证50
            }
            for key, symbol in style_indices.items():
                try:
                    df = get_incremental_daily_data(
                        key, ak.index_zh_a_hist, "日期", symbol=symbol, period="daily"
                    )
                    df.rename(
                        columns={
                            "收盘": "close",
                            "开盘": "open",
                            "最高": "high",
                            "最低": "low",
                            "成交额": "amount",
                            "涨跌幅": "pct_chg",
                        },
                        inplace=True,
                    )
                    self.data[key] = df
                except Exception:
                    self.data[key] = pd.DataFrame()

            self.data["bond_etf"] = cache_data(
                "bond_etf", ak.fund_etf_hist_em, symbol="511260", frequency="daily"
            )
            debug_print(self.data["sh_index"], "上证指数历史行情")
            debug_print(self.data["sz_index"], "深证成指历史行情")

            # print("步骤 5/11: 获取ETF列表并筛选...")
            # etf_spot = cache_data("etf_spot", ak.fund_etf_spot_em)
            # foreign_keywords = ['纳斯达克', '纳指', '标普', '日经', '德国', '法国', '印度', '沙特', '美国', '海外', '全球', '原油', '黄金']
            # mask_to_drop = etf_spot['名称'].str.contains('|'.join(foreign_keywords), na=False)
            # etf_spot = etf_spot[~mask_to_drop]
            # self.data['etf_spot'] = etf_spot[etf_spot['成交额'] > 50000000]

            print("步骤 6/13: 获取市场情绪数据(赚钱效应)...")
            self.data["market_activity"] = cache_data(
                "market_activity", ak.stock_market_activity_legu
            )

            print("步骤 7/13: 获取市场情绪数据(拥挤度)...")
            self.data["congestion"] = cache_data(
                "congestion", ak.stock_a_congestion_lg, frequency="daily"
            )

            print("步骤 8/13: 获取涨跌停与炸板数据...")

            def fetch_zt_pool():
                return _safe_ak_call(["stock_zt_pool_em", "stock_zt_pool"])

            def fetch_dt_pool():
                return _safe_ak_call(
                    ["stock_dt_pool_em", "stock_zt_pool_dt_em", "stock_zt_pool_dt"]
                )

            def fetch_zb_pool():
                return _safe_ak_call(
                    [
                        "stock_zt_pool_zb_em",
                        "stock_zt_pool_zdt_em",
                        "stock_zt_pool_zd_em",
                    ]
                )

            def fetch_zt_strong_pool():
                return _safe_ak_call(
                    ["stock_zt_pool_strong_em", "stock_zt_pool_strong"]
                )

            self.data["zt_pool"] = cache_data(
                "zt_pool", fetch_zt_pool, frequency="hourly"
            )
            self.data["dt_pool"] = cache_data(
                "dt_pool", fetch_dt_pool, frequency="hourly"
            )
            self.data["zb_pool"] = cache_data(
                "zb_pool", fetch_zb_pool, frequency="hourly"
            )
            self.data["zt_strong_pool"] = cache_data(
                "zt_strong_pool", fetch_zt_strong_pool, frequency="hourly"
            )
            debug_print(self.data["zt_pool"], "涨停池")
            debug_print(self.data["dt_pool"], "跌停池")
            debug_print(self.data["zb_pool"], "炸板池")

            print("步骤 9/13: 获取市场热点数据(量价齐升)...")
            self.data["rank_ljqs"] = cache_data("rank_ljqs", ak.stock_rank_ljqs_ths)

            print("步骤 10/13: 获取A股全体数据(用于换手率和杠杆率计算)...")
            self.data["all_a_spot"] = cache_data("all_a_spot", ak.stock_zh_a_spot_em)
            debug_print(self.data["all_a_spot"], "A股全体实时数据")

            print("步骤 11/13: 获取指数实时行情(用于盘中成交额备选)...")

            def fetch_index_spot():
                return _safe_ak_call(["index_zh_a_spot_em", "index_zh_a_spot"])

            self.data["index_spot"] = cache_data(
                "index_spot", fetch_index_spot, frequency="hourly"
            )
            debug_print(self.data["index_spot"], "指数实时行情")

            print("步骤 12/13: 获取两市融资融券数据...")
            sh_margin_df = cache_data(
                "sh_margin", ak.macro_china_market_margin_sh, frequency="daily"
            )
            sz_margin_df = cache_data(
                "sz_margin", ak.macro_china_market_margin_sz, frequency="daily"
            )
            self.data["sh_margin"] = sh_margin_df
            self.data["sz_margin"] = sz_margin_df
            debug_print(self.data["sh_margin"].tail(), "沪市融资融券余额")
            debug_print(self.data["sz_margin"].tail(), "深市融资融券余额")

            # print(f"\n基础数据获取完成。筛选出 {len(self.data['etf_spot'])} 个活跃ETF进行分析。")
            return True
        except Exception as e:
            print(f"\n数据获取过程中出现严重错误: {e}")
            return False

    def _get_elapsed_trading_minutes(self):
        """计算当天已过的交易分钟数"""
        now = datetime.now()
        if self.is_trading_day is False:
            return 0
        if now.time() < datetime(2000, 1, 1, 9, 30).time():
            return 0
        if now.time() <= datetime(2000, 1, 1, 11, 30).time():
            start = now.replace(hour=9, minute=30, second=0, microsecond=0)
            return (now - start).total_seconds() / 60
        if now.time() < datetime(2000, 1, 1, 13, 0).time():
            return 120
        if now.time() <= datetime(2000, 1, 1, 15, 0).time():
            start = now.replace(hour=13, minute=0, second=0, microsecond=0)
            return 120 + (now - start).total_seconds() / 60
        return 240

    def analyze_market_liquidity(self):
        print("正在分析市场流动性与主力行为...")
        try:
            mff = self.data.get("market_fund_flow")
            sh_index = self.data.get("sh_index")
            sz_index = self.data.get("sz_index")
            if (
                mff is None
                or mff.empty
                or sh_index is None
                or sh_index.empty
                or sz_index is None
                or sz_index.empty
            ):
                raise ValueError("市场资金流或大盘历史行情数据为空")

            total_turnover = (
                sh_index.iloc[-1]["amount"] + sz_index.iloc[-1]["amount"]
            ) / 1e8
            turnover_source = "指数日线"
            all_a_spot = self.data.get("all_a_spot")
            index_spot = self.data.get("index_spot")
            if self.run_mode != "POST_MARKET" and all_a_spot is not None:
                if not all_a_spot.empty and "成交额" in all_a_spot.columns:
                    spot_turnover = (
                        pd.to_numeric(all_a_spot["成交额"], errors="coerce")
                        .fillna(0)
                        .sum()
                        / 1e8
                    )
                    if spot_turnover > 0:
                        total_turnover = spot_turnover
                        turnover_source = "实时汇总"
            if (
                self.run_mode != "POST_MARKET"
                and turnover_source == "指数日线"
                and index_spot is not None
            ):
                amount_col = _pick_col(index_spot, ["成交额", "成交金额", "成交额(元)"])
                if not index_spot.empty and amount_col:
                    idx_turnover = (
                        pd.to_numeric(index_spot[amount_col], errors="coerce")
                        .fillna(0)
                        .sum()
                        / 1e8
                    )
                    if idx_turnover > 0:
                        total_turnover = idx_turnover
                        turnover_source = "指数实时汇总"

                    name_col = _pick_col(index_spot, ["名称", "指数名称", "index_name"])
                    if name_col:
                        spot_df = index_spot[[name_col, amount_col]].copy()
                        spot_df[name_col] = spot_df[name_col].astype(str)

                        def sum_by_name(keys):
                            mask = spot_df[name_col].str.contains(
                                "|".join(keys), na=False
                            )
                            if not mask.any():
                                return None
                            return (
                                pd.to_numeric(
                                    spot_df.loc[mask, amount_col], errors="coerce"
                                )
                                .fillna(0)
                                .sum()
                                / 1e8
                            )

                        sh_idx = sum_by_name(["上证", "上证综合", "上证指数", "沪指"])
                        sz_idx = sum_by_name(["深证", "深成指", "深证成指", "深指"])
                        if sh_idx is not None and sz_idx is not None:
                            self.analysis_result.setdefault("liquidity", {})
                            self.analysis_result["liquidity"][
                                "index_turnover_breakdown"
                            ] = {
                                "sh_index": f"{sh_idx:.2f}亿元",
                                "sz_index": f"{sz_idx:.2f}亿元",
                            }
            yesterday_turnover = (
                sh_index.iloc[-2]["amount"] + sz_index.iloc[-2]["amount"]
            ) / 1e8

            volume_analysis_turnover = total_turnover
            estimated_turnover_str = ""
            volume_desc_prefix = ""

            if self.run_mode != "POST_MARKET":
                elapsed_minutes = self._get_elapsed_trading_minutes()
                if elapsed_minutes > 0:
                    estimated_turnover = total_turnover * (240 / elapsed_minutes)
                    volume_analysis_turnover = estimated_turnover
                    volume_desc_prefix = "预估"
                    estimated_turnover_str = (
                        f" (预估全天: {estimated_turnover:.2f}亿元)"
                    )

            latest_flow = mff.iloc[-1]
            main_net_inflow = latest_flow["主力净流入-净额"] / 1e8
            retail_net_inflow = latest_flow["小单净流入-净额"] / 1e8

            avg_5d_turnover = (
                sh_index.iloc[-6:-1]["amount"].mean()
                + sz_index.iloc[-6:-1]["amount"].mean()
            ) / 1e8
            volume_level = (
                "高于5日均量"
                if volume_analysis_turnover > avg_5d_turnover
                else "低于5日均量"
            )

            volume_change = volume_analysis_turnover - yesterday_turnover
            volume_change_desc = (
                f"{volume_desc_prefix}缩量 {abs(volume_change):.2f}亿"
                if volume_change < 0
                else f"{volume_desc_prefix}放量 {volume_change:.2f}亿"
            )

            AVG_TURNOVER = 10000
            if volume_analysis_turnover < AVG_TURNOVER * 0.7:
                volume_qualitative_level = "地量水平"
            elif volume_analysis_turnover <= AVG_TURNOVER * 1.5:
                volume_qualitative_level = "平量水平"
            elif volume_analysis_turnover <= AVG_TURNOVER * 2.5:
                volume_qualitative_level = "天量水平"
            else:
                volume_qualitative_level = "巨量水平"

            inflow_percentage = (
                (main_net_inflow / volume_analysis_turnover) * 100
                if volume_analysis_turnover > 0
                else 0
            )

            liquidity_payload = {
                "total_volume": f"{total_turnover:.2f}亿元",
                "estimated_turnover_str": estimated_turnover_str,
                "volume_level": volume_level,
                "volume_change_desc": volume_change_desc,
                "main_net_inflow": f"{main_net_inflow:.2f}亿元",
                "retail_net_inflow": f"{retail_net_inflow:.2f}亿元",
                "inflow_percentage": inflow_percentage,
                "volume_qualitative_level": volume_qualitative_level,
                "turnover_source": turnover_source,
            }
            if self.analysis_result.get("liquidity", {}).get(
                "index_turnover_breakdown"
            ):
                liquidity_payload["index_turnover_breakdown"] = self.analysis_result[
                    "liquidity"
                ]["index_turnover_breakdown"]
            self.analysis_result["liquidity"] = liquidity_payload
        except Exception as e:
            print(f"  - 市场流动性分析失败: {e}")
            self.analysis_result["liquidity"] = {}
        print("市场流动性与主力行为分析完成。")

    def analyze_market_turnover(self):
        print("正在分析市场换手率...")
        try:
            all_a_spot = self.data.get("all_a_spot")
            if all_a_spot is None or all_a_spot.empty:
                raise ValueError("A股实时行情数据为空")
            valid_stocks = all_a_spot[
                (all_a_spot["流通市值"] > 0) & (all_a_spot["换手率"] > 0)
            ]
            weighted_turnover = (
                valid_stocks["换手率"] * valid_stocks["流通市值"]
            ).sum() / valid_stocks["流通市值"].sum()
            turnover_level = (
                "极高(过热)"
                if weighted_turnover > 3.5
                else "较高(活跃)"
                if weighted_turnover > 2.0
                else "中等(温和)"
                if weighted_turnover > 1.0
                else "较低(谨慎)"
            )
            self.analysis_result["turnover"] = {
                "market_turnover_rate": f"{weighted_turnover:.2f}%",
                "turnover_level": turnover_level,
            }
        except Exception as e:
            print(f"  - 市场换手率分析失败: {e}")
            self.analysis_result["turnover"] = {}
        print("市场换手率分析完成。")

    def analyze_margin_trading(self):
        """分析市场杠杆率(融资余额/总流通市值)"""
        print("正在分析市场杠杆率...")
        try:
            sh_margin = self.data.get("sh_margin")
            sz_margin = self.data.get("sz_margin")
            all_a_spot = self.data.get("all_a_spot")
            if (
                sh_margin is None
                or sh_margin.empty
                or sz_margin is None
                or sz_margin.empty
                or all_a_spot is None
                or all_a_spot.empty
            ):
                raise ValueError("融资融券或A股实时行情数据为空")

            # 计算总融资余额
            latest_sh_balance = sh_margin.iloc[-1]["融资余额"]
            latest_sz_balance = sz_margin.iloc[-1]["融资余额"]
            total_margin_balance = latest_sh_balance + latest_sz_balance

            # 计算融资余额变化
            prev_sh_balance = sh_margin.iloc[-2]["融资余额"]
            prev_sz_balance = sz_margin.iloc[-2]["融资余额"]
            prev_total_margin_balance = prev_sh_balance + prev_sz_balance
            change = (total_margin_balance - prev_total_margin_balance) / 1e8
            change_desc = (
                f"净买入 {change:.2f}亿元"
                if change > 0
                else f"净偿还 {abs(change):.2f}亿元"
            )

            # 计算总流通市值
            total_circulating_market_cap = all_a_spot["流通市值"].sum()

            # 计算杠杆率
            leverage_ratio = (
                (total_margin_balance / total_circulating_market_cap) * 100
                if total_circulating_market_cap > 0
                else 0
            )

            # 对杠杆率进行定性描述
            if leverage_ratio < 1.8:
                leverage_level = "较低"
            elif 1.8 <= leverage_ratio < 2.2:
                leverage_level = "中等"
            elif 2.2 <= leverage_ratio < 2.5:
                leverage_level = "偏高"
            else:  # >= 2.5%
                leverage_level = "风险区"

            self.analysis_result["margin_trading"] = {
                "total_balance": f"{total_margin_balance / 1e8:.2f}亿元",
                "change_desc": change_desc,
                "leverage_ratio": f"{leverage_ratio:.2f}%",
                "leverage_level": leverage_level,
            }
        except Exception as e:
            print(f"  - 市场杠杆率分析失败: {e}")
            self.analysis_result["margin_trading"] = {}
        print("市场杠杆率分析完成。")

    def analyze_northbound_fund_flow(self):
        """分析北向资金流与行业集中度"""
        print("正在分析北向资金...")
        try:
            flow_df = self.data.get("northbound_flow")
            top_df = self.data.get("northbound_top")

            result = {}
            if flow_df is not None and not flow_df.empty:
                total_col = _pick_col(
                    flow_df,
                    [
                        "北向资金",
                        "北向资金净流入",
                        "北向资金净买入",
                        "北向资金今日净买入",
                        "当日买入成交净额",
                        "净流入",
                        "净买入",
                    ],
                )
                sh_col = _pick_col(flow_df, ["沪股通", "沪股通净流入", "沪股通净买入"])
                sz_col = _pick_col(flow_df, ["深股通", "深股通净流入", "深股通净买入"])

                if total_col:
                    total_series = pd.to_numeric(
                        flow_df[total_col], errors="coerce"
                    ).dropna()
                    if not total_series.empty:
                        latest_val = _normalize_flow_value(total_series.iloc[-1])
                        avg_5d = (
                            _normalize_flow_value(total_series.tail(5).mean())
                            if len(total_series) >= 2
                            else np.nan
                        )
                        streak = 0
                        for val in reversed(total_series.tolist()):
                            if val >= 0:
                                if streak >= 0:
                                    streak += 1
                                else:
                                    break
                            else:
                                if streak <= 0:
                                    streak -= 1
                                else:
                                    break
                        if streak > 0:
                            trend_desc = f"连续净流入{streak}日"
                        elif streak < 0:
                            trend_desc = f"连续净流出{abs(streak)}日"
                        else:
                            trend_desc = "方向不明"

                        result.update(
                            {
                                "total_net_inflow": (
                                    f"{latest_val:.2f}亿元"
                                    if pd.notna(latest_val)
                                    else "未知"
                                ),
                                "five_day_avg": (
                                    f"{avg_5d:.2f}亿元" if pd.notna(avg_5d) else "未知"
                                ),
                                "flow_trend": trend_desc,
                            }
                        )

                if sh_col:
                    sh_series = pd.to_numeric(flow_df[sh_col], errors="coerce").dropna()
                    if not sh_series.empty:
                        sh_val = _normalize_flow_value(sh_series.iloc[-1])
                        result["sh_net_inflow"] = (
                            f"{sh_val:.2f}亿元" if pd.notna(sh_val) else "未知"
                        )
                if sz_col:
                    sz_series = pd.to_numeric(flow_df[sz_col], errors="coerce").dropna()
                    if not sz_series.empty:
                        sz_val = _normalize_flow_value(sz_series.iloc[-1])
                        result["sz_net_inflow"] = (
                            f"{sz_val:.2f}亿元" if pd.notna(sz_val) else "未知"
                        )

            if top_df is not None and not top_df.empty and self.stock_to_industry_map:
                top_df = top_df.copy()
                code_col = _pick_col(top_df, ["代码", "股票代码", "证券代码"])
                name_col = _pick_col(top_df, ["名称", "股票简称", "证券简称"])
                value_col = _pick_col(
                    top_df,
                    [
                        "今日净买入",
                        "净买入",
                        "净流入",
                        "当日净买入",
                        "今日净流入",
                        "买入成交净额",
                        "持股市值",
                        "持仓市值",
                        "持股数量",
                    ],
                )

                if code_col:
                    top_df[code_col] = top_df[code_col].astype(str).str.zfill(6)
                    top_df["行业"] = top_df[code_col].map(self.stock_to_industry_map)
                else:
                    top_df["行业"] = None

                if value_col:
                    top_df["统计权重"] = pd.to_numeric(
                        top_df[value_col], errors="coerce"
                    ).fillna(0.0)
                else:
                    top_df["统计权重"] = 1.0

                sector_dist = (
                    top_df.groupby("行业")["统计权重"]
                    .sum()
                    .sort_values(ascending=False)
                    .head(5)
                )
                if not sector_dist.empty:
                    result["top_industries"] = [
                        f"{idx}({val:.2f})" for idx, val in sector_dist.items()
                    ]

                if code_col and name_col:
                    top_stocks = top_df.sort_values(
                        by="统计权重", ascending=False
                    ).head(5)
                    result["top_stocks"] = [
                        f"{row[name_col]}({row[code_col]})"
                        for _, row in top_stocks.iterrows()
                    ]

            self.analysis_result["northbound"] = result
        except Exception as e:
            print(f"  - 北向资金分析失败: {e}")
            self.analysis_result["northbound"] = {}
        print("北向资金分析完成。")

    def analyze_intermarket_relationship(self):
        print("正在分析股债关系与大盘趋势...")
        try:
            sh_df = self.data.get("sh_index")
            bond_df = self.data.get("bond_etf")
            if sh_df is None or sh_df.empty or bond_df is None or bond_df.empty:
                raise ValueError("大盘或国债行情数据为空")

            sh_latest = sh_df.iloc[-1]
            sh_ma5 = sh_df["close"].iloc[-5:].mean()
            market_trend = "站上5日线" if sh_latest["close"] > sh_ma5 else "跌破5日线"
            last_60_days = sh_df.iloc[-60:]
            high_60d, low_60d = last_60_days["high"].max(), last_60_days["low"].min()
            position = (
                (sh_latest["close"] - low_60d) / (high_60d - low_60d)
                if (high_60d - low_60d) > 0
                else 0.5
            )
            position_desc = (
                "高位区域"
                if position > 0.8
                else "低位区域"
                if position < 0.2
                else "震荡中枢"
            )
            bond_latest = bond_df.iloc[-1]
            relation = "分歧"
            if sh_latest["pct_chg"] > 0.2 and bond_latest["涨跌幅"] < -0.05:
                relation = "股强债弱 (Risk-On)"
            elif sh_latest["pct_chg"] < -0.2 and bond_latest["涨跌幅"] > 0.05:
                relation = "股弱债强 (Risk-Off)"
            elif sh_latest["pct_chg"] < -0.2 and bond_latest["涨跌幅"] < -0.05:
                relation = "股债双杀 (流动性收紧)"
            elif sh_latest["pct_chg"] > 0.2 and bond_latest["涨跌幅"] > 0.05:
                relation = "股债双强 (流动性宽松)"
            self.analysis_result["intermarket"] = {
                "market_trend": market_trend,
                "relation": relation,
                "sh_index_close": f"{sh_latest['close']:.2f}",
                "sh_pct_chg": sh_latest["pct_chg"],
                "position_desc": position_desc,
            }
        except Exception as e:
            print(f"  - 股债关系分析失败: {e}")
            self.analysis_result["intermarket"] = {}
        print("股债关系与大盘趋势分析完成。")

    def analyze_market_style(self):
        """分析分市场与风格强弱"""
        print("正在分析分市场与风格强弱...")
        try:

            def calc_return(df, days):
                if df is None or df.empty or len(df) <= days:
                    return None
                try:
                    start = df.iloc[-(days + 1)]["close"]
                    end = df.iloc[-1]["close"]
                    if start == 0:
                        return None
                    return round((end / start - 1) * 100, 2)
                except Exception:
                    return None

            index_map = {
                "沪深300": self.data.get("csi300"),
                "中证1000": self.data.get("zz1000"),
                "创业板指": self.data.get("cyb"),
                "科创50": self.data.get("kcb50"),
                "北证50": self.data.get("bj50"),
            }
            perf = {}
            for name, df in index_map.items():
                if df is None or df.empty:
                    continue
                day_ret = None
                if "pct_chg" in df.columns and not df["pct_chg"].empty:
                    try:
                        day_ret = float(df.iloc[-1]["pct_chg"])
                    except Exception:
                        day_ret = None
                if day_ret is None:
                    day_ret = calc_return(df, 1)
                week_ret = calc_return(df, 5)
                perf[name] = {"day_ret": day_ret, "week_ret": week_ret}

            def compare(a, b, label_a, label_b):
                if a is None or b is None:
                    return "对比不足"
                return f"{label_a}强于{label_b}" if a > b else f"{label_b}强于{label_a}"

            large = perf.get("沪深300", {}).get("day_ret")
            small = perf.get("中证1000", {}).get("day_ret")
            growth = perf.get("创业板指", {}).get("day_ret")
            tech = perf.get("科创50", {}).get("day_ret")
            bj = perf.get("北证50", {}).get("day_ret")

            style_summary = [
                compare(small, large, "小盘", "大盘"),
                compare(growth, large, "成长", "权重"),
            ]
            if tech is not None and large is not None:
                style_summary.append(compare(tech, large, "科创", "权重"))
            if bj is not None and small is not None:
                style_summary.append(compare(bj, small, "北证", "中小盘"))

            perf_rank = sorted(
                [
                    (name, data["day_ret"])
                    for name, data in perf.items()
                    if data.get("day_ret") is not None
                ],
                key=lambda x: x[1],
                reverse=True,
            )
            perf_rank_str = [f"{name}({ret:+.2f}%)" for name, ret in perf_rank]

            self.analysis_result["style"] = {
                "index_perf": perf,
                "style_summary": " | ".join([s for s in style_summary if s]),
                "performance_rank": perf_rank_str,
            }
        except Exception as e:
            print(f"  - 分市场与风格分析失败: {e}")
            self.analysis_result["style"] = {}
        print("分市场与风格强弱分析完成。")

    def analyze_limitup_structure(self):
        """分析涨跌停结构与连板高度"""
        print("正在分析涨跌停结构...")
        try:
            zt_df = self.data.get("zt_pool")
            dt_df = self.data.get("dt_pool")
            zb_df = self.data.get("zb_pool")
            strong_df = self.data.get("zt_strong_pool")

            result = {
                "limit_up_count": len(zt_df) if zt_df is not None else 0,
                "limit_down_count": len(dt_df) if dt_df is not None else 0,
                "break_limit_count": len(zb_df) if zb_df is not None else 0,
            }

            # 连板高度优先从涨停池取
            streak_col = None
            if zt_df is not None and not zt_df.empty:
                streak_col = _pick_col(
                    zt_df, ["连板数", "连续涨停天数", "连板高度", "连板"]
                )
            if streak_col and zt_df is not None and not zt_df.empty:
                streak_val = pd.to_numeric(zt_df[streak_col], errors="coerce").max()
            elif strong_df is not None and not strong_df.empty:
                strong_col = _pick_col(
                    strong_df, ["连板数", "连续涨停天数", "连板高度", "连板"]
                )
                streak_val = (
                    pd.to_numeric(strong_df[strong_col], errors="coerce").max()
                    if strong_col
                    else np.nan
                )
            else:
                streak_val = np.nan

            if pd.notna(streak_val):
                result["streak_high"] = int(streak_val)

            # 炸板率：炸板/(涨停+炸板)
            denom = result["limit_up_count"] + result["break_limit_count"]
            if denom > 0:
                result["break_rate"] = round(
                    (result["break_limit_count"] / denom) * 100, 2
                )

            self.analysis_result["limitup"] = result
        except Exception as e:
            print(f"  - 涨跌停结构分析失败: {e}")
            self.analysis_result["limitup"] = {}
        print("涨跌停结构分析完成。")

    def analyze_market_sentiment(self):
        print("正在分析市场情绪温度...")
        try:
            activity_df = self.data.get("market_activity")
            if activity_df is None or activity_df.empty:
                raise ValueError("赚钱效应数据为空")
            up_series = activity_df[activity_df["item"] == "上涨"]["value"]
            down_series = activity_df[activity_df["item"] == "下跌"]["value"]
            if up_series.empty or down_series.empty:
                raise ValueError("未能从数据中找到'上涨'或'下跌'家数")
            up_count, down_count = up_series.iloc[0], down_series.iloc[0]
            profit_effect = (
                round((up_count / (up_count + down_count)) * 100, 2)
                if (up_count + down_count) > 0
                else 50.0
            )
            ljqs_count = len(self.data.get("rank_ljqs", pd.DataFrame()))
            limitup = self.analysis_result.get("limitup", {})
            limit_up_count = limitup.get("limit_up_count", 0)
            limit_down_count = limitup.get("limit_down_count", 0)
            break_rate = limitup.get("break_rate")
            streak_high = limitup.get("streak_high")
            congestion_df = self.data.get("congestion")
            if congestion_df is None or congestion_df.empty:
                raise ValueError("拥挤度数据为空")
            congestion = congestion_df.iloc[-1]["congestion"] * 100
            sentiment, sentiment_reason = "中性", []
            if profit_effect > 65 and limit_up_count > 80:
                sentiment, _ = (
                    "贪婪",
                    sentiment_reason.append(f"赚钱效应强({profit_effect}%)"),
                )
            elif profit_effect > 50:
                sentiment, _ = (
                    "乐观",
                    sentiment_reason.append(f"赚钱效应较好({profit_effect}%)"),
                )
            elif 40 <= profit_effect <= 50:
                sentiment, _ = (
                    "中性偏冷",
                    sentiment_reason.append(f"赚钱效应一般({profit_effect}%)"),
                )
            elif profit_effect < 40:
                sentiment, _ = (
                    "恐慌",
                    sentiment_reason.append(f"赚钱效应差({profit_effect}%)"),
                )
            if limit_up_count >= 60:
                sentiment_reason.append(f"涨停家数活跃({limit_up_count})")
            if limit_down_count >= 20:
                sentiment_reason.append(f"跌停家数偏多({limit_down_count})")
            if streak_high is not None:
                sentiment_reason.append(f"连板高度{streak_high}")
            if break_rate is not None and break_rate >= 35:
                sentiment_reason.append(f"炸板率偏高({break_rate}%)")
            if congestion > 90:
                sentiment_reason.append(f"拥挤度过高({congestion:.1f}%),警惕回调")
            elif congestion < 20:
                sentiment_reason.append(f"拥挤度较低({congestion:.1f}%),或存机会")
            self.analysis_result["sentiment"] = {
                "综合情绪": sentiment,
                "情绪摘要": " | ".join(sentiment_reason),
                "赚钱效应": f"{profit_effect}%",
                "量价齐升家数": ljqs_count,
                "涨停家数": limit_up_count,
                "跌停家数": limit_down_count,
                "炸板率": f"{break_rate:.2f}%" if break_rate is not None else "未知",
                "连板高度": streak_high if streak_high is not None else "未知",
                "大盘拥挤度": f"{congestion:.2f}%",
            }
        except Exception as e:
            print(f"  - 市场情绪分析失败: {e}")
            self.analysis_result["sentiment"] = {}
        print("市场情绪温度分析完成。")

    def analyze_sector_strength(self):
        print("正在分析板块相对强弱度...")
        industry_flow = self.data.get("industry_fund_flow")
        if industry_flow is None or industry_flow.empty:
            print("  - 行业资金流数据为空，跳过板块强度分析。")
            self.analysis_result["sector_heat_map"] = pd.DataFrame()
            return
        industry_flow = industry_flow.copy()
        rename_dict = {
            "名称": "板块名称",
            "涨跌幅": "板块涨跌幅",
            "今日主力净流入-净额": "主力净流入",
        }
        industry_flow.rename(columns=rename_dict, inplace=True)
        ljqs_df = self.data.get("rank_ljqs", pd.DataFrame())
        if not ljqs_df.empty and self.stock_to_industry_map:
            ljqs_df["代码"] = ljqs_df["股票代码"].astype(str).str.zfill(6)
            ljqs_df["精确行业"] = ljqs_df["代码"].map(self.stock_to_industry_map)
            ljqs_counts = (
                ljqs_df.groupby("精确行业")["代码"]
                .count()
                .reset_index()
                .rename(columns={"代码": "量价齐升家数"})
            )
            industry_flow = pd.merge(
                industry_flow,
                ljqs_counts,
                left_on="板块名称",
                right_on="精确行业",
                how="left",
            )
            industry_flow["量价齐升家数"].fillna(0, inplace=True)
        else:
            industry_flow["量价齐升家数"] = 0

        # --- 数据清洗与稳健打分：避免 akshare 返回全 NaN/占位符导致 rank 输出 NaN ---
        industry_flow["量价齐升家数"] = pd.to_numeric(
            industry_flow.get("量价齐升家数", 0), errors="coerce"
        ).fillna(0)

        if "主力净流入" in industry_flow.columns:
            fund_net = pd.to_numeric(industry_flow["主力净流入"], errors="coerce")
            # akshare 有时会返回整列 NaN（接口字段仍在但数据缺失），此时给一个中性分，避免热力值全是 NaN
            if fund_net.notna().any():
                industry_flow["资金强度分"] = fund_net.rank(pct=True) * 100
            else:
                industry_flow["资金强度分"] = 50.0
        else:
            industry_flow["资金强度分"] = 50.0

        # 人气分：全为 0 时 rank 也会给出中位数百分比，不会 NaN
        industry_flow["人气强度分"] = industry_flow["量价齐升家数"].rank(pct=True) * 100

        industry_flow["热力值"] = (
            0.7 * industry_flow["人气强度分"] + 0.3 * industry_flow["资金强度分"]
        ).round(2)
        self.analysis_result["sector_heat_map"] = industry_flow.sort_values(
            by="热力值", ascending=False
        )
        print("板块相对强弱度分析完成。")

    def analyze_etf_technical(self):
        etf_spot_df = self.data["etf_spot"]
        print("正在对活跃ETF进行技术面分析 (支持断点续传)...")
        today_str = datetime.now().strftime("%Y%m%d")
        progress_file = os.path.join("../cache", f"etf_tech_progress_{today_str}.pkl")
        try:
            with open(progress_file, "rb") as f:
                all_etf_analysis = pickle.load(f)
            print(f"  - 检测到已有进度，已加载 {len(all_etf_analysis)} 条分析结果。")
        except FileNotFoundError:
            all_etf_analysis = []
        analyzed_codes = {item["code"] for item in all_etf_analysis}
        etfs_to_process = [
            (row["代码"], row["名称"])
            for _, row in etf_spot_df.iterrows()
            if row["代码"] not in analyzed_codes
        ]
        if not etfs_to_process:
            print("  - 所有ETF均已分析完毕。")
            self.analysis_result["etf_technical"] = all_etf_analysis
            return
        print(f"  - 需分析 {len(etfs_to_process)} 个新ETF...")
        with (
            ThreadPoolExecutor(max_workers=5) as executor,
            tqdm(
                total=len(etfs_to_process), desc="分析ETF进度", mininterval=1.0
            ) as pbar,
        ):
            futures = [
                executor.submit(self._analyze_single_etf, etf_info)
                for etf_info in etfs_to_process
            ]
            for future in futures:
                result = future.result()
                if result:
                    all_etf_analysis.append(result)
                    with open(progress_file, "wb") as f:
                        pickle.dump(all_etf_analysis, f)
                pbar.update(1)
        self.analysis_result["etf_technical"] = all_etf_analysis
        print(f"\n完成 {len(all_etf_analysis)} 个ETF的技术面分析。")

    def _analyze_single_etf(self, etf_info):
        etf_code, etf_name = etf_info
        try:
            etf_hist = ak.fund_etf_hist_em(
                symbol=etf_code, period="daily", adjust="qfq"
            ).tail(30)
            if len(etf_hist) < 21:
                return None
            etf_hist.loc[:, "MA5"] = etf_hist["收盘"].rolling(window=5).mean()
            etf_hist.loc[:, "MA20"] = etf_hist["收盘"].rolling(window=20).mean()
            status, base_score = "观察", 2.0
            latest = etf_hist.iloc[-1]
            if latest["收盘"] > latest["MA20"] and latest["MA5"] > latest["MA20"]:
                if latest["涨跌幅"] < 0:
                    status, base_score = "上涨趋势中的回调", 3.0
                else:
                    status, base_score = "强势加速上涨", 2.5
            elif latest["收盘"] < latest["MA20"]:
                status, base_score = "弱势下跌通道", 1.0
            return {
                "name": etf_name,
                "code": etf_code,
                "technical_status": status,
                "base_score": base_score,
                "change_pct": latest["涨跌幅"],
            }
        except Exception as e:
            if DEBUG_MODE:
                print(f"\n  - [错误] 分析ETF {etf_name}({etf_code}) 失败: {e}")
            return None

    def comprehensive_scoring(self):
        print("开始进行综合评分...")
        final_scores = []
        if (
            not self.analysis_result.get("etf_technical")
            or self.analysis_result.get("sector_heat_map", pd.DataFrame()).empty
        ):
            return
        heat_map = self.analysis_result["sector_heat_map"]
        theme_to_heat = {
            row["板块名称"]: row["热力值"] for _, row in heat_map.iterrows()
        }
        for etf in self.analysis_result["etf_technical"]:
            score = etf["base_score"]
            reasons = [f"技术面: {etf['technical_status']} (基础分: {score:.1f})"]
            specific_sector, broad_theme = self.get_etf_sector_and_theme(etf["name"])
            heat_value = theme_to_heat.get(specific_sector, 50)
            heat_score = (heat_value - 50) / 15
            score += heat_score
            reasons.append(f"板块热力: {heat_score:.1f} (热力值: {heat_value})")
            final_score = np.clip(score, 0, 5)
            if final_score >= 3.5 and etf["change_pct"] < 0:
                reasons.append("回调但趋势未破，或为低吸机会")
            final_scores.append(
                {
                    "名称": etf["name"],
                    "代码": etf["code"],
                    "涨跌幅": etf["change_pct"],
                    "最终得分": final_score,
                    "分析摘要": " | ".join(reasons),
                    "主题": broad_theme,
                }
            )
        df = (
            pd.DataFrame(final_scores)
            .sort_values(by="最终得分", ascending=False)
            .reset_index(drop=True)
        )
        self.analysis_result["final_ranking"] = df
        print("综合评分完成。")

    def get_etf_sector_and_theme(self, etf_name):
        map_rules = {
            ("证券", "大金融"): ["证券", "券商"],
            ("保险", "大金融"): ["保险"],
            ("银行", "大金融"): ["银行"],
            ("半导体", "科技/半导体"): ["半导体", "芯片"],
            ("计算机", "科技/半导体"): [
                "计算机",
                "信创",
                "软件",
                "云计算",
                "AI",
                "人工智能",
            ],
            ("消费电子", "科技/半导体"): ["消费电子"],
            ("通信设备", "科技/半导体"): ["5G", "通信"],
            ("光学光电子", "科技/半导体"): ["光学"],
            ("光伏设备", "大新能源"): ["光伏"],
            ("电池", "大新能源"): ["电池", "锂电", "新能车", "电动车"],
            ("电网设备", "大新能源"): ["电网", "特高压"],
            ("食品饮料", "大消费"): ["食品", "饮料", "白酒", "消费"],
            ("家电行业", "大消费"): ["家电"],
            ("美容护理", "大消费"): ["医美", "美容"],
            ("医药商业", "医疗健康"): ["医药"],
            ("医疗服务", "医疗健康"): ["医疗"],
            ("中药", "医疗健康"): ["中药"],
            ("房地产开发", "房地产"): ["地产", "房地产"],
            ("游戏", "传媒/游戏"): ["游戏"],
            ("文化传媒", "传媒/游戏"): ["传媒", "影视"],
            ("国防军工", "军工"): ["军工", "国防"],
            ("煤炭行业", "周期/材料"): ["煤炭"],
            ("有色金属", "周期/材料"): ["有色"],
            ("钢铁行业", "周期/材料"): ["钢铁"],
            ("化学原料", "周期/材料"): ["化工"],
            ("工程机械", "高端制造"): ["机械", "制造"],
            ("专用设备", "高端制造"): ["设备"],
            ("物流行业", "交通运输"): ["运输", "物流", "航运", "港口"],
            ("农牧饲渔", "大农业"): ["农业", "养殖", "畜牧"],
        }
        if any(kw in etf_name for kw in ["恒生", "H股", "港股", "中概", "互联网"]):
            return "港股", "港股"
        for (sector, theme), keywords in map_rules.items():
            if any(keyword in etf_name for keyword in keywords):
                return sector, theme
        return "其他", "其他"

    def analyze_market_stage(self):
        print("正在进行市场阶段定性分析...")
        try:
            position_desc = self.analysis_result.get("intermarket", {}).get(
                "position_desc", "未知"
            )
            volume_level = self.analysis_result.get("liquidity", {}).get(
                "volume_qualitative_level", "未知"
            )
            main_inflow_str = self.analysis_result.get("liquidity", {}).get(
                "main_net_inflow", "0亿元"
            )
            main_inflow_value = float(re.findall(r"-?\d+\.?\d*", main_inflow_str)[0])
            stage_desc, risk_type = (
                "市场阶段特征不明显。",
                "趋势性风险与技术性风险均需关注。",
            )
            if position_desc == "高位区域":
                if volume_level in ["天量水平", "巨量水平"]:
                    if main_inflow_value < -50:
                        stage_desc, risk_type = (
                            "当前市场处于【上涨趋势末期】的巨量换手阶段，主力资金分歧加大，离场意愿明显。",
                            "趋势性风险上升，技术性回调风险剧增。",
                        )
                    else:
                        stage_desc, risk_type = (
                            "当前市场处于【牛市中期】的巨量换手阶段，资金承接良好但波动加剧。",
                            "趋势保持但技术性回调风险加剧。",
                        )
                else:
                    stage_desc, risk_type = (
                        "当前市场处于【高位震荡】阶段，短期上攻动能减弱，进入存量博弈。",
                        "趋势面临考验，技术性风险较高。",
                    )
            elif position_desc == "低位区域":
                if volume_level == "地量水平":
                    stage_desc, risk_type = (
                        "当前市场处于【熊市末期或牛市初期】的筑底阶段，成交持续低迷，市场关注度低。",
                        "趋势性风险已大幅释放，但仍需警惕技术性探底风险。",
                    )
                else:
                    stage_desc, risk_type = (
                        "当前市场处于【低位反弹】阶段，资金尝试抄底，但趋势反转仍需确认。",
                        "趋势性风险仍存，技术性反弹非反转。",
                    )
            else:
                stage_desc, risk_type = (
                    "当前市场处于【震荡整固】阶段，多空双方力量均衡，等待方向选择。",
                    "趋势不明朗，主要为技术性波动风险。",
                )
            self.analysis_result["market_stage"] = {
                "stage_description": stage_desc,
                "risk_type": risk_type,
            }
        except Exception as e:
            print(f"  - 市场阶段定性分析失败: {e}")
            self.analysis_result["market_stage"] = {}
        print("市场阶段定性分析完成。")

    def analyze_conclusion(self):
        print("正在调用AI进行动态复盘与决策建议...")
        if not AI_TOOL_AVAILABLE:
            print("  - AI工具不可用，跳过动态复盘。")
            self.analysis_result["conclusion_raw"] = "{}"  # 返回一个空的JSON字符串
            return
        try:
            liquidity = self.analysis_result.get("liquidity", {})
            sentiment = self.analysis_result.get("sentiment", {})
            intermarket = self.analysis_result.get("intermarket", {})
            heat_map = self.analysis_result.get("sector_heat_map", pd.DataFrame())
            ranking = self.analysis_result.get("final_ranking", pd.DataFrame())
            turnover = self.analysis_result.get("turnover", {})
            market_stage = self.analysis_result.get("market_stage", {})
            margin_trading = self.analysis_result.get("margin_trading", {})
            northbound = self.analysis_result.get("northbound", {})
            style = self.analysis_result.get("style", {})
            top_sectors = (
                heat_map.head(5)["板块名称"].tolist() if not heat_map.empty else []
            )
            bottom_sectors = (
                heat_map.tail(5)["板块名称"].tolist() if not heat_map.empty else []
            )
            opportunities = []
            if not ranking.empty:
                opp_df = ranking[ranking["最终得分"] >= 3.5].head(3)
                opportunities = [
                    f"{row['主题']}({row['代码']}, 现价涨跌幅: {row['涨跌幅']:.2f}%)"
                    for _, row in opp_df.iterrows()
                ]

            system_prompt = """
角色：你是一位顶级的A股市场分析师，风格冷静、客观、一针见血。
任务：根据我提供的结构化数据，生成一份专业的JSON格式分析报告。
严格要求：
1.  **JSON结构**: 返回内容必须是严格的JSON，且必须包含以下三个顶级键: "核心矛盾解读", "操作建议", "情景推演"。
    **参考格式如下**:
    ```json
    {
      "核心矛盾解读": {
        "量价背离": "总成交额3.17万亿创历史天量但指数下跌1.76%，显示资金在高位激烈换手但承接不足",
        "多空博弈": "主力资金净流出1536亿与散户净流入1294亿形成尖锐对立，杠杆资金逆势加仓191亿加剧市场波动",
        "风格割裂": "科技半导体ETF维持强势(588780涨2.29%)与金融权重板块(银行/保险)领跌形成冰火格局",
        "技术面冲突": "60日线维持多头排列但日线MACD顶背离，短期超买修复需求与中期趋势形成矛盾"
      },
      "操作建议": {
        "仓位管理": "将总仓位降至60%以下，保留10%现金应对可能的技术性反抽",
        "持仓结构调整": {
          "增持方向": "半导体ETF(588780/516920)的回调机会，关注5日线支撑",
          "减持方向": "融资余额占比超2.3%的高杠杆品种及破位金融股"
        },
        "风险对冲": "可配置20%仓位的国债ETF或黄金ETF对冲股债性价比恶化风险",
        "关键观察点": [
          "明日若反弹至3850点附近且量能不足2.8万亿，建议减仓至50%",
          "关注科创50指数能否守住2700点关键技术位",
          "跟踪两市融资余额变化，若单日减少超300亿需警惕杠杆资金撤离"
        ]
      },
      "情景推演": {
        "标题": "明日走势推演",
        "基准情景": "60%概率维持3800-3850点震荡，量能回落至2.8万亿以下(延续今日尾盘弱势)",
        "乐观情景": "30%概率放量反包今日阴线(需成交额超3.2万亿且北向净流入超80亿)",
        "悲观情景": "10%概率有效跌破3780点引发技术抛盘(关注券商板块是否破位)"
      }
    }
    ```
2.  **内容要求**:
    -   **核心矛盾解读**: 深入分析数据间的背离和矛盾点。
    -   **操作建议**: 必须清晰、可执行、结构化。
    -   **情景推演**: 根据【报告类型】和【推演标题】生成，包含概率、描述和关键观察点。
3.  **语言风格**: 保持冷静、客观、数据驱动的风格。
"""
            report_type_map = {
                "LIVE_MORNING": "盘中实时分析 (早盘)",
                "MIDDAY_SUMMARY": "午间总结",
                "LIVE_AFTERNOON": "盘中实时分析 (午盘)",
                "POST_MARKET": "盘后复盘",
            }
            forecast_title_map = {
                "LIVE_MORNING": "上午收盘推演",
                "MIDDAY_SUMMARY": "下午走势推演",
                "LIVE_AFTERNOON": "收盘走势推演",
                "POST_MARKET": "明日走势推演",
            }
            report_type = report_type_map.get(self.run_mode, "盘后复盘")
            forecast_title = forecast_title_map.get(self.run_mode, "明日走势推演")

            inflow_perc = liquidity.get("inflow_percentage", 0)
            inflow_perc_str = (
                f"净流入占比 {inflow_perc:.2f}%"
                if inflow_perc > 0
                else f"净流出占比 {abs(inflow_perc):.2f}%"
            )

            user_prompt = f"""
请根据以下今日A股数据，生成一份【{report_type}】报告，推演标题请使用【{forecast_title}】:
【市场阶段定性】
- 宏观判断: {market_stage.get("stage_description", "未知")}
- 主要风险: {market_stage.get("risk_type", "未知")}
【宏观与流动性分析】
- 上证指数: {intermarket.get("sh_index_close", "未知")}点 ({intermarket.get("sh_pct_chg", 0.00):.2f}%), 处于60日{intermarket.get("position_desc", "未知")}
- 大盘趋势: {intermarket.get("market_trend", "未知")}
- 股债关系: {intermarket.get("relation", "未知")}
- A股总成交额: {liquidity.get("total_volume", "未知")}{liquidity.get("estimated_turnover_str", "")} ({liquidity.get("volume_change_desc", "")}, {liquidity.get("volume_qualitative_level", "")}) | 来源: {liquidity.get("turnover_source", "未知")}
- 指数成交额拆分: 上证 {liquidity.get("index_turnover_breakdown", {}).get("sh_index", "未知")} | 深证 {liquidity.get("index_turnover_breakdown", {}).get("sz_index", "未知")}
- 市场换手率: {turnover.get("market_turnover_rate", "未知")} ({turnover.get("turnover_level", "未知")})
- 主力与散户行为: 主力净流入 {liquidity.get("main_net_inflow", "未知")} ({inflow_perc_str}) | 散户净流入 {liquidity.get("retail_net_inflow", "未知")}
- 杠杆资金动态: 两市融资余额 {margin_trading.get("total_balance", "未知")}，较前一日{margin_trading.get("change_desc", "变化未知")}。市场杠杆率 {margin_trading.get("leverage_ratio", "未知")} (当前处于 {margin_trading.get("leverage_level", "未知")} 水平)
【北向资金】
- 北向净流入: {northbound.get("total_net_inflow", "未知")}，5日均值: {northbound.get("five_day_avg", "未知")}，趋势: {northbound.get("flow_trend", "未知")}
- 沪股通: {northbound.get("sh_net_inflow", "未知")} | 深股通: {northbound.get("sz_net_inflow", "未知")}
- 集中行业: {", ".join(northbound.get("top_industries", [])) if northbound.get("top_industries") else "未知"}
- 代表个股: {", ".join(northbound.get("top_stocks", [])) if northbound.get("top_stocks") else "未知"}
【风格与分市场】
- 强弱总结: {style.get("style_summary", "未知")}
- 日内强度排序: {", ".join(style.get("performance_rank", [])) if style.get("performance_rank") else "未知"}
【情绪分析】
- 综合情绪: {sentiment.get("综合情绪", "未知")}
- 赚钱效应: {sentiment.get("赚钱效应", "未知")}
- 量价齐升家数: {sentiment.get("量价齐升家数", "未知")}
- 涨停/跌停: {sentiment.get("涨停家数", "未知")}/{sentiment.get("跌停家数", "未知")}
- 炸板率: {sentiment.get("炸板率", "未知")} | 连板高度: {sentiment.get("连板高度", "未知")}
- 大盘拥挤度: {sentiment.get("大盘拥挤度", "未知")}
【板块热力】
- 当前最强板块: {", ".join(top_sectors)}
- 当前最弱板块: {", ".join(bottom_sectors)}
- 潜在机会ETF(含实时价格): {", ".join(opportunities)}
"""
            content_string = chat_volces(system=system_prompt, user=user_prompt)
            # [V21.0] 直接展示AI的原始内容，不做解析；但要避免把底层异常(如 401)直接当作“观点”
            if isinstance(content_string, str) and (
                content_string.startswith("AI调用失败")
                or content_string.startswith("AI调用未配置")
            ):
                self.analysis_result["conclusion_raw"] = content_string
            else:
                self.analysis_result["conclusion_raw"] = content_string
            print("AI动态复盘与决策建议生成完毕。")
        except Exception as e:
            print(f"  - AI动态复盘失败: {e}")
            self.analysis_result["conclusion_raw"] = "AI分析模块出现异常，请检查日志。"

    def print_report(self):
        report_content = []

        report = self.analysis_result
        time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        report_title_map = {
            "LIVE_MORNING": "A股市场多维度实时分析报告 (早盘)",
            "MIDDAY_SUMMARY": "A股市场午间总结报告",
            "LIVE_AFTERNOON": "A股市场多维度实时分析报告 (午盘)",
            "POST_MARKET": "A股市场多维度综合复盘报告",
        }
        report_title = report_title_map.get(self.run_mode, "A股市场分析报告")

        # --- 开始构建报告字符串 ---
        report_content.append("=" * 80)
        report_content.append(f"{report_title} ({time_str})")
        report_content.append("=" * 80)

        market_stage = report.get("market_stage", {})
        if market_stage:
            report_content.append("\n一、市场阶段定性")
            report_content.append(
                f"  - 宏观判断: {market_stage.get('stage_description', '未能生成')}"
            )
            report_content.append(
                f"  - 主要风险: {market_stage.get('risk_type', '未能生成')}"
            )

        conclusion_raw = report.get("conclusion_raw", "")
        report_content.append("\n二、核心观点与操作建议 (由AI生成)")
        if conclusion_raw:
            # 直接展示AI返回的原始内容，不做解析
            report_content.append(conclusion_raw)
        else:
            report_content.append("未能生成AI分析。")

        intermarket = report.get("intermarket", {})
        liquidity = report.get("liquidity", {})
        turnover = report.get("turnover", {})
        margin_trading = report.get("margin_trading", {})
        report_content.append("\n三、大盘与跨市场分析 (纯数据)")
        report_content.append(
            f"  - 上证指数: 【{intermarket.get('sh_index_close', '未知')} ({intermarket.get('sh_pct_chg', 0.00):.2f}%)】，目前处于60日【{intermarket.get('position_desc', '未知')}】"
        )
        report_content.append(
            f"  - 大盘趋势: 【{intermarket.get('market_trend', '未知')}】 | 股债关系: 【{intermarket.get('relation', '未知')}】"
        )
        report_content.append(
            f"  - 成交量:   【{liquidity.get('total_volume', '未知')}{liquidity.get('estimated_turnover_str', '')}】，{liquidity.get('volume_level', '')} ({liquidity.get('volume_change_desc', '')})，属于【{liquidity.get('volume_qualitative_level', '未知')}】 | 来源: {liquidity.get('turnover_source', '未知')}"
        )
        idx_breakdown = liquidity.get("index_turnover_breakdown")
        if idx_breakdown:
            report_content.append(
                f"  - 指数成交额拆分: 上证 {idx_breakdown.get('sh_index', '未知')} | 深证 {idx_breakdown.get('sz_index', '未知')}"
            )
        report_content.append(
            f"  - 换手率:   【{turnover.get('market_turnover_rate', '未知')}】，当前市场活跃度【{turnover.get('turnover_level', '未知')}】"
        )
        inflow_perc_str = f"占比{abs(liquidity.get('inflow_percentage', 0)):.2f}%"
        report_content.append(
            f"  - 主力行为: 主力净流入 {liquidity.get('main_net_inflow', '未知')} ({inflow_perc_str}) | 散户净流入 {liquidity.get('retail_net_inflow', '未知')}"
        )
        report_content.append(
            f"  - 杠杆资金: 两市融资余额【{margin_trading.get('total_balance', '未知')}】，较前一日【{margin_trading.get('change_desc', '未知')}】"
        )
        report_content.append(
            f"  - 市场杠杆率: 【{margin_trading.get('leverage_ratio', '未知')}】，当前处于【{margin_trading.get('leverage_level', '未知')}】水平"
        )
        northbound = report.get("northbound", {})
        if northbound:
            report_content.append(
                f"  - 北向净流入: 【{northbound.get('total_net_inflow', '未知')}】 | 5日均值: {northbound.get('five_day_avg', '未知')} | {northbound.get('flow_trend', '未知')}"
            )
            report_content.append(
                f"  - 沪/深股通: 沪 {northbound.get('sh_net_inflow', '未知')} | 深 {northbound.get('sz_net_inflow', '未知')}"
            )
            if northbound.get("top_industries"):
                report_content.append(
                    f"  - 北向集中行业: {', '.join(northbound.get('top_industries', []))}"
                )
            if northbound.get("top_stocks"):
                report_content.append(
                    f"  - 北向代表个股: {', '.join(northbound.get('top_stocks', []))}"
                )

        style = report.get("style", {})
        if style:
            report_content.append("\n四、风格与分市场对比")
            report_content.append(f"  - 强弱总结: {style.get('style_summary', '未知')}")
            if style.get("performance_rank"):
                report_content.append(
                    f"  - 日内强度排序: {', '.join(style.get('performance_rank', []))}"
                )

        sentiment = report.get("sentiment", {})
        report_content.append("\n五、市场情绪温度计")
        report_content.append(
            f"  - 综合情绪: 【{sentiment.get('综合情绪', '未知')}】 | {sentiment.get('情绪摘要', '无')}"
        )
        report_content.append(
            f"  - 核心指标: 赚钱效应: {sentiment.get('赚钱效应', '未知')}, 量价齐升家数: {sentiment.get('量价齐升家数', '未知')}, 涨停/跌停: {sentiment.get('涨停家数', '未知')}/{sentiment.get('跌停家数', '未知')}, 炸板率: {sentiment.get('炸板率', '未知')}, 连板高度: {sentiment.get('连板高度', '未知')}, 大盘拥挤度: {sentiment.get('大盘拥挤度', '未知')}"
        )

        if "sector_heat_map" in report and not report["sector_heat_map"].empty:
            heat_map = report["sector_heat_map"]
            report_content.append("\n六、板块热力追踪 (人气+资金)")
            report_content.append("  --- 【当前最强板块 (TOP 5)】 ---")
            top5 = heat_map.head(5)
            for _, row in top5.iterrows():
                report_content.append(
                    f"  - 热力值: {row['热力值']:.1f} | {row['板块名称']} (量价齐升: {int(row.get('量价齐升家数', 0))})"
                )
            report_content.append("\n  --- 【当前最弱板块 (BOTTOM 5)】 ---")
            bot5 = heat_map.tail(5)
            for _, row in bot5.sort_values(by="热力值", ascending=True).iterrows():
                report_content.append(
                    f"  - 热力值: {row['热力值']:.1f} | {row['板块名称']} (量价齐升: {int(row.get('量价齐升家数', 0))})"
                )

        if "final_ranking" in report and not report["final_ranking"].empty:
            ranking_df = report["final_ranking"]
            report_content.append("\n七、ETF综合评分排名 (基于技术面与板块热力)")
            report_content.append("\n  --- 【机会清单 (TOP 5 主题)】 ---")
            opportunities = ranking_df[ranking_df["最终得分"] >= 3.5]
            if not opportunities.empty:
                displayed_themes, count = set(), 0
                for _, row in opportunities.iterrows():
                    if row["主题"] not in displayed_themes:
                        report_content.append(
                            f"  - 得分: {row['最终得分']:.1f} | {row['名称']} ({row['代码']}) | 主题: {row['主题']} | 实时涨跌: {row['涨跌幅']:.2f}%"
                        )
                        report_content.append(f"    摘要: {row['分析摘要']}")
                        displayed_themes.add(row["主题"])
                        count += 1
                    if count >= 5:
                        break
                if count == 0:
                    report_content.append("    当前市场未发现得分高于3.5的显著机会。")
            else:
                report_content.append("    当前市场未发现得分高于3.e5的显著机会。")

            report_content.append("\n  --- 【风险清单 (BOTTOM 5 主题)】 ---")
            risks = ranking_df[ranking_df["最终得分"] <= 1.5].sort_values(
                by="最终得分", ascending=True
            )
            if not risks.empty:
                displayed_themes, count = set(), 0
                for _, row in risks.iterrows():
                    if row["主题"] not in displayed_themes:
                        report_content.append(
                            f"  - 得分: {row['最终得分']:.1f} | {row['名称']} ({row['代码']}) | 主题: {row['主题']} | 实时涨跌: {row['涨跌幅']:.2f}%"
                        )
                        report_content.append(f"    摘要: {row['分析摘要']}")
                        displayed_themes.add(row["主题"])
                        count += 1
                    if count >= 5:
                        break
                if count == 0:
                    report_content.append("    当前市场未发现得分低于1.5的显著风险。")
            else:
                report_content.append("    当前市场未发现得分低于1.5的显著风险。")

        report_content.append("\n" + "=" * 80)
        report_content.append(
            "免责声明: 本报告基于公开数据和量化模型生成，所有结论仅供参考，不构成任何投资建议。"
        )
        report_content.append("=" * 80)

        # --- 将报告内容整合为单一字符串 ---
        full_report_string = "\n".join(report_content)

        # --- 打印到控制台 ---
        print("\n\n" + full_report_string)

        # --- 保存到文件 ---
        if not os.path.exists("../reports"):
            os.makedirs("../reports")

        # 创建一个安全的文件名
        safe_time_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        report_filename = os.path.join(
            "../reports", f"A_Share_Report_{safe_time_str}.txt"
        )

        try:
            with open(report_filename, "w", encoding="utf-8") as f:
                f.write(full_report_string)
            print(f"\n报告已成功保存至: {report_filename}")
        except Exception as e:
            print(f"\n[错误] 报告保存失败: {e}")

    def run_analysis(self):
        now = datetime.now()
        trade_day = self._is_trade_day(now.date())
        self.is_trading_day = trade_day if trade_day is not None else now.weekday() < 5
        if self.is_trading_day:
            if 9 <= now.hour < 12:
                self.run_mode = "LIVE_MORNING"
            elif 12 <= now.hour < 13:
                self.run_mode = "MIDDAY_SUMMARY"
            elif 13 <= now.hour < 15:
                self.run_mode = "LIVE_AFTERNOON"
            else:
                self.run_mode = "POST_MARKET"
        else:
            self.run_mode = "POST_MARKET"
        print(
            f"--- 当前时间: {now.strftime('%H:%M:%S')}, 运行模式: {self.run_mode} ---"
        )

        clean_old_cache()

        if self.fetch_data():
            self.analyze_market_liquidity()
            self.analyze_market_turnover()
            self.analyze_margin_trading()
            self.analyze_northbound_fund_flow()
            self.analyze_intermarket_relationship()
            self.analyze_market_style()
            self.analyze_limitup_structure()
            self.analyze_market_sentiment()
            self.analyze_sector_strength()
            self.analyze_market_stage()
            # self.analyze_etf_technical()
            self.comprehensive_scoring()
            self.analyze_conclusion()
            self.print_report()


if __name__ == "__main__":
    analyzer = AdvancedStockAnalyzer()
    analyzer.run_analysis()
