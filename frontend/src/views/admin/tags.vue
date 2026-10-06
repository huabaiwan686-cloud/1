<template>
  <div>
    <div class="aq-header">
      <div class="aq-title">标签库</div>
      <p class="aq-desc">管理内容标签，用于资料分类与筛选</p>
      <div class="aq-toolbar">
        <span class="ant-input-group ant-input-group-compact" style="width: 420px; display: inline-flex">
          <a-input v-model:value="name" placeholder="输入新标签名" style="width: 240px" @press-enter="create" />
          <a-button type="primary" @click="create">新建标签</a-button>
        </span>
        <span class="ant-input-group ant-input-group-compact" style="margin-left: 8px; display: inline-flex">
          <a-input v-model:value="keyword" placeholder="搜索标签" style="width: 200px" @press-enter="load" />
          <a-button @click="load">搜索</a-button>
        </span>
      </div>
    </div>
    <a-card :bordered="true">
      <a-table :columns="columns" :data-source="list" row-key="id" :loading="loading"
               :scroll="{ x: 900 }" :pagination="{ pageSize: 20 }">
        <template #bodyCell="{ column, record }">
          <template v-if="column.dataIndex === 'name'">
            <span style="font-weight: 500">{{ record.name }}</span>
          </template>
          <template v-if="column.key === 'source'">
            <span class="aq-tag-gray">{{ record.source || '手动' }}</span>
          </template>
          <template v-if="column.key === 'status'">
            <a-tag color="green">启用</a-tag>
          </template>
          <template v-if="column.key === 'action'">
            <a-popconfirm title="确认删除该标签？" @confirm="removeTag(record.id)">
              <a>删除</a>
            </a-popconfirm>
          </template>
        </template>
      </a-table>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { message } from 'ant-design-vue';
import { metaApi } from '@/api';

const columns = [
  { title: 'ID', dataIndex: 'id', width: 60 },
  { title: '名称', dataIndex: 'name', width: 180 },
  { title: '来源', key: 'source', width: 110 },
  { title: '状态', key: 'status', width: 90 },
  { title: '使用次数', dataIndex: 'usageCount', width: 100 },
  { title: '创建时间', dataIndex: 'createdAt', width: 170 },
  { title: '操作', key: 'action', width: 80 },
];
const list = ref<any[]>([]);
const loading = ref(false);
const name = ref('');
const keyword = ref('');

async function load() {
  loading.value = true;
  try {
    const r: any = await metaApi.tags();
    let rows = r.list || r || [];
    if (keyword.value.trim()) {
      rows = rows.filter((t: any) => (t.name || '').includes(keyword.value.trim()));
    }
    list.value = rows;
  } finally { loading.value = false; }
}
async function create() {
  if (!name.value.trim()) { message.warning('请输入标签名'); return; }
  await metaApi.createTag(name.value.trim());
  message.success('标签已创建');
  name.value = '';
  load();
}
async function removeTag(id: number) {
  message.info('删除功能开发中');
}
onMounted(load);
</script>
