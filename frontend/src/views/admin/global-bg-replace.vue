<template>
  <div class="page">
    <a-card class="page-card" :bordered="false" title="全局处理">
      <a-form layout="inline">
        <a-form-item label="处理开关">
          <a-switch v-model:checked="matting.enabled" />
        </a-form-item>
        <a-form-item label="默认背景">
          <a-select v-model:value="matting.backgroundId" style="width: 200px" placeholder="选择背景" allow-clear>
            <a-select-option v-for="m in list" :key="m.id" :value="m.id">{{ m.name }}</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item>
          <a-button type="primary" @click="saveMatting" :loading="saving">保存</a-button>
        </a-form-item>
      </a-form>
      <div class="hint">一个开关管理所有处理：开则照片抠图（纯白背景、保护区 30px、镜像交替）+ 视频处理 + 文字混淆，全部生效；关则全部发原图。</div>
    </a-card>

    <a-card class="page-card" :bordered="false" title="背景素材管理">
      <template #extra>
        <a-upload
          :before-upload="beforeUpload"
          :show-upload-list="false"
          accept="image/*"
        >
          <a-button type="primary">上传背景图</a-button>
        </a-upload>
      </template>
      <a-spin :spinning="loading">
        <a-empty v-if="!list.length && !loading" description="暂无背景素材，点击右上角上传" />
        <div v-else>
          <div style="margin-bottom: 8px; color: #888; font-size: 12px;">背景素材库（上传后点"设为固定"即固定使用该背景）</div>
          <div class="bg-grid">
            <div v-for="m in customList" :key="m.id" class="bg-card">
              <img :src="m.url" class="bg-thumb" />
              <div class="bg-name">{{ m.name }}</div>
              <div class="bg-actions">
                <a-button size="small" type="link" @click="selectCustom(m.id)">设为固定</a-button>
                <a-button size="small" type="link" danger @click="remove(m.id)">删除</a-button>
              </div>
            </div>
          </div>
          <a-empty v-if="!customList.length" description="暂无自定义素材，点击右上角上传" style="margin-top: 16px;" />
        </div>
      </a-spin>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { message, Modal } from 'ant-design-vue';
import { mediaApi } from '@/api';
import { computed } from 'vue';

const list = ref<any[]>([]);
const loading = ref(false);
const saving = ref(false);
const matting = ref({ enabled: false, backgroundId: null as number | null });

// 默认随机池 vs 自定义素材库
const customList = computed(() => list.value);

function selectCustom(id: number) {
  matting.value.backgroundId = id;
  message.success('已设为固定背景，记得点保存');
}

async function load() {
  loading.value = true;
  try {
    list.value = data.list || data || [];
  } catch (e: any) { message.error(e.message || '加载失败'); }
  finally { loading.value = false; }
}

async function loadMatting() {
  try {
    const data: any = await mediaApi.mattingGlobal();
    const d = data.data || data;
    // 只关注 replace_bg 模式：如果是该模式则显示启用状态
    matting.value = {
      enabled: !!d.enabled,
      backgroundId: d.backgroundId || null,
    };
  } catch { /* ignore */ }
}

async function beforeUpload(file: File) {
  const name = file.name.replace(/\.[^.]+$/, '') || '未命名';
  try {
    message.success('上传成功');
    load();
  } catch (e: any) { message.error(e.message || '上传失败'); }
  return false;
}

function remove(id: number) {
  Modal.confirm({
    title: '确认删除？',
    content: '删除后无法恢复',
    onOk: async () => {
      try {
        message.success('已删除');
        // 如果删除的是当前默认背景，清空选择
        if (matting.value.backgroundId === id) {
          matting.value.backgroundId = null;
        }
        load();
      } catch (e: any) { message.error(e.message || '删除失败'); }
    },
  });
}

async function saveMatting() {
  if (matting.value.enabled && !matting.value.backgroundId) {
    message.warning('请先选择背景素材再开启');
    return;
  }
  saving.value = true;
  try {
    await mediaApi.setMattingGlobal({
      enabled: matting.value.enabled,
      mode: '替换背景',
      background_id: matting.value.backgroundId,
    });
    await loadMatting();
    message.success('已保存，全局背景替换已' + (matting.value.enabled ? '开启' : '关闭'));
  } catch (e: any) { message.error(e.message || '保存失败'); }
  finally { saving.value = false; }
}

onMounted(() => { load(); loadMatting(); });
</script>

<style scoped>
.bg-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 16px; }
.bg-card { border: 1px solid #f0f0f0; border-radius: 8px; overflow: hidden; background: #fff; }
.bg-thumb { width: 100%; height: 120px; object-fit: cover; }
.bg-name { padding: 8px 12px; font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.bg-actions { padding: 0 12px 8px; text-align: right; }
.hint { color: #999; font-size: 12px; margin-top: 12px; }
</style>
