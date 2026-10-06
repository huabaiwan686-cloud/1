<template>
  <div>
    <a-button type="primary" @click="openEditor" style="margin-bottom: 16px">新增账号</a-button>
    <a-table :columns="columns" :data-source="list" row-key="id" :loading="loading">
      <template #bodyCell="{ column, record }">
        <a-tag v-if="column.key === 'admin'" :color="record.isAdmin ? 'blue' : 'default'">
          {{ record.isAdmin ? '管理员' : '普通' }}
        </a-tag>
      </template>
    </a-table>
    <a-modal v-model:open="visible" title="新增账号" @ok="save">
      <a-form :model="form" layout="vertical">
        <a-form-item label="登录账号"><a-input v-model:value="form.username" placeholder="登录用用户名" /></a-form-item>
        <a-form-item label="账号名称"><a-input v-model:value="form.display_name" placeholder="显示名称（可选）" /></a-form-item>
        <a-form-item label="密码"><a-input-password v-model:value="form.password" placeholder="至少 6 位" /></a-form-item>
        <a-form-item><a-checkbox v-model:checked="form.is_admin">设为管理员</a-checkbox></a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import { message } from 'ant-design-vue';
import { userApi } from '@/api';

const columns = [
  { title: 'ID', dataIndex: 'id', width: 60 },
  { title: '账号', dataIndex: 'username' },
  { title: '角色', key: 'admin', width: 100 },
  { title: '注册时间', dataIndex: 'createdAt', width: 180 },
];
const list = ref<any[]>([]); const loading = ref(false);
const visible = ref(false);
const form = reactive({ username: '', display_name: '', password: '', is_admin: false });

async function load() {
  loading.value = true;
  try { list.value = await userApi.list(); } finally { loading.value = false; }
}
function openEditor() {
  Object.assign(form, { username: '', display_name: '', password: '', is_admin: false });
  visible.value = true;
}
async function save() {
  if (!form.username || !form.password) { message.error('请填写账号和密码'); return; }
  try {
    await userApi.create(form);
    message.success('账号已创建');
    visible.value = false; load();
  } catch (e: any) { message.error(e.message); }
}
onMounted(load);
</script>
