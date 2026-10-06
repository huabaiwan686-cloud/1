<template>
  <a-card title="发送记录" :bordered="true">
    <template #extra>
      <a-space>
        <a-radio-group v-model:value="result" option-type="button" button-style="solid"
          style="margin-right: 12px" @change="reload">
          <a-radio-button value="">全部</a-radio-button>
          <a-radio-button value="success">成功</a-radio-button>
          <a-radio-button value="failed">失败</a-radio-button>
        </a-radio-group>
        <a-popconfirm title="确认清空全部发送记录？不可恢复" @confirm="clearAll">
          <a-button danger>清空记录</a-button>
        </a-popconfirm>
      </a-space>
    </template>
    <a-table :columns="columns" :data-source="list" row-key="id" :loading="loading"
      :scroll="{ x: 'max-content' }"
      :pagination="{ total, current: page, pageSize, onChange: (p: number) => { page = p; load(); } }">
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'status'">
          <a-tag :color="record.result === 'success' ? 'green' : record.result === 'failed' ? 'red' : 'default'">
            {{ record.result === 'success' ? '成功' : record.result === 'failed' ? '失败' : (record.result || '—') }}
          </a-tag>
        </template>
      </template>
    </a-table>
  </a-card>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { message } from 'ant-design-vue';
import { metaApi } from '@/api';
import { formatDateTime } from '@/utils/date';

const columns = [
  { title: '内容编号', dataIndex: 'id', width: 90 },
  { title: '操作', dataIndex: 'action', width: 140 },
  { title: '频道类型', key: 'chtype', width: 100 },
  { title: '频道ID', key: 'chid', width: 100 },
  { title: '来源', dataIndex: 'executor', width: 120 },
  { title: '状态', key: 'status', width: 90 },
  { title: '详细信息', dataIndex: 'detail' },
  { title: '时间', dataIndex: 'createdAt', width: 180, customRender: ({ text }: any) => formatDateTime(text) },
];
const list = ref<any[]>([]); const total = ref(0);
const page = ref(1); const pageSize = ref(20);
const result = ref('');
const loading = ref(false);

async function load() {
  loading.value = true;
  try {
    const data: any = await metaApi.taskLogs({
      result: result.value || undefined, page: page.value, page_size: pageSize.value,
    });
    list.value = data.list || []; total.value = data.total || 0;
  } finally { loading.value = false; }
}
function reload() { page.value = 1; load(); }
async function clearAll() {
  try { await metaApi.clearTaskLogs(); message.success('已清空'); reload(); }
  catch (e: any) { message.error(e.message); }
}
onMounted(load);
</script>
