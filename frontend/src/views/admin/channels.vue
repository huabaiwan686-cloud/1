<template>
  <div>
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
import { channelApi } from '@/api';

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

async function load() {
  loading.value = true;
  try {
    list.value = await channelApi.list(filter.value === 'all' ? undefined : filter.value);
  } finally { loading.value = false; }
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
async function pushAll(id: number) { await channelApi.pushAll(id); message.success('全量推送任务已创建'); }
onMounted(load);
</script>
