<template>
  <div class="page">
    <div class="page-title">防扫图</div>
    <div class="page-subtitle">配置图片防扫描处理参数，发布时自动应用</div>

    <a-card title="基础配置" class="page-card">
      <a-spin :spinning="loading">
        <a-form layout="vertical">
          <a-form-item label="全局总开关">
            <a-switch v-model:checked="cfg.globalEnabled" />
            <div class="hint">开启后，所有发布图片按以下配置处理</div>
          </a-form-item>
          <a-form-item label="处理模式">
            <a-radio-group v-model:value="cfg.mode">
              <a-radio value="light">轻量扰动</a-radio>
              <a-radio value="strong">强力混淆</a-radio>
              <a-radio value="custom">自定义</a-radio>
            </a-radio-group>
            <div class="hint">轻量扰动：速度快；强力混淆：防扫效果更好</div>
          </a-form-item>
          <a-form-item label="移除 EXIF">
            <a-switch v-model:checked="cfg.metadataStripEnabled" />
            <div class="hint">删除拍摄设备、定位、拍摄时间等元信息</div>
          </a-form-item>
          <a-form-item label="压缩重编码">
            <a-switch v-model:checked="cfg.compressionEnabled" />
            <div v-if="cfg.compressionEnabled" style="margin-top: 8px">
              质量 <a-slider v-model:value="cfg.compressionQuality" :min="50" :max="100" style="width: 200px; display: inline-block" /> {{ cfg.compressionQuality }}
            </div>
          </a-form-item>
          <a-form-item label="允许单条覆盖">
            <a-switch v-model:checked="cfg.allowSingleOverrideEnabled" />
          </a-form-item>
        </a-form>
      </a-spin>
    </a-card>

    <a-card title="图像扰动" class="page-card">
      <a-form layout="vertical">
        <a-form-item label="尺寸微调">
          <a-switch v-model:checked="cfg.resizeEnabled" />
          <div v-if="cfg.resizeEnabled" style="margin-top: 8px">
            缩放 <a-slider v-model:value="cfg.resizeScale" :min="80" :max="100" style="width: 200px; display: inline-block" /> {{ cfg.resizeScale }}%
          </div>
        </a-form-item>
        <a-form-item label="轻微裁剪">
          <a-switch v-model:checked="cfg.cropEnabled" />
          <div v-if="cfg.cropEnabled" style="margin-top: 8px">
            裁掉边缘 <a-slider v-model:value="cfg.cropPercent" :min="1" :max="10" style="width: 200px; display: inline-block" /> {{ cfg.cropPercent }}%
          </div>
        </a-form-item>
        <a-form-item label="噪点扰动">
          <a-switch v-model:checked="cfg.noiseEnabled" />
          <div v-if="cfg.noiseEnabled" style="margin-top: 8px">
            强度 <a-slider v-model:value="cfg.noiseStrength" :min="1" :max="50" style="width: 200px; display: inline-block" /> {{ cfg.noiseStrength }}
          </div>
        </a-form-item>
        <a-form-item label="色彩扰动">
          <a-switch v-model:checked="cfg.colorJitterEnabled" />
          <div v-if="cfg.colorJitterEnabled" style="margin-top: 8px">
            强度 <a-slider v-model:value="cfg.colorJitterStrength" :min="1" :max="50" style="width: 200px; display: inline-block" /> {{ cfg.colorJitterStrength }}
            <div class="hint">色温/亮度/饱和度随机扰动</div>
          </div>
        </a-form-item>
        <a-form-item label="锐化/模糊微扰">
          <a-switch v-model:checked="cfg.sharpenBlurEnabled" />
          <div v-if="cfg.sharpenBlurEnabled" style="margin-top: 8px">
            <a-radio-group v-model:value="cfg.sharpenBlurMode">
              <a-radio value="blur">模糊</a-radio>
              <a-radio value="sharpen">锐化</a-radio>
            </a-radio-group>
            <div style="margin-top: 8px">
              强度 <a-slider v-model:value="cfg.sharpenBlurStrength" :min="1" :max="30" style="width: 200px; display: inline-block" /> {{ cfg.sharpenBlurStrength }}
            </div>
          </div>
        </a-form-item>
      </a-form>
    </a-card>

    <a-card title="背景与水印" class="page-card">
      <a-form layout="vertical">
        <a-form-item label="人像背景替换">
          <a-switch v-model:checked="cfg.backgroundReplaceEnabled" />
          <div class="hint">开启后联动：背景纹理开、轻水印关</div>
        </a-form-item>
        <a-form-item label="背景虚化">
          <a-switch v-model:checked="cfg.backgroundBlurEnabled" />
          <div class="hint">人物保持清晰，背景高斯模糊</div>
        </a-form-item>
        <a-form-item label="背景纹理">
          <a-switch v-model:checked="cfg.backgroundTextureEnabled" />
          <div v-if="cfg.backgroundTextureEnabled" style="margin-top: 8px">
            <a-radio-group v-model:value="cfg.backgroundTexturePreset">
              <a-radio v-for="t in textures" :key="t.name" :value="t.name">
                <img v-if="t.preview" :src="t.preview" style="width: 48px; height: 48px; border-radius: 4px; vertical-align: middle;" />
                <span v-else class="blur-preview">模糊</span>
                {{ t.label }}
              </a-radio>
            </a-radio-group>
          </div>
        </a-form-item>
        <a-form-item label="轻水印">
          <a-switch v-model:checked="cfg.watermarkEnabled" />
          <div v-if="cfg.watermarkEnabled" style="margin-top: 8px">
            <a-input v-model:value="cfg.watermarkText" placeholder="水印文字" style="width: 200px" />
            <div style="margin-top: 8px">字号 <a-slider v-model:value="cfg.watermarkFontSize" :min="10" :max="60" style="width: 160px; display: inline-block" /> {{ cfg.watermarkFontSize }}px</div>
            <div>不透明度 <a-slider v-model:value="cfg.watermarkOpacity" :min="5" :max="100" style="width: 160px; display: inline-block" /> {{ cfg.watermarkOpacity }}%</div>
          </div>
        </a-form-item>
      </a-form>
    </a-card>

    <!-- 折叠高级参数 -->
    <a-card title="高级参数" class="page-card">
      <a-collapse ghost>
        <a-collapse-panel key="mask" header="遮罩 / 二维码 / 贴图">
          <a-form layout="vertical">
            <a-form-item label="遮罩">
              <a-switch v-model:checked="cfg.maskEnabled" />
              <div v-if="cfg.maskEnabled" style="margin-top: 8px">
                <a-radio-group v-model:value="cfg.maskMode">
                  <a-radio value="qr">二维码</a-radio>
                  <a-radio value="sticker">贴图</a-radio>
                </a-radio-group>
                <div style="margin-top: 8px">数量 <a-input-number v-model:value="cfg.maskCount" :min="1" :max="9" /></div>
                <div style="margin-top: 8px">不透明度 <a-slider v-model:value="cfg.maskOpacity" :min="10" :max="100" style="width: 160px; display: inline-block" /> {{ cfg.maskOpacity }}%</div>
              </div>
            </a-form-item>
            <a-form-item label="二维码文本">
              <a-input v-model:value="cfg.qrText" placeholder="扫码跳转内容" style="width: 300px" />
            </a-form-item>
            <a-form-item label="贴图文本">
              <a-input v-model:value="cfg.stickerText" placeholder="贴图上显示的文字" style="width: 300px" />
            </a-form-item>
          </a-form>
        </a-collapse-panel>
        <a-collapse-panel key="portrait" header="人像精修">
          <a-form layout="vertical">
            <a-form-item label="人像柔边">
              <a-switch v-model:checked="cfg.portraitSoftEdgeEnabled" />
              <div v-if="cfg.portraitSoftEdgeEnabled" style="margin-top: 8px">
                宽度 <a-slider v-model:value="cfg.portraitSoftEdgeWidth" :min="1" :max="40" style="width: 200px; display: inline-block" /> {{ cfg.portraitSoftEdgeWidth }}px
              </div>
            </a-form-item>
            <a-form-item label="原图叠加">
              <a-switch v-model:checked="cfg.originalOverlayEnabled" />
              <div v-if="cfg.originalOverlayEnabled" style="margin-top: 8px">
                <div>不透明度 <a-slider v-model:value="cfg.originalOverlayOpacity" :min="50" :max="100" style="width: 160px; display: inline-block" /> {{ cfg.originalOverlayOpacity }}%</div>
                <div>宽度 <a-slider v-model:value="cfg.originalOverlayWidth" :min="30" :max="100" style="width: 160px; display: inline-block" /> {{ cfg.originalOverlayWidth }}%</div>
              </div>
            </a-form-item>
            <a-form-item label="资料无水印">
              <a-switch v-model:checked="cfg.profileNoWatermarkEnabled" />
            </a-form-item>
            <a-form-item label="JPEG 质量控制">
              <a-switch v-model:checked="cfg.jpegQualityControlEnabled" />
            </a-form-item>
          </a-form>
        </a-collapse-panel>
      </a-collapse>
    </a-card>

    <a-button type="primary" @click="save" :loading="saving">保存配置</a-button>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { message } from 'ant-design-vue';
import { mediaApi } from '@/api';

const loading = ref(false);
const saving = ref(false);
const textures = ref<any[]>([]);
const cfg = ref<Record<string, any>>({ mode: 'light' });

async function load() {
  loading.value = true;
  try {
    const data: any = await mediaApi.antiScan();
    cfg.value = { mode: 'light', ...(data.data || data || {}) };
    const t: any = await mediaApi.antiScanTextures();
    textures.value = t.data || t || [];
  } catch (e: any) { message.error(e.message || '加载失败'); }
  finally { loading.value = false; }
}

async function save() {
  saving.value = true;
  try {
    await mediaApi.setAntiScan(cfg.value);
    message.success('防扫图配置已保存');
  } catch (e: any) { message.error(e.message || '保存失败'); }
  finally { saving.value = false; }
}

onMounted(load);
</script>

<style scoped>
.hint { color: #999; font-size: 12px; margin-top: 4px; }
.blur-preview {
  display: inline-block; width: 48px; height: 48px; border-radius: 4px;
  vertical-align: middle; text-align: center; line-height: 48px;
  font-size: 12px; color: #fff;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  filter: blur(1px);
}
</style>
