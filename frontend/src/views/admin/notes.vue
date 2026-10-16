<template>
  <div class="page">
    <div class="page-title">资料库</div>
    <div class="page-subtitle">管理已采集的资料，支持搜索与筛选</div>
    <a-card class="filter-card" :bordered="true" style="margin-top: 16px">
      <div class="toolbar">
        <a-input-search v-model:value="keyword" placeholder="搜索标题 / 正文关键词" @search="onSearch" style="width: 240px" allow-clear />
        <a-select v-model:value="status" style="width: 120px" @change="onSearch" placeholder="状态">
          <a-select-option value="">全部状态</a-select-option>
          <a-select-option value="draft">草稿</a-select-option>
          <a-select-option value="pending">待审核</a-select-option>
          <a-select-option value="published">已发布</a-select-option>
          <a-select-option value="offline">已下架</a-select-option>
        </a-select>
        <a-select v-model:value="channelId" style="width: 160px" @change="onSearch" placeholder="频道" allow-clear>
          <a-select-option value="">全部频道</a-select-option>
          <a-select-option v-for="c in channels" :key="c.id" :value="c.id">{{ c.name }}</a-select-option>
        </a-select>
        <a-button @click="load">刷新</a-button>
        <div style="flex: 1" />
        <a-radio-group v-model:value="viewMode" button-style="solid" size="small">
          <a-radio-button value="card">卡片</a-radio-button>
          <a-radio-button value="table">表格</a-radio-button>
        </a-radio-group>
        <a-dropdown v-if="selected.length">
          <template #overlay>
            <a-menu @click="runBatch">
              <a-menu-item key="publish">上架所选</a-menu-item>
              <a-menu-item key="unpublish">下架所选</a-menu-item>
              <a-menu-item key="delete" danger>删除所选</a-menu-item>
            </a-menu>
          </template>
          <a-button type="primary">批量 ({{ selected.length }}) <down-outlined /></a-button>
        </a-dropdown>
      </div>
    </a-card>

    <a-card :bordered="false" class="list-card">
      <a-spin :spinning="loading">
        <a-empty v-if="!list.length && !loading" description="暂无笔记" />
        <div v-else-if="viewMode === 'card'" class="note-grid">
          <div v-for="n in list" :key="n.id" class="note-card" :class="{ selected: selected.includes(n.id) }">
            <div class="note-cover" v-if="n.media && n.media.length">
              <div v-if="isVideo(n.media[0])" style="width: 1cm; height: 1cm; background: #f0f0f0; display: flex; align-items: center; justify-content: center; font-size: 12px; border-radius: 2px;">🎬</div>
              <img v-else :src="n.media[0].url" alt="" />
              <span class="note-status-badge" :class="'status-' + n.status">{{ statusText(n.status) }}</span>
              <a-checkbox class="note-check" :checked="selected.includes(n.id)" @change="(e) => toggleSelect(n.id, e.target.checked)" />
            </div>
            <div class="note-header" v-else>
              <a-checkbox :checked="selected.includes(n.id)" @change="(e) => toggleSelect(n.id, e.target.checked)" />
              <span class="note-id">#{{ n.id }}</span>
              <a-tag :color="statusColor(n.status)" size="small">{{ statusText(n.status) }}</a-tag>
              <div style="flex: 1" />
              <a-button type="link" size="small" @click="preview(n)">预览</a-button>
            </div>
            <div class="note-title">{{ n.title || '(无标题)' }}</div>
            <div class="note-preview">{{ (n.body || '').slice(0, 60) }}</div>
            <div class="note-meta">
              <span v-if="n.media && n.media.length">{{ n.media.length }} 张图</span>
              <span v-if="Array.isArray(n.tags) && n.tags.length" class="note-tags">{{ n.tags.slice(0, 2).join(' · ') }}</span>
            </div>
            <div class="note-footer">
              <span class="note-time">{{ fmtTime(n.createdAt) }}</span>
              <div class="note-actions">
                <a-button size="small" type="link" @click="preview(n)">预览</a-button>
                <a-button size="small" type="link" @click="openEdit(n)">编辑</a-button>
                <a-button size="small" type="link" @click="quickOp(n.id, 'publish')" v-if="n.status !== 'published'">上架</a-button>
                <a-button size="small" type="link" @click="quickOp(n.id, 'unpublish')" v-if="n.status === 'published'">下架</a-button>
                <a-popconfirm title="确认删除该笔记？" @confirm="deleteOne(n.id)">
                  <a-button size="small" type="link" danger>删除</a-button>
                </a-popconfirm>
              </div>
            </div>
          </div>
        </div>

        <a-table v-else :data-source="list" :pagination="false" row-key="id" size="small" :row-selection="{ selectedRowKeys: selected, onChange: onTableSelect }">
          <a-table-column title="ID" data-index="id" width="60" />
          <a-table-column title="标题" data-index="title" ellipsis>
            <template #default="{ record }"><a @click="preview(record)">{{ record.title || '(无标题)' }}</a></template>
          </a-table-column>
          <a-table-column title="状态" width="90">
            <template #default="{ record }"><a-tag :color="statusColor(record.status)" size="small">{{ statusText(record.status) }}</a-tag></template>
          </a-table-column>
          <a-table-column title="图片" width="70">
            <template #default="{ record }">{{ (record.media || []).length }}</template>
          </a-table-column>
          <a-table-column title="创建时间" width="150">
            <template #default="{ record }">{{ fmtTime(record.createdAt) }}</template>
          </a-table-column>
          <a-table-column title="操作" width="200">
            <template #default="{ record }">
              <a-button size="small" type="link" @click="preview(record)">预览</a-button>
              <a-button size="small" type="link" @click="openEdit(record)">编辑</a-button>
              <a-button size="small" type="link" @click="quickOp(record.id, 'publish')" v-if="record.status !== 'published'">上架</a-button>
              <a-button size="small" type="link" @click="quickOp(record.id, 'unpublish')" v-if="record.status === 'published'">下架</a-button>
              <a-popconfirm title="确认删除该笔记？" @confirm="deleteOne(record.id)">
                <a-button size="small" type="link" danger>删除</a-button>
              </a-popconfirm>
            </template>
          </a-table-column>
        </a-table>

        <div class="pagination-wrap" v-if="total > pageSize">
          <a-pagination :total="total" :current="page" :page-size="pageSize" @change="(p) => { page = p; load(); }" show-less-items size="small" />
        </div>
      </a-spin>
    </a-card>

    <a-modal v-model:open="previewVisible" title="笔记预览" :footer="null" width="600px">
      <div v-if="previewNote">
        <h3>{{ previewNote.title || '(无标题)' }}</h3>
        <div style="white-space: pre-wrap; margin: 12px 0;">{{ previewNote.body }}</div>
        <div v-if="previewNote.media && previewNote.media.length" style="display: flex; flex-wrap: wrap; gap: 8px;">
          <div v-for="(m, i) in previewNote.media" :key="i" style="text-align: center;">
            <div v-if="isVideo(m)" style="width: 120px; height: 120px; background: #f0f0f0; display: flex; align-items: center; justify-content: center; font-size: 24px; border-radius: 4px;">🎬</div>
            <img v-else :src="m.url" style="width: 120px; height: 120px; object-fit: cover; border-radius: 4px;" />
          </div>
        </div>
      </div>
    </a-modal>

    <a-modal v-model:open="editVisible" title="编辑笔记" :footer="null" width="600px">
      <a-form :label-col="{ span: 4 }" :wrapper-col="{ span: 20 }">
        <a-form-item label="标题">
          <a-input v-model:value="editForm.title" placeholder="笔记标题" />
        </a-form-item>
        <a-form-item label="正文">
          <a-textarea v-model:value="editForm.body" :rows="6" placeholder="笔记正文" />
        </a-form-item>
        <a-form-item label="标签">
          <a-input v-model:value="editForm.tagsText" placeholder="多个标签用 、 隔开" />
        </a-form-item>
        <a-form-item :wrapper-col="{ offset: 4 }">
          <a-button type="primary" @click="saveEdit" :loading="editSaving">保存</a-button>
        </a-form-item>
      </a-form>
    </a-modal>

  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { message } from 'ant-design-vue';
import { DownOutlined, InboxOutlined } from '@ant-design/icons-vue';
import { noteApi, channelApi, mediaApi } from '@/api';

const list = ref<any[]>([]);
const channels = ref<any[]>([]);
const total = ref(0);
const loading = ref(false);
const keyword = ref('');
const status = ref('');
const channelId = ref('');
const page = ref(1);
const pageSize = ref(24);
const selected = ref<number[]>([]);
const viewMode = ref<'card' | 'table'>('card');
const previewVisible = ref(false);
const previewNote = ref<any>(null);



const STATUS_TEXT: Record<string, string> = { draft: '草稿', pending: '待审核', approved: '已通过', published: '已发布', offline: '已下架', collected: '已采集', rejected: '已拒绝' };
const STATUS_COLOR: Record<string, string> = { draft: 'default', pending: 'orange', approved: 'blue', published: 'green', offline: 'red', collected: 'purple', rejected: 'red' };
function statusText(s: string) { return STATUS_TEXT[s] || s || '未知'; }
function statusColor(s: string) { return STATUS_COLOR[s] || 'default'; }
function isVideo(m: any) {
  if (!m) return false;
  if (m.media_type === 'video' || m.mediaType === 'video' || m.kind === 'verify') return true;
  const url = m.url || '';
  return url.toLowerCase().endsWith('.mp4') || url.toLowerCase().endsWith('.mov') || url.toLowerCase().endsWith('.webm');
}
function fmtTime(t: string) { return t ? t.slice(0, 19).replace('T', ' ') : ''; }

async function load() {
  loading.value = true;
  try {
    const data: any = await noteApi.list({ keyword: keyword.value || undefined, status: status.value || undefined, channel_id: channelId.value || undefined, page: page.value, page_size: pageSize.value });
    list.value = data.list || [];
    total.value = data.total || 0;
  } catch (e: any) { message.error(e.message || '加载失败'); }
  finally { loading.value = false; }
}
async function loadChannels() {
  try { const data: any = await channelApi.list(); channels.value = data.list || data || []; } catch { /* ignore */ }
}
function onSearch() { page.value = 1; load(); }
function toggleSelect(id: number, checked: boolean) {
  if (checked) { if (!selected.value.includes(id)) selected.value.push(id); }
  else selected.value = selected.value.filter(x => x !== id);
}
function onTableSelect(keys: any[]) { selected.value = keys as number[]; }
function preview(n: any) { previewNote.value = n; previewVisible.value = true; }
async function quickOp(id: number, op: string) {
  try { await noteApi.batch([id], op); message.success('已执行'); selected.value = selected.value.filter(x => x !== id); load(); }
  catch (e: any) { message.error(e.message || '操作失败'); }
}
async function runBatch(e: any) {
  const op = e.key;
  if (!selected.value.length) return;
  try { await noteApi.batch(selected.value, op); message.success('批量操作成功'); selected.value = []; load(); }
  catch (err: any) { message.error(err.message || '批量操作失败'); }
}
const editVisible = ref(false);
const editSaving = ref(false);
const editForm = ref({ id: 0, title: '', body: '', tagsText: '' });
function openEdit(n: any) {
  editForm.value = { id: n.id, title: n.title || '', body: n.body || '', tagsText: (Array.isArray(n.tags) ? n.tags : []).join('、') };
  editVisible.value = true;
}
async function saveEdit() {
  editSaving.value = true;
  try {
    const tags = editForm.value.tagsText.split('、').map((s: string) => s.trim()).filter(Boolean);
    await noteApi.update(editForm.value.id, { title: editForm.value.title, body: editForm.value.body, tags });
    message.success('已保存');
    editVisible.value = false;
    load();
  } catch (e: any) { message.error(e.message || '保存失败'); }
  finally { editSaving.value = false; }
}
async function deleteOne(id: number) {
  try { await noteApi.remove(id); message.success('已删除'); load(); }
  catch (e: any) { message.error(e.message || '删除失败'); }
}

onMounted(() => { load(); loadChannels(); });
</script>

<style scoped>
.toolbar-card { margin-bottom: 12px; }
.filter-card { margin-bottom: 16px; }
.toolbar { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.list-card { min-height: 400px; overflow: hidden; }
.note-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 14px; min-width: 0; }
.note-card { border: 1px solid #f0f0f0; border-radius: 8px; padding: 14px; background: #fff; transition: all 0.2s; min-width: 0; overflow: hidden; }
.note-cover { width: 1cm; height: 1cm; overflow: hidden; flex-shrink: 0; }
.note-cover img { width: 1cm; height: 1cm; object-fit: cover; }
.note-card:hover { border-color: #d9d9d9; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
.note-card.selected { border-color: #1677ff; background: #e6f4ff; }
.note-header { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.note-id { color: #999; font-size: 12px; }
.note-title { font-weight: 500; font-size: 14px; margin-bottom: 6px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.note-preview { color: #666; font-size: 13px; line-height: 1.5; height: 40px; overflow: hidden; margin-bottom: 8px; word-break: break-all; }
.note-meta { color: #999; font-size: 12px; margin-bottom: 8px; }
.note-footer { display: flex; justify-content: space-between; align-items: center; }
.note-time { color: #bbb; font-size: 12px; }
.note-actions { display: flex; gap: 4px; }
.pagination-wrap { margin-top: 18px; text-align: right; }
</style>
