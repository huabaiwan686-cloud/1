<template>
  <div class="page">
    <a-card class="page-card" :bordered="false" title="全局混淆设置">
      <a-spin :spinning="loading">
        <a-form :label-col="{ span: 6 }" :wrapper-col="{ span: 14 }" class="narrow-form">
          <a-form-item label="启用全局混淆">
            <a-switch v-model:checked="cfg.enabled" />
            <div class="hint">开启后，所有发往频道的图片自动做轻量随机扰动，防止被平台识别</div>
          </a-form-item>
          <a-form-item label="扰动强度" v-if="cfg.strength !== undefined">
            <a-slider v-model:value="cfg.strength" :min="1" :max="10" :marks="{ 1: '弱', 10: '强' }" style="width: 200px" />
            <div class="hint">强度越高越难识别，但图片质量损失越大</div>
          </a-form-item>
          <a-form-item :wrapper-col="{ offset: 6 }">
            <a-button type="primary" @click="save" :loading="saving">保存</a-button>
          </a-form-item>
        </a-form>
      </a-spin>
      <div class="hint" style="margin-top: 16px">
        说明：混淆（轻量随机扰动）对图片做像素级随机扰动，不改变视觉内容，可有效防止图片被平台去重/识别。
        表格图默认走轻量扰动，不受此开关影响。
      </div>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { message } from 'ant-design-vue';
import { mediaApi } from '@/api';

const loading = ref(false);
const saving = ref(false);
// strength 为可选：后端若支持则显示滑块，否则只显示开关
const cfg = ref<{ enabled: boolean; strength?: number }>({ enabled: false });

async function load() {
  loading.value = true;
  try {
    const data: any = await mediaApi.mattingGlobal();
    const d = data.data || data;
    // 只关注 light_perturb 模式
    cfg.value.enabled = !!d.enabled && d.mode === 'light_perturb';
    if (d.strength !== undefined) cfg.value.strength = d.strength;
  } catch (e: any) { message.error(e.message || '加载失败'); }
  finally { loading.value = false; }
}

async function save() {
  saving.value = true;
  try {
    const payload: any = {
      enabled: cfg.value.enabled,
      mode: 'light_perturb',
    };
    if (cfg.value.strength !== undefined) payload.strength = cfg.value.strength;
    await mediaApi.setMattingGlobal(payload);
    message.success('已保存，全局混淆已' + (cfg.value.enabled ? '开启' : '关闭'));
  } catch (e: any) { message.error(e.message || '保存失败'); }
  finally { saving.value = false; }
}

onMounted(() => load());
</script>

<style scoped>
.hint { color: #999; font-size: 12px; margin-top: 4px; }
</style>
