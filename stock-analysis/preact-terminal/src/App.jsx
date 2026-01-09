import { useEffect, useMemo, useRef, useState } from "preact/hooks";
import * as echarts from "echarts";

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || "";
const toApiUrl = (path) => {
  if (!apiBaseUrl) return path;
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  if (apiBaseUrl.endsWith("/api") && normalizedPath.startsWith("/api/")) {
    return `${apiBaseUrl}${normalizedPath.slice(4)}`;
  }
  return `${apiBaseUrl}${normalizedPath}`;
};

const fallbackReport = {
  timestamp: "2026-01-08 09:32:08",
  index: 4077.72,
  change: -0.2,
  volumeEstimate: "3.45",
  leverageRate: 2.53,
  mainFlow: -633.24,
  retailFlow: 576.26,
  winRate: 40.9,
  sectors: {
    strong: [
      { name: "煤炭行业", value: 90.3 },
      { name: "化学制药", value: 89.9 },
      { name: "汽车零部件", value: 86.9 },
      { name: "塑料制品", value: 85.1 },
      { name: "小金属", value: 83.4 },
    ],
    weak: [
      { name: "证券", value: 9.8 },
      { name: "船舶制造", value: 16.2 },
      { name: "保险", value: 17.3 },
      { name: "银行", value: 18.5 },
      { name: "游戏", value: 21.6 },
    ],
  },
  scenarios: [
    {
      title: "基准情景",
      probability: 60,
      type: "base",
      description:
        "指数在4060-4085区间弱势震荡。主力持续流出，散户流入放缓，放量滞涨疲态尽显。",
    },
    {
      title: "乐观情景",
      probability: 25,
      type: "optimistic",
      description:
        "金融板块早盘急跌后小幅反弹，带动指数收于4090上方。需成交额维持且主力流出收窄。",
    },
    {
      title: "悲观情景",
      probability: 15,
      type: "pessimistic",
      description:
        "跌破4060支撑下探4040。主力流出加速，引发杠杆资金恐慌抛售，出现跳水行情。",
    },
  ],
  aiAdvice: [
    "立即将总仓位降至50%以下，停止任何形式的追高买入。",
    "优先减持融资占比较高、今日领跌的金融权重股及技术面破位品种。",
    "配置10%-15%仓位的货币ETF或国债逆回购锁定流动性。",
    "紧盯主力流向，若午后流出超1000亿需进一步减仓。",
  ],
};

function useEChart(ref, option) {
  useEffect(() => {
    if (!ref.current) return;
    const chart = echarts.init(ref.current);
    chart.setOption(option);
    const onResize = () => chart.resize();
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      chart.dispose();
    };
  }, [ref, option]);
}

function MetricCard({ label, value, unit, status, subValue }) {
  const statusColors = {
    danger: "text-red-500 border-red-900/50 bg-red-950/20",
    warning: "text-yellow-500 border-yellow-900/50 bg-yellow-950/20",
    neutral: "text-zinc-400 border-zinc-800 bg-zinc-900/50",
    success: "text-green-500 border-green-900/50 bg-green-950/20",
  };
  return (
    <div
      class={`p-4 border rounded-lg ${statusColors[status]} transition-all duration-300`}
    >
      <div class="text-xs font-medium uppercase tracking-wider mb-1 opacity-70">
        {label}
      </div>
      <div class="flex items-baseline gap-1">
        <span class="text-2xl font-bold mono">{value}</span>
        {unit && <span class="text-xs opacity-60">{unit}</span>}
      </div>
      {subValue && <div class="text-xs mt-1 opacity-80">{subValue}</div>}
    </div>
  );
}

const toNumber = (value) => {
  const num = Number(value);
  return Number.isFinite(num) ? num : 0;
};

const formatFlow = (value) => Math.abs(toNumber(value)).toFixed(2);
const reportTitles = [
  {
    key: "LIVE_MORNING",
    title: "A股市场多维度实时分析报告 (早盘)",
  },
  {
    key: "MIDDAY_SUMMARY",
    title: "A股市场午间总结报告",
  },
  {
    key: "LIVE_AFTERNOON",
    title: "A股市场多维度实时分析报告 (午盘)",
  },
  {
    key: "POST_MARKET",
    title: "A股市场多维度综合复盘报告",
  },
];

export default function App() {
  const gaugeRef = useRef(null);
  const flowRef = useRef(null);
  const [report, setReport] = useState(fallbackReport);
  const [selectedDate, setSelectedDate] = useState(() =>
    new Date().toISOString().slice(0, 10),
  );
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState(null);
  const streamRef = useRef(null);
  const [rawModalOpen, setRawModalOpen] = useState(false);
  const [rawContent, setRawContent] = useState("");
  const [rawLoading, setRawLoading] = useState(false);
  const [rawError, setRawError] = useState("");
  const [textModalOpen, setTextModalOpen] = useState(false);
  const [textContent, setTextContent] = useState("");
  const [textLoading, setTextLoading] = useState(false);
  const [textError, setTextError] = useState("");
  const [debugModalOpen, setDebugModalOpen] = useState(false);
  const [debugContent, setDebugContent] = useState("");
  const [debugLoading, setDebugLoading] = useState(false);
  const [debugError, setDebugError] = useState("");
  const [indexesExpanded, setIndexesExpanded] = useState(false);
  const [expandedReportKey, setExpandedReportKey] = useState(null);
  const [detailLoading, setDetailLoading] = useState({});
  const [detailError, setDetailError] = useState({});
  const showVolume = import.meta.env.VITE_SHOW_VOLUME !== "false";

  const headerIndexes =
    report.indexes && report.indexes.length
      ? report.indexes
      : [
          {
            name: "上证指数",
            close: report.index,
            change: report.change,
          },
        ];
  const collapsedCount = 3;
  const hasOverflowIndexes = headerIndexes.length > collapsedCount;
  const visibleIndexes =
    indexesExpanded || !hasOverflowIndexes
      ? headerIndexes
      : headerIndexes.slice(0, collapsedCount);
  const textLines = useMemo(
    () => (textContent ? textContent.split(/\r?\n/) : []),
    [textContent],
  );

  const gaugeOption = useMemo(
    () => ({
      backgroundColor: "transparent",
      series: [
        {
          type: "gauge",
          min: 0,
          max: 100,
          progress: { show: true, width: 12 },
          axisLine: {
            lineStyle: {
              width: 12,
              color: [
                [0.4, "#1E2C1F"],
                [0.7, "#3B3A1B"],
                [1, "#2B1917"],
              ],
            },
          },
          axisTick: { lineStyle: { color: "#5E6A7A" } },
          splitLine: { lineStyle: { color: "#5E6A7A" } },
          pointer: { itemStyle: { color: "#FFD60A" } },
          detail: {
            valueAnimation: true,
            formatter: "{value}°C",
            color: "#F9F6EE",
            fontSize: 28,
          },
          data: [{ value: report.winRate || 0 }],
        },
      ],
    }),
    [report.winRate],
  );

  const flowOption = useMemo(
    () => ({
      backgroundColor: "transparent",
      grid: { left: 10, right: 30, top: 10, bottom: 10 },
      xAxis: {
        type: "value",
        axisLabel: { show: false },
        splitLine: { show: false },
      },
      yAxis: {
        type: "category",
        data: ["主力资金", "散户资金"],
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { color: "#a1a1aa", fontSize: 12 },
      },
      series: [
        {
          type: "bar",
          data: [
            { value: report.mainFlow, itemStyle: { color: "#ef4444" } },
            { value: report.retailFlow, itemStyle: { color: "#22c55e" } },
          ],
          barWidth: 18,
          label: { show: false },
        },
      ],
    }),
    [report.mainFlow, report.retailFlow],
  );

  useEChart(gaugeRef, gaugeOption);
  useEChart(flowRef, flowOption);

  const loadReport = async (dateStr) => {
    setLoading(true);
    setMessage("正在加载...");
    try {
      const res = await fetch(toApiUrl(`/api/report?date=${dateStr}`));
      if (res.status === 404) {
        setMessage("当日无数据，请手动触发生成");
        return;
      }
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "加载失败");
      }
      const json = await res.json();
      setReport(json.data);
      setMessage("加载完成");
    } catch (err) {
      setMessage(err.message || "加载失败");
    } finally {
      setLoading(false);
    }
  };

  const loadRawReport = async (dateStr) => {
    setRawLoading(true);
    setRawError("");
    setRawContent("");
    try {
      const res = await fetch(toApiUrl(`/api/report/raw?date=${dateStr}`));
      if (res.status === 404) {
        setRawError("当日无数据，请先触发生成");
        setRawModalOpen(true);
        return;
      }
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "加载失败");
      }
      const text = await res.text();
      setRawContent(text);
      setRawModalOpen(true);
    } catch (err) {
      setRawError(err.message || "加载失败");
      setRawModalOpen(true);
    } finally {
      setRawLoading(false);
    }
  };

  const loadTextReport = async (dateStr) => {
    setTextLoading(true);
    setTextError("");
    setTextContent("");
    try {
      const res = await fetch(toApiUrl(`/api/report/text?date=${dateStr}`));
      if (res.status === 404) {
        setTextError("当日无报告原文，请先触发生成");
        setTextModalOpen(true);
        return;
      }
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "加载失败");
      }
      const text = await res.text();
      setTextContent(text);
      setTextModalOpen(true);
    } catch (err) {
      setTextError(err.message || "加载失败");
      setTextModalOpen(true);
    } finally {
      setTextLoading(false);
    }
  };

  const loadDebugLog = async (dateStr) => {
    setDebugLoading(true);
    setDebugError("");
    setDebugContent("");
    try {
      const res = await fetch(toApiUrl(`/api/report/debug?date=${dateStr}`));
      if (res.status === 404) {
        setDebugError("当日暂无调试日志");
        setDebugModalOpen(true);
        return;
      }
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "加载失败");
      }
      const text = await res.text();
      setDebugContent(text);
      setDebugModalOpen(true);
    } catch (err) {
      setDebugError(err.message || "加载失败");
      setDebugModalOpen(true);
    } finally {
      setDebugLoading(false);
    }
  };

  const triggerReport = async (dateStr) => {
    setLoading(true);
    setMessage("正在触发生成...");
    setProgress({ percent: 5, title: "开始生成", detail: "正在建立连接" });
    if (streamRef.current) {
      streamRef.current.close();
    }

    const streamUrl = toApiUrl(`/api/run/stream?date=${dateStr}`);
    const es = new EventSource(streamUrl);
    streamRef.current = es;

    es.addEventListener("progress", (evt) => {
      try {
        const data = JSON.parse(evt.data);
        setProgress(data);
      } catch {
        setProgress({ percent: 30, title: "分析中", detail: "收到进度更新" });
      }
    });

    es.addEventListener("done", (evt) => {
      try {
        const data = JSON.parse(evt.data);
        setReport(data.data);
        setMessage("生成并加载完成");
        setProgress({
          percent: 100,
          title: "完成",
          detail: "报告已生成并加载",
        });
      } catch {
        setMessage("生成完成但解析失败");
        setProgress({ percent: 100, title: "完成", detail: "报告已生成" });
      } finally {
        setLoading(false);
        es.close();
        streamRef.current = null;
        setTimeout(() => setProgress(null), 2400);
      }
    });

    es.addEventListener("failed", (evt) => {
      let detail = "触发失败";
      try {
        const data = JSON.parse(evt.data);
        detail = data.detail || detail;
      } catch {
        // ignore
      }
      setMessage(detail);
      setProgress({ percent: 100, title: "失败", detail });
      setLoading(false);
      es.close();
      streamRef.current = null;
      setTimeout(() => setProgress(null), 2400);
    });

    es.onerror = () => {
      if (!streamRef.current) return;
      const detail = "连接中断";
      setMessage(detail);
      setProgress({ percent: 100, title: "失败", detail });
      setLoading(false);
      es.close();
      streamRef.current = null;
      setTimeout(() => setProgress(null), 2400);
    };
  };

  const loadReportDetail = async (mode) => {
    if (!mode) return;
    if (report.reportDetails?.[mode]) return;
    setDetailLoading((prev) => ({ ...prev, [mode]: true }));
    setDetailError((prev) => ({ ...prev, [mode]: "" }));
    try {
      const res = await fetch(toApiUrl(`/api/report/detail?mode=${mode}`));
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "加载失败");
      }
      const json = await res.json();
      setReport((prev) => ({
        ...prev,
        reportDetails: { ...(prev.reportDetails || {}), [mode]: json.detail },
      }));
    } catch (err) {
      setDetailError((prev) => ({
        ...prev,
        [mode]: err.message || "加载失败",
      }));
    } finally {
      setDetailLoading((prev) => ({ ...prev, [mode]: false }));
    }
  };

  useEffect(() => {
    // 首次尝试读取当日数据，若不存在提示手动触发
    loadReport(selectedDate);
    return () => {
      if (streamRef.current) {
        streamRef.current.close();
      }
    };
  }, []);

  return (
    <div class="min-h-screen bg-[#09090b] text-zinc-100 selection:bg-red-500/30">
      <header class="sticky top-0 z-50 border-b border-zinc-800 bg-zinc-950/50 backdrop-blur-md">
        <div class="mx-auto flex h-16 max-w-[1600px] items-center justify-between px-6">
          <div class="flex items-center gap-4">
            <div class="flex items-center justify-center rounded bg-red-600 p-1.5">
              <svg
                class="h-5 w-5 text-white"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
                aria-hidden="true"
              >
                <path d="M3 3v18h18" />
                <path d="M7 14l3-3 4 4 6-8" />
              </svg>
            </div>
            <div>
              <h1 class="flex items-center gap-2 text-lg font-bold tracking-tight">
                A-Share 实时风险监测系统
                <span class="animate-pulse rounded border border-red-500/20 bg-red-500/10 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-widest text-red-500">
                  High Risk
                </span>
              </h1>
              <p class="flex items-center gap-1 text-[10px] font-mono text-zinc-500">
                {report.timestamp} (实时更新中)
              </p>
            </div>
          </div>
          <div class="flex items-center gap-6 font-mono text-sm">
            <div class="flex flex-row-reverse items-center gap-3">
              {hasOverflowIndexes && (
                <button
                  class="rounded border border-zinc-800 bg-zinc-900 px-2 py-1 text-[10px] text-zinc-300 hover:border-red-500"
                  onClick={() => setIndexesExpanded((prev) => !prev)}
                >
                  {indexesExpanded ? "折叠" : "展开"}
                </button>
              )}
              <div
                class={`text-right text-[11px] leading-tight ${indexesExpanded ? "flex max-h-14 max-w-[520px] flex-row-reverse flex-wrap items-center justify-end gap-x-4 gap-y-1 overflow-hidden" : "flex max-h-14 flex-row-reverse flex-wrap items-center justify-end gap-x-4 gap-y-1 sm:max-h-none sm:flex-nowrap sm:gap-x-6"}`}
              >
                {visibleIndexes.map((item) => (
                  <div
                    key={item.name}
                    class="flex items-center gap-2 whitespace-nowrap"
                  >
                    <span class="text-[10px] uppercase text-zinc-500">
                      {item.name}
                    </span>
                    <span
                      class={`font-bold ${toNumber(item.change) < 0 ? "text-green-500" : "text-red-500"}`}
                    >
                      {toNumber(item.close).toFixed(2)} (
                      {toNumber(item.change).toFixed(2)}%)
                    </span>
                  </div>
                ))}
              </div>
            </div>
            {showVolume && (
              <div class="flex flex-col items-end">
                <span class="text-[10px] uppercase text-zinc-500">
                  预估成交
                </span>
                <span class="font-bold text-zinc-200">
                  {report.volumeEstimate}T
                </span>
              </div>
            )}
          </div>
        </div>
      </header>

      <main class="mx-auto max-w-[1600px] space-y-6 p-6">
        <div class="animate-warning group relative overflow-hidden rounded-xl border-2 border-red-600/50 p-6">
          <div class="absolute right-0 top-0 p-4 opacity-10 transition-opacity group-hover:opacity-20">
            <svg
              class="h-28 w-28 text-red-500"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="1.5"
              stroke-linecap="round"
              stroke-linejoin="round"
              aria-hidden="true"
            >
              <path d="M12 9v4" />
              <path d="M12 17h.01" />
              <path d="M10.3 3.7l-8.2 14.2A2 2 0 0 0 3.8 20h16.4a2 2 0 0 0 1.7-2.9L13.7 3.7a2 2 0 0 0-3.4 0z" />
            </svg>
          </div>
          <div class="flex items-start gap-4">
            <div class="shrink-0 rounded-lg bg-red-600 p-3 text-white">
              <svg
                class="h-8 w-8"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
                aria-hidden="true"
              >
                <path d="M12 9v4" />
                <path d="M12 17h.01" />
                <path d="M10.3 3.7l-8.2 14.2A2 2 0 0 0 3.8 20h16.4a2 2 0 0 0 1.7-2.9L13.7 3.7a2 2 0 0 0-3.4 0z" />
              </svg>
            </div>
            <div class="flex-1">
              <h2 class="mb-2 text-2xl font-bold text-red-500">
                顶级预警：天量滞涨 / 趋势末期
              </h2>
              <p class="mb-4 max-w-4xl text-sm leading-relaxed text-zinc-300">
                当前市场处于上涨趋势末期的巨量换手阶段，主力资金离场意愿极其强烈。杠杆率已达
                <span class="font-bold text-red-500"> 2.53%</span>{" "}
                风险阈值，散户大量承接主力抛单，市场脆弱性剧增。
              </p>
              <div class="flex flex-wrap gap-4">
                <div class="flex items-center gap-2 rounded-md bg-red-600 px-4 py-2 text-sm font-bold text-white shadow-lg shadow-red-900/20">
                  核心指令：仓位立即降至 50% 以下
                </div>
                <div class="rounded-md border border-zinc-700 bg-zinc-800 px-4 py-2 text-sm font-semibold text-zinc-300">
                  关键防御：回避金融、游戏权重
                </div>
              </div>
            </div>
          </div>
        </div>

        {progress && (
          <div class="fixed bottom-6 right-6 z-50 w-72 rounded-lg border border-zinc-800 bg-zinc-950/90 p-4 shadow-xl backdrop-blur">
            <div class="mb-2 flex items-center justify-between text-xs text-zinc-400">
              <span>生成进度</span>
              <span class="mono">{progress.percent}%</span>
            </div>
            <div class="mb-3 h-2 w-full overflow-hidden rounded-full bg-zinc-800">
              <div
                class="h-full bg-red-500 transition-all duration-500"
                style={{ width: `${progress.percent}%` }}
              />
            </div>
            <div class="text-sm font-semibold text-zinc-100">
              {progress.title}
            </div>
            <div class="mt-1 text-xs text-zinc-400">{progress.detail}</div>
          </div>
        )}

        {rawModalOpen && (
          <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-6">
            <div class="max-h-[80vh] w-full max-w-3xl overflow-hidden rounded-xl border border-zinc-800 bg-zinc-950 shadow-2xl">
              <div class="flex items-center justify-between border-b border-zinc-800 px-4 py-3">
                <div class="text-sm font-semibold text-zinc-100">原始 JSON</div>
                <button
                  class="rounded border border-zinc-800 bg-zinc-900 px-3 py-1 text-xs text-zinc-200 hover:border-red-500"
                  onClick={() => setRawModalOpen(false)}
                >
                  关闭
                </button>
              </div>
              <div class="max-h-[70vh] overflow-auto p-4">
                {rawError && <div class="text-sm text-red-400">{rawError}</div>}
                {!rawError && (
                  <pre class="whitespace-pre-wrap text-xs leading-relaxed text-zinc-300">
                    {rawContent || "空内容"}
                  </pre>
                )}
              </div>
            </div>
          </div>
        )}

        {textModalOpen && (
          <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-6">
            <div class="max-h-[85vh] w-full max-w-5xl overflow-hidden rounded-xl border border-zinc-800 bg-zinc-950 shadow-2xl">
              <div class="flex items-center justify-between border-b border-zinc-800 px-5 py-3">
                <div>
                  <div class="text-sm font-semibold text-zinc-100">
                    报告原文
                  </div>
                  <div class="text-[11px] text-zinc-500">
                    {selectedDate} 最新生成版本
                  </div>
                </div>
                <button
                  class="rounded border border-zinc-800 bg-zinc-900 px-3 py-1 text-xs text-zinc-200 hover:border-red-500"
                  onClick={() => setTextModalOpen(false)}
                >
                  关闭
                </button>
              </div>
              <div class="max-h-[75vh] overflow-auto px-5 py-4">
                {textError && (
                  <div class="text-sm text-red-400">{textError}</div>
                )}
                {!textError && (
                  <div class="rounded-xl border border-zinc-800 bg-zinc-950/60 p-4">
                    {!textContent && (
                      <div class="text-sm text-zinc-400">空内容</div>
                    )}
                    {textContent && (
                      <div class="space-y-1 font-mono text-xs leading-relaxed text-zinc-200">
                        {textLines.map((line, idx) => (
                          <div
                            key={`${idx}-${line}`}
                            class="grid grid-cols-[2.5rem_1fr] gap-3"
                          >
                            <span class="text-[10px] text-zinc-500">
                              {String(idx + 1).padStart(3, " ")}
                            </span>
                            <span
                              class={`whitespace-pre-wrap ${
                                line.startsWith("=")
                                  ? "font-semibold text-red-400"
                                  : "text-zinc-200"
                              }`}
                            >
                              {line || " "}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {debugModalOpen && (
          <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-6">
            <div class="max-h-[80vh] w-full max-w-3xl overflow-hidden rounded-xl border border-zinc-800 bg-zinc-950 shadow-2xl">
              <div class="flex items-center justify-between border-b border-zinc-800 px-4 py-3">
                <div class="text-sm font-semibold text-zinc-100">调试日志</div>
                <button
                  class="rounded border border-zinc-800 bg-zinc-900 px-3 py-1 text-xs text-zinc-200 hover:border-red-500"
                  onClick={() => setDebugModalOpen(false)}
                >
                  关闭
                </button>
              </div>
              <div class="max-h-[70vh] overflow-auto p-4">
                {debugError && (
                  <div class="text-sm text-red-400">{debugError}</div>
                )}
                {!debugError && (
                  <pre class="whitespace-pre-wrap text-xs leading-relaxed text-zinc-300">
                    {debugContent || "空内容"}
                  </pre>
                )}
              </div>
            </div>
          </div>
        )}

        <div class="grid grid-cols-1 gap-6 lg:grid-cols-12">
          <div class="lg:col-span-12 flex flex-wrap items-center gap-3">
            <input
              type="date"
              class="rounded border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-red-500"
              value={selectedDate}
              onInput={(e) => setSelectedDate(e.target.value)}
            />
            <button
              class="rounded border border-zinc-800 bg-zinc-900 px-4 py-2 text-sm font-semibold text-zinc-200 hover:border-red-500 disabled:cursor-not-allowed disabled:opacity-50"
              disabled={loading}
              onClick={() => loadReport(selectedDate)}
            >
              读取所选日期
            </button>
            <button
              class="rounded border border-zinc-800 bg-zinc-900 px-4 py-2 text-sm font-semibold text-zinc-200 hover:border-red-500 disabled:cursor-not-allowed disabled:opacity-50"
              disabled={rawLoading}
              onClick={() => loadRawReport(selectedDate)}
            >
              {rawLoading ? "读取中..." : "查看原始 JSON"}
            </button>
            <button
              class="rounded border border-zinc-800 bg-zinc-900 px-4 py-2 text-sm font-semibold text-zinc-200 hover:border-red-500 disabled:cursor-not-allowed disabled:opacity-50"
              disabled={textLoading}
              onClick={() => loadTextReport(selectedDate)}
            >
              {textLoading ? "读取中..." : "查看报告原文"}
            </button>
            <button
              class="rounded border border-zinc-800 bg-zinc-900 px-4 py-2 text-sm font-semibold text-zinc-200 hover:border-red-500 disabled:cursor-not-allowed disabled:opacity-50"
              disabled={debugLoading}
              onClick={() => loadDebugLog(selectedDate)}
            >
              {debugLoading ? "读取中..." : "查看调试日志"}
            </button>
            <button
              class="rounded bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-50"
              disabled={loading}
              onClick={() => triggerReport(selectedDate)}
            >
              {loading ? "执行中..." : "手动触发生成"}
            </button>
            {message && <span class="text-sm text-zinc-400">{message}</span>}
          </div>

          <div class="space-y-6 lg:col-span-4">
            <div class="grid grid-cols-2 gap-4">
              <MetricCard
                label="市场杠杆率"
                value={report.leverageRate}
                unit="%"
                status="danger"
                subValue="融资买入惯性冲高"
              />
              <MetricCard
                label="全天预估成交"
                value={report.volumeEstimate}
                unit="万亿"
                status="danger"
                subValue="较5日均量放量17%"
              />
              <MetricCard
                label="赚钱效应"
                value={report.winRate}
                unit="%"
                status="warning"
                subValue="结构性分化严重"
              />
              <MetricCard
                label="拥挤度"
                value="44.16"
                unit="%"
                status="neutral"
                subValue="大盘情绪中性偏冷"
              />
            </div>

            <div class="rounded-xl border border-zinc-800 bg-zinc-900/50 p-5">
              <div class="mb-6 flex items-center justify-between">
                <h3 class="flex items-center gap-2 text-sm font-bold uppercase tracking-wider">
                  资金背离区 (亿元)
                </h3>
                <span class="text-[10px] text-zinc-500">主力出 / 散户进</span>
              </div>
              <div class="h-[200px] w-full" ref={flowRef}></div>
              <p class="mt-4 rounded bg-zinc-950 p-3 text-[11px] italic leading-relaxed text-zinc-500">
                主力流出 {formatFlow(report.mainFlow)} 亿，散户逆势买入{" "}
                {formatFlow(report.retailFlow)}{" "}
                亿。典型的牛末换手特征，主导力量正在从专业机构向非理性散户转换。
              </p>
            </div>
          </div>

          <div class="space-y-6 lg:col-span-5">
            <div class="rounded-xl border border-zinc-800 bg-zinc-900/50 p-5">
              <div class="mb-6 flex items-center justify-between">
                <h3 class="flex items-center gap-2 text-sm font-bold uppercase tracking-wider">
                  板块热力分布 (人气追踪)
                </h3>
              </div>

              <div class="space-y-4">
                <div>
                  <div class="mb-2 flex items-center justify-between">
                    <span class="text-[10px] font-bold uppercase tracking-widest text-zinc-500">
                      强势防御区 (煤炭/制药)
                    </span>
                    <span class="text-[10px] text-green-500">HOT &gt; 80</span>
                  </div>
                  <div class="grid grid-cols-2 gap-2 sm:grid-cols-3">
                    {report.sectors.strong.map((s) => (
                      <div
                        key={s.name}
                        class="group cursor-default rounded border border-red-800/40 bg-red-900/20 p-3 transition-colors hover:bg-red-900/40"
                      >
                        <div class="mb-1 text-[11px] font-bold text-red-400">
                          {s.name}
                        </div>
                        <div class="flex items-baseline justify-between">
                          <span class="mono text-lg font-bold">{s.value}</span>
                          <span class="text-[10px] opacity-60">🔥</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div class="pt-2">
                  <div class="mb-2 flex items-center justify-between">
                    <span class="text-[10px] font-bold uppercase tracking-widest text-zinc-500">
                      极度虚弱区 (金融/游戏)
                    </span>
                    <span class="text-[10px] text-red-500">COLD &lt; 20</span>
                  </div>
                  <div class="grid grid-cols-2 gap-2 sm:grid-cols-3">
                    {report.sectors.weak.map((s) => (
                      <div
                        key={s.name}
                        class="group cursor-default rounded border border-green-900/20 bg-green-900/10 p-3 transition-colors hover:bg-green-950/30"
                      >
                        <div class="mb-1 text-[11px] font-bold text-green-700">
                          {s.name}
                        </div>
                        <div class="flex items-baseline justify-between">
                          <span class="mono text-lg font-bold">{s.value}</span>
                          <span class="text-[10px] text-green-900 opacity-60">
                            ❄️
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            <div class="rounded-xl border border-zinc-800 bg-zinc-900/50 p-5">
              <h3 class="mb-4 flex items-center gap-2 text-sm font-bold uppercase tracking-wider">
                AI 核心避险策略
              </h3>
              <ul class="space-y-3">
                {report.aiAdvice.map((advice) => (
                  <li key={advice} class="flex gap-3 text-sm text-zinc-300">
                    <span class="mt-1 text-purple-500">›</span>
                    {advice}
                  </li>
                ))}
              </ul>
            </div>
          </div>

          <div class="space-y-4 lg:col-span-3">
            <div class="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4">
              <div class="mb-3 text-[11px] font-bold uppercase tracking-wider text-zinc-400">
                报告类型
              </div>
              <div class="space-y-2 text-xs text-zinc-300">
                {reportTitles.map((item) => {
                  const isExpanded = expandedReportKey === item.key;
                  const isCurrent = report.runMode === item.key;
                  const detail =
                    report.reportDetails?.[item.key] ||
                    (isCurrent ? report.conclusionRaw : "");
                  const isLoading = detailLoading[item.key];
                  const errorMsg = detailError[item.key];
                  return (
                    <div
                      key={item.key}
                      class="rounded border border-zinc-800/80"
                    >
                      <button
                        class="flex w-full items-center justify-between gap-2 px-3 py-2 text-left hover:bg-zinc-950/40"
                        onClick={() => {
                          const next = isExpanded ? null : item.key;
                          setExpandedReportKey(next);
                          if (!isExpanded) {
                            loadReportDetail(item.key);
                          }
                        }}
                      >
                        <span class="flex items-center gap-2">
                          <span
                            class={`h-1.5 w-1.5 rounded-full ${
                              isCurrent ? "bg-red-500" : "bg-zinc-600"
                            }`}
                          ></span>
                          <span class="leading-snug">{item.title}</span>
                        </span>
                        <span class="text-[10px] text-zinc-500">
                          {isExpanded ? "收起" : "展开"}
                        </span>
                      </button>
                      {isExpanded && (
                        <div class="border-t border-zinc-800/80 px-3 py-2 text-[11px] leading-relaxed text-zinc-400">
                          {isLoading ? (
                            "加载中..."
                          ) : errorMsg ? (
                            <span class="text-red-400">{errorMsg}</span>
                          ) : detail ? (
                            <pre class="whitespace-pre-wrap font-sans">
                              {detail}
                            </pre>
                          ) : (
                            "暂无详情"
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
            <h3 class="mb-2 px-1 text-sm font-bold uppercase tracking-wider text-zinc-300">
              {report.forecastTitle || "明日走势推演"}
            </h3>

            {report.scenarios.map((scen) => (
              <div
                key={scen.title}
                class={`rounded-xl border p-4 transition-all duration-300 ${
                  scen.type === "base"
                    ? "border-zinc-700 bg-zinc-800/80 ring-2 ring-zinc-700/50"
                    : scen.type === "optimistic"
                      ? "border-zinc-800 bg-zinc-900/30 opacity-70 grayscale hover:opacity-100 hover:grayscale-0"
                      : "border-red-900/30 bg-red-950/20 opacity-70 grayscale hover:opacity-100 hover:grayscale-0"
                }`}
              >
                <div class="mb-2 flex items-center justify-between">
                  <span
                    class={`rounded px-2 py-0.5 text-[10px] font-bold uppercase tracking-tighter ${
                      scen.type === "base"
                        ? "bg-blue-500 text-white"
                        : scen.type === "optimistic"
                          ? "bg-green-600 text-white"
                          : "bg-red-600 text-white"
                    }`}
                  >
                    {scen.title}
                  </span>
                  <span class="mono text-xl font-black italic opacity-80">
                    {scen.probability}%
                  </span>
                </div>
                <p class="text-xs font-medium leading-relaxed text-zinc-400">
                  {scen.description}
                </p>
              </div>
            ))}

            <div class="mt-8 rounded border border-zinc-800 bg-zinc-950 p-4">
              <p class="text-[10px] leading-tight text-zinc-600">
                免责声明:
                本报告基于公开数据和量化模型生成，所有结论仅供参考，不构成任何投资建议。杠杆交易风险巨大，请理性操作。
              </p>
            </div>
          </div>
        </div>
      </main>

      <div class="fixed bottom-6 right-6 z-[60]">
        <div class="flex cursor-pointer items-center gap-3 rounded-full bg-red-600 px-6 py-3 text-white shadow-2xl shadow-red-500/30 transition-transform hover:scale-105 hover:bg-red-700">
          <span class="text-sm font-bold">高危警示：4077点 承压严重</span>
        </div>
      </div>
    </div>
  );
}
