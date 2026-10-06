<template>
  <div>
    <div class="aq-header">
      <div class="aq-title">消息推送</div>
      <p class="aq-desc">创建消息模板并推送到群组，支持定时推送计划</p>
    </div>
    <a-tabs>
    <a-tab-pane key="tpl" tab="消息模板">
      <a-button type="primary" @click="openTpl()" class="mb-16">新建模板</a-button>
      <a-table :columns="tplCols" :data-source="templates" row-key="id" :loading="loading">
        <template #bodyCell="{ column, record }">
          <a-space v-if="column.key === 'action'" class="table-actions">
            <a @click="pushTpl(record.id)">推送</a>
            <a-popconfirm title="确认删除？" @confirm="delTpl(record.id)"><a>删除</a></a-popconfirm>
          </a-space>
        </template>
      </a-table>
      <a-modal class="modal-form" v-model:open="tplVisible" title="消息模板" @ok="saveTpl">
        <a-form :model="tplEditing" layout="vertical">
          <a-form-item label="名称"><a-input v-model:value="tplEditing.name" /></a-form-item>
          <a-form-item label="内容"><a-textarea v-model:value="tplEditing.content" :rows="4" /></a-form-item>
          <a-form-item label="媒体（图片/视频混合，最多 10 个）">
            <a-upload v-model:file-list="tplMediaList" :before-upload="() => false" multiple list-type="picture-card">
              <div>+ 上传</div>
            </a-upload>
          </a-form-item>
        </a-form>
      </a-modal>
    </a-tab-pane>
    <a-tab-pane key="plan" tab="推送计划">
      <a-button type="primary" @click="openPlan()" class="mb-16">新建计划</a-button>
      <a-table :columns="planCols" :data-source="plans" row-key="id">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'tpl'">{{ tplName(record.templateId) }}</template>
          <a-popconfirm v-if="column.key === 'action'" title="确认删除？" @confirm="delPlan(record.id)">
            <a>删除</a>
          </a-popconfirm>
        </template>
      </a-table>
      <a-modal class="modal-form" v-model:open="planVisible" title="推送计划" @ok="savePlan">
        <a-alert type="error" show-icon class="mb-16"
          message="风险提示：请勿使用上架账号进行群发，频繁群发可能导致账号受限" />
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
            <a-space class="mb-8">
              <a-button size="small" @click="refreshDialogs" :loading="dlgLoading">刷新缓存</a-button>
              <span class="hint">{{ dlgCachedAt ? '缓存时间：' + dlgCachedAt : '尚未缓存，请点刷新' }}</span>
            </a-space>
            <a-select v-model:value="planEditing.target_groups" mode="multiple" placeholder="从缓存的会话中选择"
              style="width: 100%" :options="dlgOptions" />
          </a-form-item>
          <a-form-item label="执行间隔"><a-input-number v-model:value="planEditing.interval_days" :min="1" /> 天</a-form-item>
          <a-form-item label="或每 X 小时执行一次（>0 时优先按小时）"><a-input-number v-model:value="planEditing.interval_hours" :min="0" /> 小时</a-form-item>
          <a-form-item label="群组之间发送间隔"><a-input-number v-model:value="planEditing.multi_interval_seconds" :min="0" /> 秒</a-form-item>
          <a-form-item label="执行时间点（逗号分隔 HH:mm）"><a-input v-model:value="planEditing.times_str" placeholder="09:00,21:00" style="width: 100%" /></a-form-item>
        </a-form>
      </a-modal>
    </a-tab-pane>
  </a-tabs>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import { message } from 'ant-design-vue';
import { messageApi, tgApi, mediaApi } from '@/api';

const tplCols = [
  { title: 'ID', dataIndex: 'id', width: 60 },
  { title: '代码', dataIndex: 'code', width: 130 },
  { title: '名称', dataIndex: 'name' },
  { title: '媒体', dataIndex: 'mediaCount', width: 80 },
  { title: '操作', key: 'action', width: 140 },
];
const planCols = [
  { title: 'ID', dataIndex: 'id', width: 60 },
  { title: '模板', key: 'tpl', width: 160 },
  { title: '间隔', dataIndex: 'intervalDays', width: 80 },
  { title: '操作', key: 'action', width: 80 },
];
function tplName(id: number) {
  const t = templates.value.find((x: any) => x.id === id);
  return t ? `${t.name} (${t.code})` : '#' + id;
}
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
  } catch (e: any) { message.error(e.message || '加载失败'); }
  finally { loading.value = false; }
}
async function loadDialogs() {
  dlgOptions.value = []; dlgCachedAt.value = '';
  if (!planEditing.account_id) return;
  try {
    const r: any = await messageApi.dialogs(planEditing.account_id);
    dlgOptions.value = (r.list || []).map((d: any) => ({
      value: d.chatId, label: `${d.title}${d.username ? ' (@' + d.username + ')' : ''} [${d.kind}]`,
    }));
    dlgCachedAt.value = r.cachedAt ? r.cachedAt.slice(0, 16).replace('T', ' ') : '';
  } catch (e: any) { message.error(e.message || '加载会话失败'); }
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
function openTpl() { Object.assign(tplEditing, { name: '', content: '' }); tplMediaList.value = []; tplVisible.value = true; }
const tplMediaList = ref<any[]>([]);
async function saveTpl() {
  const media: any[] = [];
  try {
    for (const f of tplMediaList.value.slice(0, 10)) {
      let url = f.url;
      if (!url && f.originFileObj) {
        const res: any = await mediaApi.uploadMaterial(f.originFileObj, 'template');
        url = res.url; f.url = url;
      }
      if (url) {
        const isVideo = /\.(mp4|mov|avi|mkv)$/i.test(f.name || url);
        media.push({ url, type: isVideo ? 'video' : 'image' });
      }
    }
    await messageApi.createTemplate({ name: tplEditing.name, content: tplEditing.content, media });
    message.success('已创建'); tplVisible.value = false; load();
  } catch (e: any) { message.error(e.message || '保存失败'); }
}
async function delTpl(id: number) {
  try { await messageApi.deleteTemplate(id); message.success('已删除'); load(); }
  catch (e: any) { message.error(e.message || '删除失败'); }
}
async function pushTpl(id: number) {
  try { const r: any = await messageApi.pushTemplate(id); message.success(r.msg || '推送完成'); }
  catch (e: any) { message.error(e.message || '推送失败'); }
}
function openPlan() {
  Object.assign(planEditing, { template_id: null, account_id: null, target_groups: [], interval_days: 1, interval_hours: 0, multi_interval_seconds: 0, times_str: '' });
  dlgOptions.value = []; dlgCachedAt.value = '';
  planVisible.value = true;
}
async function savePlan() {
  try {
    await messageApi.createPlan({
      account_id: planEditing.account_id,
      template_id: planEditing.template_id,
      target_groups: planEditing.target_groups || [],
      interval_days: planEditing.interval_days,
      interval_hours: planEditing.interval_hours || 0,
      multi_interval_seconds: planEditing.multi_interval_seconds || 0,
      times: planEditing.times_str.split(',').map((s: string) => s.trim()).filter(Boolean),
    });
    message.success('已创建'); planVisible.value = false; load();
  } catch (e: any) { message.error(e.message || '保存失败'); }
}
async function delPlan(id: number) {
  try { await messageApi.deletePlan(id); message.success('已删除'); load(); }
  catch (e: any) { message.error(e.message || '删除失败'); }
}
onMounted(load);
</script>
