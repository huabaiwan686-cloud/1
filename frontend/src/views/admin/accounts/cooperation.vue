<template>
  <div>
    <a-space style="margin-bottom: 16px">
      <a-input v-model:value="importText" placeholder="批量导入，每行一个 @xxxbot" style="width: 300px" />
      <a-button @click="doImport">导入</a-button>
    </a-space>
    <a-table :columns="columns" :data-source="list" row-key="id" :loading="loading">
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'action'">
          <a-space>
            <a @click="review(record.id, true)">通过</a>
            <a @click="review(record.id, false)">拒绝</a>
          </a-space>
        </template>
      </template>
    </a-table>
    <a-divider>合作配置</a-divider>
    <a-form :model="cfg" layout="inline">
      <a-form-item label="通知方式">
        <a-select v-model:value="cfg.notify_mode" style="width: 160px">
          <a-select-option value="two_way_group">双向群</a-select-option>
          <a-select-option value="bot_dm">Bot 私聊</a-select-option>
        </a-select>
      </a-form-item>
      <a-form-item><a-checkbox v-model:checked="cfg.need_review">需要审核</a-checkbox></a-form-item>
      <a-form-item><a-button type="primary" @click="saveCfg">保存配置</a-button></a-form-item>
    </a-form>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import { message } from 'ant-design-vue';
import { socialApi } from '@/api';

const columns = [
  { title: 'ID', dataIndex: 'id', width: 60 },
  { title: '机器人', dataIndex: 'botUsername' },
  { title: '审核状态', dataIndex: 'reviewStatus', width: 110 },
  { title: '操作', key: 'action', width: 140 },
];
const list = ref<any[]>([]); const loading = ref(false);
const importText = ref('');
const cfg = reactive({ two_way_bot_id: null as any, notify_mode: 'two_way_group', channel_ids: [] as number[], need_review: true, enabled: true });

async function load() {
  loading.value = true;
  try { list.value = await socialApi.cooperations(); } finally { loading.value = false; }
}
async function doImport() {
  const names = importText.value.split('\n').map(s => s.trim()).filter(Boolean);
  const r: any = await socialApi.importCoops(names);
  message.success(`已导入 ${r.imported} 个`); importText.value = ''; load();
}
async function review(id: number, approve: boolean) {
  await socialApi.reviewCoop(id, approve); message.success('已审核'); load();
}
async function saveCfg() {
  await socialApi.saveCoopConfig({ ...cfg }); message.success('合作配置已保存');
}
onMounted(load);
</script>
