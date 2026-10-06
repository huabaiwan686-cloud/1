<template>
  <a-card title="群聊监听（发布端）">
    <a-alert message="监听计划的命中记录：谁在哪个群触发了关键词、发出了几组素材" type="info" style="margin-bottom: 16px" />
    <a-table :columns="columns" :data-source="list" row-key="id" :loading="loading" :pagination="{ pageSize: 20 }">
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'result'">
          <a-tag :color="record.result === 'success' ? 'green' : 'default'">{{ record.result === 'success' ? '已发送' : record.result === 'skipped' ? '跳过' : '失败' }}</a-tag>
        </template>
      </template>
    </a-table>
  </a-card>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { listenApi } from '@/api';

const columns = [
  { title: '时间', dataIndex: 'createdAt', width: 170 },
  { title: '触发用户', dataIndex: 'tgUsername', width: 130 },
  { title: '触发群', dataIndex: 'chatTitle' },
  { title: '关键词', dataIndex: 'keyword', width: 90 },
  { title: '城市', dataIndex: 'cityName', width: 90 },
  { title: '发出组数', dataIndex: 'notesSent', width: 90 },
  { title: '结果', key: 'result', width: 90 },
];
const list = ref<any[]>([]); const loading = ref(false);
onMounted(async () => {
  loading.value = true;
  try { list.value = await listenApi.hits(); } finally { loading.value = false; }
});
</script>
