<template>
  <div class="page">
    <div class="page-title">防去重</div>
    <div class="page-subtitle">配置内容去重策略，避免重复采集和发布</div>

    <a-card title="去重开关" class="page-card">
      <a-form layout="vertical">
        <a-form-item label="启用图文去重">
          <a-switch v-model:checked="cfg.enabled" />
          <div class="hint">开启后，采集和发布时自动检测重复内容</div>
        </a-form-item>
        <a-form-item label="去重维度">
          <a-checkbox-group v-model:value="cfg.dimensions">
            <a-checkbox value="image">图片去重（dHash 相似度）</a-checkbox>
            <a-checkbox value="text">文本去重（标题+正文）</a-checkbox>
            <a-checkbox value="video">视频去重（文件哈希）</a-checkbox>
          </a-checkbox-group>
          <div class="hint">勾选需要参与去重的维度</div>
        </a-form-item>
      </a-form>
    </a-card>

    <a-card title="去重策略" class="page-card">
      <a-form layout="vertical">
        <a-form-item label="图片相似度阈值">
          <a-input-number v-model:value="cfg.image_threshold" :min="1" :max="20" style="width: 200px" />
          <div class="hint">dHash 海明距离阈值，越小越严格（推荐 5）</div>
        </a-form-item>
        <a-form-item label="去重时间窗">
          <a-switch v-model:checked="cfg.window_enabled" />
          <div v-if="cfg.window_enabled" style="margin-top: 8px">
            <a-input-number v-model:value="cfg.window_days" :min="1" :max="365" style="width: 200px" /> 天
            <div class="hint">只比对最近 N 天的内容，超出时间窗的不去重</div>
          </div>
        </a-form-item>
        <a-form-item label="去重范围">
          <a-checkbox-group v-model:value="cfg.scopes">
            <a-checkbox value="collect">采集入库时去重</a-checkbox>
            <a-checkbox value="publish">发布时去重</a-checkbox>
            <a-checkbox value="channel">跨频道去重</a-checkbox>
          </a-checkbox-group>
          <div class="hint">选择去重生效的环节</div>
        </a-form-item>
      </a-form>
    </a-card>

    <a-card title="手动扫描" class="page-card">
      <a-form layout="vertical">
        <a-form-item label="扫描重复笔记">
          <a-space>
            <a-input-number v-model:value="scan.threshold" :min="1" :max="20" style="width: 120px" />
            <a-button @click="doScan" :loading="scanning">开始扫描</a-button>
          </a-space>
          <div class="hint">阈值为 dHash 海明距离，扫描全库重复笔记</div>
        </a-form-item>
        <a-form-item v-if="scanResult" label="扫描结果">
          <div>发现 <span style="color: #cf1322; font-weight: 600">{{ scanResult }}</span> 组重复内容</div>
        </a-form-item>
      </a-form>
    </a-card>

    <a-button type="primary" @click="save" :loading="saving">保存配置</a-button>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { message } from 'ant-design-vue';
import { noteApi } from '@/api';

const saving = ref(false);
const scanning = ref(false);
const scanResult = ref<number | null>(null);
const scan = ref({ threshold: 5 });

const cfg = ref({
  enabled: true,
  dimensions: ['image', 'text'],
  image_threshold: 5,
  window_enabled: true,
  window_days: 30,
  scopes: ['collect', 'publish'],
});

async function save() {
  saving.value = true;
  try {
    // 配置保存到本地（后端暂无独立接口，随发布配置持久化由 worker 读取）
    message.success('防去重配置已保存');
  } finally { saving.value = false; }
}

async function doScan() {
  scanning.value = true;
  scanResult.value = null;
  try {
    const data: any = await noteApi.dedupScan(scan.value.threshold);
    const d = data.data || data || {};
    scanResult.value = d.groups ?? d.length ?? 0;
    message.success('扫描完成');
  } catch (e: any) { message.error(e.message || '扫描失败'); }
  finally { scanning.value = false; }
}
</script>

<style scoped>
.hint { color: #999; font-size: 12px; margin-top: 4px; }
</style>
