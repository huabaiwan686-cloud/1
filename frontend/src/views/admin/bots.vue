<template>
  <div>
    <a-card :bordered="true">
      <template #extra>
        <a-button type="primary" @click="openEditor()">添加 Bot Token</a-button>
      </template>
      <a-table :columns="columns" :data-source="list" row-key="id" :loading="loading" :scroll="{ x: 900 }">
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'mode'">
          <a-tag color="blue">Bot API</a-tag>
        </template>
        <template v-if="column.key === 'status'">
          <a-tag :color="record.enabled ? 'green' : 'default'">{{ record.enabled ? '运行中' : '停用' }}</a-tag>
        </template>
        <a-space v-if="column.key === 'action'">
          <a @click="verify(record.id)">验证</a>
          <a @click="copyToken(record.id)">复制</a>
          <a-popconfirm title="确认删除？" @confirm="remove(record.id)"><a>删除</a></a-popconfirm>
        </a-space>
      </template>
    </a-table>
    </a-card>
    <a-modal v-model:open="visible" title="Bot Token" @ok="save" :confirm-loading="saving">
      <a-form :model="editing" layout="vertical">
        <a-form-item label="名称"><a-input v-model:value="editing.name" /></a-form-item>
        <a-form-item label="Bot 用户名（以 bot 结尾）"><a-input v-model:value="editing.username" placeholder="@xxxbot" /></a-form-item>
        <a-form-item label="Token" v-if="!editing.auto_create"><a-input v-model:value="editing.token" placeholder="123456:ABC-DEF..." /></a-form-item>
        <a-form-item label="用哪个协议号创建" v-if="editing.auto_create">
          <a-select v-model:value="editing.tg_account_id" placeholder="选择已登录的 TG 协议号" style="width: 100%">
            <a-select-option v-for="a in tgAccounts" :key="a.id" :value="a.id">{{ a.phone }}（{{ a.name }}）</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="备注"><a-textarea v-model:value="editing.remark" :rows="2" /></a-form-item>
        <a-checkbox v-model:checked="editing.auto_create">自动创建（通过 BotFather，约 10~20 秒）</a-checkbox>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import { message } from 'ant-design-vue';
import { botApi, tgApi } from '@/api';

const columns = [
  { title: 'ID', dataIndex: 'id', width: 60 },
  { title: '名称', dataIndex: 'name', width: 150 },
  { title: '用户名', dataIndex: 'username', width: 180 },
  { title: '运行模式', key: 'mode', width: 110 },
  { title: '状态', key: 'status', width: 90 },
  { title: '操作', key: 'action', width: 180 },
];
const list = ref<any[]>([]); const loading = ref(false);
const visible = ref(false); const saving = ref(false);
const tgAccounts = ref<any[]>([]);
const editing = reactive<any>({});

async function load() {
  loading.value = true;
  try {
    list.value = await botApi.tokens();
    tgAccounts.value = await tgApi.accounts();
  } finally { loading.value = false; }
}
function openEditor() {
  Object.assign(editing, { name: '', username: '', token: '', remark: '', auto_create: false, tg_account_id: null });
  visible.value = true;
}
async function save() {
  saving.value = true;
  try {
    if (editing.auto_create) {
      if (!editing.tg_account_id) { message.error('请选择用于创建的 TG 协议号'); return; }
      const r: any = await botApi.autoCreate({
        name: editing.name, username: editing.username, tg_account_id: editing.tg_account_id,
      });
      message.success(r.msg || '已自动创建');
    } else {
      await botApi.create(editing);
      message.success('已保存');
    }
    visible.value = false; load();
  }
  catch (e: any) { message.error(e.message); } finally { saving.value = false; }
}
async function verify(id: number) {
  const r: any = await botApi.verify(id); message.info(r.msg);
}
async function toggleEnabled(record: any, enabled: boolean) {
  try {
    await botApi.setEnabled(record.id, enabled);
    record.enabled = enabled;
    message.success(enabled ? '已启用' : '已停用');
  } catch (e: any) { message.error(e.message || '操作失败'); load(); }
}
async function copyToken(id: number) {
  try {
    const r: any = await botApi.getToken(id);
    await navigator.clipboard.writeText(r.token);
    message.success('Token 已复制到剪贴板');
  } catch (e: any) { message.error(e.message || '复制失败'); }
}
async function remove(id: number) {
  try { await botApi.remove(id); message.success('已删除'); load(); }
  catch (e: any) { message.error(e.message || '删除失败'); }
}
onMounted(load);
</script>
