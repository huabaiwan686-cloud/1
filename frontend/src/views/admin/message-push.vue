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
          <a-form-item label="执行协议号">
            <a-select v-model:value="planEditing.account_id" placeholder="选择 TG 协议号" style="width: 100%" @change="loadDialogs">
              <a-select-option v-for="a in tgAccounts" :key="a.id" :value="a.id">{{ a.phone }}（{{ a.name }}）</a-select-option>
            </a-select>
          </a-form-item>
          <a-form-item label="目标群组">
            <a-space style="margin-bottom: 8px">
              <a-button size="small" @click="refreshDialogs" :loading="dlgLoading">刷新缓存</a-button>
              <span style="color: #999; font-size: 12px">{{ dlgCachedAt ? '缓存时间：' + dlgCachedAt : '尚未缓存，请点刷新' }}</span>
            </a-space>
            <a-select v-model:value="planEditing.target_groups" mode="multiple" placeholder="从缓存的会话中选择"
              style="width: 100%" :options="dlgOptions" />
          </a-form-item>
          <a-form-item label="执行间隔"><a-input-number v-model:value="planEditing.interval_days" :min="1" /> 天</a-form-item>
          <a-form-item label="执行时间点（逗号分隔 HH:mm）"><a-input v-model:value="planEditing.times_str" placeholder="09:00,21:00" style="width: 100%" /></a-form-item>
        </a-form>
      </a-modal>
    </a-tab-pane>
  </a-tabs>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import { message } from 'ant-design-vue';
import { messageApi, tgApi } from '@/api';

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
const tgAccounts = ref<any[]>([]);
const dlgOptions = ref<any[]>([]);
const dlgCachedAt = ref('');
const dlgLoading = ref(false);

async function load() {
  loading.value = true;
  try {
    templates.value = await messageApi.templates();
    plans.value = await messageApi.plans();
    tgAccounts.value = await tgApi.accounts();
  } finally { loading.value = false; }
}
async function loadDialogs() {
  dlgOptions.value = []; dlgCachedAt.value = '';
  if (!planEditing.account_id) return;
  const r: any = await messageApi.dialogs(planEditing.account_id);
  dlgOptions.value = r.list.map((d: any) => ({
    value: d.chatId, label: `${d.title}${d.username ? ' (@' + d.username + ')' : ''} [${d.kind}]`,
  }));
  dlgCachedAt.value = r.cachedAt ? r.cachedAt.slice(0, 16).replace('T', ' ') : '';
}
async function refreshDialogs() {
  if (!planEditing.account_id) { message.error('请先选择执行协议号'); return; }
  dlgLoading.value = true;
  try {
    const r: any = await messageApi.refreshDialogs(planEditing.account_id);
    message.success(r.msg || '已刷新');
    await loadDialogs();
  } catch (e: any) { message.error(e.message); } finally { dlgLoading.value = false; }
}
function openTpl() { Object.assign(tplEditing, { name: '', content: '' }); tplVisible.value = true; }
async function saveTpl() {
  await messageApi.createTemplate(tplEditing);
  message.success('已创建'); tplVisible.value = false; load();
}
async function delTpl(id: number) { await messageApi.deleteTemplate(id); message.success('已删除'); load(); }
async function pushTpl(id: number) { await messageApi.pushTemplate(id); message.success('推送任务已创建'); }
function openPlan() {
  Object.assign(planEditing, { template_id: null, account_id: null, target_groups: [], interval_days: 1, times_str: '' });
  dlgOptions.value = []; dlgCachedAt.value = '';
  planVisible.value = true;
}
async function savePlan() {
  await messageApi.createPlan({
    account_id: planEditing.account_id,
    template_id: planEditing.template_id,
    target_groups: planEditing.target_groups || [],
    interval_days: planEditing.interval_days,
    times: planEditing.times_str.split(',').map((s: string) => s.trim()).filter(Boolean),
  });
  message.success('已创建'); planVisible.value = false; load();
}
async function delPlan(id: number) { await messageApi.deletePlan(id); message.success('已删除'); load(); }
onMounted(load);
</script>
