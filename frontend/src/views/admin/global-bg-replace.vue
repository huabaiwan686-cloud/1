<template>
  <div class="page">
    <a-card class="page-card" :bordered="false" title="全局背景替换">
      <a-form layout="inline">
        <a-form-item label="启用">
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
      <div class="hint">开启后，所有发往频道的图片自动抠图并替换为所选背景；服务器只保留原图，处理图不留存（表格图直接原图发送除外）</div>
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
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { message, Modal } from 'ant-design-vue';
import { mediaApi } from '@/api';

const list = ref<any[]>([]);
const loading = ref(false);
const saving = ref(false);
const matting = ref({ enabled: false, backgroundId: null as number | null });

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
    // 只关注 replace_bg 模式：如果是该模式则显示启用状态
    matting.value = {
      enabled: !!d.enabled && (d.mode === '替换背景' || !d.mode),
      backgroundId: d.backgroundId || null,
    };
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
