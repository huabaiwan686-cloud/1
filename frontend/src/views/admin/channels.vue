<template>
  <div>
    <a-card title="全局抠图模式" style="margin-bottom: 16px">
      <a-space>
        <a-switch v-model:checked="gm.enabled" @change="saveGm" />
        <span style="color: #666">开启后，所有发往频道的资料按所选背景自动抠图后发送；服务器只保留原图，处理图不留存，每次循环重新处理</span>
      </a-space>
      <div style="margin-top: 12px">
        <a-select v-model:value="gm.background_id" placeholder="选择抠图背景素材（先选背景再开开关）" style="width: 320px" @change="saveGm">
          <a-select-option v-for="m in materials" :key="m.id" :value="m.id">{{ m.name }}</a-select-option>
        </a-select>
        <span style="color: #999; margin-left: 12px">每次上架/循环推送时实时处理，按次扣额度（重复图不重复扣）</span>
      </div>
    </a-card>
    <a-space style="margin-bottom: 16px">
      <a-button type="primary" @click="openEditor()">添加频道</a-button>
      <a-radio-group v-model:value="filter" @change="load">
        <a-radio-button value="all">全部</a-radio-button>
        <a-radio-button :value="true">上架中</a-radio-button>
        <a-radio-button :value="false">已下架</a-radio-button>
      </a-radio-group>
    </a-space>
    <a-table :columns="columns" :data-source="list" row-key="id" :loading="loading">
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'status'">
          <a-tag :color="record.isActive ? 'green' : 'default'">{{ record.isActive ? '上架' : '下架' }}</a-tag>
        </template>
        <template v-else-if="column.key === 'bot'">
          <span>{{ botName(record.botId) }}</span>
        </template>
        <template v-else-if="column.key === 'action'">
          <a-space>
            <a @click="openEditor(record)">编辑</a>
            <a @click="check(record.id)">检测</a>
            <a @click="pushAll(record.id)">全量推送</a>
            <a-popconfirm title="清空该频道的待发送定时队列？" @confirm="clearQueue(record.id)"><a>清空队列</a></a-popconfirm>
            <a-popconfirm title="确认删除？" @confirm="remove(record.id)"><a>删除</a></a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>
    <a-modal v-model:open="visible" title="频道配置" @ok="save">
      <a-form :model="editing" layout="vertical">
        <a-form-item label="频道名称"><a-input v-model:value="editing.name" /></a-form-item>
        <a-form-item label="用户名"><a-input v-model:value="editing.username" placeholder="@xxx（公开频道）" /></a-form-item>
        <a-form-item label="频道 ID（私有频道填，如 -1001234567890，优先于用户名）">
          <a-input v-model:value="editing.tg_channel_id" placeholder="-100..." />
        </a-form-item>
        <a-form-item label="推送机器人（需为该频道管理员）">
          <a-select v-model:value="editing.bot_id" placeholder="选择机器人" style="width: 100%" allow-clear>
            <a-select-option v-for="b in botTokens" :key="b.id" :value="b.id">@{{ b.username || b.name }}</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="防扫图模式">
          <a-select v-model:value="editing.anti_scan_mode">
            <a-select-option value="original">原图</a-select-option>
            <a-select-option value="replace_bg">替换背景</a-select-option>
            <a-select-option value="blur_bg">背景虚化（人像模式）</a-select-option>
            <a-select-option value="light_perturb">轻量随机扰动</a-select-option>
          </a-select>
        </a-form-item>
        <a-space>
          <a-checkbox v-model:checked="editing.is_active">上架</a-checkbox>
          <a-checkbox v-model:checked="editing.is_default">默认选中</a-checkbox>
        </a-space>
      </a-form>
    </a-modal>

    <a-card title="智能频道推荐规则" style="margin-top: 16px">
      <div style="color: #666; margin-bottom: 12px">按关键词/标签/城市/省份/价格自动匹配发布频道；无命中时回退默认频道。正文标注行格式：城市：北京 / 省份：广东 / 价格：￥500</div>
      <a-button type="primary" @click="openRuleEditor()" style="margin-bottom: 12px">添加规则</a-button>
      <a-table :columns="ruleColumns" :data-source="rules" row-key="id" :loading="ruleLoading" size="small">
        <template #bodyCell="{ column, record }">
          <a-tag v-if="column.key === 'enabled'" :color="record.enabled ? 'green' : 'default'">{{ record.enabled ? '启用' : '禁用' }}</a-tag>
          <a-space v-else-if="column.key === 'raction'">
            <a-popconfirm title="确认删除？" @confirm="removeRule(record.id)"><a>删除</a></a-popconfirm>
          </a-space>
        </template>
      </a-table>
    </a-card>
    <a-modal v-model:open="ruleVisible" title="推荐规则" @ok="saveRule">
      <a-form :model="ruleForm" layout="vertical">
        <a-form-item label="规则名称"><a-input v-model:value="ruleForm.name" /></a-form-item>
        <a-form-item label="关键词（标题+正文包含）"><a-input v-model:value="ruleForm.keyword" /></a-form-item>
        <a-form-item label="标签"><a-input v-model:value="ruleForm.tag" /></a-form-item>
        <a-row :gutter="12">
          <a-col :span="12"><a-form-item label="城市"><a-input v-model:value="ruleForm.city" placeholder="如：北京" /></a-form-item></a-col>
          <a-col :span="12"><a-form-item label="省份"><a-input v-model:value="ruleForm.province" placeholder="如：广东" /></a-form-item></a-col>
        </a-row>
        <a-row :gutter="12">
          <a-col :span="12"><a-form-item label="最低价格"><a-input-number v-model:value="ruleForm.price_min" style="width: 100%" /></a-form-item></a-col>
          <a-col :span="12"><a-form-item label="最高价格"><a-input-number v-model:value="ruleForm.price_max" style="width: 100%" /></a-form-item></a-col>
        </a-row>
        <a-form-item label="匹配的频道"><a-select v-model:value="ruleForm.channel_ids" mode="multiple" style="width: 100%">
          <a-select-option v-for="c in list" :key="c.id" :value="c.id">{{ c.name }}</a-select-option>
        </a-select></a-form-item>
        <a-checkbox v-model:checked="ruleForm.enabled">启用</a-checkbox>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import { message } from 'ant-design-vue';
import { channelApi, mediaApi, botApi } from '@/api';

const columns = [
  { title: 'ID', dataIndex: 'id', width: 60 },
  { title: '名称', dataIndex: 'name' },
  { title: '用户名', dataIndex: 'username' },
  { title: '推送机器人', key: 'bot', width: 150 },
  { title: '防扫图', dataIndex: 'antiScanMode', width: 120 },
  { title: '状态', key: 'status', width: 80 },
  { title: '操作', key: 'action', width: 260 },
];
const list = ref<any[]>([]); const loading = ref(false);
const filter = ref<any>('all'); const visible = ref(false);
const editing = reactive<any>({});
const gm = reactive<any>({ enabled: false, background_id: null });
const materials = ref<any[]>([]);
const botTokens = ref<any[]>([]);

function botName(id: number) {
  const b = botTokens.value.find((x: any) => x.id === id);
  return b ? '@' + (b.username || b.name) : (id ? '#' + id : '未绑定');
}

async function load() {
  loading.value = true;
  try {
    list.value = await channelApi.list(filter.value === 'all' ? undefined : filter.value);
    const g: any = await mediaApi.mattingGlobal();
    gm.enabled = g.enabled; gm.background_id = g.backgroundId;
    materials.value = await mediaApi.materials();
    botTokens.value = await botApi.tokens();
  } finally { loading.value = false; }
}
async function saveGm() {
  if (gm.enabled && !gm.background_id) {
    message.warning('请先选择抠图背景素材，再开启全局抠图');
    gm.enabled = false;
    return;
  }
  try {
    await mediaApi.setMattingGlobal({ enabled: gm.enabled, background_id: gm.background_id });
    message.success('全局抠图模式已' + (gm.enabled ? '开启' : '关闭'));
  } catch (e: any) { message.error(e.message); load(); }
}
function openEditor(r?: any) {
  Object.assign(editing, { name: '', username: '', tg_channel_id: '', anti_scan_mode: 'original', is_active: true, is_default: false, bot_id: null });
  if (r) {
    // 后端返回 camelCase，表单用 snake_case，逐个映射避免编辑时静默重置
    editing.id = r.id;
    editing.name = r.name ?? '';
    editing.username = r.username ?? '';
    editing.tg_channel_id = r.tgChannelId ?? '';
    editing.anti_scan_mode = r.antiScanMode ?? 'original';
    editing.is_active = r.isActive ?? true;
    editing.is_default = r.isDefault ?? false;
    editing.bot_id = r.botId ?? null;
  }
  visible.value = true;
}
async function save() {
  try {
    if (editing.id) await channelApi.update(editing.id, editing);
    else await channelApi.create(editing);
    message.success('已保存'); visible.value = false; load();
  } catch (e: any) { message.error(e.message); }
}
async function remove(id: number) { await channelApi.remove(id); message.success('已删除'); load(); }
async function check(id: number) { const r: any = await channelApi.check(id); message.info(r.msg); }
async function pushAll(id: number) { const r: any = await channelApi.pushAll(id); message.success(r.msg || '全量推送完成'); }
async function clearQueue(id: number) { const r: any = await channelApi.clearQueue(id); message.success(r.msg || '队列已清空'); }
// 智能推荐规则
const ruleColumns = [
  { title: 'ID', dataIndex: 'id', width: 50 },
  { title: '规则', dataIndex: 'name' },
  { title: '关键词', dataIndex: 'keyword' },
  { title: '标签', dataIndex: 'tag' },
  { title: '城市', dataIndex: 'city' },
  { title: '状态', key: 'enabled', width: 70 },
  { title: '操作', key: 'raction', width: 80 },
];
const rules = ref<any[]>([]); const ruleLoading = ref(false);
const ruleVisible = ref(false);
const ruleForm = reactive({ name: '', keyword: '', tag: '', city: '', province: '', price_min: null, price_max: null, channel_ids: [], enabled: true });
async function loadRules() {
  ruleLoading.value = true;
  try { rules.value = await channelApi.publishRules(); } finally { ruleLoading.value = false; }
}
function openRuleEditor() {
  Object.assign(ruleForm, { name: '', keyword: '', tag: '', city: '', province: '', price_min: null, price_max: null, channel_ids: [], enabled: true });
  ruleVisible.value = true;
}
async function saveRule() {
  try { await channelApi.createPublishRule(ruleForm); message.success('已保存'); ruleVisible.value = false; loadRules(); }
  catch (e: any) { message.error(e.message); }
}
async function removeRule(id: number) { await channelApi.deletePublishRule(id); message.success('已删除'); loadRules(); }
onMounted(() => { load(); loadRules(); });
</script>
