<template>
  <div>
    <a-alert message="采集后需审核的资料会在此列出，审核通过进入笔记库" type="info" style="margin-bottom: 16px" />
    <a-table :columns="columns" :data-source="list" row-key="id" :loading="loading"
      :pagination="{ total, current: page, pageSize, onChange: (p: number) => { page = p; load(); } }">
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'action'">
          <a-space>
            <a @click="approve(record.id, true)">通过</a>
            <a @click="approve(record.id, false)">拒绝</a>
          </a-space>
        </template>
      </template>
    </a-table>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { message } from 'ant-design-vue';
import { noteApi } from '@/api';

const columns = [
  { title: 'ID', dataIndex: 'id', width: 70 },
  { title: '标题', dataIndex: 'title' },
  { title: '来源', dataIndex: 'source', width: 90 },
  { title: '采集时间', dataIndex: 'createdAt', width: 180 },
  { title: '操作', key: 'action', width: 140 },
];
const list = ref<any[]>([]);
const total = ref(0); const page = ref(1); const pageSize = ref(20);
const loading = ref(false);

async function load() {
  loading.value = true;
  try {
    const data: any = await noteApi.list({ status: 'pending', page: page.value, page_size: pageSize.value });
    list.value = data.list; total.value = data.total;
  } finally { loading.value = false; }
}
async function approve(id: number, pass: boolean) {
  // 审核通过=发布入库；拒绝=下架
  await noteApi.batch([id], pass ? 'publish' : 'unpublish');
  message.success(pass ? '已通过并发布' : '已拒绝');
  load();
}
onMounted(load);
</script>
