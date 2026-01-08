import { useEffect, useMemo, useRef } from "preact/hooks";
import * as echarts from "echarts";

const report = {
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
      { name: "煤炭行业", value: 90.3, count: 30 },
      { name: "化学制药", value: 89.9, count: 46 },
      { name: "汽车零部件", value: 86.9, count: 36 },
      { name: "塑料制品", value: 85.1, count: 28 },
      { name: "小金属", value: 83.4, count: 26 },
    ],
    weak: [
      { name: "证券", value: 9.8, count: 2 },
      { name: "船舶制造", value: 16.2, count: 0 },
      { name: "保险", value: 17.3, count: 0 },
      { name: "银行", value: 18.5, count: 2 },
      { name: "游戏", value: 21.6, count: 3 },
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

export default function App() {
  const flowRef = useRef(null);

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
    [],
  );

  useEChart(flowRef, flowOption);

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
          <div class="flex items-center gap-8 font-mono text-sm">
            <div class="flex flex-col items-end">
              <span class="text-[10px] uppercase text-zinc-500">上证指数</span>
              <span
                class={`font-bold ${report.change < 0 ? "text-green-500" : "text-red-500"}`}
              >
                {report.index.toFixed(2)} ({report.change.toFixed(2)}%)
              </span>
            </div>
            <div class="flex flex-col items-end">
              <span class="text-[10px] uppercase text-zinc-500">预估成交</span>
              <span class="font-bold text-zinc-200">
                {report.volumeEstimate}T
              </span>
            </div>
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

        <div class="grid grid-cols-1 gap-6 lg:grid-cols-12">
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
                subValue="40.9% 结构性分化严重"
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
                主力流出 633 亿，散户逆势买入 576
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
                {report.aiAdvice.map((advice, i) => (
                  <li key={advice} class="flex gap-3 text-sm text-zinc-300">
                    <span class="mt-1 text-purple-500">›</span>
                    {advice}
                  </li>
                ))}
              </ul>
            </div>
          </div>

          <div class="space-y-4 lg:col-span-3">
            <h3 class="mb-2 px-1 text-sm font-bold uppercase tracking-wider text-zinc-300">
              上午收盘推演
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
