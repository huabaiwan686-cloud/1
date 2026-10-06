<template>
  <a-card title="群聊监听（发布端）">
    <a-alert message="此处展示监听计划的命中记录（待接入实时推送）" type="info" style="margin-bottom: 16px" />
    <a-table :columns="columns" :data-source="list" row-key="id" :loading="loading" />
  </a-card>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { listenApi } from '@/api';

const columns = [
  { title: 'ID', dataIndex: 'id', width: 60 },
  { title: '计划', dataIndex: 'name' },
  { title: '绑定 ID', dataIndex: 'bindId', width: 130 },
];
const list = ref<any[]>([]); const loading = ref(false);
onMounted(async () => {
  loading.value = true;
  try { list.value = await listenApi.plans(); } finally { loading.value = false; }
});
</script>
