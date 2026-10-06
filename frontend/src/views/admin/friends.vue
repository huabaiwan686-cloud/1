<template>
  <div>
    <div class="aq-header">
      <div class="aq-title">好友关注</div>
      <p class="aq-desc">管理关注关系，查看粉丝与关注请求</p>
      <div class="aq-toolbar">
        <a-input v-model:value="search" placeholder="搜索用户" class="search-input" @press-enter="load" />
        <a-input v-model:value="username" placeholder="@username" style="width: 200px" />
        <a-button type="primary" @click="apply">申请关注</a-button>
      </div>
    </div>
    <a-card :bordered="true" style="margin-bottom: 16px; max-width: 640px">
      <a-form :label-col="{ span: 8 }" :wrapper-col="{ span: 14 }">
        <a-form-item label="关注需审核">
          <a-switch v-model:checked="followCfg.followApprovalRequired" @change="saveCfg" />
          <div class="aq-tip">开启后，他人关注需管理员审核通过</div>
        </a-form-item>
        <a-form-item label="公开关注" style="margin-bottom: 0">
          <a-switch v-model:checked="followCfg.publicFollowEnabled" @change="saveCfg" />
          <div class="aq-tip">关闭后，关注列表仅自己可见</div>
        </a-form-item>
      </a-form>
    </a-card>
    <a-tabs v-model:active-key="direction" @change="load">
      <a-tab-pane key="" tab="全部">
        <friend-table :list="list" :loading="loading" />
      </a-tab-pane>
      <a-tab-pane key="following" tab="我关注的">
        <friend-table :list="list" :loading="loading" />
      </a-tab-pane>
      <a-tab-pane key="follower" tab="粉丝">
        <friend-table :list="list" :loading="loading" />
      </a-tab-pane>
      <a-tab-pane key="request" tab="关注请求">
        <friend-table :list="list" :loading="loading" />
      </a-tab-pane>
      <a-tab-pane key="blocked" tab="已屏蔽">
        <friend-table :list="list" :loading="loading" />
      </a-tab-pane>
    </a-tabs>
  </div>
</template>

<script setup lang="ts">
import { h, onMounted, ref } from 'vue';
import { message, Table } from 'ant-design-vue';
import { socialApi } from '@/api';

const columns = [
  { title: 'ID', dataIndex: 'id', width: 60, className: 'hide-mobile' },
  { title: '用户', dataIndex: 'username' },
  { title: '昵称', dataIndex: 'nickname', width: 140 },
  { title: '关系', dataIndex: 'direction', width: 110 },
  { title: '时间', dataIndex: 'createdAt', width: 170, className: 'hide-mobile' },
];

const FriendTable = {
  props: ['list', 'loading'],
  render() {
    return h(Table, {
      columns,
      dataSource: this.list,
      rowKey: 'id',
      loading: this.loading,
    });
  },
};

const list = ref<any[]>([]);
const loading = ref(false);
const search = ref('');
const username = ref('');
const direction = ref('');
const followCfg = ref({ followApprovalRequired: false, publicFollowEnabled: true });

async function load() {
  loading.value = true;
  try {
    const r: any = await socialApi.friends(direction.value);
    list.value = r.list || r || [];
  } finally { loading.value = false; }
}
async function apply() {
  if (!username.value.trim()) { message.warning('请输入用户名'); return; }
  await socialApi.applyFriend(username.value.trim());
  message.success('已发送关注申请');
  username.value = '';
  load();
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
