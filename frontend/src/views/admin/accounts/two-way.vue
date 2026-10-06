<template>
  <div>
    <a-button type="primary" @click="visible = true" style="margin-bottom: 16px">新建双向机器人</a-button>
    <a-table :columns="columns" :data-source="list" row-key="id" :loading="loading" />
    <a-modal v-model:open="visible" title="双向机器人" @ok="save">
      <a-form :model="form" layout="vertical">
        <a-form-item label="Bot Token">
          <a-select v-model:value="form.bot_token_id" style="width: 100%">
            <a-select-option v-for="b in bots" :key="b.id" :value="b.id">{{ b.name }}</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="TG 账号">
          <a-select v-model:value="form.tg_account_id" style="width: 100%">
            <a-select-option v-for="a in accounts" :key="a.id" :value="a.id">{{ a.name }}</a-select-option>
          </a-select>
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import { message } from 'ant-design-vue';
import { socialApi, botApi, tgApi } from '@/api';

const columns = [
  { title: 'ID', dataIndex: 'id', width: 60 },
  { title: '群组', dataIndex: 'groupName' },
  { title: '邀请链接', dataIndex: 'inviteLink' },
  { title: '状态', dataIndex: 'status', width: 100 },
];
const list = ref<any[]>([]); const bots = ref<any[]>([]); const accounts = ref<any[]>([]);
const loading = ref(false); const visible = ref(false);
const form = reactive({ bot_token_id: null as any, tg_account_id: null as any });

async function load() {
  loading.value = true;
  try {
    list.value = await socialApi.twoWayBots();
    bots.value = await botApi.tokens();
    accounts.value = await tgApi.accounts();
  } finally { loading.value = false; }
}
async function save() {
  await socialApi.createTwoWay(form);
  message.success('已创建'); visible.value = false; load();
}
onMounted(load);
</script>
