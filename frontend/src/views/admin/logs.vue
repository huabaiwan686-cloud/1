<template>
  <div>
    <a-space style="margin-bottom: 16px">
      <a-input-search v-model:value="keyword" placeholder="搜索详情" @search="load" style="width: 240px" />
      <a-select v-model:value="result" style="width: 130px" @change="load" allow-clear placeholder="结果">
        <a-select-option value="success">成功</a-select-option>
        <a-select-option value="failed">失败</a-select-option>
        <a-select-option value="processing">处理中</a-select-option>
      </a-select>
    </a-space>
    <a-table :columns="columns" :data-source="list" row-key="id" :loading="loading"
      :pagination="{ total, current: page, pageSize, onChange: (p: number) => { page = p; load(); } }">
      <template #bodyCell="{ column, record }">
        <a-tag v-if="column.key === 'result'" :color="record.result === 'success' ? 'green' : record.result === 'failed' ? 'red' : 'orange'">
          {{ record.result }}
        </a-tag>
      </template>
    </a-table>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { metaApi } from '@/api';

const columns = [
  { title: 'ID', dataIndex: 'id', width: 70 },
  { title: '动作', dataIndex: 'action', width: 140 },
  { title: '执行方', dataIndex: 'executor', width: 120 },
  { title: '结果', key: 'result', width: 90 },
  { title: '详情', dataIndex: 'detail' },
  { title: '时间', dataIndex: 'createdAt', width: 180 },
];
const list = ref<any[]>([]); const total = ref(0);
const page = ref(1); const pageSize = ref(20);
const keyword = ref(''); const result = ref(undefined as any);
const loading = ref(false);

async function load() {
  loading.value = true;
  try {
    const data: any = await metaApi.taskLogs({ keyword: keyword.value, result: result.value, page: page.value, page_size: pageSize.value });
    list.value = data.list; total.value = data.total;
  } finally { loading.value = false; }
}
onMounted(load);
</script>
