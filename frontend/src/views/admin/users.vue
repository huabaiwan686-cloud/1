<template>
  <div>
    <a-table :columns="columns" :data-source="list" row-key="id" :loading="loading">
      <template #bodyCell="{ column, record }">
        <a-tag v-if="column.key === 'admin'" :color="record.isAdmin ? 'blue' : 'default'">
          {{ record.isAdmin ? '管理员' : '普通' }}
        </a-tag>
      </template>
    </a-table>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import request from '@/utils/request';

const columns = [
  { title: 'ID', dataIndex: 'id', width: 60 },
  { title: '账号', dataIndex: 'username' },
  { title: '角色', key: 'admin', width: 100 },
  { title: '注册时间', dataIndex: 'createdAt', width: 180 },
];
const list = ref<any[]>([]); const loading = ref(false);
onMounted(async () => {
  loading.value = true;
  try { list.value = await request.get('/api/account/users'); } finally { loading.value = false; }
});
</script>
