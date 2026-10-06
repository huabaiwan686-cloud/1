<template>
  <div>
    <a-space style="margin-bottom: 16px">
      <a-input-search v-model:value="keyword" placeholder="搜索标题/正文" @search="load" style="width: 240px" />
      <a-select v-model:value="status" style="width: 140px" @change="load">
        <a-select-option value="all">全部</a-select-option>
        <a-select-option value="draft">草稿</a-select-option>
        <a-select-option value="pending">待审核</a-select-option>
        <a-select-option value="published">已发布</a-select-option>
        <a-select-option value="offline">已下架</a-select-option>
        <a-select-option value="collected">已采集</a-select-option>
      </a-select>
      <a-select v-model:value="batchOp" placeholder="批量操作 (VIP)" style="width: 200px">
        <a-select-option value="publish">上架</a-select-option>
        <a-select-option value="unpublish">下架</a-select-option>
        <a-select-option value="delete">删除</a-select-option>
        <a-select-option value="strip_number_title">删除编号和标题</a-select-option>
        <a-select-option value="find_duplicates">查找重复资料</a-select-option>
        <a-select-option value="clear_channels">清空频道选择</a-select-option>
        <a-select-option value="text_replace">文本替换</a-select-option>
        <a-select-option value="remove_suffix">删除后缀</a-select-option>
        <a-select-option value="add_suffix">添加后缀</a-select-option>
        <a-select-option value="replace_fee_line">替换最后一行介绍费</a-select-option>
      </a-select>
      <a-button type="primary" :disabled="!selected.length || !batchOp" @click="runBatch">
        执行 ({{ selected.length }})
      </a-button>
    </a-space>

    <a-table
      :columns="columns"
      :data-source="list"
      :loading="loading"
      row-key="id"
      :row-selection="{ selectedRowKeys: selected, onChange: onSelect }"
      :pagination="{ total, current: page, pageSize, onChange: onPage }"
    />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { message, Modal } from 'ant-design-vue';
import { noteApi } from '@/api';

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
const page = ref(1);
const pageSize = ref(20);
const selected = ref<number[]>([]);
const batchOp = ref('');

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

async function runBatch() {
  Modal.confirm({
    title: `确认对 ${selected.value.length} 条资料执行「${batchOp.value}」？`,
    onOk: async () => {
      const res: any = await noteApi.batch(selected.value, batchOp.value);
      if (res.duplicates) {
        Modal.info({ title: '重复资料', content: JSON.stringify(res.duplicates, null, 2) });
      } else {
        message.success(`已处理 ${res.count} 条`);
      }
      selected.value = [];
      load();
    },
  });
}

onMounted(load);
</script>
