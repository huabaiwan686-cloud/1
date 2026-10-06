<template>
  <div>
    <a-card title="快速推送" style="margin-bottom: 16px">
      <a-alert message="选择模板和发送协议号，一键把模板文案+媒体推送到下方全部快速目标群组" type="info" style="margin-bottom: 16px" />
      <a-form layout="vertical">
        <a-form-item label="发送协议号">
          <a-select v-model:value="accountId" placeholder="选择已登录的 TG 协议号" style="width: 100%">
            <a-select-option v-for="a in accounts" :key="a.id" :value="a.id">{{ a.phone }}（{{ a.name }}）</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="模板">
          <a-select v-model:value="tplId" style="width: 100%" placeholder="选择模板">
            <a-select-option v-for="t in templates" :key="t.id" :value="t.id">{{ t.name }} ({{ t.code }})</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item>
          <a-button type="primary" :disabled="!tplId || !accountId" @click="push" :loading="loading">立即推送到 {{ targets.length }} 个目标</a-button>
        </a-form-item>
      </a-form>
    </a-card>
    <a-card title="快速推送目标">
      <a-form layout="inline" style="margin-bottom: 16px">
        <a-form-item><a-input v-model:value="newName" placeholder="目标名称" style="width: 160px" /></a-form-item>
        <a-form-item><a-input v-model:value="newTarget" placeholder="群用户名 @xxx 或 ID" style="width: 220px" /></a-form-item>
        <a-form-item><a-button type="primary" @click="addTarget">添加目标</a-button></a-form-item>
      </a-form>
      <a-table :columns="columns" :data-source="targets" row-key="id" :loading="tLoading" :pagination="false">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'action'">
            <a-popconfirm title="确认删除？" @confirm="removeTarget(record.id)"><a>删除</a></a-popconfirm>
          </template>
        </template>
      </a-table>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { message } from 'ant-design-vue';
import { messageApi, tgApi } from '@/api';

const templates = ref<any[]>([]);
const accounts = ref<any[]>([]);
const targets = ref<any[]>([]);
const tplId = ref<number | null>(null);
const accountId = ref<number | null>(null);
const loading = ref(false); const tLoading = ref(false);
const newName = ref(''); const newTarget = ref('');
const columns = [
  { title: 'ID', dataIndex: 'id', width: 60 },
  { title: '名称', dataIndex: 'name' },
  { title: '目标', dataIndex: 'target' },
  { title: '操作', key: 'action', width: 80 },
];

async function loadTargets() {
  tLoading.value = true;
  try { targets.value = await messageApi.quickTargets(); } finally { tLoading.value = false; }
}
async function addTarget() {
  if (!newName.value || !newTarget.value) { message.error('请填写名称和目标'); return; }
  await messageApi.createQuickTarget({ name: newName.value, target: newTarget.value });
  newName.value = ''; newTarget.value = '';
  message.success('已添加'); loadTargets();
}
async function removeTarget(id: number) {
  await messageApi.deleteQuickTarget(id);
  message.success('已删除'); loadTargets();
}
onMounted(async () => {
  templates.value = await messageApi.templates();
  accounts.value = await tgApi.accounts();
  loadTargets();
});
async function push() {
  loading.value = true;
  try {
    const r: any = await messageApi.quickPush(tplId.value!, accountId.value!);
    message.success(r.msg || '推送完成');
  } catch (e: any) { message.error(e.message); } finally { loading.value = false; }
}
</script>
