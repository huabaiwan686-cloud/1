<template>
  <div class="page">
    <div class="page-title">频道配置</div>
    <div class="page-subtitle">管理推送频道与全局抠图模式</div>
    <a-card title="全局抠图模式" class="page-card" style="margin-top: 16px">
      <a-space>
        <a-switch v-model:checked="gm.enabled" @change="saveGm" />
        <span class="desc-text">开启后，所有发往频道的资料按所选背景自动抠图后发送；服务器只保留原图，处理图不留存，每次循环重新处理</span>
      </a-space>
      <div class="mt-12">
        <a-select v-model:value="gm.background_id" placeholder="选择抠图背景素材（先选背景再开开关）" style="width: 320px" @change="saveGm">
          <a-select-option v-for="m in materials" :key="m.id" :value="m.id">{{ m.name }}</a-select-option>
        </a-select>
        <span class="hint" style="margin-left: 12px">每次上架/循环推送时实时处理，按次扣额度（重复图不重复扣）</span>
      </div>
    </a-card>
    <a-card title="个人水印设置" class="page-card">
      <div class="desc-text mb-12">开启后，你发布的每张图片都会自动叠加水印（视频不加）。这是你个人的设置，只影响你自己发布的内容。</div>
      <div>
        <div class="form-row">
          <a-switch v-model:checked="wm.enabled" />
          <span>启用水印</span>
        </div>
        <div class="form-row">
          <span class="form-label">水印类型</span>
          <a-radio-group v-model:value="wm.type">
            <a-radio value="text">文字水印</a-radio>
            <a-radio value="qr">二维码水印</a-radio>
          </a-radio-group>
        </div>
        <div class="form-row">
          <span class="form-label">{{ wm.type === 'qr' ? '二维码内容' : '水印文字' }}</span>
          <a-input v-model:value="wm.content" :placeholder="wm.type === 'qr' ? '二维码数据（链接或文本）' : '例如：@我的频道'" style="width: 320px" />
        </div>
        <div class="form-row">
          <span class="form-label">水印位置</span>
          <a-select v-model:value="wm.position" style="width: 160px">
            <a-select-option value="top-left">左上</a-select-option>
            <a-select-option value="top-right">右上</a-select-option>
            <a-select-option value="bottom-left">左下</a-select-option>
            <a-select-option value="bottom-right">右下</a-select-option>
            <a-select-option value="center">居中</a-select-option>
          </a-select>
          <template v-if="wm.type === 'text'">
            <span class="form-label" style="width: auto; margin-left: 16px">不透明度</span>
            <a-slider v-model:value="wm.opacity" :min="10" :max="100" style="width: 160px" />
            <span>{{ wm.opacity }}%</span>
          </template>
          <template v-else>
            <span class="form-label" style="width: auto; margin-left: 16px">二维码尺寸</span>
            <a-input-number v-model:value="wm.qr_size" :min="48" :max="300" style="width: 100px" />
          </template>
        </div>
        <div class="form-row">
          <a-button type="primary" @click="saveWm">保存水印设置</a-button>
          <a-button @click="previewWm">预览效果</a-button>
        </div>
        <div v-if="wmPreview" class="mt-12">
          <div class="hint mb-8">预览效果：</div>
          <img :src="wmPreview" style="max-width: 400px; border: 1px solid #eee; border-radius: 4px" />
        </div>
      </div>
    </a-card>
    <div class="page-toolbar">
      <a-button type="primary" @click="openEditor()">添加频道</a-button>
      <a-radio-group v-model:value="filter" @change="load">
        <a-radio-button value="all">全部</a-radio-button>
        <a-radio-button :value="true">上架中</a-radio-button>
        <a-radio-button :value="false">已下架</a-radio-button>
      </a-radio-group>
    </div>
    <a-table :columns="columns" :data-source="list" row-key="id" :loading="loading" :scroll="{ x: 'max-content' }">
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'status'">
          <a-tag :color="record.isActive ? 'green' : 'default'">{{ record.isActive ? '上架' : '下架' }}</a-tag>
        </template>
        <template v-else-if="column.key === 'bot'">
          <span>{{ botName(record.botId) }}</span>
        </template>
        <template v-else-if="column.key === 'action'">
          <a-space class="table-actions">
            <a @click="openEditor(record)">编辑</a>
            <a @click="check(record.id)">检测</a>
            <a @click="pushAll(record.id)">全量推送</a>
            <a-popconfirm title="清空该频道的待发送定时队列？" @confirm="clearQueue(record.id)"><a>清空队列</a></a-popconfirm>
            <a-popconfirm title="确认删除？" @confirm="remove(record.id)"><a>删除</a></a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>
    <a-modal class="modal-form" v-model:open="visible" title="频道配置" @ok="save">
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
          </a-select>
        </a-form-item>
        <a-space>
          <a-checkbox v-model:checked="editing.is_active">上架</a-checkbox>
          <a-checkbox v-model:checked="editing.is_default">默认选中</a-checkbox>
        </a-space>
      </a-form>
    </a-modal>

    <a-card title="智能频道推荐规则" class="mt-16">
      <div class="desc-text mb-12">按关键词/标签/城市/省份/价格自动匹配发布频道；无命中时回退默认频道。正文标注行格式：城市：北京 / 省份：广东 / 价格：￥500</div>
      <a-button type="primary" @click="openRuleEditor()" class="mb-12">添加规则</a-button>
      <a-table :columns="ruleColumns" :data-source="rules" row-key="id" :loading="ruleLoading" size="small">
        <template #bodyCell="{ column, record }">
          <a-tag v-if="column.key === 'enabled'" :color="record.enabled ? 'green' : 'default'">{{ record.enabled ? '启用' : '禁用' }}</a-tag>
          <a-space v-else-if="column.key === 'raction'">
            <a-popconfirm title="确认删除？" @confirm="removeRule(record.id)"><a>删除</a></a-popconfirm>
          </a-space>
        </template>
      </a-table>
    </a-card>
    <a-modal class="modal-form" v-model:open="ruleVisible" title="推荐规则" @ok="saveRule">
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
// 个人水印设置（P1-13/P1-14）
const wm = reactive<any>({ type: 'text', content: '', position: 'bottom-right', opacity: 70, qr_size: 100, enabled: false });
const wmPreview = ref('');

async function loadWm() {
  try {
    const s: any = await mediaApi.watermarkSetting();
    Object.assign(wm, s);
  } catch (e: any) { /* 忽略 */ }
}
async function saveWm() {
  if (wm.enabled && !wm.content.trim()) {
    message.warning('启用水印前请填写水印内容');
    return;
  }
  try {
    await mediaApi.setWatermarkSetting(wm);
    message.success('水印设置已保存');
  } catch (e: any) { message.error(e.message); }
}
async function previewWm() {
  if (!wm.content.trim()) { message.warning('请先填写水印内容'); return; }
  // 用一张空白测试图做预览
  const canvas = document.createElement('canvas');
  canvas.width = 600; canvas.height = 400;
  const ctx = canvas.getContext('2d')!;
  const grad = ctx.createLinearGradient(0, 0, 600, 400);
  grad.addColorStop(0, '#a8d8ea'); grad.addColorStop(1, '#f6d5f7');
  ctx.fillStyle = grad; ctx.fillRect(0, 0, 600, 400);
  canvas.toBlob(async (blob) => {
    if (!blob) return;
    try {
      const r: any = await mediaApi.watermarkPreview(new File([blob], 'preview.png', { type: 'image/png' }), {
        type: wm.type, content: wm.content, position: wm.position, opacity: wm.opacity, qr_size: wm.qr_size,
      });
      wmPreview.value = r.preview;
    } catch (e: any) { message.error(e.message); }
  }, 'image/png');
}

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
onMounted(() => { load(); loadRules(); loadWm(); });
</script>
