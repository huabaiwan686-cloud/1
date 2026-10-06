<template>
  <div>
    <a-card :bordered="true">
      <template #extra>
        <a-button type="primary" @click="visible = true">新建双向机器人</a-button>
      </template>
      <a-table :columns="columns" :data-source="list" row-key="id" :loading="loading" :scroll="{ x: 900 }">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'botId'">
            <span>{{ botName(record.botTokenId) }}</span>
          </template>
          <template v-if="column.key === 'enabled'">
            <a-switch :checked="record.enabled !== false" size="small" @change="(v) => toggleEnabled(record, v)" />
          </template>
          <template v-if="column.key === 'action'">
            <a-popconfirm title="确认删除？" @confirm="remove(record.id)"><a>删除</a></a-popconfirm>
          </template>
        </template>
      </a-table>
    </a-card>
    <a-modal v-model:open="visible" title="双向机器人" @ok="save" width="520px">
      <a-form :model="form" layout="vertical">
        <a-form-item label="Bot">
          <a-select v-model:value="form.bot_token_id" placeholder="选择 Bot" style="width: 100%">
            <a-select-option v-for="b in bots" :key="b.id" :value="b.id">{{ b.name }}（{{ b.username }}）</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="客服 Chat ID">
          <a-input v-model:value="form.service_chat_id" placeholder="客服的 Telegram Chat ID" />
        </a-form-item>
        <a-form-item label="TG 账号">
          <a-select v-model:value="form.tg_account_id" placeholder="选择 TG 账号" style="width: 100%">
            <a-select-option v-for="a in accounts" :key="a.id" :value="a.id">{{ a.phone }}（{{ a.name }}）</a-select-option>
          </a-select>
        </a-form-item>
      </a-form>
      <div class="aq-tip">双向机器人：用户发给 Bot 的消息转发给客服，客服回复自动转回用户</div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import { message } from 'ant-design-vue';
import { socialApi, botApi, tgApi } from '@/api';

// meiren 双向机器人列：ID/Bot ID/客服 Chat ID/开关/操作
const columns = [
  { title: 'ID', dataIndex: 'id', width: 60, className: 'hide-mobile' },
  { title: 'Bot ID', key: 'botId', width: 200 },
  { title: '客服 Chat ID', dataIndex: 'serviceChatId', width: 170 },
  { title: '开关', key: 'enabled', width: 80 },
  { title: '操作', key: 'action', width: 80 },
];
const list = ref<any[]>([]);
const bots = ref<any[]>([]);
const accounts = ref<any[]>([]);
const loading = ref(false);
const visible = ref(false);
const form = reactive({ bot_token_id: null as any, service_chat_id: '', tg_account_id: null as any });

function botName(id: number) {
  const b = bots.value.find((x: any) => x.id === id);
  return b ? `${b.name}（#${id}）` : (id ? '#' + id : '—');
}
async function load() {
  loading.value = true;
  try {
    const r: any = await socialApi.twoWayBots();
    list.value = (r.list || r || []).map((b: any) => ({
      ...b,
      botTokenId: b.bot_token_id,
      serviceChatId: b.service_chat_id,
    }));
    bots.value = await botApi.tokens();
    accounts.value = await tgApi.accounts();
  } finally { loading.value = false; }
}
async function save() {
  if (!form.bot_token_id) { message.warning('请选择 Bot'); return; }
  await socialApi.createTwoWay(form);
  message.success('已创建');
  visible.value = false;
  Object.assign(form, { bot_token_id: null, service_chat_id: '', tg_account_id: null });
  load();
}
async function toggleEnabled(record: any, enabled: boolean) {
  try {
    await socialApi.updateTwoWay(record.id, { enabled });
    record.enabled = enabled;
    message.success(enabled ? '已启用' : '已停用');
  } catch (e: any) { message.error(e.message || '操作失败'); }
}
async function remove(id: number) {
  try {
    await socialApi.removeTwoWay(id);
    message.success('已删除');
    load();
  } catch (e: any) { message.error(e.message || '删除失败'); }
}
onMounted(load);
</script>
