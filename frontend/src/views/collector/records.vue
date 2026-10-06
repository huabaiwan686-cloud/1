<template>
  <div>
    <a-card title="采集记录">
      <a-table :columns="columns" :data-source="list" row-key="id" :loading="loading"
               :pagination="{ total, current: page, pageSize, onChange: onPage }">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'result'">
            <a-tag :color="record.result === 'success' ? 'green' : record.result === 'failed' ? 'red' : 'orange'">
              {{ resultText(record.result) }}
            </a-tag>
          </template>
        </template>
      </a-table>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { collectorApi } from '@/api';

const columns = [
  { title: 'ID', dataIndex: 'id', width: 60 },
  { title: '资料ID', dataIndex: 'noteId', width: 80 },
  { title: '动作', dataIndex: 'action', width: 140 },
  { title: '执行人', dataIndex: 'executor', width: 120 },
  { title: '结果', key: 'result', width: 100 },
  { title: '详情', dataIndex: 'detail', ellipsis: true },
  { title: '时间', dataIndex: 'createdAt', width: 180 },
];
const list = ref<any[]>([]); const loading = ref(false);
const page = ref(1); const pageSize = 20; const total = ref(0);

function resultText(r: string) {
  return { success: '成功', failed: '失败', processing: '处理中' }[r] || r;
}

async function load() {
  loading.value = true;
  try {
    const r: any = await collectorApi.myRecords({ page: page.value, page_size: pageSize });
    list.value = r.list; total.value = r.total;
  } finally { loading.value = false; }
}
function onPage(p: number) { page.value = p; load(); }
onMounted(load);
</script>
