<template>
  <div class="page">
    <!-- 3 张统计卡片 -->
    <a-row :gutter="16">
      <a-col :span="8">
        <a-card :bordered="true">
          <a-statistic title="资料总数" :value="stats.notesTotal || 0" />
        </a-card>
      </a-col>
      <a-col :span="8">
        <a-card :bordered="true">
          <a-statistic title="采集源" :value="stats.collectSources || 0" />
        </a-card>
      </a-col>
      <a-col :span="8">
        <a-card :bordered="true">
          <a-statistic title="推送频道" :value="stats.channelsActive || 0" />
        </a-card>
      </a-col>
    </a-row>

    <!-- 系统健康 -->
    <a-card :bordered="true" title="系统健康" style="margin-top: 16px">
      <a-row :gutter="16">
        <a-col :span="6">
          <a-statistic title="在线协议号" :value="stats.tgOnline || 0" />
        </a-col>
        <a-col :span="6">
          <a-statistic title="今日推送" :value="stats.todayPublishes || 0" />
        </a-col>
        <a-col :span="6">
          <a-statistic title="今日成功率" :value="successRate" />
        </a-col>
        <a-col :span="6">
          <a-statistic title="24h 失败" :value="stats.publishFailed24h || 0" value-style="color: #0ca678" />
        </a-col>
      </a-row>
      <a-divider orientation="left" style="margin: 12px 0">近 7 天推送趋势</a-divider>
      <div class="trend-bars">
        <div v-for="(d, i) in trend7" :key="i" class="trend-bar-item">
          <div class="trend-bar-value">{{ d.value }}</div>
          <div class="trend-bar" :style="{ height: barHeight(d.value) + 'px' }"></div>
          <div class="trend-bar-date">{{ d.date }}</div>
        </div>
      </div>
    </a-card>

    <!-- 客服卡片 -->
    <a-card :bordered="true" style="margin-top: 16px">
      <div class="service-row">
        <span class="service-icon">!</span>
        <span class="service-text">遇到问题？联系客服获取帮助</span>
        <a-button type="primary" @click="contactService">联系客服</a-button>
      </div>
    </a-card>

    <!-- 按省市分布 -->
    <a-collapse style="margin-top: 16px">
      <a-collapse-panel key="1" header="按省市分布">
        <div class="tag-group">
          <a-tag v-for="(v, k) in stats.notesByCity" :key="k" color="blue">{{ k }}: {{ v }}</a-tag>
          <span v-if="!stats.notesByCity || Object.keys(stats.notesByCity).length === 0" class="empty-text">暂无数据</span>
        </div>
      </a-collapse-panel>
    </a-collapse>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import request from '@/utils/request';

const stats = ref<any>({ notesByCity: {} });
const trend7 = ref<{ date: string; value: number }[]>([]);

const successRate = computed(() => {
  const total = stats.value.todayPublishes || 0;
  const failed = stats.value.publishFailed24h || 0;
  if (total <= 0) return '0%';
  return Math.round(((total - failed) / total) * 100) + '%';
});

const maxTrend = computed(() => {
  let m = 0;
  for (const d of trend7.value) m = Math.max(m, d.value);
  return m || 1;
});
function barHeight(v: number) {
  return Math.max(4, Math.round((v / maxTrend.value) * 90));
}

function contactService() {
  window.open('https://t.me/lingjuli', '_blank');
}

onMounted(async () => {
  try {
    const r: any = await request.get('/api/dashboard/stats');
    stats.value = r.data || r;
  } catch { /* ignore */ }
  try {
    const r: any = await request.get('/api/dashboard/trend', {
      params: { days: 7 },
    });
    const data = r.data || r;
    // 兼容：取发布成功系列或第一条系列
    const dates: string[] = data.dates || [];
    let series: number[] = [];
    const ss: any[] = data.series || [];
    const ok = ss.find((s: any) => s.name === '发布成功') || ss[0];
    if (ok) series = ok.data || [];
    trend7.value = dates.slice(-7).map((d: string, i: number) => ({
      date: (d || '').slice(5),
      value: series[series.length - 7 + i] || 0,
    }));
  } catch { /* ignore */ }
});
</script>

<style scoped>
.trend-bars {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  height: 90px;
}
.trend-bar-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-end;
  height: 100%;
}
.trend-bar-value {
  font-size: 11px;
  color: #5a6276;
}
.trend-bar {
  width: 22px;
  background: #2f55e0;
  border-radius: 4px 4px 0 0;
  margin-top: 2px;
}
.trend-bar-date {
  font-size: 10px;
  color: #9aa1ad;
  margin-top: 4px;
}
.service-row {
  display: flex;
  align-items: center;
  gap: 12px;
}
.service-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: #1677ff;
  color: #fff;
  font-weight: 700;
  font-size: 16px;
}
.service-text { flex: 1; font-size: 14px; }
.tag-group { display: flex; flex-wrap: wrap; gap: 8px; }
.empty-text { color: #8a91a5; font-size: 14px; }
</style>
