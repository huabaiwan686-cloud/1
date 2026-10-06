<template>
  <a-tabs>
    <a-tab-pane key="tpl" tab="消息模板">
      <a-button type="primary" @click="openTpl()" style="margin-bottom: 16px">新建模板</a-button>
      <a-table :columns="tplCols" :data-source="templates" row-key="id" :loading="loading">
        <template #bodyCell="{ column, record }">
          <a-space v-if="column.key === 'action'">
            <a @click="pushTpl(record.id)">推送</a>
            <a-popconfirm title="确认删除？" @confirm="delTpl(record.id)"><a>删除</a></a-popconfirm>
          </a-space>
        </template>
      </a-table>
      <a-modal v-model:open="tplVisible" title="消息模板" @ok="saveTpl">
        <a-form :model="tplEditing" layout="vertical">
          <a-form-item label="名称"><a-input v-model:value="tplEditing.name" /></a-form-item>
          <a-form-item label="内容"><a-textarea v-model:value="tplEditing.content" :rows="4" /></a-form-item>
        </a-form>
      </a-modal>
    </a-tab-pane>
    <a-tab-pane key="plan" tab="推送计划">
      <a-button type="primary" @click="openPlan()" style="margin-bottom: 16px">新建计划</a-button>
      <a-table :columns="planCols" :data-source="plans" row-key="id">
        <template #bodyCell="{ column, record }">
          <a-popconfirm v-if="column.key === 'action'" title="确认删除？" @confirm="delPlan(record.id)">
            <a>删除</a>
          </a-popconfirm>
        </template>
      </a-table>
      <a-modal v-model:open="planVisible" title="推送计划" @ok="savePlan">
        <a-form :model="planEditing" layout="vertical">
          <a-form-item label="模板">
            <a-select v-model:value="planEditing.template_id" style="width: 100%">
              <a-select-option v-for="t in templates" :key="t.id" :value="t.id">{{ t.name }} ({{ t.code }})</a-select-option>
            </a-select>
          </a-form-item>
          <a-form-item label="目标群组（逗号分隔）"><a-input v-model:value="planEditing.target_groups_str" /></a-form-item>
          <a-form-item label="执行间隔"><a-input-number v-model:value="planEditing.interval_days" :min="1" /> 天</a-form-item>
          <a-form-item label="执行时间点（逗号分隔 HH:mm）"><a-input v-model:value="planEditing.times_str" placeholder="09:00,21:00" /></a-form-item>
        </a-form>
      </a-modal>
    </a-tab-pane>
  </a-tabs>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import { message } from 'ant-design-vue';
import { messageApi } from '@/api';

const tplCols = [
  { title: 'ID', dataIndex: 'id', width: 60 },
  { title: '代码', dataIndex: 'code', width: 130 },
  { title: '名称', dataIndex: 'name' },
  { title: '媒体', dataIndex: 'mediaCount', width: 80 },
  { title: '操作', key: 'action', width: 140 },
];
const planCols = [
  { title: 'ID', dataIndex: 'id', width: 60 },
  { title: '模板', dataIndex: 'templateId', width: 80 },
  { title: '间隔', dataIndex: 'intervalDays', width: 80 },
  { title: '操作', key: 'action', width: 80 },
];
const templates = ref<any[]>([]); const plans = ref<any[]>([]);
const loading = ref(false);
const tplVisible = ref(false); const planVisible = ref(false);
const tplEditing = reactive<any>({}); const planEditing = reactive<any>({});

async function load() {
  loading.value = true;
  try {
    templates.value = await messageApi.templates();
    plans.value = await messageApi.plans();
  } finally { loading.value = false; }
}
function openTpl() { Object.assign(tplEditing, { name: '', content: '' }); tplVisible.value = true; }
async function saveTpl() {
  await messageApi.createTemplate(tplEditing);
  message.success('已创建'); tplVisible.value = false; load();
}
async function delTpl(id: number) { await messageApi.deleteTemplate(id); message.success('已删除'); load(); }
async function pushTpl(id: number) { await messageApi.pushTemplate(id); message.success('推送任务已创建'); }
function openPlan() {
  Object.assign(planEditing, { template_id: null, target_groups_str: '', interval_days: 1, times_str: '' });
  planVisible.value = true;
}
async function savePlan() {
  await messageApi.createPlan({
    template_id: planEditing.template_id,
    target_groups: planEditing.target_groups_str.split(',').map((s: string) => s.trim()).filter(Boolean),
    interval_days: planEditing.interval_days,
    times: planEditing.times_str.split(',').map((s: string) => s.trim()).filter(Boolean),
  });
  message.success('已创建'); planVisible.value = false; load();
}
async function delPlan(id: number) { await messageApi.deletePlan(id); message.success('已删除'); load(); }
onMounted(load);
</script>
