<template>
  <div class="page">
    <div class="page-title">频道配置</div>
    <div class="page-subtitle">管理推送频道</div>
    <div class="page-toolbar">
      <a-button type="primary" @click="openEditor()">添加频道</a-button>
      <a-radio-group v-model:value="filter" @change="load">
        <a-radio-button value="all">全部</a-radio-button>
        <a-radio-button :value="true">上架中</a-radio-button>
        <a-radio-button :value="false">已下架</a-radio-button>
      </a-radio-group>
    </div>
    <a-table :columns="columns" :data-source="list" row-key="id" :loading="loading" :scroll="{ x: 'max-content' }">
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'status'">
          <a-tag :color="record.isActive ? 'green' : 'default'">{{ record.isActive ? '上架' : '下架' }}</a-tag>
        </template>
        <template v-else-if="column.key === 'bot'">
          <span>{{ botName(record.botId) }}</span>
        </template>
        <template v-else-if="column.key === 'action'">
          <a-space class="table-actions">
            <a @click="openEditor(record)">编辑</a>
            <a @click="check(record.id)">检测</a>
            <a @click="pushAll(record.id)">全量推送</a>
            <a-popconfirm title="清空该频道的待发送定时队列？" @confirm="clearQueue(record.id)"><a>清空队列</a></a-popconfirm>
            <a-popconfirm title="确认删除？" @confirm="remove(record.id)"><a>删除</a></a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>
    <a-modal class="modal-form" v-model:open="visible" title="频道配置" @ok="save">
      <a-form :model="editing" layout="vertical">
        <a-form-item label="频道名称"><a-input v-model:value="editing.name" /></a-form-item>
        <a-form-item label="用户名"><a-input v-model:value="editing.username" placeholder="@xxx（公开频道）" /></a-form-item>
        <a-form-item label="频道编号（私有频道填，如 -1001234567890，优先于用户名）">
          <a-input v-model:value="editing.tg_channel_id" placeholder="-100..." />
        </a-form-item>
        <a-form-item>
          <a-button type="dashed" @click="openChannelPicker">从 TG 选择频道（只显示频道）</a-button>
        </a-form-item>
        <a-form-item label="推送机器人（需为该频道管理员）">
          <a-select v-model:value="editing.bot_id" placeholder="选择机器人" style="width: 100%" allow-clear>
            <a-select-option v-for="b in botTokens" :key="b.id" :value="b.id">@{{ b.username || b.name }}</a-select-option>
          </a-select>
        </a-form-item>
        <a-space>
          <a-checkbox v-model:checked="editing.is_active">上架</a-checkbox>
          <a-checkbox v-model:checked="editing.is_default">默认选中</a-checkbox>
        </a-space>
      </a-form>
    </a-modal>

    <!-- TG 选频道（只显示该 Bot 为管理员的频道） -->
    <a-modal v-model:open="pickerVisible" title="选择频道（仅显示该 Bot 为管理员的频道）" :footer="null" :width="600">
      <a-space style="margin-bottom: 12px">
        <a-select v-model:value="pickerAccountId" placeholder="选择协议号（用于读取频道列表）" style="width: 260px">
          <a-select-option v-for="a in tgAccounts" :key="a.id" :value="a.id">{{ a.phone }}（{{ a.name }}）</a-select-option>
        </a-select>
        <a-button type="primary" @click="loadPickerChannels" :loading="pickerLoading">刷新缓存并筛选</a-button>
      </a-space>
      <div style="color: #888; font-size: 12px; margin-bottom: 8px">已选机器人：{{ botName(editing.bot_id) }}，仅列出该机器人为管理员的频道。手动输入 uuid / 用户名功能保留，可直接填写。</div>
      <a-list :data-source="pickerChannels" :loading="pickerLoading">
        <template #renderItem="{ item }">
          <a-list-item @click="pickChannel(item)" style="cursor: pointer">
            <a-list-item-meta :title="item.title" :description="item.username ? '@' + item.username : 'ID: ' + item.chatId" />
          </a-list-item>
        </template>
      </a-list>
      <a-empty v-if="!pickerChannels.length && !pickerLoading" description="暂无频道，请先在协议号页面刷新缓存" />
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import { message, Modal } from 'ant-design-vue';
import { channelApi, mediaApi, botApi, tgApi, messageApi } from '@/api';

const columns = [
  { title: '编号', dataIndex: 'id', width: 60 },
  { title: '名称', dataIndex: 'name' },
  { title: '用户名', dataIndex: 'username' },
  { title: '推送机器人', key: 'bot', width: 150 },
  { title: '状态', key: 'status', width: 80 },
  { title: '操作', key: 'action', width: 260 },
];
const list = ref<any[]>([]);
const allChannels = ref<any[]>([]); // 规则选择器用全量，不受顶部筛选影响 const loading = ref(false);
const filter = ref<any>('all'); const visible = ref(false);
const editing = reactive<any>({});
const botTokens = ref<any[]>([]);
// TG 选频道
const tgAccounts = ref<any[]>([]);
const pickerVisible = ref(false);
const pickerAccountId = ref<number | null>(null);
const pickerChannels = ref<any[]>([]);
const pickerLoading = ref(false);

async function openChannelPicker() {
  pickerVisible.value = true;
  if (!tgAccounts.value.length) {
    try { tgAccounts.value = await tgApi.accounts(); } catch {}
  }
}

async function loadPickerChannels() {
  if (!pickerAccountId.value) { message.warning('请先选择协议号'); return; }
  if (!editing.bot_id) { message.warning('请先选择推送机器人'); return; }
  pickerLoading.value = true;
  try {
    // 只显示该 Bot 为管理员的频道
    const r: any = await channelApi.botChannels(editing.bot_id, pickerAccountId.value);
    pickerChannels.value = r.list || r || [];
    if (!pickerChannels.value.length) message.info('该机器人暂无管理的频道');
  } catch (e: any) { message.error(e.message || '加载频道失败'); }
  finally { pickerLoading.value = false; }
}

function pickChannel(c: any) {
  editing.name = c.title || '';
  editing.username = c.username ? '@' + c.username : '';
  editing.tg_channel_id = String(c.chatId || '');
  pickerVisible.value = false;
  message.success('已选择频道，请补全机器人后保存');
}

function botName(id: number) {
  const b = botTokens.value.find((x: any) => x.id === id);
  return b ? '@' + (b.username || b.name) : (id ? '#' + id : '未绑定');
}

async function load() {
  loading.value = true;
  try {
    const [l, b] = await Promise.allSettled([
      channelApi.list(filter.value === 'all' ? undefined : filter.value),
      botApi.tokens(),
    ]);
    if (l.status === 'fulfilled') { list.value = l.value; allChannels.value = l.value; }
    if (b.status === 'fulfilled') botTokens.value = b.value;
  } finally { loading.value = false; }
}
function openEditor(r?: any) {
  // 清除 id，避免编辑后新建时 stale-id 覆盖原记录
  delete (editing as any).id;
  Object.assign(editing, { name: '', username: '', tg_channel_id: '', is_active: true, is_default: false, bot_id: null });
  if (r) {
    // 后端返回 camelCase，表单用 snake_case，逐个映射避免编辑时静默重置
    editing.id = r.id;
    editing.name = r.name ?? '';
    editing.username = r.username ?? '';
    editing.tg_channel_id = r.tgChannelId ?? '';
    editing.is_active = r.isActive ?? true;
    editing.is_default = r.isDefault ?? false;
    editing.bot_id = r.botId ?? null;
  }
  visible.value = true;
}
async function save() {
  if (!editing.name?.trim()) { message.error('请填写频道名称'); return; }
  if (!editing.username?.trim() && !editing.tg_channel_id?.toString().trim()) {
    message.error('请填写频道用户名或频道编号'); return;
  }
  try {
    if (editing.id) await channelApi.update(editing.id, editing);
    else await channelApi.create(editing);
    message.success('已保存'); visible.value = false; load();
  } catch (e: any) { message.error(e.message); }
}
async function remove(id: number) {
  try { await channelApi.remove(id); message.success('已删除'); load(); }
  catch (e: any) { message.error(e.message || '删除失败'); }
}
async function check(id: number) {
  try { const r: any = await channelApi.check(id); message.info(r.data?.msg || r.msg); }
  catch (e: any) { message.error(e.message || '检查失败'); }
}
async function pushAll(id: number) {
  Modal.confirm({
    title: '确认全量推送？',
    content: '将向该频道推送所有待发送内容',
    onOk: async () => {
      try {
        const r: any = await channelApi.pushAll(id);
        message.success(r.msg || '全量推送完成');
      } catch (e: any) { message.error(e.message || '推送失败'); }
    },
  });
}
async function clearQueue(id: number) {
  try { const r: any = await channelApi.clearQueue(id); message.success(r.msg || '队列已清空'); }
  catch (e: any) { message.error(e.message || '清空失败'); }
}
onMounted(() => { load(); });
</script>
