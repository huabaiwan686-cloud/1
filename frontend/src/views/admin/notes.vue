<template>
  <div class="notes-page">
    <!-- 顶部工具栏 -->
    <a-card class="toolbar-card" :bordered="false">
      <div class="toolbar">
        <a-input-search
          v-model:value="keyword"
          placeholder="搜索标题 / 正文关键词"
          @search="load"
          style="width: 260px"
          allow-clear
        />
        <a-select v-model:value="status" style="width: 120px" @change="load">
          <a-select-option value="all">全部状态</a-select-option>
          <a-select-option value="draft">草稿</a-select-option>
          <a-select-option value="pending">待审核</a-select-option>
          <a-select-option value="published">已发布</a-select-option>
          <a-select-option value="offline">已下架</a-select-option>
        </a-select>
        <a-button @click="load">刷新</a-button>
        <div style="flex: 1" />
        <a-dropdown v-if="selected.length">
          <template #overlay>
            <a-menu @click="runBatch">
              <a-menu-item key="publish">上架所选</a-menu-item>
              <a-menu-item key="unpublish">下架所选</a-menu-item>
              <a-menu-item key="delete" danger>删除所选</a-menu-item>
            </a-menu>
          </template>
          <a-button type="primary">
            批量操作 ({{ selected.length }}) <down-outlined />
          </a-button>
        </a-dropdown>
      </div>
    </a-card>

    <!-- 内容区 -->
    <a-card :bordered="false" class="list-card">
      <a-spin :spinning="loading">
        <a-empty v-if="!list.length && !loading" description="暂无笔记，点击上方刷新试试" />
        <div v-else class="note-grid">
          <div v-for="n in list" :key="n.id" class="note-card" :class="{ selected: selected.includes(n.id) }">
            <div class="note-header">
              <a-checkbox :checked="selected.includes(n.id)" @change="(e: any) => toggleSelect(n.id, e.target.checked)" />
              <span class="note-id">#{{ n.id }}</span>
              <a-tag :color="statusColor(n.status)">{{ statusText(n.status) }}</a-tag>
            </div>
            <div class="note-title">{{ n.title || '(无标题)' }}</div>
            <div class="note-preview">{{ (n.content || '').slice(0, 80) }}</div>
            <div class="note-footer">
              <span class="note-time">{{ formatTime(n.createdAt) }}</span>
              <div class="note-actions">
                <a-button size="small" type="link" @click="quickOp(n.id, 'publish')" v-if="n.status !== 'published'">上架</a-button>
                <a-button size="small" type="link" @click="quickOp(n.id, 'unpublish')" v-if="n.status === 'published'">下架</a-button>
              </div>
            </div>
          </div>
        </div>
        <div class="pagination-wrap" v-if="total > pageSize">
          <a-pagination
            :total="total" :current="page" :page-size="pageSize"
            @change="(p: number) => { page = p; load(); }"
            show-less-items
          />
        </div>
      </a-spin>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { message } from 'ant-design-vue';
import { DownOutlined } from '@ant-design/icons-vue';
import { noteApi } from '@/api';

const list = ref<any[]>([]);
const total = ref(0);
const loading = ref(false);
const keyword = ref('');
const status = ref('all');
const page = ref(1);
const pageSize = ref(24);
const selected = ref<number[]>([]);

const STATUS_TEXT: Record<string, string> = {
  draft: '草稿', pending: '待审核', approved: '已通过',
  published: '已发布', offline: '已下架', collected: '已采集', rejected: '已拒绝',
};
const STATUS_COLOR: Record<string, string> = {
  draft: 'default', pending: 'orange', approved: 'blue',
  published: 'green', offline: 'red', collected: 'purple', rejected: 'red',
};
function statusText(s: string) { return STATUS_TEXT[s] || s; }
function statusColor(s: string) { return STATUS_COLOR[s] || 'default'; }
function formatTime(t: string) {
  if (!t) return '';
  return t.slice(0, 16).replace('T', ' ');
}

async function load() {
  loading.value = true;
  try {
    const data: any = await noteApi.list({
      keyword: keyword.value, status: status.value,
      page: page.value, page_size: pageSize.value,
    });
    list.value = data.list || [];
    total.value = data.total || 0;
  } catch (e: any) {
    message.error(e.message || '加载失败');
  } finally {
    loading.value = false;
  }
}

function toggleSelect(id: number, checked: boolean) {
  if (checked) selected.value.push(id);
  else selected.value = selected.value.filter(x => x !== id);
}

async function quickOp(id: number, op: string) {
  try {
    await noteApi.batch([id], op);
    message.success('已执行');
    selected.value = selected.value.filter(x => x !== id);
    load();
  } catch (e: any) {
    message.error(e.message || '操作失败');
  }
}

async function runBatch(e: any) {
  const op = e.key;
  if (!selected.value.length) return;
  try {
    await noteApi.batch(selected.value, op);
    message.success(`批量${op === 'publish' ? '上架' : op === 'unpublish' ? '下架' : '删除'}成功`);
    selected.value = [];
    load();
  } catch (err: any) {
    message.error(err.message || '批量操作失败');
  }
}

onMounted(() => { load(); });
</script>

<style scoped>
.notes-page { padding: 4px; }
.toolbar-card { margin-bottom: 12px; }
.toolbar { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.list-card { min-height: 400px; }
.note-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 14px;
}
.note-card {
  border: 1px solid #f0f0f0;
  border-radius: 8px;
  padding: 14px;
  background: #fff;
  transition: all 0.2s;
  cursor: default;
}
.note-card:hover { border-color: #d9d9d9; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
.note-card.selected { border-color: #1890ff; background: #f6fbff; }
.note-header { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.note-id { color: #999; font-size: 12px; }
.note-title { font-weight: 500; font-size: 14px; margin-bottom: 6px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.note-preview { color: #666; font-size: 13px; line-height: 1.5; height: 40px; overflow: hidden; margin-bottom: 10px; }
.note-footer { display: flex; justify-content: space-between; align-items: center; }
.note-time { color: #bbb; font-size: 12px; }
.note-actions { display: flex; gap: 4px; }
.pagination-wrap { margin-top: 18px; text-align: right; }
</style>
