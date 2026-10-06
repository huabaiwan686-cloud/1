<template>
  <div class="page">
    <a-card class="page-card" :bordered="false" title="防扫图配置">
      <a-spin :spinning="loading">
        <a-form :label-col="{ span: 6 }" :wrapper-col="{ span: 16 }">
          <a-form-item label="全局总开关">
            <a-switch v-model:checked="cfg.globalEnabled" />
          </a-form-item>
          <a-form-item label="允许单条覆盖">
            <a-switch v-model:checked="cfg.allowSingleOverrideEnabled" />
          </a-form-item>
          <a-form-item label="发送前强制处理">
            <a-switch v-model:checked="cfg.forceBeforeSendEnabled" />
          </a-form-item>
        </a-form>

        <a-tabs v-model:activeKey="tab">
          <a-tab-pane key="basic" tab="基础保护">
            <a-form :label-col="{ span: 6 }" :wrapper-col="{ span: 16 }">
              <a-form-item label="移除 EXIF">
                <a-switch v-model:checked="cfg.metadataStripEnabled" />
                <div class="hint">删除拍摄设备、定位、拍摄时间等元信息</div>
              </a-form-item>
              <a-form-item label="压缩重编码">
                <a-switch v-model:checked="cfg.compressionEnabled" />
                <a-slider v-if="cfg.compressionEnabled" v-model:value="cfg.compressionQuality" :min="50" :max="100" style="width: 200px" />
                <span v-if="cfg.compressionEnabled" class="hint">质量 {{ cfg.compressionQuality }}</span>
              </a-form-item>
              <a-form-item label="尺寸微调">
                <a-switch v-model:checked="cfg.resizeEnabled" />
                <a-slider v-if="cfg.resizeEnabled" v-model:value="cfg.resizeScale" :min="80" :max="100" style="width: 200px" />
                <span v-if="cfg.resizeEnabled" class="hint">缩放 {{ cfg.resizeScale }}%</span>
              </a-form-item>
              <a-form-item label="轻微裁剪">
                <a-switch v-model:checked="cfg.cropEnabled" />
                <a-slider v-if="cfg.cropEnabled" v-model:value="cfg.cropPercent" :min="1" :max="10" style="width: 200px" />
                <span v-if="cfg.cropEnabled" class="hint">裁掉边缘 {{ cfg.cropPercent }}%</span>
              </a-form-item>
              <a-form-item label="JPEG 质量控制">
                <a-switch v-model:checked="cfg.jpegQualityControlEnabled" />
              </a-form-item>
            </a-form>
          </a-tab-pane>

          <a-tab-pane key="perturb" tab="图像扰动">
            <a-form :label-col="{ span: 6 }" :wrapper-col="{ span: 16 }">
              <a-form-item label="噪点扰动">
                <a-switch v-model:checked="cfg.noiseEnabled" />
                <a-slider v-if="cfg.noiseEnabled" v-model:value="cfg.noiseStrength" :min="1" :max="50" style="width: 200px" />
                <span v-if="cfg.noiseEnabled" class="hint">强度 {{ cfg.noiseStrength }}</span>
              </a-form-item>
              <a-form-item label="色彩扰动">
                <a-switch v-model:checked="cfg.colorJitterEnabled" />
                <a-slider v-if="cfg.colorJitterEnabled" v-model:value="cfg.colorJitterStrength" :min="1" :max="50" style="width: 200px" />
                <span v-if="cfg.colorJitterEnabled" class="hint">强度 {{ cfg.colorJitterStrength }}（色温/亮度/饱和度）</span>
              </a-form-item>
              <a-form-item label="锐化/模糊微扰">
                <a-switch v-model:checked="cfg.sharpenBlurEnabled" />
                <template v-if="cfg.sharpenBlurEnabled">
                  <a-radio-group v-model:value="cfg.sharpenBlurMode" style="margin-left: 12px">
                    <a-radio value="blur">模糊</a-radio>
                    <a-radio value="sharpen">锐化</a-radio>
                  </a-radio-group>
                  <a-slider v-model:value="cfg.sharpenBlurStrength" :min="1" :max="30" style="width: 200px" />
                  <span class="hint">强度 {{ cfg.sharpenBlurStrength }}</span>
                </template>
              </a-form-item>
            </a-form>
          </a-tab-pane>

          <a-tab-pane key="bg" tab="背景水印">
            <a-form :label-col="{ span: 6 }" :wrapper-col="{ span: 16 }">
              <a-form-item label="人像背景替换">
                <a-switch v-model:checked="cfg.backgroundReplaceEnabled" />
                <div class="hint">开启后联动：背景纹理开、轻水印关</div>
              </a-form-item>
              <a-form-item label="背景虚化">
                <a-switch v-model:checked="cfg.backgroundBlurEnabled" />
              </a-form-item>
              <a-form-item label="人像柔边">
                <a-switch v-model:checked="cfg.portraitSoftEdgeEnabled" />
                <a-slider v-if="cfg.portraitSoftEdgeEnabled" v-model:value="cfg.portraitSoftEdgeWidth" :min="1" :max="40" style="width: 200px" />
                <span v-if="cfg.portraitSoftEdgeEnabled" class="hint">宽度 {{ cfg.portraitSoftEdgeWidth }}px</span>
              </a-form-item>
              <a-form-item label="原图叠加">
                <a-switch v-model:checked="cfg.originalOverlayEnabled" />
                <template v-if="cfg.originalOverlayEnabled">
                  <div>不透明度 <a-slider v-model:value="cfg.originalOverlayOpacity" :min="50" :max="100" style="width: 160px; display: inline-block" /> {{ cfg.originalOverlayOpacity }}%</div>
                  <div>宽度 <a-slider v-model:value="cfg.originalOverlayWidth" :min="30" :max="100" style="width: 160px; display: inline-block" /> {{ cfg.originalOverlayWidth }}%</div>
                </template>
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
                  <div class="hint" style="margin-top: 4px">人物背景模糊：抠出人物主体，背景做高斯模糊处理</div>
                </div>
              </a-form-item>
              <a-form-item label="轻水印">
                <a-switch v-model:checked="cfg.watermarkEnabled" />
                <template v-if="cfg.watermarkEnabled">
                  <a-input v-model:value="cfg.watermarkText" placeholder="水印文字" style="width: 200px; margin-top: 8px" />
                  <div style="margin-top: 8px">字号 <a-slider v-model:value="cfg.watermarkFontSize" :min="10" :max="60" style="width: 160px; display: inline-block" /> {{ cfg.watermarkFontSize }}px</div>
                  <div>不透明度 <a-slider v-model:value="cfg.watermarkOpacity" :min="5" :max="100" style="width: 160px; display: inline-block" /> {{ cfg.watermarkOpacity }}%</div>
                </template>
              </a-form-item>
              <a-form-item label="资料无水印">
                <a-switch v-model:checked="cfg.profileNoWatermarkEnabled" />
              </a-form-item>
            </a-form>
          </a-tab-pane>

          <a-tab-pane key="mask" tab="遮罩/二维码/贴图">
            <a-form :label-col="{ span: 6 }" :wrapper-col="{ span: 16 }">
              <a-form-item label="遮罩">
                <a-switch v-model:checked="cfg.maskEnabled" />
                <template v-if="cfg.maskEnabled">
                  <a-radio-group v-model:value="cfg.maskMode" style="margin-left: 12px">
                    <a-radio value="qr">二维码</a-radio>
                    <a-radio value="sticker">贴图</a-radio>
                  </a-radio-group>
                  <div style="margin-top: 8px">数量 <a-input-number v-model:value="cfg.maskCount" :min="1" :max="9" /></div>
                  <div style="margin-top: 8px">不透明度 <a-slider v-model:value="cfg.maskOpacity" :min="10" :max="100" style="width: 160px; display: inline-block" /> {{ cfg.maskOpacity }}%</div>
                </template>
              </a-form-item>
              <a-form-item label="二维码文本">
                <a-input v-model:value="cfg.qrText" placeholder="扫码跳转内容" style="width: 300px" />
              </a-form-item>
              <a-form-item label="贴图文本">
                <a-input v-model:value="cfg.stickerText" placeholder="贴图上显示的文字" style="width: 300px" />
              </a-form-item>
            </a-form>
          </a-tab-pane>
        </a-tabs>

        <a-form-item :wrapper-col="{ offset: 6 }" style="margin-top: 16px">
          <a-button type="primary" @click="save" :loading="saving">保存配置</a-button>
        </a-form-item>
      </a-spin>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { message } from 'ant-design-vue';
import { mediaApi } from '@/api';

const loading = ref(false);
const saving = ref(false);
const tab = ref('basic');
const textures = ref<any[]>([]);
const cfg = ref<Record<string, any>>({});

async function load() {
  loading.value = true;
  try {
    const data: any = await mediaApi.antiScan();
    cfg.value = data.data || data || {};
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
.page { padding: 16px; }
.page-card { max-width: 900px; margin: 0 auto; }
.blur-preview {
  display: inline-block; width: 48px; height: 48px; border-radius: 4px;
  vertical-align: middle; text-align: center; line-height: 48px;
  font-size: 12px; color: #fff;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  filter: blur(1px);
}
</style>
