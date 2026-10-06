<template>
  <div>
    <a-space style="margin-bottom: 16px">
      <a-button type="primary" @click="openEditor()">发布公告</a-button>
    </a-space>
    <a-table :columns="columns" :data-source="list" row-key="id" :loading="loading">
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'enabled'">
          <a-tag :color="record.enabled ? 'green' : 'default'">{{ record.enabled ? '展示中' : '已关闭' }}</a-tag>
        </template>
        <template v-else-if="column.key === 'action'">
          <a-space>
            <a @click="openEditor(record)">编辑</a>
            <a @click="toggle(record)">{{ record.enabled ? '关闭' : '开启' }}</a>
            <a-popconfirm title="确认删除？" @confirm="remove(record.id)"><a>删除</a></a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>
    <a-modal v-model:open="visible" title="公告" @ok="save">
      <a-form :model="editing" layout="vertical">
        <a-form-item label="标题"><a-input v-model:value="editing.title" /></a-form-item>
        <a-form-item label="内容"><a-textarea v-model:value="editing.content" :rows="6" /></a-form-item>
        <a-checkbox v-model:checked="editing.enabled">启用（登录后弹窗展示）</a-checkbox>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import { message } from 'ant-design-vue';
import { announceApi } from '@/api';

const columns = [
  { title: 'ID', dataIndex: 'id', width: 60 },
  { title: '标题', dataIndex: 'title' },
  { title: '状态', key: 'enabled', width: 100 },
  { title: '更新时间', dataIndex: 'updatedAt', width: 180 },
  { title: '操作', key: 'action', width: 200 },
];
const list = ref<any[]>([]); const loading = ref(false);
const visible = ref(false);
const editing = reactive<any>({});

async function load() {
  loading.value = true;
  try { list.value = await announceApi.list(); } finally { loading.value = false; }
}
function openEditor(r?: any) {
  Object.assign(editing, { title: '', content: '', enabled: true, ...r });
  visible.value = true;
}
async function save() {
  try {
    if (editing.id) await announceApi.update(editing.id, editing);
    else await announceApi.create(editing);
    message.success('已保存'); visible.value = false; load();
  } catch (e: any) { message.error(e.message); }
}
async function toggle(r: any) {
  await announceApi.update(r.id, { ...r, enabled: !r.enabled });
  message.success('已' + (!r.enabled ? '开启' : '关闭')); load();
}
async function remove(id: number) { await announceApi.remove(id); message.success('已删除'); load(); }
onMounted(load);
</script>
