<template>
  <div>
    <a-card title="全局抠图模式" style="margin-bottom: 16px">
      <a-space>
        <a-switch v-model:checked="gm.enabled" @change="saveGm" />
        <span style="color: #666">开启后，所有发往频道的资料按所选背景自动抠图后发送；服务器只保留原图，处理图不留存，每次循环重新处理</span>
      </a-space>
      <div style="margin-top: 12px">
        <a-select v-model:value="gm.background_id" placeholder="选择抠图背景素材（先选背景再开开关）" style="width: 320px" @change="saveGm">
          <a-select-option v-for="m in materials" :key="m.id" :value="m.id">{{ m.name }}</a-select-option>
        </a-select>
        <span style="color: #999; margin-left: 12px">每次上架/循环推送时实时处理，按次扣额度（重复图不重复扣）</span>
      </div>
    </a-card>
    <a-space style="margin-bottom: 16px">
      <a-button type="primary" @click="openEditor()">添加频道</a-button>
      <a-radio-group v-model:value="filter" @change="load">
        <a-radio-button value="all">全部</a-radio-button>
        <a-radio-button :value="true">上架中</a-radio-button>
        <a-radio-button :value="false">已下架</a-radio-button>
      </a-radio-group>
    </a-space>
    <a-table :columns="columns" :data-source="list" row-key="id" :loading="loading">
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'status'">
          <a-tag :color="record.isActive ? 'green' : 'default'">{{ record.isActive ? '上架' : '下架' }}</a-tag>
        </template>
        <template v-else-if="column.key === 'action'">
          <a-space>
            <a @click="openEditor(record)">编辑</a>
            <a @click="check(record.id)">检测</a>
            <a @click="pushAll(record.id)">全量推送</a>
            <a-popconfirm title="确认删除？" @confirm="remove(record.id)"><a>删除</a></a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>
    <a-modal v-model:open="visible" title="频道配置" @ok="save">
      <a-form :model="editing" layout="vertical">
        <a-form-item label="频道名称"><a-input v-model:value="editing.name" /></a-form-item>
        <a-form-item label="用户名"><a-input v-model:value="editing.username" placeholder="@xxx" /></a-form-item>
        <a-form-item label="防扫图模式">
          <a-select v-model:value="editing.anti_scan_mode">
            <a-select-option value="original">原图</a-select-option>
            <a-select-option value="replace_bg">替换背景</a-select-option>
            <a-select-option value="blur_bg">背景虚化（人像模式）</a-select-option>
            <a-select-option value="light_perturb">轻量随机扰动</a-select-option>
          </a-select>
        </a-form-item>
        <a-space>
          <a-checkbox v-model:checked="editing.is_active">上架</a-checkbox>
          <a-checkbox v-model:checked="editing.is_default">默认选中</a-checkbox>
        </a-space>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import { message } from 'ant-design-vue';
import { channelApi, mediaApi } from '@/api';

const columns = [
  { title: 'ID', dataIndex: 'id', width: 60 },
  { title: '名称', dataIndex: 'name' },
  { title: '用户名', dataIndex: 'username' },
  { title: '防扫图', dataIndex: 'antiScanMode', width: 120 },
  { title: '状态', key: 'status', width: 80 },
  { title: '操作', key: 'action', width: 260 },
];
const list = ref<any[]>([]); const loading = ref(false);
const filter = ref<any>('all'); const visible = ref(false);
const editing = reactive<any>({});
const gm = reactive<any>({ enabled: false, background_id: null });
const materials = ref<any[]>([]);

async function load() {
  loading.value = true;
  try {
    list.value = await channelApi.list(filter.value === 'all' ? undefined : filter.value);
    const g: any = await mediaApi.mattingGlobal();
    gm.enabled = g.enabled; gm.background_id = g.backgroundId;
    materials.value = await mediaApi.materials();
  } finally { loading.value = false; }
}
async function saveGm() {
  if (gm.enabled && !gm.background_id) {
    message.warning('请先选择抠图背景素材，再开启全局抠图');
    gm.enabled = false;
    return;
  }
  try {
    await mediaApi.setMattingGlobal({ enabled: gm.enabled, background_id: gm.background_id });
    message.success('全局抠图模式已' + (gm.enabled ? '开启' : '关闭'));
  } catch (e: any) { message.error(e.message); load(); }
}
function openEditor(r?: any) {
  Object.assign(editing, { name: '', username: '', anti_scan_mode: 'original', is_active: true, is_default: false, ...r });
  visible.value = true;
}
async function save() {
  try {
    if (editing.id) await channelApi.update(editing.id, editing);
    else await channelApi.create(editing);
    message.success('已保存'); visible.value = false; load();
  } catch (e: any) { message.error(e.message); }
}
async function remove(id: number) { await channelApi.remove(id); message.success('已删除'); load(); }
async function check(id: number) { const r: any = await channelApi.check(id); message.info(r.msg); }
async function pushAll(id: number) { const r: any = await channelApi.pushAll(id); message.success(r.msg || '全量推送完成'); }
onMounted(load);
</script>
