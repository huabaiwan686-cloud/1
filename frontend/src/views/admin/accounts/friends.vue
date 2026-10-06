<template>
  <div>
    <a-card size="small" title="关注配置" style="margin-bottom: 16px; max-width: 600px">
      <a-form :label-col="{ span: 8 }" :wrapper-col="{ span: 14 }">
        <a-form-item label="关注需审核">
          <a-switch v-model:checked="followCfg.followApprovalRequired" @change="saveCfg" />
          <div class="hint">开启后，他人关注需管理员审核通过</div>
        </a-form-item>
        <a-form-item label="公开关注">
          <a-switch v-model:checked="followCfg.publicFollowEnabled" @change="saveCfg" />
          <div class="hint">关闭后，关注列表仅自己可见</div>
        </a-form-item>
      </a-form>
    </a-card>
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
const followCfg = ref({ followApprovalRequired: false, publicFollowEnabled: true });

async function load() {
  loading.value = true;
  try { list.value = await socialApi.friends(direction.value); } finally { loading.value = false; }
}
async function apply() {
  await socialApi.applyFriend(username.value);
  message.success('已关注'); username.value = ''; load();
}
async function loadCfg() {
  try {
    const d: any = await socialApi.followConfig();
    followCfg.value = { ...followCfg.value, ...(d.data || d) };
  } catch {}
}
async function saveCfg() {
  try {
    await socialApi.setFollowConfig(followCfg.value);
    message.success('关注配置已保存');
  } catch (e: any) { message.error(e.message || '保存失败'); loadCfg(); }
}
onMounted(() => { load(); loadCfg(); });
</script>

<style scoped>
.hint { color: #999; font-size: 12px; margin-top: 4px; }
</style>
