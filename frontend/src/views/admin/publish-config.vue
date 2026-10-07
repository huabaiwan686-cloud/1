<template>
  <div class="page">
    <a-card class="page-card" :bordered="false" title="循环发布设置">
      <a-spin :spinning="loading">
        <a-form :label-col="{ span: 6 }" :wrapper-col="{ span: 14 }" class="narrow-form">
          <a-form-item label="发布间隔（秒）">
            <a-input-number v-model:value="cfg.publish_interval_seconds" :min="0" :max="3600" style="width: 200px" />
            <div class="hint">定时发布批次之间的等待秒数，0 为不等待</div>
          </a-form-item>
          <a-form-item label="群推目标打乱">
            <a-switch v-model:checked="cfg.push_shuffle_targets" />
            <div class="hint">开启后每次群推打乱目标群组顺序，防检测</div>
          </a-form-item>
          <a-form-item label="监听素材打乱">
            <a-switch v-model:checked="cfg.listen_shuffle_notes" />
            <div class="hint">开启后监听命中时打乱 DM 素材顺序</div>
          </a-form-item>
          <a-form-item :wrapper-col="{ offset: 6 }">
            <a-button type="primary" @click="save" :loading="saving">保存</a-button>
          </a-form-item>
        </a-form>
      </a-spin>
    </a-card>

    <a-card class="page-card" :bordered="false" title="混淆/防扫说明">
      <div class="desc-text">
        图片混淆（防扫）是按频道配置的：进入「频道配置」页，点击频道卡片的「编辑」，
        在「防扫模式」中选择：原图 / 替换背景 / 背景虚化。
      </div>
      <div class="hint" style="margin-top: 8px">
        全局抠图开关在「背景素材管理」页。发布时按频道防扫模式 + 全局抠图设置自动处理。
      </div>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { message } from 'ant-design-vue';
import { sysconfigApi } from '@/api';

const loading = ref(false);
const saving = ref(false);
const cfg = ref({
  publish_interval_seconds: 0,
  push_shuffle_targets: false,
  listen_shuffle_notes: false,
});

async function load() {
  loading.value = true;
  try {
    const data: any = await sysconfigApi.getPublish();
    const d = data.data || data;
    cfg.value = {
      publish_interval_seconds: d.publish_interval_seconds || 0,
      push_shuffle_targets: !!d.push_shuffle_targets,
      listen_shuffle_notes: !!d.listen_shuffle_notes,
    };
  } catch (e: any) { message.error(e.message || '加载失败'); }
  finally { loading.value = false; }
}

async function save() {
  saving.value = true;
  try {
    await sysconfigApi.setPublish(cfg.value);
    message.success('已保存，worker 下一轮生效');
  } catch (e: any) { message.error(e.message || '保存失败'); }
  finally { saving.value = false; }
}

onMounted(() => load());
</script>

<style scoped>
.hint { color: #999; font-size: 12px; margin-top: 4px; }
.desc-text { color: #666; font-size: 14px; line-height: 1.8; }
</style>
