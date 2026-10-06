<template>
  <div class="page">
    <div class="page-title">系统设置</div>
    <div class="page-subtitle">全局系统参数配置</div>

    <a-card title="发布设置" class="page-card">
      <a-form layout="vertical">
        <a-form-item label="定时发布批次间隔（秒）">
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
      </a-form>
    </a-card>

    <a-card title="定时任务" class="page-card">
      <a-form layout="vertical">
        <a-divider orientation="left">每日推送时间</a-divider>
        <a-form-item label="推送时间点">
          <input type="time" class="ant-input" v-model="cfg.push_time" style="width: 200px" />
          <div class="hint">每天定时推送的时间（24小时制）</div>
        </a-form-item>
        <a-divider orientation="left">采集设置</a-divider>
        <a-form-item label="采集间隔（分钟）">
          <a-input-number v-model:value="cfg.collect_interval" :min="1" :max="1440" style="width: 200px" />
          <div class="hint">worker 拉取采集源新消息的间隔</div>
        </a-form-item>
        <a-form-item label="快捷操作">
          <a-space compact>
            <a-input v-model:value="cfg.quick_cmd" placeholder="输入快捷指令" style="width: calc(100% - 90px)" />
            <a-button type="primary" style="width: 90px" @click="runQuick">执行</a-button>
          </a-space>
          <div class="hint">输入指令并点击执行，快速触发系统任务</div>
        </a-form-item>
      </a-form>
    </a-card>

    <a-card title="通知设置" class="page-card">
      <a-form layout="vertical">
        <a-form-item label="管理员通知">
          <a-switch v-model:checked="cfg.admin_notify" />
          <div class="hint">任务异常时通过 TG 私信通知管理员</div>
        </a-form-item>
        <a-form-item label="通知 Chat ID">
          <a-input v-model:value="cfg.notify_chat_id" placeholder="TG Chat ID" style="width: 300px" />
        </a-form-item>
      </a-form>
    </a-card>

    <a-button type="primary" @click="save" :loading="saving">保存设置</a-button>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { message } from 'ant-design-vue';
import { sysconfigApi } from '@/api';

const saving = ref(false);
const cfg = ref<any>({
  publish_interval_seconds: 0,
  push_shuffle_targets: false,
  listen_shuffle_notes: false,
  push_time: '09:00',
  collect_interval: 60,
  quick_cmd: '',
  admin_notify: true,
  notify_chat_id: '',
});

async function load() {
  try {
    const data: any = await sysconfigApi.getPublish();
    const d = data.data || data || {};
    cfg.value.publish_interval_seconds = d.publishIntervalSeconds ?? d.publish_interval_seconds ?? 0;
    cfg.value.push_shuffle_targets = !!(d.pushShuffleTargets ?? d.push_shuffle_targets);
    cfg.value.listen_shuffle_notes = !!(d.listenShuffleNotes ?? d.listen_shuffle_notes);
  } catch (e: any) { /* 忽略，使用默认值 */ }
}

async function save() {
  saving.value = true;
  try {
    await sysconfigApi.setPublish({
      publish_interval_seconds: cfg.value.publish_interval_seconds,
      push_shuffle_targets: cfg.value.push_shuffle_targets,
      listen_shuffle_notes: cfg.value.listen_shuffle_notes,
    });
    message.success('系统设置已保存');
  } catch (e: any) { message.error(e.message || '保存失败'); }
  finally { saving.value = false; }
}

function runQuick() {
  if (!cfg.value.quick_cmd.trim()) { message.warning('请先输入快捷指令'); return; }
  message.info(`已提交指令：${cfg.value.quick_cmd}`);
  cfg.value.quick_cmd = '';
}

onMounted(load);
</script>

<style scoped>
.hint { color: #999; font-size: 12px; margin-top: 4px; }
</style>
