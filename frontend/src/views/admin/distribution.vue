<template>
  <div>
    <div class="aq-header">
      <div class="aq-title">分发规则</div>
      <p class="aq-desc">按关键词、标签、城市等条件自动匹配发布频道</p>
    </div>
    <a-tabs>
      <a-tab-pane key="keyword" tab="关键词规则">
        <a-card :bordered="true">
          <a-form :model="form" layout="vertical" style="max-width: 640px">
            <a-form-item label="规则名称" :rules="[{ required: true, message: '请输入规则名称' }]">
              <a-input v-model:value="form.name" placeholder="如：北京高端线" />
            </a-form-item>
            <a-form-item label="关键词（标题+正文包含）">
              <a-input v-model:value="form.keyword" placeholder="多个关键词用逗号分隔" />
            </a-form-item>
            <a-form-item label="标签匹配">
              <a-select v-model:value="form.tag" placeholder="选择标签" allow-clear style="width: 100%">
                <a-select-option v-for="t in tags" :key="t.id" :value="t.name">{{ t.name }}</a-select-option>
              </a-select>
            </a-form-item>
            <a-form-item label="城市">
              <a-input v-model:value="form.city" placeholder="如：北京" />
              <div class="aq-tip">匹配正文"城市：北京"标注行</div>
            </a-form-item>
            <a-form-item>
              <a-button type="primary" @click="save" :loading="saving">保存规则</a-button>
            </a-form-item>
          </a-form>
        </a-card>
        <a-card :bordered="true" title="已有规则" style="margin-top: 16px">
          <a-table :columns="columns" :data-source="rules" row-key="id" :loading="loading" :pagination="false">
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'enabled'">
                <a-tag :color="record.enabled ? 'green' : 'default'">{{ record.enabled ? '启用' : '停用' }}</a-tag>
              </template>
              <template v-if="column.key === 'action'">
                <a-popconfirm title="确认删除该规则？" @confirm="removeRule(record.id)">
                  <a>删除</a>
                </a-popconfirm>
              </template>
            </template>
          </a-table>
        </a-card>
      </a-tab-pane>
      <a-tab-pane key="advanced" tab="高级规则">
        <a-card :bordered="true">
          <a-form :model="advForm" layout="vertical" style="max-width: 640px">
            <a-form-item label="规则名称">
              <a-input v-model:value="advForm.name" placeholder="如：高价单专线" />
            </a-form-item>
            <a-form-item label="省份">
              <a-input v-model:value="advForm.province" placeholder="匹配正文省份标注行" />
            </a-form-item>
            <a-form-item label="价格区间">
              <a-space>
                <a-input-number v-model:value="advForm.price_min" placeholder="最低价" :min="0" />
                <span>—</span>
                <a-input-number v-model:value="advForm.price_max" placeholder="最高价" :min="0" />
              </a-space>
            </a-form-item>
            <a-form-item label="命中后发布到的频道">
              <a-select v-model:value="advForm.channel_ids" mode="multiple" placeholder="选择频道" style="width: 100%">
                <a-select-option v-for="c in channels" :key="c.id" :value="c.id">{{ c.name }}</a-select-option>
              </a-select>
            </a-form-item>
            <a-form-item>
              <a-button type="primary" @click="saveAdvanced" :loading="saving">保存高级规则</a-button>
            </a-form-item>
          </a-form>
        </a-card>
      </a-tab-pane>
    </a-tabs>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import { message } from 'ant-design-vue';
import { channelApi, metaApi } from '@/api';

const columns = [
  { title: 'ID', dataIndex: 'id', width: 60 },
  { title: '名称', dataIndex: 'name', width: 160 },
  { title: '关键词', dataIndex: 'keyword', width: 160 },
  { title: '标签', dataIndex: 'tag', width: 110 },
  { title: '城市', dataIndex: 'city', width: 90 },
  { title: '状态', key: 'enabled', width: 80 },
  { title: '操作', key: 'action', width: 80 },
];
const rules = ref<any[]>([]);
const tags = ref<any[]>([]);
const channels = ref<any[]>([]);
const loading = ref(false);
const saving = ref(false);
const form = reactive({ name: '', keyword: '', tag: '', city: '' });
const advForm = reactive({ name: '', province: '', price_min: null as any, price_max: null as any, channel_ids: [] as number[] });

async function load() {
  loading.value = true;
  try {
    const r: any = await channelApi.publishRules();
    rules.value = r.list || r || [];
    tags.value = await metaApi.tags();
    channels.value = await channelApi.list(true);
  } finally { loading.value = false; }
}
async function save() {
  if (!form.name.trim()) { message.warning('请输入规则名称'); return; }
  saving.value = true;
  try {
    await channelApi.createPublishRule({ ...form });
    message.success('规则已创建');
    Object.assign(form, { name: '', keyword: '', tag: '', city: '' });
    load();
  } catch (e: any) { message.error(e.message); } finally { saving.value = false; }
}
async function saveAdvanced() {
  if (!advForm.name.trim()) { message.warning('请输入规则名称'); return; }
  saving.value = true;
  try {
    await channelApi.createPublishRule({ ...advForm });
    message.success('高级规则已创建');
    Object.assign(advForm, { name: '', province: '', price_min: null, price_max: null, channel_ids: [] });
    load();
  } catch (e: any) { message.error(e.message); } finally { saving.value = false; }
}
async function removeRule(id: number) {
  await channelApi.deletePublishRule(id);
  message.success('已删除');
  load();
}
onMounted(load);
</script>
