<template>
  <div>
    <a-card :bordered="true">
      <template #extra>
        <a-button type="primary" @click="openEditor()">新建监听</a-button>
      </template>
      <a-table :columns="columns" :data-source="list" row-key="id" :loading="loading" :scroll="{ x: 1000 }">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'botId'">
            <span>{{ botName(record.botId) }}</span>
          </template>
          <template v-if="column.key === 'enabled'">
            <a-switch :checked="record.enabled" size="small" @change="(v) => togglePlan(record.id, v)" />
          </template>
          <template v-if="column.key === 'action'">
            <a-space>
              <a @click="openEditor(record)">编辑</a>
              <a-popconfirm title="确认删除？" @confirm="remove(record.id)"><a>删除</a></a-popconfirm>
            </a-space>
          </template>
        </template>
      </a-table>
    </a-card>
    <a-card :bordered="true" title="命中记录" style="margin-top: 16px">
      <a-table :columns="hitColumns" :data-source="hits" row-key="id" :loading="hitsLoading"
               :pagination="{ pageSize: 20 }" :scroll="{ x: 900 }">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'result'">
            <a-tag :color="record.result === 'success' ? 'green' : 'default'">
              {{ record.result === 'success' ? '已发送' : record.result === 'skipped' ? '跳过' : '失败' }}
            </a-tag>
          </template>
        </template>
      </a-table>
    </a-card>
    <a-modal v-model:open="visible" title="群监听" @ok="save" width="520px">
      <a-form :model="editing" layout="vertical">
        <a-form-item label="名称" :rules="[{ required: true, message: '请输入名称' }]">
          <a-input v-model:value="editing.name" placeholder="监听计划名称" />
        </a-form-item>
        <a-form-item label="Bot">
          <a-select v-model:value="editing.bot_id" placeholder="选择 Bot" style="width: 100%">
            <a-select-option v-for="b in bots" :key="b.id" :value="b.id">{{ b.name }}（{{ b.username }}）</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="目标 Chat ID">
          <a-input v-model:value="editing.target_chat_id" placeholder="如：-1001234567890" />
        </a-form-item>
        <a-form-item label="关键词（逗号分隔）">
          <a-input v-model:value="editing.keywords_str" placeholder="北京,上海" />
        </a-form-item>
        <a-form-item label="监听协议号">
          <a-select v-model:value="editing.account_id" placeholder="选择已登录的 TG 协议号" style="width: 100%">
            <a-select-option v-for="a in tgAccounts" :key="a.id" :value="a.id">{{ a.phone }}（{{ a.name }}）</a-select-option>
          </a-select>
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import { message } from 'ant-design-vue';
import { listenApi, botApi, tgApi } from '@/api';

// meiren 群监听列：名称/Bot ID/目标 Chat ID/关键词/开关/操作
const columns = [
  { title: 'ID', dataIndex: 'id', width: 60 },
  { title: '名称', dataIndex: 'name', width: 160 },
  { title: 'Bot ID', key: 'botId', width: 180 },
  { title: '目标 Chat ID', dataIndex: 'targetChatId', width: 170 },
  { title: '关键词', dataIndex: 'keywordsText', width: 200 },
  { title: '开关', key: 'enabled', width: 80 },
  { title: '操作', key: 'action', width: 130 },
];
const hitColumns = [
  { title: '时间', dataIndex: 'createdAt', width: 170 },
  { title: '触发用户', dataIndex: 'tgUsername', width: 130 },
  { title: '触发群', dataIndex: 'chatTitle', width: 160 },
  { title: '关键词', dataIndex: 'keyword', width: 100 },
  { title: '结果', key: 'result', width: 90 },
];
const list = ref<any[]>([]);
const bots = ref<any[]>([]);
const tgAccounts = ref<any[]>([]);
const hits = ref<any[]>([]);
const loading = ref(false);
const hitsLoading = ref(false);
const visible = ref(false);
const editing = reactive<any>({});

function botName(id: number) {
  const b = bots.value.find((x: any) => x.id === id);
  return b ? `${b.name}（#${id}）` : (id ? '#' + id : '—');
}
function openEditor(record?: any) {
  Object.assign(editing, {
    id: record?.id || null,
    name: record?.name || '',
    bot_id: record?.botId || null,
    target_chat_id: record?.targetChatId || '',
    keywords_str: record?.keywordsText || '',
    account_id: record?.accountId || null,
  });
  visible.value = true;
}
async function load() {
  loading.value = true;
  try {
    const r: any = await listenApi.plans();
    list.value = (r.list || r || []).map((p: any) => ({
      ...p,
      botId: p.bot_id,
      targetChatId: p.target_chat_id,
      keywordsText: (p.keywords || []).join(','),
      accountId: p.account_id,
    }));
    bots.value = await botApi.tokens();
    tgAccounts.value = await tgApi.accounts();
  } finally { loading.value = false; }
}
async function loadHits() {
  hitsLoading.value = true;
  try {
    const r: any = await listenApi.hits();
    hits.value = r.list || r || [];
  } finally { hitsLoading.value = false; }
}
async function save() {
  if (!editing.name?.trim()) { message.warning('请输入名称'); return; }
  try {
    const payload = {
      name: editing.name,
      bot_id: editing.bot_id,
      target_chat_id: editing.target_chat_id,
      keywords_str: editing.keywords_str,
      account_id: editing.account_id,
    };
    if (editing.id) await listenApi.update(editing.id, payload);
    else await listenApi.create(payload);
    message.success('已保存');
    visible.value = false;
    load();
  } catch (e: any) { message.error(e.message); }
}
async function togglePlan(id: number, enabled: boolean) {
  try {
    await listenApi.toggle(id, enabled);
    message.success(enabled ? '已启用' : '已停用');
    load();
  } catch (e: any) { message.error(e.message || '操作失败'); }
}
async function remove(id: number) {
  try {
    await listenApi.remove(id);
    message.success('已删除');
    load();
  } catch (e: any) { message.error(e.message || '删除失败'); }
}
onMounted(() => { load(); loadHits(); });
</script>
