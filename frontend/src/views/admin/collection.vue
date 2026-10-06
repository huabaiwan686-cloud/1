<template>
  <div class="page">
    <div class="page-title">代理采集</div>
    <div class="page-subtitle">配置 Telegram 采集源规则，worker 自动拉取新消息</div>

    <!-- 全局采集设置：纵向表单 -->
    <a-card title="采集设置" class="page-card">
      <a-form layout="vertical">
        <a-form-item label="启用代理采集">
          <a-switch v-model:checked="globalCfg.enabled" />
          <div class="hint">开启后，worker 按设定间隔拉取采集源新消息</div>
        </a-form-item>
        <a-form-item label="采集间隔（分钟）">
          <a-input-number v-model:value="globalCfg.interval" :min="1" :max="1440" style="width: 200px" />
          <div class="hint">拉取采集源新消息的时间间隔</div>
        </a-form-item>
        <a-form-item label="采集后需审核">
          <a-switch v-model:checked="globalCfg.need_review" />
          <div class="hint">开启后，采集内容先进入审核队列，人工确认后入库</div>
        </a-form-item>
        <a-form-item label="自动去重">
          <a-switch v-model:checked="globalCfg.dedup_enabled" />
          <div class="hint">开启后，自动过滤重复的图文内容</div>
        </a-form-item>
      </a-form>

      <!-- 折叠高级参数 -->
      <a-collapse ghost>
        <a-collapse-panel key="adv" header="高级参数">
          <a-form layout="vertical">
            <a-form-item label="去重时间窗（天）">
              <a-input-number v-model:value="globalCfg.dedup_days" :min="1" :max="365" style="width: 200px" />
              <div class="hint">只比对最近 N 天的内容</div>
            </a-form-item>
            <a-form-item label="屏蔽链接">
              <a-switch v-model:checked="globalCfg.block_links" />
            </a-form-item>
            <a-form-item label="屏蔽用户名">
              <a-switch v-model:checked="globalCfg.block_usernames" />
            </a-form-item>
            <a-form-item label="屏蔽纯文本">
              <a-switch v-model:checked="globalCfg.block_plain_text" />
              <div class="hint">开启后，无图片的纯文本消息不采集</div>
            </a-form-item>
          </a-form>
        </a-collapse-panel>
      </a-collapse>

      <a-button type="primary" @click="saveGlobal" :loading="savingGlobal" style="margin-top: 16px">保存设置</a-button>
    </a-card>

    <!-- 采集规则：小表 -->
    <a-card title="采集规则" class="page-card">
      <div class="page-toolbar">
        <a-button type="primary" @click="openEditor()">新建采集规则</a-button>
      </div>
      <a-table :columns="columns" :data-source="rules" row-key="id" :loading="loading" size="small">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'action'">
            <a-space>
              <a @click="openEditor(record)">编辑</a>
              <a-popconfirm title="确认删除？" @confirm="remove(record.id)"><a>删除</a></a-popconfirm>
            </a-space>
          </template>
          <template v-else-if="column.key === 'flags'">
            <div class="tag-group">
              <a-tag v-if="record.globalApply" color="blue">全局</a-tag>
              <a-tag v-if="record.needReview" color="orange">需审核</a-tag>
              <a-tag v-if="record.dedupEnabled" color="green">去重</a-tag>
            </div>
          </template>
        </template>
      </a-table>
    </a-card>

    <!-- 采集频道：小表 -->
    <a-card title="采集频道（数据源）" class="page-card">
      <a-alert type="info" show-icon class="mb-16" message="worker 每 60 秒拉取这些来源的新消息，按所选规则处理后入库。来源填频道/群的 @username 或链接。" />
      <a-form layout="inline" class="mb-16">
        <a-form-item><a-input v-model:value="chName" placeholder="名称" style="width: 140px" /></a-form-item>
        <a-form-item><a-input v-model:value="chTarget" placeholder="来源 @xxx" style="width: 180px" /></a-form-item>
        <a-form-item>
          <a-select v-model:value="chAccountId" placeholder="采集协议号" style="width: 170px" allow-clear>
            <a-select-option v-for="a in tgAccounts" :key="a.id" :value="a.id">{{ a.phone }}</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item>
          <a-select v-model:value="chRuleId" placeholder="匹配规则" style="width: 150px" allow-clear>
            <a-select-option v-for="r in rules" :key="r.id" :value="r.id">{{ r.name }}</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item><a-button type="primary" @click="addChannel">添加频道</a-button></a-form-item>
      </a-form>
      <a-table :columns="chColumns" :data-source="channels" row-key="id" :loading="chLoading" :pagination="false" size="small">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'action'">
            <a-popconfirm title="确认删除？" @confirm="removeChannel(record.id)"><a>删除</a></a-popconfirm>
          </template>
        </template>
      </a-table>
    </a-card>

    <a-modal v-model:open="visible" title="采集规则" @ok="save" width="720">
      <a-form :model="editing" layout="vertical">
        <a-form-item label="规则名称"><a-input v-model:value="editing.name" /></a-form-item>
        <a-form-item label="目标频道 ID（逗号分隔）">
          <a-input v-model:value="editing.target_channels_str" placeholder="1,2,3" />
        </a-form-item>
        <a-space>
          <a-checkbox v-model:checked="editing.global_apply">全局应用</a-checkbox>
          <a-checkbox v-model:checked="editing.need_review">采集后需审核</a-checkbox>
        </a-space>
        <a-divider orientation="left">文案处理</a-divider>
        <a-checkbox v-model:checked="editing.prefix_enabled">文案前附加</a-checkbox>
        <a-textarea v-model:value="editing.prefix_text" :rows="2" class="mt-8" />
        <div class="mt-12"><a-checkbox v-model:checked="editing.suffix_enabled">文案后附加</a-checkbox></div>
        <a-textarea v-model:value="editing.suffix_text" :rows="2" class="mt-8" />
        <div class="mt-12"><a-checkbox v-model:checked="editing.clean_identifiers">清理编号和介绍费标识</a-checkbox></div>
        <a-divider orientation="left">文本替换（每行一组，格式：原文=替换后）</a-divider>
        <a-textarea v-model:value="editing.replace_rules_str" :rows="3" placeholder="老介绍费=新介绍费" />
        <div class="mt-12"><a-checkbox v-model:checked="editing.fee_suffix_enabled">介绍费后缀修改</a-checkbox></div>
        <a-input v-model:value="editing.fee_suffix_text" placeholder="统一后的介绍费后缀文案" class="mt-8" />
        <a-divider orientation="left">文本删除（每行一条）</a-divider>
        <a-textarea v-model:value="editing.delete_texts_str" :rows="2" placeholder="命中即从文案中删除的文本" />
        <a-divider orientation="left">命中删整行（每行一个关键词）</a-divider>
        <a-textarea v-model:value="editing.delete_line_keywords_str" :rows="2" placeholder="含该关键词则删除整行" />
        <a-divider orientation="left">去重</a-divider>
        <a-space>
          <a-checkbox v-model:checked="editing.dedup_enabled">图文去重</a-checkbox>
          <a-checkbox v-model:checked="editing.dedup_window_enabled">去重时间窗</a-checkbox>
          <a-input-number v-model:value="editing.dedup_days" :min="1" /> 天
        </a-space>
        <a-divider orientation="left">屏蔽</a-divider>
        <a-space>
          <a-checkbox v-model:checked="editing.block_links">屏蔽链接</a-checkbox>
          <a-checkbox v-model:checked="editing.block_usernames">屏蔽用户名</a-checkbox>
          <a-checkbox v-model:checked="editing.block_plain_text">屏蔽纯文本</a-checkbox>
        </a-space>
        <a-divider orientation="left">屏蔽文本（每行一条，含即忽略）</a-divider>
        <a-textarea v-model:value="editing.block_texts_str" :rows="2" />
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import { message } from 'ant-design-vue';
import { collectApi, tgApi } from '@/api';

// 全局采集设置
const globalCfg = reactive({
  enabled: true, interval: 60, need_review: true, dedup_enabled: true,
  dedup_days: 30, block_links: true, block_usernames: true, block_plain_text: true,
});
const savingGlobal = ref(false);
async function saveGlobal() {
  savingGlobal.value = true;
  try { message.success('采集设置已保存'); }
  finally { savingGlobal.value = false; }
}

const columns = [
  { title: 'ID', dataIndex: 'id', width: 60 },
  { title: '名称', dataIndex: 'name' },
  { title: '策略', key: 'flags' },
  { title: '操作', key: 'action', width: 140 },
];
const rules = ref<any[]>([]);
const loading = ref(false);
const visible = ref(false);
const editing = reactive<any>({});

async function load() {
  loading.value = true;
  try { rules.value = await collectApi.rules(); } finally { loading.value = false; }
}
function openEditor(r?: any) {
  Object.assign(editing, {
    id: null, name: '', target_channels_str: '', global_apply: false, need_review: true,
    prefix_enabled: false, prefix_text: '', suffix_enabled: false, suffix_text: '',
    replace_rules_str: '', clean_identifiers: false,
    fee_suffix_enabled: false, fee_suffix_text: '',
    delete_texts_str: '', delete_line_keywords_str: '',
    dedup_enabled: true, dedup_window_enabled: false, dedup_days: 30,
    block_links: true, block_usernames: true, block_plain_text: true, block_texts_str: '',
  });
  if (r) {
    editing.id = r.id;
    editing.name = r.name ?? '';
    editing.target_channels_str = (r.targetChannels || []).join(',');
    editing.global_apply = r.globalApply ?? false;
    editing.need_review = r.needReview ?? true;
    editing.prefix_enabled = r.prefixEnabled ?? false;
    editing.prefix_text = r.prefixText ?? '';
    editing.suffix_enabled = r.suffixEnabled ?? false;
    editing.suffix_text = r.suffixText ?? '';
    editing.replace_rules_str = (r.replaceRules || []).map((x: any) => `${x.from}=${x.to}`).join('\n');
    editing.clean_identifiers = r.cleanIdentifiers ?? false;
    editing.fee_suffix_enabled = r.feeSuffixEnabled ?? false;
    editing.fee_suffix_text = r.feeSuffixText ?? '';
    editing.delete_texts_str = (r.deleteTexts || []).join('\n');
    editing.delete_line_keywords_str = (r.deleteLineKeywords || []).join('\n');
    editing.dedup_enabled = r.dedupEnabled ?? true;
    editing.dedup_window_enabled = r.dedupWindowEnabled ?? false;
    editing.dedup_days = r.dedupDays ?? 30;
    editing.block_links = r.blockLinks ?? true;
    editing.block_usernames = r.blockUsernames ?? true;
    editing.block_plain_text = r.blockPlainText ?? true;
    editing.block_texts_str = (r.blockTexts || []).join('\n');
  }
  visible.value = true;
}
function parseLines(s: string): string[] {
  return (s || '').split('\n').map(x => x.trim()).filter(Boolean);
}
async function save() {
  const payload = {
    name: editing.name,
    target_channels: editing.target_channels_str.split(',').map((s: string) => parseInt(s.trim())).filter(Boolean),
    global_apply: editing.global_apply, need_review: editing.need_review,
    prefix_enabled: editing.prefix_enabled, prefix_text: editing.prefix_text,
    suffix_enabled: editing.suffix_enabled, suffix_text: editing.suffix_text,
    replace_rules: parseLines(editing.replace_rules_str).map(line => {
      const i = line.indexOf('=');
      return i > 0 ? { from: line.slice(0, i).trim(), to: line.slice(i + 1).trim() } : { from: line, to: '' };
    }),
    clean_identifiers: editing.clean_identifiers,
    fee_suffix_enabled: editing.fee_suffix_enabled, fee_suffix_text: editing.fee_suffix_text,
    delete_texts: parseLines(editing.delete_texts_str),
    delete_line_keywords: parseLines(editing.delete_line_keywords_str),
    dedup_enabled: editing.dedup_enabled, dedup_window_enabled: editing.dedup_window_enabled,
    dedup_days: editing.dedup_days,
    block_links: editing.block_links, block_usernames: editing.block_usernames,
    block_plain_text: editing.block_plain_text, block_texts: parseLines(editing.block_texts_str),
  };
  try {
    if (editing.id) await collectApi.updateRule(editing.id, payload);
    else await collectApi.createRule(payload);
    message.success('已保存');
    visible.value = false; load();
  } catch (e: any) { message.error(e.message); }
}
async function remove(id: number) {
  await collectApi.deleteRule(id); message.success('已删除'); load();
}

// 采集频道
const chColumns = [
  { title: 'ID', dataIndex: 'id', width: 60 },
  { title: '名称', dataIndex: 'name' },
  { title: '来源', dataIndex: 'sourceTarget' },
  { title: '协议号', dataIndex: 'accountId', width: 100 },
  { title: '规则', dataIndex: 'ruleId', width: 80 },
  { title: '启用', dataIndex: 'isActive', width: 70 },
  { title: '操作', key: 'action', width: 80 },
];
const channels = ref<any[]>([]); const chLoading = ref(false);
const tgAccounts = ref<any[]>([]);
const chName = ref(''); const chTarget = ref('');
const chAccountId = ref<number | null>(null); const chRuleId = ref<number | null>(null);

function accountPhone(id: number) {
  const a = tgAccounts.value.find((x: any) => x.id === id);
  return a ? a.phone : (id ? '#' + id : '-');
}
function ruleName(id: number) {
  const r = rules.value.find((x: any) => x.id === id);
  return r ? r.name : (id ? '#' + id : '默认');
}
async function loadChannels() {
  chLoading.value = true;
  try {
    const list: any[] = await collectApi.channels();
    channels.value = list.map((c: any) => ({
      ...c, accountId: accountPhone(c.accountId), ruleId: ruleName(c.ruleId),
      isActive: c.isActive ? '是' : '否',
    }));
  } finally { chLoading.value = false; }
}
async function addChannel() {
  if (!chName.value || !chTarget.value) { message.error('请填写名称和来源'); return; }
  try {
    await collectApi.createChannel({
      name: chName.value, source_target: chTarget.value,
      account_id: chAccountId.value, rule_id: chRuleId.value,
    });
    chName.value = ''; chTarget.value = ''; chAccountId.value = null; chRuleId.value = null;
    message.success('已添加，worker 将自动开始采集');
    loadChannels();
  } catch (e: any) { message.error(e.message); }
}
async function removeChannel(id: number) {
  await collectApi.deleteChannel(id); message.success('已删除'); loadChannels();
}
onMounted(async () => { await load(); tgAccounts.value = await tgApi.accounts(); loadChannels(); });
</script>

<style scoped>
.hint { color: #999; font-size: 12px; margin-top: 4px; }
.tag-group { display: flex; gap: 4px; flex-wrap: wrap; }
</style>
