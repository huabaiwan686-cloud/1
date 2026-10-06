<template>
  <div class="page">
    <a-card title="超级管理员 · 用户管控" class="page-card">
      <div class="desc-text">可管理所有会员/用户账号：新增、删除、开关管理员权限、禁用/启用、重置密码</div>
    </a-card>
    <a-card title="邀请码" class="page-card">
      <a-space class="mb-12">
        <a-button type="primary" @click="genCode">生成邀请码</a-button>
        <span class="desc-text">把邀请码发给会员，他在登录页点"注册"即可自助注册账号密码</span>
      </a-space>
      <a-table :columns="codeColumns" :data-source="codes" row-key="code" size="small" :pagination="{ pageSize: 8 }">
        <template #bodyCell="{ column, record }">
          <a v-if="column.key === 'copy'" @click="copyCode(record.code)">复制</a>
        </template>
      </a-table>
    </a-card>
    <a-button type="primary" @click="openEditor" class="mb-16">新增账号</a-button>
    <a-table :columns="columns" :data-source="list" row-key="id" :loading="loading">
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'admin'">
          <a-tag :color="record.isAdmin ? 'blue' : 'default'">{{ record.isAdmin ? '管理员' : '普通' }}</a-tag>
        </template>
        <template v-else-if="column.key === 'active'">
          <a-tag :color="record.isActive ? 'green' : 'red'">{{ record.isActive ? '正常' : '已禁用' }}</a-tag>
        </template>
        <template v-else-if="column.key === 'member'">
          <a-tag :color="record.isMember ? 'gold' : 'default'">{{ record.isMember ? '会员' : '普通' }}</a-tag>
        </template>
        <template v-else-if="column.key === 'action'">
          <a-space class="table-actions">
            <a @click="toggleAdmin(record)">{{ record.isAdmin ? '取消管理员' : '设为管理员' }}</a>
            <a @click="toggleMember(record)">{{ record.isMember ? '取消会员' : '设为会员' }}</a>
            <a @click="toggleActive(record)">{{ record.isActive ? '禁用' : '启用' }}</a>
            <a @click="openReset(record)">重置密码</a>
            <a-popconfirm title="确认删除该账号？不可恢复" @confirm="remove(record.id)">
              <a style="color: #ff4d4f">删除</a>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>
    <a-modal class="modal-form" v-model:open="visible" title="新增账号" @ok="save">
      <a-form :model="form" layout="vertical">
        <a-form-item label="登录账号"><a-input v-model:value="form.username" placeholder="登录用用户名" /></a-form-item>
        <a-form-item label="账号名称"><a-input v-model:value="form.display_name" placeholder="显示名称（可选）" /></a-form-item>
        <a-form-item label="密码"><a-input-password v-model:value="form.password" placeholder="至少 6 位" /></a-form-item>
        <a-form-item><a-checkbox v-model:checked="form.is_admin">设为管理员（无限制使用所有功能）</a-checkbox></a-form-item>
      </a-form>
    </a-modal>
    <a-modal class="modal-form" v-model:open="resetVisible" title="重置密码" @ok="doReset">
      <a-form layout="vertical">
        <a-form-item :label="`账号：${resetTarget.username}`">
          <a-input-password v-model:value="resetPassword" placeholder="新密码，至少 6 位" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import { message } from 'ant-design-vue';
import { userApi, inviteApi } from '@/api';

const columns = [
  { title: 'ID', dataIndex: 'id', width: 60 },
  { title: '账号', dataIndex: 'username' },
  { title: '名称', dataIndex: 'displayName' },
  { title: '角色', key: 'admin', width: 100 },
  { title: '会员', key: 'member', width: 100 },
  { title: '状态', key: 'active', width: 100 },
  { title: '注册时间', dataIndex: 'createdAt', width: 180 },
  { title: '操作', key: 'action', width: 380 },
];
const list = ref<any[]>([]); const loading = ref(false);
const visible = ref(false);
const form = reactive({ username: '', display_name: '', password: '', is_admin: false });
const resetVisible = ref(false);
const resetTarget = ref<any>({});
const resetPassword = ref('');

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
    message.success('账号已创建'); visible.value = false; load();
  } catch (e: any) { message.error(e.message); }
}
async function toggleAdmin(r: any) {
  try {
    await userApi.update(r.id, { is_admin: !r.isAdmin });
    message.success(r.isAdmin ? '已取消管理员' : '已设为管理员'); load();
  } catch (e: any) { message.error(e.message); }
}
async function toggleMember(r: any) {
  try {
    await userApi.update(r.id, { is_member: !r.isMember });
    message.success(r.isMember ? '已取消会员' : '已设为会员'); load();
  } catch (e: any) { message.error(e.message); }
}
async function toggleActive(r: any) {
  try {
    await userApi.update(r.id, { is_active: !r.isActive });
    message.success(r.isActive ? '已禁用' : '已启用'); load();
  } catch (e: any) { message.error(e.message); }
}
function openReset(r: any) {
  resetTarget.value = r; resetPassword.value = ''; resetVisible.value = true;
}
async function doReset() {
  if (!resetPassword.value || resetPassword.value.length < 6) { message.error('密码至少 6 位'); return; }
  try {
    await userApi.update(resetTarget.value.id, { password: resetPassword.value });
    message.success('密码已重置'); resetVisible.value = false;
  } catch (e: any) { message.error(e.message); }
}
async function remove(id: number) {
  try { await userApi.remove(id); message.success('已删除'); load(); }
  catch (e: any) { message.error(e.message); }
}
const codeColumns = [
  { title: '邀请码', dataIndex: 'code' },
  { title: '状态', dataIndex: 'used', width: 120,
    customRender: ({ text, record }: any) => text ? `已使用(${record.usedBy})` : '未使用' },
  { title: '操作', key: 'copy', width: 80 },
];
const codes = ref<any[]>([]);
async function loadCodes() {
  try { codes.value = (await inviteApi.list()).codes || []; } catch {}
}
async function genCode() {
  try {
    const r: any = await inviteApi.generate();
    message.success('邀请码已生成：' + r.code);
    loadCodes();
  } catch (e: any) { message.error(e.message); }
}
function copyCode(code: string) {
  navigator.clipboard.writeText(code).then(
    () => message.success('已复制：' + code),
    () => message.error('复制失败，请手动复制'));
}
onMounted(() => { load(); loadCodes(); });
</script>
