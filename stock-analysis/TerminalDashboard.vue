<template>
  <div class="min-h-screen bg-[#0B111A] text-slate-100">
    <div class="mx-auto max-w-6xl px-4 py-6">
      <header class="rounded-xl border border-slate-800 bg-[#0F1521] p-4 shadow-inner">
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 class="text-2xl font-semibold tracking-wide">A股风险监控台</h1>
            <div class="text-xs text-slate-400">{{ report.as_of }}</div>
          </div>
          <div class="text-sm text-amber-300">市场定性：{{ report.market_qualitative }}</div>
        </div>
      </header>

      <section class="mt-5 rounded-2xl border border-red-500 bg-gradient-to-r from-[#3A0D0D] to-[#140707] p-4 blink">
        <div class="text-sm uppercase tracking-[0.2em] text-red-300">预警区</div>
        <div class="mt-1 text-lg font-semibold text-red-400">
          {{ report.warning }}
        </div>
      </section>

      <section class="mt-5 grid gap-4 lg:grid-cols-[1.2fr_1fr_1fr]">
        <div class="rounded-xl border border-slate-800 bg-[#0F1521] p-4">
          <div class="text-sm text-slate-400">情绪温度</div>
          <div ref="gaugeRef" class="h-56 w-full"></div>
          <div class="mt-3 grid grid-cols-2 gap-3">
            <div class="rounded-lg border border-slate-800 bg-[#0B111A] p-3">
              <div class="text-xs text-slate-500">天量滞涨成交额</div>
              <div class="text-xl font-semibold text-amber-100">
                {{ report.risk.volume_trillion }}万亿
              </div>
            </div>
            <div class="rounded-lg border border-slate-800 bg-[#0B111A] p-3">
              <div class="text-xs text-slate-500">杠杆率</div>
              <div class="text-xl font-semibold text-amber-100">
                {{ report.risk.leverage_pct }}%
              </div>
            </div>
          </div>
        </div>

        <div class="rounded-xl border border-slate-800 bg-[#0F1521] p-4">
          <div class="text-sm text-slate-400">背离区</div>
          <div ref="flowRef" class="mt-2 h-64 w-full"></div>
        </div>

        <div class="rounded-xl border border-slate-800 bg-[#0F1521] p-4">
          <div class="text-sm text-slate-400">板块热力</div>
          <div ref="treeRef" class="mt-2 h-64 w-full"></div>
        </div>
      </section>

      <section class="mt-5 grid gap-4 lg:grid-cols-[1.5fr_1fr]">
        <div class="rounded-xl border border-slate-800 bg-[#0F1521] p-4">
          <div class="text-sm text-slate-400">推演区</div>
          <div class="mt-3 grid gap-3 md:grid-cols-3">
            <div
              v-for="item in report.scenarios"
              :key="item.name"
              class="rounded-lg border border-slate-800 bg-[#0B111A] p-3"
            >
              <div class="text-sm font-semibold text-amber-300">{{ item.name }}</div>
              <div class="text-xs text-slate-500">概率 {{ Math.round(item.prob * 100) }}%</div>
              <div class="mt-2 text-sm text-slate-200">{{ item.desc }}</div>
            </div>
          </div>
        </div>
        <div class="rounded-xl border border-slate-800 bg-[#0F1521] p-4">
          <div class="text-sm text-slate-400">JSON 入参示例</div>
          <pre class="mt-3 max-h-64 overflow-auto rounded-lg border border-slate-800 bg-[#0B111A] p-3 text-xs text-slate-300">{{ jsonPreview }}</pre>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onBeforeUnmount, ref } from "vue";
import * as echarts from "echarts";

const report = ref({
  as_of: "2026-01-08 09:32",
  market_qualitative: "上涨趋势末期",
  warning: "仓位立即降至50%以下",
  risk: { volume_trillion: 3.45, leverage_pct: 2.53 },
  flows: { main_billion: -633, retail_billion: 576 },
  sentiment_temp: 86,
  sectors: [
    { name: "煤炭", heat: 92 },
    { name: "制药", heat: 88 },
    { name: "有色", heat: 64 },
    { name: "电力设备", heat: 52 },
    { name: "金融", heat: 18 },
    { name: "游戏", heat: 12 },
    { name: "消费", heat: 41 },
  ],
  scenarios: [
    { name: "基准", prob: 0.45, desc: "高位震荡，风险边际收缩" },
    { name: "乐观", prob: 0.2, desc: "情绪续热，但量能透支" },
    { name: "悲观", prob: 0.35, desc: "量价背离扩大，回撤加速" },
  ],
});

const gaugeRef = ref(null);
const flowRef = ref(null);
const treeRef = ref(null);
let gaugeChart;
let flowChart;
let treeChart;

const jsonPreview = computed(() => JSON.stringify(report.value, null, 2));

const initGauge = () => {
  if (!gaugeRef.value) return;
  gaugeChart = echarts.init(gaugeRef.value);
  gaugeChart.setOption({
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
        data: [{ value: report.value.sentiment_temp }],
      },
    ],
  });
};

const initFlows = () => {
  if (!flowRef.value) return;
  flowChart = echarts.init(flowRef.value);
  flowChart.setOption({
    backgroundColor: "transparent",
    grid: { left: 30, right: 20, top: 20, bottom: 20 },
    xAxis: {
      type: "category",
      data: ["主力", "散户"],
      axisLine: { lineStyle: { color: "#394455" } },
      axisTick: { show: false },
      axisLabel: { color: "#C7D0D9" },
    },
    yAxis: {
      type: "value",
      splitLine: { lineStyle: { color: "#1B2430" } },
      axisLine: { show: false },
      axisLabel: { color: "#6B7789" },
    },
    series: [
      {
        type: "bar",
        data: [report.value.flows.main_billion, report.value.flows.retail_billion],
        barWidth: 36,
        label: { show: true, position: "top", color: "#E6EDF3" },
        itemStyle: {
          color: (params) => (params.dataIndex === 0 ? "#FF3B30" : "#34C759"),
        },
      },
    ],
  });
};

const initTreemap = () => {
  if (!treeRef.value) return;
  treeChart = echarts.init(treeRef.value);
  treeChart.setOption({
    backgroundColor: "transparent",
    series: [
      {
        type: "treemap",
        data: report.value.sectors.map((s) => ({ name: s.name, value: s.heat })),
        label: { color: "#E6EDF3" },
        upperLabel: { show: false },
        itemStyle: { borderColor: "#0B111A" },
        color: ["#1E2C1F", "#FFD60A", "#FF3B30"],
      },
    ],
  });
};

const resizeAll = () => {
  gaugeChart?.resize();
  flowChart?.resize();
  treeChart?.resize();
};

onMounted(async () => {
  await nextTick();
  initGauge();
  initFlows();
  initTreemap();
  window.addEventListener("resize", resizeAll);
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", resizeAll);
  gaugeChart?.dispose();
  flowChart?.dispose();
  treeChart?.dispose();
});
</script>

<style scoped>
.blink {
  animation: blink 1.2s infinite;
}

@keyframes blink {
  0%,
  100% {
    box-shadow: 0 0 0 0 rgba(255, 59, 48, 0.8);
  }
  50% {
    box-shadow: 0 0 18px 2px rgba(255, 59, 48, 0.65);
  }
}
</style>
