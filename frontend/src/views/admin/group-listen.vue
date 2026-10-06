<template>
  <div>
    <a-button type="primary" @click="openEditor()" style="margin-bottom: 16px">新建监听计划</a-button>
    <a-table :columns="columns" :data-source="list" row-key="id" :loading="loading">
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'bind'">
          <a-tag color="blue">{{ record.bindId }}</a-tag>
        </template>
        <template v-else-if="column.key === 'action'">
          <a-popconfirm title="确认删除？" @confirm="remove(record.id)"><a>删除</a></a-popconfirm>
        </template>
      </template>
    </a-table>
    <a-modal v-model:open="visible" title="关键字监听" @ok="save">
      <a-form :model="editing" layout="vertical">
        <a-form-item label="计划名称"><a-input v-model:value="editing.name" /></a-form-item>
        <a-form-item label="监听目标（逗号分隔）"><a-input v-model:value="editing.targets_str" placeholder="@group1,@channel1" /></a-form-item>
        <a-form-item label="关键词（逗号分隔）"><a-input v-model:value="editing.keywords_str" placeholder="上新,到货" /></a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import { message } from 'ant-design-vue';
import { listenApi } from '@/api';

const columns = [
  { title: 'ID', dataIndex: 'id', width: 60 },
  { title: '名称', dataIndex: 'name' },
  { title: '绑定 ID', key: 'bind', width: 130 },
  { title: '操作', key: 'action', width: 80 },
];
const list = ref<any[]>([]); const loading = ref(false);
const visible = ref(false); const editing = reactive<any>({});

async function load() {
  loading.value = true;
  try { list.value = await listenApi.plans(); } finally { loading.value = false; }
}
function openEditor() {
  Object.assign(editing, { name: '', targets_str: '', keywords_str: '' });
  visible.value = true;
}
async function save() {
  await listenApi.create({
    name: editing.name,
    targets: editing.targets_str.split(',').map((s: string) => s.trim()).filter(Boolean),
    keywords: editing.keywords_str.split(',').map((s: string) => s.trim()).filter(Boolean),
  });
  message.success('已创建，请将 8 位绑定 ID 发给官方机器人完成绑定');
  visible.value = false; load();
}
async function remove(id: number) { await listenApi.remove(id); message.success('已删除'); load(); }
onMounted(load);
</script>
