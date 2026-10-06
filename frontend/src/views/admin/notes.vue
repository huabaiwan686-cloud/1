<template>
  <div>
    <a-space style="margin-bottom: 16px" wrap>
      <a-input-search v-model:value="keyword" placeholder="搜索标题/正文" @search="load" style="width: 220px" />
      <a-select v-model:value="status" style="width: 130px" @change="load">
        <a-select-option value="all">全部</a-select-option>
        <a-select-option value="draft">草稿</a-select-option>
        <a-select-option value="pending">待审核</a-select-option>
        <a-select-option value="published">已发布</a-select-option>
        <a-select-option value="offline">已下架</a-select-option>
        <a-select-option value="collected">已采集</a-select-option>
      </a-select>
      <a-radio-group v-model:value="view" button-style="solid">
        <a-radio-button value="gallery">画廊</a-radio-button>
        <a-radio-button value="table">表格</a-radio-button>
      </a-radio-group>
      <a-select v-model:value="batchOp" :placeholder="canFull ? '批量操作' : '批量上下架'" style="width: 190px">
        <a-select-option value="publish">上架</a-select-option>
        <a-select-option value="unpublish">下架</a-select-option>
        <template v-if="canFull">
        <a-select-option value="delete">删除</a-select-option>
        <a-select-option value="strip_number_title">删除编号和标题</a-select-option>
        <a-select-option value="find_duplicates">查找重复资料</a-select-option>
        <a-select-option value="clear_channels">清空频道选择</a-select-option>
        </template>
        <a-select-option value="text_replace">文本替换</a-select-option>
        <a-select-option value="remove_suffix">删除后缀</a-select-option>
        <a-select-option value="add_suffix">添加后缀</a-select-option>
        <a-select-option value="replace_fee_line">替换最后一行介绍费</a-select-option>
      </a-select>
      <a-button type="primary" :disabled="!selected.length || !batchOp" @click="runBatch">
        执行 ({{ selected.length }})
      </a-button>
      <a-button v-if="selected.length" @click="selected = []">取消选择</a-button>
    </a-space>

    <a-modal v-model:open="batchParamsVisible" :title="'批量操作参数：' + (batchParamsCfg?.label || '')" @ok="confirmBatchParams">
      <a-form layout="vertical">
        <a-form-item v-for="f in (batchParamsCfg?.fields || [])" :key="f.key" :label="f.label">
          <a-input v-model:value="batchParams[f.key]" :placeholder="f.placeholder" />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 画廊视图 -->
    <div v-if="view === 'gallery'">
      <a-spin :spinning="loading">
        <div v-if="!list.length && !loading" class="empty">
          <inbox-outlined style="font-size: 48px; color: #ccc" />
          <p>暂无资料</p>
        </div>
        <div class="gallery">
          <div v-for="n in list" :key="n.id" class="card" :class="{ selected: selected.includes(n.id) }">
            <div class="img-wrap" @click="openPreview(n)">
              <img :src="thumbUrl(n)" :alt="n.title" loading="lazy" @error="onImgError" />
              <span class="status-badge" :class="n.status">{{ statusText(n.status) }}</span>
              <span class="media-count" v-if="n.media.length > 1">{{ n.media.length }} 张</span>
              <div class="checker" @click.stop>
                <a-checkbox :checked="selected.includes(n.id)" @change="(e: any) => toggleSelect(n.id, e.target.checked)" />
              </div>
              <div class="hover-actions" @click.stop>
                <a-button size="small" @click="openPreview(n)">预览</a-button>
                <a-button size="small" type="primary" v-if="n.status !== 'published'" @click="quickOp(n.id, 'publish')">上架</a-button>
                <a-button size="small" v-if="n.status === 'published'" @click="quickOp(n.id, 'unpublish')">下架</a-button>
              </div>
            </div>
            <div class="card-meta">
              <div class="card-title" :title="n.title">{{ n.title || '无标题' }}</div>
              <div class="card-tags">
                <a-tag v-for="t in (n.tags || []).slice(0, 3)" :key="t" size="small">{{ t }}</a-tag>
              </div>
              <div class="card-time">{{ (n.createdAt || '').slice(0, 16).replace('T', ' ') }}</div>
            </div>
          </div>
        </div>
      </a-spin>
      <a-pagination
        :total="total" :current="page" :page-size="pageSize"
        @change="(p: number) => { page = p; load(); }"
        style="margin-top: 16px; text-align: right"
      />
    </div>

    <!-- 表格视图 -->
    <a-table
      v-else
      :columns="columns"
      :data-source="list"
      :loading="loading"
      row-key="id"
      :row-selection="{ selectedRowKeys: selected, onChange: onSelect }"
      :pagination="{ total, current: page, pageSize, onChange: onPage }"
    />

    <!-- 预览弹窗 -->
    <a-modal v-model:open="previewVisible" :title="previewItem.title || '无标题'" :footer="null" width="720px">
      <a-carousel v-if="previewItem.media && previewItem.media.length" arrows>
        <div v-for="m in previewItem.media" :key="m.id" class="preview-slide">
          <video v-if="m.mediaType === 'video'" :src="m.url" controls style="max-width: 100%; max-height: 60vh" />
          <img v-else :src="m.url" />
        </div>
      </a-carousel>
      <a-descriptions :column="2" size="small" style="margin-top: 12px">
        <a-descriptions-item label="状态">{{ statusText(previewItem.status) }}</a-descriptions-item>
        <a-descriptions-item label="来源">{{ previewItem.source }}</a-descriptions-item>
        <a-descriptions-item label="标签">{{ (previewItem.tags || []).join('、') }}</a-descriptions-item>
        <a-descriptions-item label="创建时间">{{ (previewItem.createdAt || '').slice(0, 16).replace('T', ' ') }}</a-descriptions-item>
      </a-descriptions>
      <pre class="preview-body">{{ previewItem.body }}</pre>
      <a-space style="margin-top: 12px">
        <a-button type="primary" v-if="previewItem.status !== 'published'" @click="quickOp(previewItem.id, 'publish'); previewVisible = false">上架</a-button>
        <a-button v-if="previewItem.status === 'published'" @click="quickOp(previewItem.id, 'unpublish'); previewVisible = false">下架</a-button>
        <a-popconfirm v-if="canFull" title="确认删除？" @confirm="quickOp(previewItem.id, 'delete'); previewVisible = false">
          <a-button danger>删除</a-button>
        </a-popconfirm>
      </a-space>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { message, Modal } from 'ant-design-vue';
import { InboxOutlined } from '@ant-design/icons-vue';
import { noteApi, authApi } from '@/api';

const columns = [
  { title: 'ID', dataIndex: 'id', width: 70 },
  { title: '标题', dataIndex: 'title' },
  { title: '状态', dataIndex: 'status', width: 90 },
  { title: '来源', dataIndex: 'source', width: 90 },
  { title: '创建时间', dataIndex: 'createdAt', width: 180 },
];
const list = ref<any[]>([]);
const total = ref(0);
const loading = ref(false);
const keyword = ref('');
const status = ref('all');
const view = ref('gallery');
const page = ref(1);
const pageSize = ref(24);
const selected = ref<number[]>([]);
const batchOp = ref('');
const previewVisible = ref(false);
const previewItem = ref<any>({});

const STATUS_TEXT: Record<string, string> = {
  draft: '草稿', pending: '待审核', approved: '已通过', published: '已发布',
  offline: '已下架', collected: '已采集', rejected: '已拒绝',
};
function statusText(s: string) { return STATUS_TEXT[s] || s; }
function coverOf(n: any) {
  const show = (n.media || []).find((m: any) => m.kind === 'show') || n.media[0];
  return show ? show.url : '';
}
function thumbUrl(n: any) {
  const url = coverOf(n);
  return url ? `/api/media/thumb?src=${encodeURIComponent(url)}&w=400` : '';
}
function onImgError(e: Event) {
  (e.target as HTMLImageElement).src =
    'data:image/svg+xml,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="400" height="533"><rect width="400" height="533" fill="#f0f0f0"/><text x="200" y="266" text-anchor="middle" fill="#bbb">无图片</text></svg>');
}

async function load() {
  loading.value = true;
  try {
    const data: any = await noteApi.list({
      keyword: keyword.value, status: status.value,
      page: page.value, page_size: pageSize.value,
    });
    list.value = data.list;
    total.value = data.total;
  } finally {
    loading.value = false;
  }
}
function onSelect(keys: number[]) { selected.value = keys; }
function onPage(p: number) { page.value = p; load(); }
function toggleSelect(id: number, checked: boolean) {
  selected.value = checked ? [...selected.value, id] : selected.value.filter((x) => x !== id);
}
function openPreview(n: any) { previewItem.value = n; previewVisible.value = true; }
async function quickOp(id: number, op: string) {
  await noteApi.batch([id], op);
  message.success('已执行');
  selected.value = selected.value.filter((x) => x !== id);
  load();
}
async function runBatch() {
  const needParams: Record<string, { label: string; fields: { key: string; label: string; placeholder?: string }[] }> = {
    text_replace: { label: '文本替换', fields: [
      { key: 'from', label: '查找', placeholder: '要替换的原文' },
      { key: 'to', label: '替换为', placeholder: '新文本' },
    ]},
    remove_suffix: { label: '删除后缀', fields: [
      { key: 'suffix', label: '后缀', placeholder: '结尾匹配才删除' },
    ]},
    add_suffix: { label: '添加后缀', fields: [
      { key: 'suffix', label: '后缀', placeholder: '追加到正文末尾' },
    ]},
    replace_fee_line: { label: '替换最后一行介绍费', fields: [
      { key: 'fee_text', label: '介绍费文本', placeholder: '留空会清空最后一行，请谨慎' },
    ]},
  };
  const cfg = needParams[batchOp.value];
  if (cfg) { openBatchParams(cfg); return; }
  doBatch({});
}
const batchParamsVisible = ref(false);
const batchParamsCfg = ref<any>(null);
const batchParams = reactive<Record<string, string>>({});
function openBatchParams(cfg: any) {
  batchParamsCfg.value = cfg;
  Object.keys(batchParams).forEach(k => delete batchParams[k]);
  cfg.fields.forEach((f: any) => batchParams[f.key] = '');
  batchParamsVisible.value = true;
}
async function confirmBatchParams() {
  batchParamsVisible.value = false;
  doBatch({ ...batchParams });
}
async function doBatch(params: any) {
  Modal.confirm({
    title: `确认对 ${selected.value.length} 条资料执行「${batchOp.value}」？`,
    onOk: async () => {
      const res: any = await noteApi.batch(selected.value, batchOp.value, params);
      if (res.duplicates) {
        Modal.info({ title: '重复资料', content: JSON.stringify(res.duplicates, null, 2) });
      } else {
        message.success(`已处理 ${res.count} 条`);
      }
      selected.value = [];
      batchOp.value = '';
      load();
    },
  });
}

const canFull = ref(false);
onMounted(async () => {
  load();
  try {
    const me: any = await authApi.current();
    canFull.value = !!(me.isAdmin || me.isMember);
  } catch {}
});
</script>

<style scoped>
.gallery {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 16px;
}
.card {
  border: 1px solid #f0f0f0;
  border-radius: 8px;
  overflow: hidden;
  background: #fff;
  transition: box-shadow 0.2s, border-color 0.2s;
  cursor: pointer;
}
.card:hover { box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12); }
.card.selected { border-color: #1677ff; box-shadow: 0 0 0 2px rgba(22, 119, 255, 0.2); }
.img-wrap {
  position: relative;
  aspect-ratio: 3 / 4;
  background: #f5f5f5;
  overflow: hidden;
}
.img-wrap img { width: 100%; height: 100%; object-fit: cover; display: block; }
.status-badge {
  position: absolute; top: 8px; left: 8px;
  font-size: 12px; padding: 2px 8px; border-radius: 4px;
  background: rgba(0, 0, 0, 0.55); color: #fff;
}
.status-badge.published { background: rgba(82, 196, 26, 0.9); }
.status-badge.pending { background: rgba(250, 140, 22, 0.9); }
.media-count {
  position: absolute; bottom: 8px; right: 8px;
  font-size: 12px; padding: 2px 8px; border-radius: 4px;
  background: rgba(0, 0, 0, 0.55); color: #fff;
}
.checker {
  position: absolute; top: 8px; right: 8px;
  opacity: 0; transition: opacity 0.2s;
  background: #fff; border-radius: 4px; padding: 2px;
}
.card:hover .checker, .card.selected .checker { opacity: 1; }
.hover-actions {
  position: absolute; left: 0; right: 0; bottom: 0;
  display: flex; gap: 8px; justify-content: center;
  padding: 8px; background: linear-gradient(transparent, rgba(0, 0, 0, 0.55));
  opacity: 0; transition: opacity 0.2s;
}
.card:hover .hover-actions { opacity: 1; }
.card-meta { padding: 10px 12px; }
.card-title {
  font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.card-tags { margin-top: 6px; min-height: 22px; }
.card-time { margin-top: 4px; font-size: 12px; color: #999; }
.empty { text-align: center; padding: 60px 0; color: #999; }
.preview-slide { text-align: center; background: #000; }
.preview-slide img { max-height: 60vh; max-width: 100%; object-fit: contain; }
.preview-body {
  margin-top: 12px; white-space: pre-wrap; word-break: break-word;
  background: #fafafa; padding: 12px; border-radius: 6px; max-height: 200px; overflow: auto;
}
@media (max-width: 768px) {
  .gallery { grid-template-columns: repeat(2, 1fr); gap: 10px; }
}
</style>
