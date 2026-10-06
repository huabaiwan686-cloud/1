<template>
  <div>
    <a-button type="primary" @click="openEditor()" style="margin-bottom: 16px">新建监听计划</a-button>
    <a-table :columns="columns" :data-source="list" row-key="id" :loading="loading">
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'bind'">
          <a-tag color="blue">{{ record.bindId }}</a-tag>
        </template>
        <template v-else-if="column.key === 'account'">
          <span>{{ accountName(record.accountId) }}</span>
        </template>
        <template v-else-if="column.key === 'action'">
          <a-popconfirm title="确认删除？" @confirm="remove(record.id)"><a>删除</a></a-popconfirm>
        </template>
      </template>
    </a-table>
    <a-modal v-model:open="visible" title="关键字监听" @ok="save">
      <a-form :model="editing" layout="vertical">
        <a-form-item label="计划名称"><a-input v-model:value="editing.name" /></a-form-item>
        <a-form-item label="监听协议号（必填，否则计划不会执行）">
          <a-select v-model:value="editing.account_id" placeholder="选择已登录的 TG 协议号" style="width: 100%">
            <a-select-option v-for="a in tgAccounts" :key="a.id" :value="a.id">{{ a.phone }}（{{ a.name }}）</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="监听目标（逗号分隔）"><a-input v-model:value="editing.targets_str" placeholder="@group1,@channel1" /></a-form-item>
        <a-form-item label="关键词（逗号分隔，地区词如：北京,上海）"><a-input v-model:value="editing.keywords_str" placeholder="北京,上海" /></a-form-item>
        <a-form-item label="自定义关键词→城市（每行一组）">
          <a-textarea v-model:value="editing.map_str" :rows="3" placeholder="京妞=北京&#10;魔都=上海" />
        </a-form-item>
        <a-alert type="info" show-icon message="有人在监听群里发地区关键词，系统自动私聊他该地区全部已上架素材（文字+媒体+验证视频）" />
      </a-form>
    </a-modal>

    <h3 style="margin: 24px 0 12px">命中记录</h3>
    <a-table :columns="hitColumns" :data-source="hits" row-key="id" :loading="hitsLoading" :pagination="{ pageSize: 20 }">
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'result'">
          <a-tag :color="record.result === 'success' ? 'green' : 'default'">{{ record.result === 'success' ? '已发送' : record.result === 'skipped' ? '跳过' : '失败' }}</a-tag>
        </template>
      </template>
    </a-table>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import { message } from 'ant-design-vue';
import { listenApi, tgApi } from '@/api';

const columns = [
  { title: 'ID', dataIndex: 'id', width: 60 },
  { title: '名称', dataIndex: 'name' },
  { title: '协议号', key: 'account', width: 170 },
  { title: '绑定 ID', key: 'bind', width: 130 },
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
  { title: '结果', key: 'result', width: 90 },
  { title: '详情', dataIndex: 'detail', ellipsis: true },
];

async function load() {
  loading.value = true;
  try {
    list.value = await listenApi.plans();
    tgAccounts.value = await tgApi.accounts();
  } finally { loading.value = false; }
}
async function loadHits() {
  hitsLoading.value = true;
  try { hits.value = await listenApi.hits(); } finally { hitsLoading.value = false; }
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
  await listenApi.create({
    name: editing.name,
    account_id: editing.account_id,
    targets: editing.targets_str.split(',').map((s: string) => s.trim()).filter(Boolean),
    keywords: editing.keywords_str.split(',').map((s: string) => s.trim()).filter(Boolean),
    keyword_city_map: parseMap(editing.map_str),
  });
  message.success('监听计划已创建，worker 将自动开始监听');
  visible.value = false; load();
}
async function remove(id: number) { await listenApi.remove(id); message.success('已删除'); load(); }
onMounted(() => { load(); loadHits(); });
</script>
