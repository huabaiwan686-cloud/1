<template>
  <div class="page">
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
        <div v-else class="bg-grid">
          <div v-for="m in list" :key="m.id" class="bg-card">
            <img :src="m.url" class="bg-thumb" />
            <div class="bg-name">{{ m.name }}</div>
            <div class="bg-actions">
              <a-button size="small" type="link" danger @click="remove(m.id)">删除</a-button>
            </div>
          </div>
        </div>
      </a-spin>
    </a-card>

    <a-card class="page-card" :bordered="false" title="全局抠图设置">
      <a-form layout="inline">
        <a-form-item label="启用全局抠图">
          <a-switch v-model:checked="matting.enabled" />
        </a-form-item>
        <a-form-item label="抠图模式">
          <a-select v-model:value="matting.mode" style="width: 180px">
            <a-select-option value="替换背景">替换背景</a-select-option>
            <a-select-option value="背景虚化">背景虚化（人像模式）</a-select-option>
            <a-select-option value="原图">原图（不处理）</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="默认背景" v-if="matting.mode === '替换背景'">
          <a-select v-model:value="matting.backgroundId" style="width: 200px" placeholder="选择背景" allow-clear>
            <a-select-option v-for="m in list" :key="m.id" :value="m.id">{{ m.name }}</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item>
          <a-button type="primary" @click="saveMatting">保存</a-button>
        </a-form-item>
      </a-form>
      <div class="hint">开启后，所有发往频道的图片将按所选模式自动处理（表格图直接原图发送除外）</div>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { message, Modal } from 'ant-design-vue';
import { mediaApi } from '@/api';

const list = ref<any[]>([]);
const loading = ref(false);
const matting = ref({ enabled: false, mode: '替换背景', backgroundId: null as number | null });

async function load() {
  loading.value = true;
  try {
    const data: any = await mediaApi.materials();
    list.value = data.list || data || [];
  } catch (e: any) { message.error(e.message || '加载失败'); }
  finally { loading.value = false; }
}

async function loadMatting() {
  try {
    const data: any = await mediaApi.mattingGlobal();
    const d = data.data || data;
    matting.value = { enabled: !!d.enabled, mode: d.mode || '替换背景', backgroundId: d.backgroundId || null };
  } catch { /* ignore */ }
}

async function beforeUpload(file: File) {
  const name = file.name.replace(/\.[^.]+$/, '') || '未命名';
  try {
    await mediaApi.uploadMaterial(file, name);
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
        await mediaApi.deleteMaterial(id);
        message.success('已删除');
        load();
      } catch (e: any) { message.error(e.message || '删除失败'); }
    },
  });
}

async function saveMatting() {
  try {
    await mediaApi.setMattingGlobal({
      enabled: matting.value.enabled,
      mode: matting.value.mode,
      background_id: matting.value.backgroundId,
    });
    message.success('已保存');
  } catch (e: any) { message.error(e.message || '保存失败'); }
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
