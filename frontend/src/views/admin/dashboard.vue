<template>
  <div>
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
          <a-statistic title="今日推送" :value="todayPushText" />
        </a-col>
        <a-col :span="6">
          <a-statistic title="今日成功率" :value="successRate" />
        </a-col>
        <a-col :span="6">
          <a-statistic title="24h 失败" :value="stats.publishFailed24h || 0" value-style="color: #0ca678" />
        </a-col>
      </a-row>
      <a-divider style="margin: 12px 0">近 7 天推送趋势</a-divider>
      <div style="display: flex; align-items: flex-end; gap: 8px; height: 90px">
        <div
          v-for="(d, i) in trend7"
          :key="i"
          style="display: flex; flex-direction: column; align-items: center; flex: 1"
        >
          <div style="font-size: 11px; color: #5a6276">{{ d.value }}</div>
          <div
            :style="{
              width: '22px',
              background: '#2f55e0',
              borderRadius: '4px 4px 0 0',
              height: barHeight(d.value) + 'px',
            }"
          ></div>
          <div style="font-size: 10px; color: #9aa1ad; margin-top: 4px">{{ d.date }}</div>
        </div>
      </div>
    </a-card>

    <!-- 客服卡片（无边框） -->
    <a-card :bordered="false" style="margin-top: 16px">
      <a-result
        status="info"
        title="有任何问题或需要开通 VIP，请联系客服 TG：@lingjuli"
        sub-title="客服工作时间 9:00-23:00（北京时间）"
      >
        <template #extra>
          <a-button type="primary" href="https://t.me/lingjuli" target="_blank">
            联系客服 @lingjuli
          </a-button>
        </template>
      </a-result>
    </a-card>

    <!-- 按省市分布 -->
    <a-card :bordered="true" style="margin-top: 16px">
      <a-collapse ghost>
        <a-collapse-panel key="1" :header="`📊 按省市分布（${cityTotal} 条资料，点击展开）`">
          <div class="tag-group">
            <a-tag v-for="(v, k) in stats.notesByCity" :key="k" color="blue">{{ k }}：{{ v }}</a-tag>
            <span v-if="!cityTotal" class="empty-text">暂无数据</span>
          </div>
        </a-collapse-panel>
      </a-collapse>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import request from '@/utils/request';

const stats = ref<any>({ notesByCity: {} });
const trend7 = ref<{ date: string; value: number }[]>([]);

const todayPushText = computed(() => {
  const total = stats.value.todayPublishes || 0;
  const failed = stats.value.publishFailed24h || 0;
  const okCount = Math.max(0, total - failed);
  return `${okCount}/${total}`;
});

const successRate = computed(() => {
  const total = stats.value.todayPublishes || 0;
  const failed = stats.value.publishFailed24h || 0;
  if (total <= 0) return '0%';
  return Math.round(((total - failed) / total) * 100) + '%';
});

const cityTotal = computed(() => {
  const m = stats.value.notesByCity || {};
  return Object.values(m).reduce((a: number, b: any) => a + (b || 0), 0);
});

const maxTrend = computed(() => {
  let m = 0;
  for (const d of trend7.value) m = Math.max(m, d.value);
  return m || 1;
});
function barHeight(v: number) {
  return Math.max(4, Math.round((v / maxTrend.value) * 90));
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
/* 统计数值 28px / 字重 600（对标 meiren） */
:deep(.ant-statistic-content-value) {
  font-size: 28px;
  font-weight: 600;
}
.tag-group { display: flex; flex-wrap: wrap; gap: 8px; }
.empty-text { color: #8a91a5; font-size: 14px; }
</style>
