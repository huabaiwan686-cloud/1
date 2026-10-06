<template>
  <div>
    <a-card title="我的内容">
      <a-space style="margin-bottom: 16px">
        <a-radio-group v-model:value="status" @change="load">
          <a-radio-button value="">全部</a-radio-button>
          <a-radio-button value="draft">草稿</a-radio-button>
          <a-radio-button value="pending">待审核</a-radio-button>
          <a-radio-button value="published">已上架</a-radio-button>
          <a-radio-button value="offline">已下架</a-radio-button>
        </a-radio-group>
      </a-space>
      <a-table :columns="columns" :data-source="list" row-key="id" :loading="loading"
               :pagination="{ total, current: page, pageSize, onChange: onPage }">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'status'">
            <a-tag :color="statusColor(record.status)">{{ record.statusText }}</a-tag>
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
  { title: '标题', dataIndex: 'title' },
  { title: '状态', key: 'status', width: 100 },
  { title: '提交时间', dataIndex: 'createdAt', width: 180 },
  { title: '上架时间', dataIndex: 'publishedAt', width: 180 },
];
const list = ref<any[]>([]); const loading = ref(false);
const status = ref(''); const page = ref(1); const pageSize = 20; const total = ref(0);

const COLORS: any = { draft: 'default', pending: 'orange', published: 'green', offline: 'red' };
function statusColor(s: string) { return COLORS[s] || 'default'; }

async function load() {
  loading.value = true;
  try {
    const r: any = await collectorApi.myNotes({ status: status.value || undefined, page: page.value, page_size: pageSize });
    list.value = r.list; total.value = r.total;
  } finally { loading.value = false; }
}
function onPage(p: number) { page.value = p; load(); }
onMounted(load);
</script>
