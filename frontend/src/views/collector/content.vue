<template>
  <div class="profiles-page">
    <div class="page-header">
      <div>
        <h2 class="page-title">资料库</h2>
        <p class="page-desc">管理已采集的资料，支持搜索、筛选与去重</p>
      </div>
      <div class="toolbar">
        <a-button>上传资料</a-button>
      </div>
    </div>
    <a-card class="table-card" :bordered="true">
      <template #extra>
        <a-space style="gap: 8px">
          <a-select v-model:value="status" style="width: 120px" @change="load">
            <a-select-option value="">全部状态</a-select-option>
            <a-select-option value="draft">草稿</a-select-option>
            <a-select-option value="pending">待审核</a-select-option>
            <a-select-option value="published">已上架</a-select-option>
            <a-select-option value="offline">已下架</a-select-option>
          </a-select>
          <a-input-search v-model:value="keyword" placeholder="搜索标题/正文" class="search-input" @search="load" />
        </a-space>
      </template>
      <a-table :columns="columns" :data-source="list" row-key="id" :loading="loading"
               :pagination="{ total, current: page, pageSize, onChange: onPage }"
               :scroll="{ x: 1300 }">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'status'">
            <a-tag :color="statusColor(record.status)">{{ record.statusText }}</a-tag>
          </template>
          <template v-if="column.key === 'action'">
            <a-space>
              <a @click="viewDetail(record)">查看</a>
              <a v-if="record.status === 'published'" @click="unpublishNote(record.id)">下架</a>
              <a-popconfirm title="确认删除？" @confirm="removeNote(record.id)"><a>删除</a></a-popconfirm>
            </a-space>
          </template>
        </template>
      </a-table>
    </a-card>
    <a-modal v-model:open="detailVisible" title="资料详情" :footer="null" width="640px">
      <a-descriptions :column="1" size="small" bordered>
        <a-descriptions-item label="标题">{{ detail.title }}</a-descriptions-item>
        <a-descriptions-item label="状态">{{ detail.statusText }}</a-descriptions-item>
        <a-descriptions-item label="标签">{{ (detail.tags || []).join('、') }}</a-descriptions-item>
        <a-descriptions-item label="正文"><pre style="white-space:pre-wrap;margin:0">{{ detail.body }}</pre></a-descriptions-item>
      </a-descriptions>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { message } from 'ant-design-vue';
import { collectorApi, noteApi } from '@/api';

// meiren 资料库 13 列
const columns = [
  { title: 'ID', dataIndex: 'id', width: 60, className: 'hide-mobile' },
  { title: '标题', dataIndex: 'title', width: 180 },
  { title: '首图', key: 'cover', width: 80 },
  { title: '媒体数', dataIndex: 'mediaCount', width: 70 },
  { title: '标签', dataIndex: 'tagsText', width: 140 },
  { title: '城市', dataIndex: 'cityName', width: 90 },
  { title: '状态', key: 'status', width: 90 },
  { title: '来源', dataIndex: 'source', width: 90 },
  { title: '采集时间', dataIndex: 'createdAt', width: 160 },
  { title: '上架时间', dataIndex: 'publishedAt', width: 160 },
  { title: '发布次数', dataIndex: 'publishCount', width: 80 },
  { title: '备注', dataIndex: 'serviceRemark', width: 120 },
  { title: '操作', key: 'action', width: 120, fixed: 'right' },
];
const list = ref<any[]>([]);
const loading = ref(false);
const status = ref('');
const keyword = ref('');
const page = ref(1);
const pageSize = 20;
const total = ref(0);
const detailVisible = ref(false);
const detail = ref<any>({});

const COLORS: any = { draft: 'default', pending: 'orange', published: 'green', offline: 'red' };
function statusColor(s: string) { return COLORS[s] || 'default'; }

async function load() {
  loading.value = true;
  try {
    const r: any = await collectorApi.myNotes({
      status: status.value || undefined,
      keyword: keyword.value || undefined,
      page: page.value,
      page_size: pageSize,
    });
    list.value = (r.list || []).map((n: any) => ({
      ...n,
      tagsText: (n.tags || []).join('、'),
      mediaCount: (n.media || []).length,
    }));
    total.value = r.total || 0;
  } catch (e: any) { message.error(e.message || '加载失败'); }
  finally { loading.value = false; }
}
function onPage(p: number) { page.value = p; load(); }
function viewDetail(record: any) { detail.value = record; detailVisible.value = true; }
async function removeNote(id: number) {
  try {
    await noteApi.remove(id);
    message.success('已删除');
    load();
  } catch (e: any) { message.error(e.message || '删除失败'); }
}
async function unpublishNote(id: number) {
  try {
    await noteApi.unpublish(id);
    message.success('已下架');
    load();
  } catch (e: any) { message.error(e.message || '下架失败'); }
}
onMounted(load);
</script>
