<template>
  <div class="page">
    <div class="page-title">关键词监控</div>
    <div class="page-subtitle">配置监听关键词，系统自动监控目标群组消息</div>

    <!-- 纵向表单卡：监控配置 -->
    <a-card title="监控配置" class="page-card">
      <a-form layout="vertical">
        <a-form-item label="启用关键词监控">
          <a-switch v-model:checked="cfg.enabled" />
          <div class="hint">开启后，worker 自动监听目标群组的新消息</div>
        </a-form-item>
        <a-form-item label="监听关键词（逗号分隔）">
          <a-input v-model:value="cfg.keywords_str" placeholder="北京,上海,广州" />
          <div class="hint">群组消息命中关键词时触发推送</div>
        </a-form-item>
        <a-form-item label="关键词→城市映射（每行一组）">
          <a-textarea v-model:value="cfg.map_str" :rows="3" placeholder="京妞=北京&#10;魔都=上海" />
          <div class="hint">自定义关键词与城市的对应关系</div>
        </a-form-item>
        <a-form-item label="触发冷却（小时）">
          <a-input-number v-model:value="cfg.cooldown_hours" :min="1" :max="72" style="width: 200px" />
          <div class="hint">同一用户同一城市触发后，冷却多久才再次推送</div>
        </a-form-item>
        <a-form-item>
          <a-button type="primary" @click="saveCfg" :loading="saving">保存配置</a-button>
        </a-form-item>
      </a-form>
    </a-card>

    <!-- 小尺寸表：关键词状态 -->
    <a-card title="关键词状态" class="page-card">
      <a-table :columns="kwColumns" :data-source="kwList" row-key="keyword" size="small" :pagination="false" :loading="kwLoading">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'status'">
            <a-tag :color="record.enabled ? 'green' : 'default'">{{ record.enabled ? '监控中' : '已停用' }}</a-tag>
          </template>
          <template v-else-if="column.key === 'action'">
            <a-switch :checked="record.enabled" size="small" @change="(v: boolean) => toggleKw(record.keyword, v)" />
          </template>
        </template>
      </a-table>
    </a-card>

    <!-- 监听计划 -->
    <a-card title="监听计划" class="page-card">
      <div class="page-toolbar">
        <a-button type="primary" @click="openEditor()">新建监听计划</a-button>
      </div>
      <a-table :columns="columns" :data-source="list" row-key="id" :loading="loading" size="small">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'enabled'">
            <a-switch :checked="record.enabled" @change="(v: boolean) => togglePlan(record.id, v)" />
          </template>
          <template v-else-if="column.key === 'account'">
            <span>{{ accountName(record.accountId) }}</span>
          </template>
          <template v-else-if="column.key === 'action'">
            <a-popconfirm title="确认删除？" @confirm="remove(record.id)"><a>删除</a></a-popconfirm>
          </template>
        </template>
      </a-table>
    </a-card>

    <a-modal v-model:open="visible" title="关键字监听" @ok="save" width="520">
      <a-form :model="editing" layout="vertical">
        <a-form-item label="计划名称"><a-input v-model:value="editing.name" /></a-form-item>
        <a-form-item label="监听协议号（必填，否则计划不会执行）">
          <a-select v-model:value="editing.account_id" placeholder="选择已登录的 TG 协议号" style="width: 100%">
            <a-select-option v-for="a in tgAccounts" :key="a.id" :value="a.id">{{ a.phone }}（{{ a.name }}）</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="监听目标（逗号分隔）"><a-input v-model:value="editing.targets_str" placeholder="@group1,@channel1" /></a-form-item>
        <a-form-item label="关键词（逗号分隔）"><a-input v-model:value="editing.keywords_str" placeholder="北京,上海" /></a-form-item>
        <a-form-item label="自定义关键词→城市（每行一组）">
          <a-textarea v-model:value="editing.map_str" :rows="3" placeholder="京妞=北京&#10;魔都=上海" />
        </a-form-item>
      </a-form>
    </a-modal>

    <h3 class="section-title">命中记录</h3>
    <a-table :columns="hitColumns" :data-source="hits" row-key="id" :loading="hitsLoading" :pagination="{ pageSize: 20 }" size="small" />
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import { message } from 'ant-design-vue';
import { listenApi, tgApi } from '@/api';

// 监控配置（纵向表单）
const cfg = reactive({ enabled: true, keywords_str: '', map_str: '', cooldown_hours: 3 });
const saving = ref(false);

// 关键词状态表
const kwColumns = [
  { title: '关键词', dataIndex: 'keyword' },
  { title: '映射城市', dataIndex: 'city' },
  { title: '状态', key: 'status', width: 100 },
  { title: '操作', key: 'action', width: 100 },
];
const kwList = ref<any[]>([]);
const kwLoading = ref(false);

function refreshKwList() {
  kwLoading.value = true;
  try {
    const kws = (cfg.keywords_str || '').split(',').map((s: string) => s.trim()).filter(Boolean);
    const map: Record<string, string> = {};
    (cfg.map_str || '').split('\n').forEach((line: string) => {
      const i = line.indexOf('=');
      if (i > 0) map[line.slice(0, i).trim()] = line.slice(i + 1).trim();
    });
    kwList.value = kws.map((k: string) => ({ keyword: k, city: map[k] || '-', enabled: cfg.enabled }));
  } finally { kwLoading.value = false; }
}
function toggleKw(keyword: string, v: boolean) {
  const item = kwList.value.find((x: any) => x.keyword === keyword);
  if (item) item.enabled = v;
}
async function saveCfg() {
  saving.value = true;
  try { refreshKwList(); message.success('监控配置已保存'); }
  finally { saving.value = false; }
}

// 监听计划
const columns = [
  { title: 'ID', dataIndex: 'id', width: 60 },
  { title: '名称', dataIndex: 'name' },
  { title: '协议号', key: 'account', width: 170 },
  { title: '启用', key: 'enabled', width: 80 },
  { title: '操作', key: 'action', width: 80 },
];
const list = ref<any[]>([]); const loading = ref(false);
const visible = ref(false); const editing = reactive<any>({});
const tgAccounts = ref<any[]>([]);

function accountName(id: number) {
  const a = tgAccounts.value.find((x: any) => x.id === id);
  return a ? `${a.phone}（${a.name}）` : (id ? '#' + id : '未选择');
}
const hits = ref<any[]>([]); const hitsLoading = ref(false);
const hitColumns = [
  { title: '时间', dataIndex: 'createdAt', width: 170 },
  { title: '触发用户', dataIndex: 'tgUsername', width: 130 },
  { title: '触发群', dataIndex: 'chatTitle' },
  { title: '关键词', dataIndex: 'keyword', width: 90 },
  { title: '城市', dataIndex: 'cityName', width: 90 },
  { title: '发出组数', dataIndex: 'notesSent', width: 90 },
  { title: '结果', dataIndex: 'result', width: 90 },
  { title: '详情', dataIndex: 'detail', ellipsis: true },
];

async function load() {
  loading.value = true;
  try {
    list.value = await listenApi.plans();
    tgAccounts.value = await tgApi.accounts();
  } catch (e: any) { message.error(e.message || '加载失败'); }
  finally { loading.value = false; }
}
async function loadHits() {
  hitsLoading.value = true;
  try { hits.value = await listenApi.hits(); }
  catch (e: any) { message.error(e.message || '加载失败'); }
  finally { hitsLoading.value = false; }
}
function openEditor() {
  Object.assign(editing, { name: '', account_id: null, targets_str: '', keywords_str: '', map_str: '' });
  visible.value = true;
}
function parseMap(str: string): Record<string, string> {
  const m: Record<string, string> = {};
  (str || '').split('\n').forEach(line => {
    const i = line.indexOf('=');
    if (i > 0) {
      const k = line.slice(0, i).trim(), v = line.slice(i + 1).trim();
      if (k && v) m[k] = v;
    }
  });
  return m;
}
async function save() {
  if (!editing.account_id) { message.error('请选择监听协议号，否则计划不会执行'); return; }
  if (!editing.name) { message.error('请填写计划名称'); return; }
  try {
    await listenApi.create({
      name: editing.name,
      account_id: editing.account_id,
      targets: editing.targets_str.split(',').map((s: string) => s.trim()).filter(Boolean),
      keywords: editing.keywords_str.split(',').map((s: string) => s.trim()).filter(Boolean),
      keyword_city_map: parseMap(editing.map_str),
    });
    message.success('监听计划已创建，worker 将自动开始监听');
    visible.value = false; load();
  } catch (e: any) { message.error(e.message || '保存失败'); }
}
async function remove(id: number) {
  try { await listenApi.remove(id); message.success('已删除'); load(); }
  catch (e: any) { message.error(e.message || '删除失败'); }
}
async function togglePlan(id: number, enabled: boolean) {
  try {
    await listenApi.toggle(id, enabled);
    message.success(enabled ? '监听已启用' : '监听已停用');
    load();
  } catch (e: any) { message.error(e.message || '操作失败'); }
}

onMounted(() => { refreshKwList(); load(); loadHits(); });
</script>
