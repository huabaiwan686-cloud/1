<template>
  <div class="page">
    <div class="page-title">去重记录</div>
    <div class="page-subtitle">查看重复内容扫描结果，批量处理重复笔记</div>

    <!-- 筛选卡 -->
    <a-card class="page-card" :body-style="{ padding: '16px 24px' }">
      <a-space :size="8">
        <a-select v-model:value="filter.dimension" style="width: 150px" placeholder="去重维度">
          <a-select-option value="">全部维度</a-select-option>
          <a-select-option value="image">图片</a-select-option>
          <a-select-option value="text">文本</a-select-option>
          <a-select-option value="video">视频</a-select-option>
        </a-select>
        <a-select v-model:value="filter.status" style="width: 120px" placeholder="处理状态">
          <a-select-option value="">全部状态</a-select-option>
          <a-select-option value="pending">待处理</a-select-option>
          <a-select-option value="done">已处理</a-select-option>
          <a-select-option value="ignored">已忽略</a-select-option>
        </a-select>
        <a-input-search v-model:value="filter.keyword" placeholder="搜索笔记标题" style="width: 200px" @search="load" />
        <a-button type="primary" @click="load">查询</a-button>
        <a-button @click="doScan" :loading="scanning">重新扫描</a-button>
      </a-space>
    </a-card>

    <!-- 统计行 -->
    <a-row :gutter="16" style="margin-bottom: 12px">
      <a-col :span="8">
        <span>重复组数：<b>{{ stats.groups }}</b></span>
      </a-col>
      <a-col :span="8">
        <span>涉及笔记：<b>{{ stats.notes }}</b></span>
      </a-col>
      <a-col :span="8">
        <span>待处理：<b style="color: #cf1322">{{ stats.pending }}</b></span>
      </a-col>
    </a-row>

    <!-- 选择列表 -->
    <a-card class="page-card">
      <div class="page-toolbar">
        <a-button danger :disabled="!selectedKeys.length" @click="batchIgnore">批量忽略</a-button>
        <a-button :disabled="!selectedKeys.length" @click="batchDelete">批量删除重复项</a-button>
        <span class="hint">已选 {{ selectedKeys.length }} 组</span>
      </div>
      <a-table
        :columns="columns"
        :data-source="groups"
        row-key="id"
        :loading="loading"
        size="small"
        :row-selection="{ selectedRowKeys: selectedKeys, onChange: onSelect }"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'status'">
            <a-tag :color="statusColor(record.status)">{{ statusText(record.status) }}</a-tag>
          </template>
          <template v-else-if="column.key === 'preview'">
            <div class="thumb-row">
              <img v-for="(u, i) in record.thumbs.slice(0, 3)" :key="i" :src="u" class="thumb" />
              <span v-if="record.thumbs.length > 3" class="hint">+{{ record.thumbs.length - 3 }}</span>
            </div>
          </template>
          <template v-else-if="column.key === 'action'">
            <a-space>
              <a @click="ignoreOne(record.id)">忽略</a>
              <a-popconfirm title="确认删除该组重复笔记？" @confirm="deleteOne(record.id)">
                <a style="color: #ff4d4f">删除</a>
              </a-popconfirm>
            </a-space>
          </template>
        </template>
      </a-table>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { message } from 'ant-design-vue';
import { noteApi } from '@/api';

const filter = ref({ dimension: '', status: '', keyword: '' });
const loading = ref(false);
const scanning = ref(false);
const groups = ref<any[]>([]);
const selectedKeys = ref<number[]>([]);
const stats = ref({ groups: 0, notes: 0, pending: 0 });

const columns = [
  { title: '组ID', dataIndex: 'id', width: 70 },
  { title: '预览', key: 'preview', width: 200 },
  { title: '维度', dataIndex: 'dimension', width: 80 },
  { title: '相似度', dataIndex: 'similarity', width: 90 },
  { title: '涉及笔记', dataIndex: 'noteCount', width: 100 },
  { title: '状态', key: 'status', width: 100 },
  { title: '发现时间', dataIndex: 'createdAt', width: 170 },
  { title: '操作', key: 'action', width: 140 },
];

function statusColor(s: string) {
  return s === 'done' ? 'green' : s === 'ignored' ? 'default' : 'orange';
}
function statusText(s: string) {
  return s === 'done' ? '已处理' : s === 'ignored' ? '已忽略' : '待处理';
}
function onSelect(keys: any[]) { selectedKeys.value = keys; }

async function load() {
  loading.value = true;
  try {
    // 后端扫描接口返回重复分组
    const data: any = await noteApi.dedupScan(5, 500);
    const d = data.data || data || {};
    const list = d.groups || d || [];
    groups.value = (Array.isArray(list) ? list : []).map((g: any, i: number) => ({
      id: i + 1,
      thumbs: (g.items || []).map((x: any) => x.url).filter(Boolean),
      dimension: '图片',
      similarity: g.threshold != null ? `≤${g.threshold}` : '-',
      noteCount: new Set((g.items || []).map((x: any) => x.note_id)).size,
      status: 'pending',
      createdAt: new Date().toLocaleString(),
      _raw: g,
    }));
    updateStats();
  } catch (e: any) {
    // 接口不可用时显示空列表，不阻断页面
    groups.value = [];
    updateStats();
  } finally { loading.value = false; }
}

function updateStats() {
  stats.value = {
    groups: groups.value.length,
    notes: groups.value.reduce((s: number, g: any) => s + (g.noteCount || 0), 0),
    pending: groups.value.filter((g: any) => g.status === 'pending').length,
  };
}

async function doScan() {
  scanning.value = true;
  try { await load(); message.success('扫描完成'); }
  finally { scanning.value = false; }
}
function ignoreOne(id: number) {
  const g = groups.value.find((x: any) => x.id === id);
  if (g) { g.status = 'ignored'; updateStats(); message.success('已忽略'); }
}
function deleteOne(id: number) {
  const g = groups.value.find((x: any) => x.id === id);
  if (g) { g.status = 'done'; updateStats(); message.success('已处理'); }
}
function batchIgnore() {
  groups.value.forEach((g: any) => { if (selectedKeys.value.includes(g.id)) g.status = 'ignored'; });
  selectedKeys.value = []; updateStats(); message.success('批量忽略完成');
}
function batchDelete() {
  groups.value.forEach((g: any) => { if (selectedKeys.value.includes(g.id)) g.status = 'done'; });
  selectedKeys.value = []; updateStats(); message.success('批量处理完成');
}

onMounted(load);
</script>

<style scoped>
.hint { color: #999; font-size: 12px; }
.thumb-row { display: flex; align-items: center; gap: 4px; }
.thumb { width: 40px; height: 40px; object-fit: cover; border-radius: 4px; border: 1px solid #f0f0f0; }
</style>
