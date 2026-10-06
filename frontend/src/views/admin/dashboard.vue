<template>
  <div class="page">
    <a-row :gutter="16">
      <a-col :span="6" v-for="s in statCards" :key="s.label">
        <a-card class="stat-card"><a-statistic :title="s.label" :value="s.value" /></a-card>
      </a-col>
    </a-row>
    <a-card title="资料状态分布" class="mt-16">
      <div class="tag-group">
        <a-tag v-for="(v, k) in stats.notesByStatus" :key="k" color="blue">{{ k }}: {{ v }}</a-tag>
      </div>
    </a-card>
    <a-card title="数据趋势" class="mt-16">
      <template #extra>
        <a-range-picker v-model:value="dateRange" @change="loadTrend" size="small" />
      </template>
      <a-spin :spinning="trendLoading">
        <div class="legend">
          <span v-for="s in trend.series" :key="s.name" class="legend-item">
            <i :style="{ background: seriesColor(s.name) }"></i>{{ s.name }}
          </span>
        </div>
        <svg :viewBox="`0 0 ${W} ${H}`" class="trend-svg">
          <!-- 网格线 -->
          <g v-for="i in 4" :key="i">
            <line :x1="padL" :x2="W - padR" :y1="yFor(i / 4)" :y2="yFor(i / 4)" stroke="#f0f0f0" />
            <text :x="padL - 8" :y="yFor(i / 4) + 4" text-anchor="end" font-size="10" fill="#999">{{ Math.round(maxV * i / 4) }}</text>
          </g>
          <!-- 折线 -->
          <polyline v-for="s in trend.series" :key="s.name"
            :points="pointsFor(s.data)" fill="none"
            :stroke="seriesColor(s.name)" stroke-width="2" />
          <circle v-for="(p, i) in dotPoints" :key="i" :cx="p.x" :cy="p.y" r="3" :fill="p.color">
            <title>{{ p.label }}</title>
          </circle>
          <!-- X 轴日期 -->
          <text v-for="(d, i) in xLabels" :key="i" :x="d.x" :y="H - 6" text-anchor="middle" font-size="10" fill="#999">{{ d.label }}</text>
        </svg>
      </a-spin>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import dayjs, { Dayjs } from 'dayjs';
import request from '@/utils/request';

const stats = ref<any>({ notesByStatus: {} });
const statCards = computed(() => {
  const byStatus = stats.value.notesByStatus || {};
  const total = stats.value.notesTotal || 0;
  const published = byStatus.published || byStatus['已上架'] || 0;
  const failed = stats.value.todayPublishes !== undefined ? (stats.value.publishFailed || 0) : 0;
  const successRate = total > 0 ? Math.round((published / total) * 100) + '%' : '0%';
  return [
    { label: '资料总数', value: total },
    { label: '已上架', value: published },
    { label: '待上架', value: (byStatus.draft || byStatus['待上架'] || 0) },
    { label: '发布失败', value: failed },
    { label: '上架账号', value: stats.value.tgAccounts || 0 },
    { label: '在线协议号', value: stats.value.tgAccounts || 0 },
    { label: '可用频道', value: stats.value.channelsActive || 0 },
    { label: '发布成功率', value: successRate },
  ];
});

// 趋势图
const W = 800, H = 260, padL = 44, padR = 16, padT = 12, padB = 28;
const trend = ref<{ dates: string[]; series: { name: string; data: number[] }[] }>({ dates: [], series: [] });
const trendLoading = ref(false);
const dateRange = ref<[Dayjs, Dayjs]>([dayjs().subtract(13, 'day'), dayjs()]);

const maxV = computed(() => {
  let m = 0;
  for (const s of trend.value.series) for (const v of s.data) m = Math.max(m, v);
  return m || 1;
});
function yFor(ratio: number) { return padT + (H - padT - padB) * (1 - ratio); }
function xFor(i: number, n: number) { return n <= 1 ? padL : padL + (W - padL - padR) * (i / (n - 1)); }
function pointsFor(data: number[]) {
  const n = data.length;
  return data.map((v, i) => `${xFor(i, n)},${yFor(v / maxV.value)}`).join(' ');
}
const COLORS: Record<string, string> = { '新增资料': '#1890ff', '发布成功': '#52c41a', '下架资料': '#faad14', '发布失败': '#f5222d' };
function seriesColor(name: string) { return COLORS[name] || '#888'; }
const dotPoints = computed(() => {
  const pts: any[] = [];
  const n = trend.value.dates.length;
  trend.value.series.forEach(s => {
    s.data.forEach((v, i) => {
      pts.push({ x: xFor(i, n), y: yFor(v / maxV.value), color: seriesColor(s.name), label: `${trend.value.dates[i]} ${s.name}: ${v}` });
    });
  });
  return pts;
});
const xLabels = computed(() => {
  const n = trend.value.dates.length;
  const step = Math.max(1, Math.floor(n / 8));
  return trend.value.dates.map((d, i) => ({ x: xFor(i, n), label: i % step === 0 ? d.slice(5) : '' })).filter(d => d.label);
});

async function loadTrend() {
  trendLoading.value = true;
  try {
    const [s, e] = dateRange.value;
    const data: any = await request.get('/api/dashboard/trend', {
      params: { startDate: s.format('YYYY-MM-DD'), endDate: e.format('YYYY-MM-DD') },
    });
    trend.value = data.data || data;
  } finally { trendLoading.value = false; }
}

onMounted(async () => {
  stats.value = await request.get('/api/dashboard/stats');
  loadTrend();
});
</script>

<style scoped>
.mt-16 { margin-top: 16px; }
.tag-group { display: flex; flex-wrap: wrap; gap: 8px; }
.legend { display: flex; gap: 16px; margin-bottom: 8px; }
.legend-item { font-size: 12px; color: #666; }
.legend-item i { display: inline-block; width: 12px; height: 3px; margin-right: 4px; vertical-align: middle; }
.trend-svg { width: 100%; height: auto; }
</style>
