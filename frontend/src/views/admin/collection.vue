<template>
  <div>
    <a-button type="primary" @click="openEditor()" style="margin-bottom: 16px">新建采集规则</a-button>
    <a-table :columns="columns" :data-source="rules" row-key="id" :loading="loading">
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'action'">
          <a-space>
            <a @click="openEditor(record)">编辑</a>
            <a-popconfirm title="确认删除？" @confirm="remove(record.id)"><a>删除</a></a-popconfirm>
          </a-space>
        </template>
        <template v-else-if="column.key === 'flags'">
          <a-tag v-if="record.globalApply" color="blue">全局</a-tag>
          <a-tag v-if="record.needReview" color="orange">需审核</a-tag>
          <a-tag v-if="record.dedupEnabled" color="green">去重</a-tag>
        </template>
      </template>
    </a-table>

    <a-modal v-model:open="visible" title="采集规则" @ok="save" width="720px">
      <a-form :model="editing" layout="vertical">
        <a-form-item label="规则名称"><a-input v-model:value="editing.name" /></a-form-item>
        <a-form-item label="目标频道 ID（逗号分隔）">
          <a-input v-model:value="editing.target_channels_str" placeholder="1,2,3" />
        </a-form-item>
        <a-space>
          <a-checkbox v-model:checked="editing.global_apply">全局应用</a-checkbox>
          <a-checkbox v-model:checked="editing.need_review">采集后需审核</a-checkbox>
        </a-space>
        <a-divider>文案处理</a-divider>
        <a-checkbox v-model:checked="editing.prefix_enabled">文案前附加</a-checkbox>
        <a-textarea v-model:value="editing.prefix_text" :rows="2" />
        <a-checkbox v-model:checked="editing.suffix_enabled">文案后附加</a-checkbox>
        <a-textarea v-model:value="editing.suffix_text" :rows="2" />
        <a-checkbox v-model:checked="editing.clean_identifiers">清理编号和介绍费标识</a-checkbox>
        <a-divider>去重</a-divider>
        <a-space>
          <a-checkbox v-model:checked="editing.dedup_enabled">图文去重</a-checkbox>
          <a-checkbox v-model:checked="editing.dedup_window_enabled">去重时间窗</a-checkbox>
          <a-input-number v-model:value="editing.dedup_days" :min="1" /> 天
        </a-space>
        <a-divider>屏蔽</a-divider>
        <a-space>
          <a-checkbox v-model:checked="editing.block_links">屏蔽链接</a-checkbox>
          <a-checkbox v-model:checked="editing.block_usernames">屏蔽用户名</a-checkbox>
          <a-checkbox v-model:checked="editing.block_plain_text">屏蔽纯文本</a-checkbox>
        </a-space>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import { message } from 'ant-design-vue';
import { collectApi } from '@/api';

const columns = [
  { title: 'ID', dataIndex: 'id', width: 60 },
  { title: '名称', dataIndex: 'name' },
  { title: '策略', key: 'flags' },
  { title: '操作', key: 'action', width: 140 },
];
const rules = ref<any[]>([]);
const loading = ref(false);
const visible = ref(false);
const editing = reactive<any>({});

async function load() {
  loading.value = true;
  try { rules.value = await collectApi.rules(); } finally { loading.value = false; }
}
function openEditor(r?: any) {
  Object.assign(editing, {
    name: '', target_channels_str: '', global_apply: false, need_review: true,
    prefix_enabled: false, prefix_text: '', suffix_enabled: false, suffix_text: '',
    clean_identifiers: false, dedup_enabled: true, dedup_window_enabled: false,
    dedup_days: 30, block_links: true, block_usernames: true, block_plain_text: true,
    ...(r ? { ...r, target_channels_str: (r.targetChannels || []).join(',') } : {}),
  });
  visible.value = true;
}
async function save() {
  const payload = {
    ...editing,
    target_channels: editing.target_channels_str.split(',').map((s: string) => parseInt(s.trim())).filter(Boolean),
  };
  delete payload.target_channels_str; delete payload.targetChannels;
  try {
    if (editing.id) await collectApi.updateRule(editing.id, payload);
    else await collectApi.createRule(payload);
    message.success('已保存');
    visible.value = false; load();
  } catch (e: any) { message.error(e.message); }
}
async function remove(id: number) {
  await collectApi.deleteRule(id); message.success('已删除'); load();
}
onMounted(load);
</script>
