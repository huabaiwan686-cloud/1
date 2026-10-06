<template>
  <a-card title="协议号" :bordered="true">
    <template #extra>
      <a-space>
        <a-button @click="refreshAll" :loading="batchLoading">批量检测</a-button>
        <a-button @click="importVisible = true">上传 Session</a-button>
        <a-button type="primary" @click="addVisible = true">添加协议号</a-button>
      </a-space>
    </template>
    <a-table :columns="columns" :data-source="list" row-key="id" :loading="loading"
      :scroll="{ x: 'max-content' }">
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'status'">
          <a-tag :color="record.status === 'online' ? 'green' : 'default'">{{ record.status === 'online' ? '在线' : '离线' }}</a-tag>
        </template>
        <template v-else-if="column.key === 'action'">
          <a-space>
            <a @click="refresh(record.id)">刷新状态</a>
            <a @click="openTransfer(record)">转移</a>
            <a-popconfirm title="确认删除？" @confirm="remove(record.id)"><a>删除</a></a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>
  </a-card>

  <!-- 添加协议号：手机号 / 扫码 二选一 -->
  <a-modal class="modal-form" v-model:open="addVisible" title="添加协议号" :footer="null" :width="520">
    <a-space direction="vertical" style="width: 100%">
      <a-button type="primary" block @click="addVisible = false; phoneVisible = true">手机号登录</a-button>
      <a-button block @click="addVisible = false; openQr()">扫码登录</a-button>
    </a-space>
  </a-modal>

  <a-modal class="modal-form" v-model:open="phoneVisible" title="手机号登录" @ok="startPhone" ok-text="发送验证码" :width="520">
    <a-form layout="vertical">
      <a-form-item label="手机号" required><a-input v-model:value="phone" placeholder="+8613800000000" /></a-form-item>
    </a-form>
  </a-modal>
  <a-modal class="modal-form" v-model:open="codeVisible" title="输入验证码" @ok="verifyCode" ok-text="登录" :width="520">
    <a-form layout="vertical">
      <a-form-item label="Telegram 验证码" required><a-input v-model:value="code" placeholder="Telegram 验证码" /></a-form-item>
      <a-form-item label="二级密码（如有）"><a-input v-model:value="password" placeholder="二级密码（如有）" /></a-form-item>
    </a-form>
  </a-modal>
  <a-modal class="modal-form" v-model:open="qrVisible" title="扫码登录" :footer="null" @cancel="stopQrPoll" :width="520">
    <div v-if="qrLoading" style="text-align: center; padding: 24px"><a-spin tip="正在生成二维码…" /></div>
    <div v-else-if="qrStage === 'expired'" style="text-align: center; padding: 16px">
      <a-alert message="二维码已过期" type="warning" style="margin-bottom: 12px" />
      <a-button type="primary" @click="openQr">重新生成</a-button>
    </div>
    <div v-else-if="qrStage === 'need_password'" style="padding: 8px">
      <a-alert message="该账号开启了两步验证，请输入二级密码完成登录" type="info" style="margin-bottom: 12px" />
      <a-input v-model:value="qrPassword" placeholder="二级密码" style="margin-bottom: 12px" />
      <a-button type="primary" block @click="pollQr(true)">确认登录</a-button>
    </div>
    <div v-else style="text-align: center">
      <img v-if="qrImage" :src="'data:image/png;base64,' + qrImage" style="width: 220px; height: 220px" />
      <p v-else style="word-break: break-all; color: #666">{{ qrUrl }}</p>
      <p style="color: #999; margin-top: 8px">{{ qrTip }}</p>
    </div>
  </a-modal>

  <a-modal class="modal-form" v-model:open="importVisible" title="上传 Session" @ok="doImport" ok-text="导入" :width="520">
    <a-form layout="vertical">
      <a-form-item label="手机号" required><a-input v-model:value="importPhone" placeholder="如 +8613800000000" /></a-form-item>
      <a-form-item label="Session 文件" required>
        <input type="file" accept=".session" @change="onSessionFile" />
        <p v-if="importFileName" style="color: #999; margin-top: 8px">已选择：{{ importFileName }}</p>
      </a-form-item>
      <div class="desc-text">上传 Telethon 的 .session 文件，关联到指定手机号，导入后自动验证登录态。</div>
    </a-form>
  </a-modal>

  <a-modal class="modal-form" v-model:open="transferVisible" title="账号转移" @ok="doTransfer" :width="520">
    <p style="color: #666">把该协议号转移给目标用户（不选=转回公共池）。</p>
    <a-select v-model:value="transferUserId" placeholder="选择目标用户（不选=公共池）" allow-clear style="width: 100%">
      <a-select-option v-for="u in users" :key="u.id" :value="u.id">{{ u.username }}</a-select-option>
    </a-select>
  </a-modal>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue';
import { message } from 'ant-design-vue';
import { tgApi, userApi } from '@/api';
import { formatDateTime } from '@/utils/date';

const columns = [
  { title: '协议号', dataIndex: 'phone' },
  { title: '状态', key: 'status', width: 100 },
  { title: '文件大小', key: 'fsize', width: 110, className: 'hide-mobile' },
  { title: '最后检测', key: 'lastcheck', width: 180, customRender: ({ text }: any) => formatDateTime(text), className: 'hide-mobile' },
  { title: '上传时间', dataIndex: 'createdAt', width: 180, customRender: ({ text }: any) => formatDateTime(text), className: 'hide-mobile' },
  { title: '操作', key: 'action', width: 220 },
];
const list = ref<any[]>([]); const loading = ref(false); const batchLoading = ref(false);
const addVisible = ref(false);
const phoneVisible = ref(false); const codeVisible = ref(false); const qrVisible = ref(false);
const phone = ref(''); const code = ref(''); const password = ref('');
const sessionKey = ref('');
const qrToken = ref(''); const qrUrl = ref(''); const qrImage = ref('');
const qrStage = ref('waiting'); const qrLoading = ref(false); const qrPassword = ref('');
const qrTip = ref('请用 Telegram 手机端扫码');
let qrTimer: any = null;
const importVisible = ref(false); const importPhone = ref('');
const importFile = ref<File | null>(null); const importFileName = ref('');
const transferVisible = ref(false);
const transferUserId = ref<number | null>(null);
const transferId = ref(0);
const users = ref<any[]>([]);

async function load() {
  loading.value = true;
  try { list.value = await tgApi.accounts(); } finally { loading.value = false; }
}
async function refreshAll() {
  batchLoading.value = true;
  try {
    for (const a of list.value) { try { await tgApi.refreshAccount(a.id); } catch {} }
    message.success('批量检测完成'); load();
  } finally { batchLoading.value = false; }
}
async function startPhone() {
  if (!phone.value) { message.error('请填写手机号'); return; }
  try {
    const r: any = await tgApi.loginStart(phone.value);
    sessionKey.value = r.sessionKey;
    phoneVisible.value = false; codeVisible.value = true;
    message.success('验证码已发送');
  } catch (e: any) { message.error(e.message || '发送验证码失败'); }
}
async function verifyCode() {
  if (!code.value) { message.error('请输入验证码'); return; }
  try {
    await tgApi.loginVerify(sessionKey.value, code.value, password.value);
    message.success('登录成功'); codeVisible.value = false; load();
  } catch (e: any) { message.error(e.message || '登录失败，请检查验证码'); }
}
async function openQr() {
  qrVisible.value = true; qrLoading.value = true; qrStage.value = 'waiting';
  qrPassword.value = ''; stopQrPoll();
  try {
    const r: any = await tgApi.qrLogin();
    qrToken.value = r.qrToken; qrUrl.value = r.url; qrImage.value = r.qrImage || '';
    qrTip.value = '请用 Telegram 手机端扫码';
    qrTimer = setInterval(() => pollQr(false), 3000);
  } catch (e: any) {
    message.error(e.message || '生成二维码失败');
    qrVisible.value = false;
  } finally { qrLoading.value = false; }
}
async function pollQr(withPassword: boolean) {
  try {
    const r: any = await tgApi.qrStatus(qrToken.value, withPassword ? qrPassword.value : '');
    if (r.stage === 'done') {
      stopQrPoll(); qrVisible.value = false;
      message.success('扫码登录成功'); load();
    } else if (r.stage === 'expired') {
      stopQrPoll(); qrStage.value = 'expired';
    } else if (r.stage === 'need_password') {
      qrStage.value = 'need_password';
    } else {
      qrTip.value = '等待扫码…';
    }
  } catch (e: any) { message.error(e.message || '轮询失败'); }
}
function stopQrPoll() { if (qrTimer) { clearInterval(qrTimer); qrTimer = null; } }
function onSessionFile(e: any) {
  const f = e.target.files?.[0];
  if (f) { importFile.value = f; importFileName.value = f.name; }
}
async function doImport() {
  if (!importPhone.value) { message.error('请填写手机号'); return; }
  if (!importFile.value) { message.error('请选择 .session 文件'); return; }
  try {
    const r: any = await tgApi.importSession(importPhone.value, importFile.value);
    message.success(r.msg || '导入成功');
    importVisible.value = false; importPhone.value = ''; importFile.value = null; importFileName.value = '';
    load();
  } catch (e: any) { message.error(e.message || '导入失败'); }
}
onUnmounted(stopQrPoll);
async function refresh(id: number) {
  try { await tgApi.refreshAccount(id); message.success('状态已刷新'); load(); }
  catch (e: any) { message.error(e.message); }
}
async function remove(id: number) {
  try { await tgApi.removeAccount(id); message.success('已删除'); load(); }
  catch (e: any) { message.error(e.message); }
}
async function openTransfer(record: any) {
  transferId.value = record.id; transferUserId.value = record.userId || null;
  try { users.value = await userApi.list(); } catch { users.value = []; }
  transferVisible.value = true;
}
async function doTransfer() {
  try {
    const r: any = await tgApi.transferAccount(transferId.value, transferUserId.value);
    message.success(r.msg || '已转移'); transferVisible.value = false; load();
  } catch (e: any) { message.error(e.message); }
}
onMounted(load);
</script>
