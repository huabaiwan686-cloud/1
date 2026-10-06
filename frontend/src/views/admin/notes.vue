<template>
  <div class="page">
    <div class="page-title">笔记管理</div>
    <div class="page-subtitle">创建、发布、下架你的内容笔记</div>
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
        <a-button @click="showDedup">查找重复</a-button>
        <a-button @click="imgSearchVisible = true">以图搜图</a-button>
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
            <div class="note-cover" v-if="n.images && n.images.length">
              <img :src="n.images[0]" alt="" />
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
            <div class="note-preview">{{ (n.content || '').slice(0, 60) }}</div>
            <div class="note-meta">
              <span v-if="n.images && n.images.length">{{ n.images.length }} 张图</span>
              <span v-if="n.tags && n.tags.length" class="note-tags">{{ (n.tags || []).slice(0, 2).join(' · ') }}</span>
            </div>
            <div class="note-footer">
              <span class="note-time">{{ fmtTime(n.createdAt) }}</span>
              <div class="note-actions">
                <a-button size="small" type="link" @click="preview(n)">预览</a-button>
                <a-button size="small" type="link" @click="quickOp(n.id, 'publish')" v-if="n.status !== 'published'">上架</a-button>
                <a-button size="small" type="link" @click="quickOp(n.id, 'unpublish')" v-if="n.status === 'published'">下架</a-button>
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
            <template #default="{ record }">{{ (record.images || []).length }}</template>
          </a-table-column>
          <a-table-column title="创建时间" width="150">
            <template #default="{ record }">{{ fmtTime(record.createdAt) }}</template>
          </a-table-column>
          <a-table-column title="操作" width="140">
            <template #default="{ record }">
              <a-button size="small" type="link" @click="preview(record)">预览</a-button>
              <a-button size="small" type="link" @click="quickOp(record.id, 'publish')" v-if="record.status !== 'published'">上架</a-button>
              <a-button size="small" type="link" @click="quickOp(record.id, 'unpublish')" v-if="record.status === 'published'">下架</a-button>
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
        <div style="white-space: pre-wrap; margin: 12px 0;">{{ previewNote.content }}</div>
        <div v-if="previewNote.images && previewNote.images.length" style="display: flex; flex-wrap: wrap; gap: 8px;">
          <img v-for="(img, i) in previewNote.images" :key="i" :src="img" style="width: 120px; height: 120px; object-fit: cover; border-radius: 4px;" />
        </div>
      </div>
    </a-modal>

    <a-modal v-model:open="dedupVisible" title="重复图片" :footer="null" width="700px">
      <a-spin :spinning="dedupLoading">
        <a-empty v-if="!dedupGroups.length && !dedupLoading" description="未发现重复" />
        <div v-for="(g, gi) in dedupGroups" :key="gi" style="margin-bottom: 16px; border: 1px solid #f0f0f0; border-radius: 8px; padding: 12px;">
          <div style="margin-bottom: 8px; color: #999;">第 {{ gi + 1 }} 组（{{ g.length }} 张相似）</div>
          <div style="display: flex; flex-wrap: wrap; gap: 8px;">
            <div v-for="(item, ii) in g" :key="ii" style="text-align: center;">
              <img :src="item.url" style="width: 100px; height: 100px; object-fit: cover; border-radius: 4px;" />
              <div style="font-size: 12px; color: #999;">笔记 #{{ item.note_id }}</div>
            </div>
          </div>
        </div>
      </a-spin>
    </a-modal>
    <a-modal v-model:open="imgSearchVisible" title="以图搜图" :footer="null" width="700px">
      <a-upload-dragger :before-upload="doImageSearch" :show-upload-list="false" accept="image/*">
        <p class="ant-upload-drag-icon"><inbox-outlined /></p>
        <p class="ant-upload-text">点击上传或拖拽图片到此处，也可直接粘贴截图 (Ctrl+V)</p>
      </a-upload-dragger>
      <a-spin :spinning="imgSearchLoading" style="margin-top: 16px; width: 100%;">
        <div v-if="imgSearchResults.length" style="display: flex; flex-wrap: wrap; gap: 12px; margin-top: 12px;">
          <div v-for="(r, i) in imgSearchResults" :key="i" style="text-align: center; cursor: pointer;" @click="preview({id: r.note_id})">
            <img :src="r.media_url" style="width: 120px; height: 120px; object-fit: cover; border-radius: 8px;" />
            <div style="font-size: 12px;">{{ r.note_title || ('笔记 #' + r.note_id) }}</div>
            <div style="font-size: 11px; color: #999;">相似度 {{ 100 - r.distance }}%</div>
          </div>
        </div>
        <a-empty v-if="imgSearched && !imgSearchResults.length && !imgSearchLoading" description="未找到相似图片" style="margin-top: 12px;" />
      </a-spin>
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
const dedupVisible = ref(false);
const imgSearchVisible = ref(false);
const imgSearchLoading = ref(false);
const imgSearchResults = ref<any[]>([]);
const imgSearched = ref(false);

async function doImageSearch(file: File) {
  imgSearchLoading.value = true; imgSearched.value = false; imgSearchResults.value = [];
  try {
    const fd = new FormData();
    fd.append('file', file);
    const data: any = await mediaApi.imageSearch(fd);
    imgSearchResults.value = data.items || [];
    imgSearched.value = true;
  } catch (e: any) { message.error(e.message || '搜索失败'); }
  finally { imgSearchLoading.value = false; }
  return false; // 阻止自动上传
}
const dedupLoading = ref(false);
const dedupGroups = ref<any[]>([]);

const STATUS_TEXT: Record<string, string> = { draft: '草稿', pending: '待审核', approved: '已通过', published: '已发布', offline: '已下架', collected: '已采集', rejected: '已拒绝' };
const STATUS_COLOR: Record<string, string> = { draft: 'default', pending: 'orange', approved: 'blue', published: 'green', offline: 'red', collected: 'purple', rejected: 'red' };
function statusText(s: string) { return STATUS_TEXT[s] || s || '未知'; }
function statusColor(s: string) { return STATUS_COLOR[s] || 'default'; }
function fmtTime(t: string) { return t ? t.slice(0, 16).replace('T', ' ') : ''; }

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
async function showDedup() {
  dedupVisible.value = true; dedupLoading.value = true; dedupGroups.value = [];
  try { const data: any = await mediaApi.dedupScanNotes({}); dedupGroups.value = data.groups || data.list || []; }
  catch (e: any) { message.error(e.message || '扫描失败'); }
  finally { dedupLoading.value = false; }
}
onMounted(() => { load(); loadChannels(); });
</script>

<style scoped>
.toolbar-card { margin-bottom: 12px; }
.filter-card { margin-bottom: 16px; }
.toolbar { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.list-card { min-height: 400px; }
.note-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 14px; }
.note-card { border: 1px solid #f0f0f0; border-radius: 8px; padding: 14px; background: #fff; transition: all 0.2s; }
.note-card:hover { border-color: #d9d9d9; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
.note-card.selected { border-color: #1890ff; background: #f6fbff; }
.note-header { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.note-id { color: #999; font-size: 12px; }
.note-title { font-weight: 500; font-size: 14px; margin-bottom: 6px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.note-preview { color: #666; font-size: 13px; line-height: 1.5; height: 40px; overflow: hidden; margin-bottom: 8px; }
.note-meta { color: #999; font-size: 12px; margin-bottom: 8px; }
.note-footer { display: flex; justify-content: space-between; align-items: center; }
.note-time { color: #bbb; font-size: 12px; }
.note-actions { display: flex; gap: 4px; }
.pagination-wrap { margin-top: 18px; text-align: right; }
</style>
