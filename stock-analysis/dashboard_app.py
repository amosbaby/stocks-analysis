import json
from typing import Any, Dict

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


def load_report() -> Dict[str, Any]:
    # Replace this with a backend call, e.g. requests.get("http://127.0.0.1:3008/api/report").json()
    raw = {
        "as_of": "2026-01-08 09:32",
        "market_qualitative": "上涨趋势末期",
        "warning": "仓位立即降至50%以下",
        "risk": {"volume_trillion": 3.45, "leverage_pct": 2.53},
        "flows": {"main_billion": -633, "retail_billion": 576},
        "sentiment_temp": 86,
        "sectors": [
            {"name": "煤炭", "heat": 92},
            {"name": "制药", "heat": 88},
            {"name": "有色", "heat": 64},
            {"name": "电力设备", "heat": 52},
            {"name": "金融", "heat": 18},
            {"name": "游戏", "heat": 12},
            {"name": "消费", "heat": 41},
        ],
        "scenarios": [
            {"name": "基准", "prob": 0.45, "desc": "高位震荡，风险边际收缩"},
            {"name": "乐观", "prob": 0.20, "desc": "情绪续热，但量能透支"},
            {"name": "悲观", "prob": 0.35, "desc": "量价背离扩大，回撤加速"},
        ],
    }
    return raw


def build_gauge(value: float) -> go.Figure:
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=value,
            number={"suffix": "°C", "font": {"color": "#F9F6EE", "size": 36}},
            gauge={
                "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "#5E6A7A"},
                "bar": {"color": "#FF3B30"},
                "bgcolor": "#0B111A",
                "borderwidth": 1,
                "bordercolor": "#1B2430",
                "steps": [
                    {"range": [0, 40], "color": "#0F2A2A"},
                    {"range": [40, 70], "color": "#1E2C1F"},
                    {"range": [70, 100], "color": "#2B1917"},
                ],
                "threshold": {
                    "line": {"color": "#FFD60A", "width": 4},
                    "thickness": 0.85,
                    "value": 80,
                },
            },
            title={"text": "情绪温度", "font": {"color": "#9AA4B2", "size": 16}},
        )
    )
    fig.update_layout(margin=dict(l=20, r=20, t=30, b=20), paper_bgcolor="#0B111A")
    return fig


def build_flow_bars(flows: Dict[str, float]) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=["主力", "散户"],
            y=[flows["main_billion"], flows["retail_billion"]],
            marker_color=["#FF3B30", "#34C759"],
            text=[f"{flows['main_billion']}亿", f"{flows['retail_billion']}亿"],
            textposition="outside",
        )
    )
    fig.update_layout(
        height=260,
        paper_bgcolor="#0B111A",
        plot_bgcolor="#0B111A",
        font_color="#C7D0D9",
        xaxis=dict(showgrid=False, zeroline=False),
        yaxis=dict(
            showgrid=True, gridcolor="#1B2430", zeroline=True, zerolinecolor="#394455"
        ),
        margin=dict(l=20, r=20, t=20, b=20),
    )
    return fig


def build_treemap(sectors: list[Dict[str, Any]]) -> go.Figure:
    fig = px.treemap(
        sectors,
        path=["name"],
        values="heat",
        color="heat",
        color_continuous_scale=["#1E2C1F", "#FFD60A", "#FF3B30"],
        range_color=(0, 100),
    )
    fig.update_layout(
        height=320,
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="#0B111A",
        font_color="#E6EDF3",
        coloraxis_showscale=False,
    )
    return fig


def main() -> None:
    st.set_page_config(page_title="A股风险监控台", layout="wide")
    st.markdown(
        """
        <style>
        :root {
            color-scheme: dark;
        }
        html, body, [class*="css"]  {
            background-color: #0B111A;
            color: #E6EDF3;
            font-family: "IBM Plex Sans", "Noto Sans CJK SC", sans-serif;
        }
        .panel {
            background: #0F1521;
            border: 1px solid #1B2430;
            border-radius: 12px;
            padding: 16px;
            box-shadow: 0 0 0 1px rgba(255,255,255,0.02) inset;
        }
        .grid {
            display: grid;
            grid-template-columns: 1.2fr 1fr 1fr;
            gap: 16px;
        }
        .row {
            display: grid;
            grid-template-columns: 1.5fr 1fr;
            gap: 16px;
        }
        .warning {
            background: linear-gradient(120deg, #3A0D0D, #140707);
            border: 1px solid #FF3B30;
            border-radius: 14px;
            padding: 18px;
            animation: blink 1.2s infinite;
        }
        .warning h2 {
            margin: 0 0 6px 0;
            color: #FF3B30;
            font-size: 20px;
            letter-spacing: 0.5px;
        }
        .warning p {
            margin: 0;
            color: #FDECEC;
            font-size: 16px;
        }
        @keyframes blink {
            0%, 100% { box-shadow: 0 0 0 0 rgba(255,59,48,0.8); }
            50% { box-shadow: 0 0 16px 2px rgba(255,59,48,0.65); }
        }
        .kpi {
            display: flex;
            justify-content: space-between;
            gap: 12px;
        }
        .kpi div {
            flex: 1;
            background: #0B111A;
            border: 1px solid #1B2430;
            border-radius: 10px;
            padding: 12px;
        }
        .kpi span {
            display: block;
            color: #6B7789;
            font-size: 12px;
        }
        .kpi strong {
            font-size: 20px;
            color: #F9F6EE;
        }
        .scenario {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 12px;
        }
        .scenario .card {
            background: #0B111A;
            border: 1px solid #1B2430;
            border-radius: 12px;
            padding: 12px;
        }
        .scenario .name {
            color: #FFD60A;
            font-weight: 600;
        }
        .scenario .prob {
            color: #9AA4B2;
            font-size: 12px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    report = load_report()
    st.markdown(
        f"""
        <div class="panel">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <h1 style="margin:0; font-size:26px;">A股风险监控台</h1>
                    <div style="color:#6B7789; font-size:13px;">{report["as_of"]}</div>
                </div>
                <div style="color:#FFD60A; font-size:14px;">市场定性：{report["market_qualitative"]}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div class="warning" style="margin-top:16px;">
            <h2>预警区</h2>
            <p>{report["warning"]}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="grid" style="margin-top:16px;">', unsafe_allow_html=True)

    with st.container():
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.plotly_chart(build_gauge(report["sentiment_temp"]), use_container_width=True)
        st.markdown(
            f"""
            <div class="kpi">
                <div>
                    <span>天量滞涨成交额</span>
                    <strong>{report["risk"]["volume_trillion"]}万亿</strong>
                </div>
                <div>
                    <span>杠杆率</span>
                    <strong>{report["risk"]["leverage_pct"]}%</strong>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

    with st.container():
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.markdown("<h3 style='margin-top:0;'>背离区</h3>", unsafe_allow_html=True)
        st.plotly_chart(build_flow_bars(report["flows"]), use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with st.container():
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.markdown("<h3 style='margin-top:0;'>板块热力</h3>", unsafe_allow_html=True)
        st.plotly_chart(build_treemap(report["sectors"]), use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="row" style="margin-top:16px;">', unsafe_allow_html=True)

    with st.container():
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.markdown("<h3 style='margin-top:0;'>推演区</h3>", unsafe_allow_html=True)
        st.markdown('<div class="scenario">', unsafe_allow_html=True)
        for item in report["scenarios"]:
            st.markdown(
                f"""
                <div class="card">
                    <div class="name">{item["name"]}</div>
                    <div class="prob">概率 {int(item["prob"] * 100)}%</div>
                    <div style="margin-top:8px; color:#C7D0D9;">{item["desc"]}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        st.markdown("</div></div>", unsafe_allow_html=True)

    with st.container():
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.markdown(
            "<h3 style='margin-top:0;'>JSON 入参示例</h3>", unsafe_allow_html=True
        )
        st.code(json.dumps(report, ensure_ascii=False, indent=2), language="json")
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
