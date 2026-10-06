<template>
  <div>
    <a-button type="primary" @click="openEditor()" style="margin-bottom: 16px">添加 Bot Token</a-button>
    <a-table :columns="columns" :data-source="list" row-key="id" :loading="loading">
      <template #bodyCell="{ column, record }">
        <a-space v-if="column.key === 'action'">
          <a @click="verify(record.id)">验证</a>
          <a-popconfirm title="确认删除？" @confirm="remove(record.id)"><a>删除</a></a-popconfirm>
        </a-space>
      </template>
    </a-table>
    <a-modal v-model:open="visible" title="Bot Token" @ok="save">
      <a-form :model="editing" layout="vertical">
        <a-form-item label="名称"><a-input v-model:value="editing.name" /></a-form-item>
        <a-form-item label="Bot 用户名（以 bot 结尾）"><a-input v-model:value="editing.username" placeholder="@xxxbot" /></a-form-item>
        <a-form-item label="Token"><a-input v-model:value="editing.token" placeholder="123456:ABC-DEF..." /></a-form-item>
        <a-form-item label="备注"><a-textarea v-model:value="editing.remark" :rows="2" /></a-form-item>
        <a-checkbox v-model:checked="editing.auto_create">自动创建（通过 BotFather）</a-checkbox>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import { message } from 'ant-design-vue';
import { botApi } from '@/api';

const columns = [
  { title: 'ID', dataIndex: 'id', width: 60 },
  { title: '名称', dataIndex: 'name' },
  { title: '用户名', dataIndex: 'username' },
  { title: '操作', key: 'action', width: 140 },
];
const list = ref<any[]>([]); const loading = ref(false);
const visible = ref(false); const editing = reactive<any>({});

async function load() {
  loading.value = true;
  try { list.value = await botApi.tokens(); } finally { loading.value = false; }
}
function openEditor() {
  Object.assign(editing, { name: '', username: '', token: '', remark: '', auto_create: false });
  visible.value = true;
}
async function save() {
  try { await botApi.create(editing); message.success('已保存'); visible.value = false; load(); }
  catch (e: any) { message.error(e.message); }
}
async function verify(id: number) {
  const r: any = await botApi.verify(id); message.info(r.msg);
}
async function remove(id: number) { await botApi.remove(id); message.success('已删除'); load(); }
onMounted(load);
</script>
