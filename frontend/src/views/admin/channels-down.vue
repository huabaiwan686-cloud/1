<template>
  <a-card title="下架频道" :bordered="true">
    <template #extra>
      <a-button type="primary" @click="openEditor()">添加频道</a-button>
    </template>
    <a-table :columns="columns" :data-source="list" row-key="id" :loading="loading"
      :scroll="{ x: 'max-content' }">
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'direction'">
          <a-tag color="default">下架</a-tag>
        </template>
        <template v-else-if="column.key === 'status'">
          <a-tag :color="record.isActive ? 'green' : 'default'">{{ record.isActive ? '上架' : '下架' }}</a-tag>
        </template>
        <template v-else-if="column.key === 'action'">
          <a-space>
            <a @click="openEditor(record)">编辑</a>
            <a @click="check(record.id)">检测</a>
            <a-popconfirm title="确认删除？" @confirm="remove(record.id)"><a>删除</a></a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>
  </a-card>
  <a-modal class="modal-form" v-model:open="visible" title="频道配置" @ok="save" :width="520">
    <a-form :model="editing" layout="vertical">
      <a-form-item label="频道名称" required><a-input v-model:value="editing.name" /></a-form-item>
      <a-form-item label="用户名"><a-input v-model:value="editing.username" placeholder="@xxx（公开频道）" /></a-form-item>
      <a-form-item label="目标 ChatID">
        <a-input v-model:value="editing.tg_channel_id" placeholder="-100...（私有频道填，优先于用户名）" />
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
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import { message } from 'ant-design-vue';
import { channelApi, botApi } from '@/api';

const columns = [
  { title: 'ID', dataIndex: 'id', width: 70 },
  { title: '频道', dataIndex: 'name' },
  { title: '用户名', dataIndex: 'username' },
  { title: '目标ChatID', dataIndex: 'tgChannelId', width: 180 },
  { title: '方向', key: 'direction', width: 90 },
  { title: '状态', key: 'status', width: 90 },
  { title: '操作', key: 'action', width: 200 },
];
const list = ref<any[]>([]); const loading = ref(false);
const visible = ref(false);
const editing = reactive<any>({});
const botTokens = ref<any[]>([]);

async function load() {
  loading.value = true;
  try {
    const all: any[] = await channelApi.list(false);
    list.value = (all || []).filter((c: any) => !c.isActive);
    botTokens.value = await botApi.tokens();
  } finally { loading.value = false; }
}
function openEditor(r?: any) {
  Object.assign(editing, { id: 0, name: '', username: '', tg_channel_id: '', is_active: false, is_default: false, bot_id: null });
  if (r) {
    editing.id = r.id;
    editing.name = r.name ?? '';
    editing.username = r.username ?? '';
    editing.tg_channel_id = r.tgChannelId ?? '';
    editing.is_active = r.isActive ?? false;
    editing.is_default = r.isDefault ?? false;
    editing.bot_id = r.botId ?? null;
  }
  visible.value = true;
}
async function save() {
  if (!editing.name) { message.error('请填写频道名称'); return; }
  try {
    if (editing.id) await channelApi.update(editing.id, editing);
    else await channelApi.create(editing);
    message.success('已保存'); visible.value = false; load();
  } catch (e: any) { message.error(e.message); }
}
async function remove(id: number) {
  try { await channelApi.remove(id); message.success('已删除'); load(); }
  catch (e: any) { message.error(e.message); }
}
async function check(id: number) {
  try { const r: any = await channelApi.check(id); message.info(r.msg || '检测完成'); }
  catch (e: any) { message.error(e.message); }
}
onMounted(load);
</script>
