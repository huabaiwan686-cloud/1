<template>
  <a-card title="快速推送">
    <a-alert message="选择模板，一键推送到快速推送目标群组" type="info" style="margin-bottom: 16px" />
    <a-form layout="vertical">
      <a-form-item label="模板">
        <a-select v-model:value="tplId" style="width: 100%" placeholder="选择模板">
          <a-select-option v-for="t in templates" :key="t.id" :value="t.id">{{ t.name }} ({{ t.code }})</a-select-option>
        </a-select>
      </a-form-item>
      <a-form-item>
        <a-button type="primary" :disabled="!tplId" @click="push" :loading="loading">立即推送</a-button>
      </a-form-item>
    </a-form>
  </a-card>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { message } from 'ant-design-vue';
import { messageApi } from '@/api';

const templates = ref<any[]>([]);
const tplId = ref<number | null>(null);
const loading = ref(false);
onMounted(async () => { templates.value = await messageApi.templates(); });
async function push() {
  loading.value = true;
  try { await messageApi.pushTemplate(tplId.value!); message.success('推送任务已创建'); }
  catch (e: any) { message.error(e.message); } finally { loading.value = false; }
}
</script>
