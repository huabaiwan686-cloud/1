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
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import request from '@/utils/request';

const stats = ref<any>({ notesByStatus: {} });
const statCards = computed(() => [
  { label: '资料总数', value: stats.value.notesTotal || 0 },
  { label: '今日发布', value: stats.value.todayPublishes || 0 },
  { label: '上架频道', value: stats.value.channelsActive || 0 },
  { label: '图片额度剩余', value: stats.value.quotaLeft || 0 },
]);
onMounted(async () => {
  stats.value = await request.get('/api/dashboard/stats');
});
</script>
