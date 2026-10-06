<template>
  <a-card title="用户管理" :bordered="true">
    <template #extra>
      <a-button type="primary" @click="openEditor">添加子账号</a-button>
    </template>
    <a-table :columns="columns" :data-source="list" row-key="id" :loading="loading"
      :scroll="{ x: 'max-content' }">
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'password'">
          <span style="color: rgba(0,0,0,.45)">••••••</span>
        </template>
        <template v-else-if="column.key === 'role'">
          <a-tag v-if="record.isAdmin" color="blue">管理员</a-tag>
          <a-tag v-else-if="record.isMember" color="gold">会员</a-tag>
          <a-tag v-else color="default">普通</a-tag>
        </template>
        <template v-else-if="column.key === 'status'">
          <a-tag :color="record.isActive ? 'green' : 'default'">{{ record.isActive ? '正常' : '已禁用' }}</a-tag>
        </template>
        <template v-else-if="column.key === 'action'">
          <a-space>
            <a @click="resetAndCopy(record)">重置并复制密码</a>
            <a @click="toggleAdmin(record)">{{ record.isAdmin ? '取消管理员' : '设为管理员' }}</a>
            <a @click="toggleActive(record)">{{ record.isActive ? '禁用' : '启用' }}</a>
            <a-popconfirm title="确认删除该账号？不可恢复" @confirm="remove(record.id)">
              <a>删除</a>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>
  </a-card>

  <a-card title="邀请码" :bordered="true" style="margin-top: 16px">
    <template #extra>
      <a-button type="primary" @click="genCode">生成邀请码</a-button>
    </template>
    <div class="desc-text" style="margin-bottom: 12px">把邀请码发给会员，他在登录页点"注册"即可自助注册账号密码</div>
    <a-table :columns="codeColumns" :data-source="codes" row-key="code" size="small" :pagination="{ pageSize: 8 }">
      <template #bodyCell="{ column, record }">
        <a v-if="column.key === 'copy'" @click="copyCode(record.code)">复制</a>
      </template>
    </a-table>
  </a-card>

  <a-modal class="modal-form" v-model:open="visible" title="添加子账号" @ok="save" :width="520">
    <a-form :model="form" layout="vertical">
      <a-form-item label="登录账号" required><a-input v-model:value="form.username" placeholder="登录用用户名" /></a-form-item>
      <a-form-item label="昵称"><a-input v-model:value="form.display_name" placeholder="显示名称（可选）" /></a-form-item>
      <a-form-item label="密码" required><a-input-password v-model:value="form.password" placeholder="至少 6 位" /></a-form-item>
      <a-form-item><a-checkbox v-model:checked="form.is_admin">设为管理员（无限制使用所有功能）</a-checkbox></a-form-item>
    </a-form>
  </a-modal>
  <a-modal class="modal-form" v-model:open="resetVisible" title="重置密码" @ok="doReset" :width="520">
    <a-form layout="vertical">
      <a-form-item :label="`账号：${resetTarget.username}`" required>
        <a-input-password v-model:value="resetPassword" placeholder="新密码，至少 6 位" />
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import { message } from 'ant-design-vue';
import { userApi, inviteApi } from '@/api';

const columns = [
  { title: 'ID', dataIndex: 'id', width: 70 },
  { title: '用户名', dataIndex: 'username' },
  { title: '密码', key: 'password', width: 120 },
  { title: '昵称', dataIndex: 'displayName' },
  { title: '角色', key: 'role', width: 100 },
  { title: '创建时间', dataIndex: 'createdAt', width: 180 },
  { title: '操作', key: 'action', width: 320 },
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
async function toggleActive(r: any) {
  try {
    await userApi.update(r.id, { is_active: !r.isActive });
    message.success(r.isActive ? '已禁用' : '已启用'); load();
  } catch (e: any) { message.error(e.message); }
}
// 重置并复制密码：生成随机密码 → 重置 → 复制到剪贴板
async function resetAndCopy(r: any) {
  const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789';
  let pwd = '';
  for (let i = 0; i < 10; i++) pwd += chars[Math.floor(Math.random() * chars.length)];
  try {
    await userApi.update(r.id, { password: pwd });
    message.success('密码已重置');
    try { await navigator.clipboard.writeText(pwd); message.success('新密码已复制：' + pwd); }
    catch { message.info('新密码：' + pwd); }
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
  { title: '状态', dataIndex: 'used', width: 160,
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
