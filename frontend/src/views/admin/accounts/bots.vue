<template>
  <div>
    <a-space style="margin-bottom: 16px">
      <a-button type="primary" @click="openEditor()">添加 Bot Token</a-button>
      <a-button @click="openManaged()">官方一键创建</a-button>
    </a-space>
    <a-alert v-if="mgmt.showSetup" type="warning" show-icon style="margin-bottom: 16px"
             message="官方创建未配置：先在 BotFather 给管理机器人开启 Management Mode，再填入它的 token" />
    <a-space v-if="mgmt.showSetup" style="margin-bottom: 16px">
      <a-input v-model:value="mgmt.token" placeholder="管理机器人的 token" style="width: 360px" />
      <a-button type="primary" @click="saveManagedSetup" :loading="mgmt.saving">保存配置</a-button>
    </a-space>
    <a-table :columns="columns" :data-source="list" row-key="id" :loading="loading">
      <template #bodyCell="{ column, record }">
        <a-space v-if="column.key === 'action'">
          <a @click="verify(record.id)">验证</a>
          <a-popconfirm title="确认删除？" @confirm="remove(record.id)"><a>删除</a></a-popconfirm>
        </a-space>
      </template>
    </a-table>
    <a-modal v-model:open="visible" title="Bot Token" @ok="save" :confirm-loading="saving">
      <a-form :model="editing" layout="vertical">
        <a-form-item label="名称"><a-input v-model:value="editing.name" /></a-form-item>
        <a-form-item label="Bot 用户名（以 bot 结尾）"><a-input v-model:value="editing.username" placeholder="@xxxbot" /></a-form-item>
        <a-form-item label="Token" v-if="!editing.auto_create"><a-input v-model:value="editing.token" placeholder="123456:ABC-DEF..." /></a-form-item>
        <a-form-item label="用哪个协议号创建" v-if="editing.auto_create">
          <a-select v-model:value="editing.tg_account_id" placeholder="选择已登录的 TG 协议号" style="width: 100%">
            <a-select-option v-for="a in tgAccounts" :key="a.id" :value="a.id">{{ a.phone }}（{{ a.name }}）</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="备注"><a-textarea v-model:value="editing.remark" :rows="2" /></a-form-item>
        <a-checkbox v-model:checked="editing.auto_create">自动创建（通过 BotFather，约 10~20 秒）</a-checkbox>
      </a-form>
    </a-modal>
    <a-modal v-model:open="mgmt.visible" title="官方一键创建（稳定）" :footer="null">
      <a-form layout="vertical">
        <a-form-item label="名称"><a-input v-model:value="mgmt.name" /></a-form-item>
        <a-form-item label="Bot 用户名（以 bot 结尾）"><a-input v-model:value="mgmt.username" placeholder="@xxxbot" /></a-form-item>
      </a-form>
      <a-button type="primary" block @click="doManagedCreate" :loading="mgmt.creating">生成创建链接</a-button>
      <div v-if="mgmt.link" style="margin-top: 16px">
        <p style="color: #666">在手机 TG 里打开下面的链接并点确认，token 会自动回到这里（约 1 分钟内）：</p>
        <a :href="mgmt.link" target="_blank" style="word-break: break-all">{{ mgmt.link }}</a>
        <div style="margin-top: 12px"><a-button @click="checkManaged" :loading="mgmt.checking">我已确认，检查一下</a-button></div>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import { message } from 'ant-design-vue';
import { botApi, tgApi, authApi } from '@/api';

const columns = [
  { title: 'ID', dataIndex: 'id', width: 60 },
  { title: '名称', dataIndex: 'name' },
  { title: '用户名', dataIndex: 'username' },
  { title: '操作', key: 'action', width: 140 },
];
const list = ref<any[]>([]); const loading = ref(false);
const visible = ref(false); const saving = ref(false);
const tgAccounts = ref<any[]>([]);
const editing = reactive<any>({});

async function load() {
  loading.value = true;
  try {
    list.value = await botApi.tokens();
    tgAccounts.value = await tgApi.accounts();
  } finally { loading.value = false; }
}
function openEditor() {
  Object.assign(editing, { name: '', username: '', token: '', remark: '', auto_create: false, tg_account_id: null });
  visible.value = true;
}
async function save() {
  saving.value = true;
  try {
    if (editing.auto_create) {
      if (!editing.tg_account_id) { message.error('请选择用于创建的 TG 协议号'); return; }
      const r: any = await botApi.autoCreate({
        name: editing.name, username: editing.username, tg_account_id: editing.tg_account_id,
      });
      message.success(r.msg || '已自动创建');
    } else {
      await botApi.create(editing);
      message.success('已保存');
    }
    visible.value = false; load();
  }
  catch (e: any) { message.error(e.message); } finally { saving.value = false; }
}
async function verify(id: number) {
  const r: any = await botApi.verify(id); message.info(r.msg);
}
async function remove(id: number) { await botApi.remove(id); message.success('已删除'); load(); }

// ---- 官方一键创建（Managed Bots） ----
const mgmt = reactive<any>({ visible: false, name: '', username: '', link: '', token: '',
  showSetup: false, saving: false, creating: false, checking: false });
async function loadManagedStatus() {
  try {
    const s: any = await botApi.managedStatus();
    const me: any = await authApi.current();
    mgmt.showSetup = !s.configured && me.isAdmin;
  } catch { /* ignore */ }
}
function openManaged() {
  Object.assign(mgmt, { name: '', username: '', link: '' });
  mgmt.visible = true;
}
async function saveManagedSetup() {
  if (!mgmt.token) { message.error('请填写管理机器人的 token'); return; }
  mgmt.saving = true;
  try {
    const r: any = await botApi.managedSetup(mgmt.token);
    message.success(r.msg || '已配置'); mgmt.showSetup = false; mgmt.token = '';
  } catch (e: any) { message.error(e.message); } finally { mgmt.saving = false; }
}
async function doManagedCreate() {
  if (!mgmt.username) { message.error('请填写 Bot 用户名'); return; }
  mgmt.creating = true;
  try {
    const r: any = await botApi.managedCreate({ name: mgmt.name, username: mgmt.username });
    mgmt.link = r.link;
  } catch (e: any) { message.error(e.message); } finally { mgmt.creating = false; }
}
async function checkManaged() {
  mgmt.checking = true;
  try {
    await load();
    const pending: any[] = await botApi.managedPending();
    const stillWaiting = pending.some((p: any) => p.username === mgmt.username.replace('@', '').toLowerCase());
    if (!stillWaiting) { message.success('创建完成，token 已自动入库'); mgmt.visible = false; }
    else message.info('还没确认，稍后再试');
  } catch (e: any) { message.error(e.message); } finally { mgmt.checking = false; }
}
onMounted(() => { load(); loadManagedStatus(); });
</script>
