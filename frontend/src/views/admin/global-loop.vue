<template>
  <div class="page">
    <a-card class="page-card" :bordered="false" title="全局循环发布设置">
      <a-spin :spinning="loading">
        <a-form :label-col="{ span: 6 }" :wrapper-col="{ span: 14 }" class="narrow-form">
          <a-form-item label="启用循环发布">
            <a-switch v-model:checked="cfg.enabled" />
            <div class="hint">开启后，笔记按设定间隔循环发布到频道</div>
          </a-form-item>
          <a-form-item label="发布间隔（秒）">
            <a-input-number v-model:value="cfg.publish_interval_seconds" :min="0" :max="3600" style="width: 200px" />
            <div class="hint">定时发布批次之间的等待秒数，0 为不等待</div>
          </a-form-item>
          <a-form-item label="循环间隔（秒）">
            <a-input-number v-model:value="cfg.loop_interval_seconds" :min="30" style="width: 200px" />
            <div class="hint">所有循环任务的统一间隔，保存后已运行的任务也会同步更新</div>
          </a-form-item>
          <a-form-item :wrapper-col="{ offset: 6 }">
            <a-button type="primary" @click="save" :loading="saving">保存</a-button>
          </a-form-item>
        </a-form>
      </a-spin>
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
  enabled: true,
  publish_interval_seconds: 0,
  loop_interval_seconds: 259200,
});

async function load() {
  loading.value = true;
  try {
    const data: any = await sysconfigApi.getPublish();
    const d = data.data || data;
    cfg.value = {
      enabled: d.loopEnabled !== undefined ? !!d.loopEnabled : (d.enabled !== undefined ? !!d.enabled : true),
      publish_interval_seconds: d.publishIntervalSeconds ?? d.publish_interval_seconds ?? 0,
      loop_interval_seconds: d.loopIntervalSeconds ?? d.loop_interval_seconds ?? 259200,
    };
  } catch (e: any) { message.error(e.message || '加载失败'); }
  finally { loading.value = false; }
}

async function save() {
  // 前置校验间隔，避免 setPublish 已保存但 setLoopInterval 失败
  const interval = Number(cfg.value.loop_interval_seconds);
  if (!interval || interval < 30) {
    message.error('循环间隔不能为空且不能小于 30 秒');
    return;
  }
  saving.value = true;
  try {
    await sysconfigApi.setPublish({
      ...cfg.value,
      loop_enabled: cfg.value.enabled,
    });
    // 同步循环间隔到所有运行中的任务
    if (cfg.value.loop_interval_seconds) {
      await sysconfigApi.setLoopInterval(cfg.value.loop_interval_seconds);
    }
    // 保存后重新拉取，确认后端真的存上了（防缓存/假保存）
    await load();
    message.success('已保存，worker 下一轮生效');
  } catch (e: any) { message.error(e.message || '保存失败'); }
  finally { saving.value = false; }
}

onMounted(() => load());
</script>

<style scoped>
.hint { color: #999; font-size: 12px; margin-top: 4px; }
</style>
