<template>
  <div>
    <a-space style="margin-bottom: 16px">
      <a-input v-model:value="username" placeholder="@username" style="width: 200px" />
      <a-button type="primary" @click="apply">发送关注申请</a-button>
      <a-radio-group v-model:value="direction" @change="load">
        <a-radio-button value="">全部</a-radio-button>
        <a-radio-button value="following">我关注的</a-radio-button>
        <a-radio-button value="follower">粉丝</a-radio-button>
        <a-radio-button value="request">请求</a-radio-button>
        <a-radio-button value="blocked">屏蔽</a-radio-button>
      </a-radio-group>
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
  { title: '用户', dataIndex: 'username' },
  { title: '关系', dataIndex: 'direction', width: 110 },
];
const list = ref<any[]>([]); const loading = ref(false);
const username = ref(''); const direction = ref('');

async function load() {
  loading.value = true;
  try { list.value = await socialApi.friends(direction.value); } finally { loading.value = false; }
}
async function apply() {
  await socialApi.applyFriend(username.value);
  message.success('关注申请已发送'); username.value = ''; load();
}
onMounted(load);
</script>
