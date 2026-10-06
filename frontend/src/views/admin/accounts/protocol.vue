<template>
  <div>
    <a-space style="margin-bottom: 16px">
      <a-button type="primary" @click="qrVisible = true">扫码登录</a-button>
      <a-button @click="phoneVisible = true">手机号登录</a-button>
    </a-space>
    <a-table :columns="columns" :data-source="list" row-key="id" :loading="loading">
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'status'">
          <a-tag :color="record.status === 'online' ? 'green' : 'default'">{{ record.status }}</a-tag>
        </template>
        <template v-else-if="column.key === 'action'">
          <a-space>
            <a @click="refresh(record.id)">刷新状态</a>
            <a-popconfirm title="确认删除？" @confirm="remove(record.id)"><a>删除</a></a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>

    <a-modal v-model:open="phoneVisible" title="手机号登录" @ok="startPhone" ok-text="发送验证码">
      <a-input v-model:value="phone" placeholder="+8613800000000" />
    </a-modal>
    <a-modal v-model:open="codeVisible" title="输入验证码" @ok="verifyCode" ok-text="登录">
      <a-input v-model:value="code" placeholder="Telegram 验证码" />
      <a-input v-model:value="password" placeholder="二级密码（如有）" style="margin-top: 8px" />
    </a-modal>
    <a-modal v-model:open="qrVisible" title="扫码登录" :footer="null">
      <a-alert message="扫码登录待接入 Telethon，请先用手机号登录" type="warning" />
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { message } from 'ant-design-vue';
import { tgApi } from '@/api';

const columns = [
  { title: 'ID', dataIndex: 'id', width: 60 },
  { title: '名称', dataIndex: 'name' },
  { title: '用户名', dataIndex: 'username' },
  { title: '状态', key: 'status', width: 100 },
  { title: '操作', key: 'action', width: 180 },
];
const list = ref<any[]>([]); const loading = ref(false);
const phoneVisible = ref(false); const codeVisible = ref(false); const qrVisible = ref(false);
const phone = ref(''); const code = ref(''); const password = ref('');
const sessionKey = ref('');

async function load() {
  loading.value = true;
  try { list.value = await tgApi.accounts(); } finally { loading.value = false; }
}
async function startPhone() {
  const r: any = await tgApi.loginStart(phone.value);
  sessionKey.value = r.sessionKey;
  phoneVisible.value = false; codeVisible.value = true;
  message.success('验证码已发送');
}
async function verifyCode() {
  await tgApi.loginVerify(sessionKey.value, code.value, password.value);
  message.success('登录成功'); codeVisible.value = false; load();
}
async function refresh(id: number) { await tgApi.refreshAccount(id); load(); }
async function remove(id: number) { await tgApi.removeAccount(id); message.success('已删除'); load(); }
onMounted(load);
</script>
