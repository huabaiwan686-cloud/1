<template>
  <div>
    <a-card :bordered="true">
      <template #extra>
        <a-button type="primary" @click="openEditor()">添加 Bot Token</a-button>
      </template>
      <a-table :columns="columns" :data-source="list" row-key="id" :loading="loading" :scroll="{ x: 900 }">
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'mode'">
          <a-tag color="blue">机器人</a-tag>
        </template>
        <template v-if="column.key === 'status'">
          <a-tag :color="record.enabled ? 'green' : 'default'">{{ record.enabled ? '运行中' : '停用' }}</a-tag>
        </template>
        <template v-if="column.key === 'submission'">
          <a-tag :color="record.submission_enabled ? 'orange' : 'default'">{{ record.submission_enabled ? '投稿' : '-' }}</a-tag>
        </template>
        <a-space v-if="column.key === 'action'">
          <a @click="verify(record.id)">验证</a>
          <a @click="copyToken(record.id)">复制</a>
          <a @click="toggleSubmission(record)">{{ record.submission_enabled ? '关闭投稿' : '设为投稿Bot' }}</a>
          <a v-if="record.submission_enabled" @click="openChannels(record)">投稿频道</a>
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
    <a-modal v-model:open="channelsVisible" title="投稿目标频道" @ok="saveChannels" :confirm-loading="channelsSaving">
      <p style="color: #666; margin-bottom: 12px;">不选 = 发到该账号全部启用频道；勾选 = 只发到所选频道。</p>
      <a-checkbox-group v-model:value="selectedChannels" style="display: flex; flex-direction: column; gap: 8px;">
        <a-checkbox v-for="ch in channels" :key="ch.id" :value="ch.id">{{ ch.name }}</a-checkbox>
      </a-checkbox-group>
      <a-empty v-if="!channels.length" description="暂无启用频道" />
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import { message } from 'ant-design-vue';
import { botApi, tgApi, channelApi } from '@/api';

const columns = [
  { title: '编号', dataIndex: 'id', width: 60, className: 'hide-mobile' },
  { title: '名称', dataIndex: 'name', width: 150 },
  { title: '用户名', dataIndex: 'username', width: 180 },
  { title: '运行模式', key: 'mode', width: 110 },
  { title: '状态', key: 'status', width: 90 },
  { title: '投稿Bot', key: 'submission', width: 90 },
  { title: '操作', key: 'action', width: 240 },
];
const list = ref<any[]>([]); const loading = ref(false);
const visible = ref(false); const saving = ref(false);
const tgAccounts = ref<any[]>([]);
const channels = ref<any[]>([]);
const channelsVisible = ref(false);
const channelsSaving = ref(false);
const selectedChannels = ref<number[]>([]);
const editingBot = ref<any>(null);
const editing = reactive<any>({});

async function load() {
  loading.value = true;
  try {
    // 两个接口独立加载，一个失败不影响另一个
    const [bots, accounts] = await Promise.allSettled([
      botApi.tokens(),
      tgApi.accounts(),
    ]);
    if (bots.status === 'fulfilled') list.value = bots.value;
    if (accounts.status === 'fulfilled') tgAccounts.value = accounts.value;
  } finally { loading.value = false; }
}
function openEditor() {
  Object.assign(editing, { name: '', username: '', token: '', remark: '', auto_create: false, tg_account_id: null });
  visible.value = true;
}
async function save() {
  if (!editing.name?.trim()) { message.error('请填写 Bot 名称'); return; }
  if (!editing.auto_create && !editing.token?.trim()) { message.error('请填写 Bot Token'); return; }
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
  try {
    const r: any = await botApi.verify(id);
    message.success(r.msg || '验证成功');
  } catch (e: any) {
    message.error(e.message || '验证失败');
  }
}
async function toggleEnabled(record: any, enabled: boolean) {
  try {
    await botApi.setEnabled(record.id, enabled);
    record.enabled = enabled;
    message.success(enabled ? '已启用' : '已停用');
  } catch (e: any) { message.error(e.message || '操作失败'); load(); }
}
async function toggleSubmission(record: any) {
  const enabled = !record.submission_enabled;
  try {
    await botApi.toggleSubmission(record.id, enabled);
    record.submission_enabled = enabled;
    message.success(enabled ? '已设为投稿 Bot（Webhook 已注册）' : '已关闭投稿');
  } catch (e: any) { message.error(e.message || '操作失败'); }
}
async function copyToken(id: number) {
  try {
    const r: any = await botApi.getToken(id);
    await navigator.clipboard.writeText(r.token);
    message.success('Token 已复制到剪贴板');
  } catch (e: any) { message.error(e.message || '复制失败'); }
}
async function openChannels(record: any) {
  editingBot.value = record;
  selectedChannels.value = [...(record.submission_channel_ids || [])];
  try {
    const data: any = await channelApi.list(true);
    channels.value = data.list || data || [];
  } catch { channels.value = []; }
  channelsVisible.value = true;
}
async function saveChannels() {
  if (!editingBot.value) return;
  channelsSaving.value = true;
  try {
    await botApi.setSubmissionChannels(editingBot.value.id, selectedChannels.value);
    editingBot.value.submission_channel_ids = [...selectedChannels.value];
    message.success('投稿目标频道已保存');
    channelsVisible.value = false;
  } catch (e: any) { message.error(e.message || '保存失败'); }
  finally { channelsSaving.value = false; }
}
async function remove(id: number) {
  try { await botApi.remove(id); message.success('已删除'); load(); }
  catch (e: any) { message.error(e.message || '删除失败'); }
}
onMounted(load);
</script>
