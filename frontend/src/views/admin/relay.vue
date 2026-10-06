<template>
  <a-card title="自动转发" :bordered="true">
    <template #extra>
      <a-button type="primary" @click="openEditor()">添加规则</a-button>
    </template>
    <a-table :columns="columns" :data-source="list" row-key="id" :loading="loading"
      :scroll="{ x: 'max-content' }">
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'keyword'">
          <span style="color: rgba(0,0,0,.45)">—</span>
        </template>
        <template v-else-if="column.key === 'enabled'">
          <a-switch :checked="record.enabled" @change="(v: boolean) => toggle(record, v)" />
        </template>
        <template v-else-if="column.key === 'action'">
          <a-space>
            <a @click="openEditor(record)">编辑</a>
            <a-popconfirm title="确认删除该规则？" @confirm="remove(record.id)"><a>删除</a></a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>
  </a-card>
  <a-modal class="modal-form" v-model:open="visible" title="转发规则" @ok="save" :width="520">
    <a-form :model="form" layout="vertical">
      <a-form-item label="规则名称"><a-input v-model:value="form.name" placeholder="如：采集转发" /></a-form-item>
      <a-form-item label="执行协议号" required>
        <a-select v-model:value="form.account_id" placeholder="选择协议号" style="width: 100%">
          <a-select-option v-for="a in accounts" :key="a.id" :value="a.id">{{ a.phone || a.name }}</a-select-option>
        </a-select>
      </a-form-item>
      <a-form-item label="源群" required>
        <a-input v-model:value="form.source_chat" placeholder="源群用户名/链接/ID" />
      </a-form-item>
      <a-form-item label="目标群" required>
        <a-input v-model:value="form.target_chat" placeholder="目标群用户名/链接/ID" />
      </a-form-item>
      <a-form-item><a-checkbox v-model:checked="form.enabled">启用</a-checkbox></a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import { message } from 'ant-design-vue';
import { forwardApi, tgApi } from '@/api';

const columns = [
  { title: 'ID', dataIndex: 'id', width: 70 },
  { title: '协议号', dataIndex: 'accountId', width: 140,
    customRender: ({ text }: any) => accountName(text) },
  { title: '源群', dataIndex: 'sourceChat' },
  { title: '目标群', dataIndex: 'targetChat' },
  { title: '关键词', key: 'keyword', width: 120 },
  { title: '开关', key: 'enabled', width: 90 },
  { title: '操作', key: 'action', width: 160 },
];
const list = ref<any[]>([]); const loading = ref(false);
const visible = ref(false); const editId = ref(0);
const form = reactive<any>({ name: '', account_id: null, source_chat: '', target_chat: '', enabled: true });
const accounts = ref<any[]>([]);

function accountName(id: number) {
  const a = accounts.value.find((x: any) => x.id === id);
  return a ? (a.phone || a.name || ('#' + id)) : (id ? '#' + id : '—');
}

async function load() {
  loading.value = true;
  try {
    list.value = await forwardApi.rules();
    accounts.value = await tgApi.accounts();
  } finally { loading.value = false; }
}
function openEditor(r?: any) {
  editId.value = r?.id || 0;
  Object.assign(form, {
    name: r?.name ?? '', account_id: r?.accountId ?? null,
    source_chat: r?.sourceChat ?? '', target_chat: r?.targetChat ?? '',
    enabled: r?.enabled ?? true,
  });
  visible.value = true;
}
async function save() {
  if (!form.source_chat.trim() || !form.target_chat.trim()) { message.error('源群和目标群不能为空'); return; }
  try {
    await forwardApi.create(form);
    message.success('已保存，worker 将在 1 分钟内自动生效');
    visible.value = false; load();
  } catch (e: any) { message.error(e.message); }
}
async function toggle(r: any, v: boolean) {
  try { await forwardApi.toggle(r.id, v); message.success(v ? '已启用' : '已停用'); load(); }
  catch (e: any) { message.error(e.message); }
}
async function remove(id: number) {
  try { await forwardApi.remove(id); message.success('已删除'); load(); }
  catch (e: any) { message.error(e.message); }
}
onMounted(load);
</script>
