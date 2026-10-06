<template>
  <div>
    <a-space style="margin-bottom: 16px">
      <a-input v-model:value="bindCode" placeholder="输入绑定码" style="width: 240px" />
      <a-button type="primary" @click="bind">绑定</a-button>
    </a-space>
    <a-table :columns="columns" :data-source="list" row-key="id" :loading="loading" />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { message } from 'ant-design-vue';
import { socialApi } from '@/api';

const columns = [
  { title: 'ID', dataIndex: 'id', width: 60 },
  { title: '绑定码', dataIndex: 'bindCode' },
  { title: '平台', dataIndex: 'platformName' },
  { title: '状态', dataIndex: 'status', width: 100 },
];
const list = ref<any[]>([]); const loading = ref(false);
const bindCode = ref('');

async function load() {
  loading.value = true;
  try { list.value = await socialApi.bindings(); } finally { loading.value = false; }
}
async function bind() {
  await socialApi.createBinding(bindCode.value);
  message.success('绑定码已提交'); bindCode.value = ''; load();
}
onMounted(load);
</script>
