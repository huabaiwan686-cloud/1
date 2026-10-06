<template>
  <div>
    <div class="aq-header">
      <div class="aq-title">素材上传</div>
      <p class="aq-desc">上传资料图片与验证视频，保存为草稿或直接发布</p>
    </div>
    <a-tabs>
      <a-tab-pane key="single" tab="发布资料">
        <a-card :bordered="true">
          <a-form :model="form" layout="horizontal" @finish="onSubmit"
                  :label-col="{ span: 4 }" :wrapper-col="{ span: 16 }">
      <a-form-item label="标题" name="title" :rules="[{ required: true, message: '请输入标题' }]">
        <a-input v-model:value="form.title" placeholder="资料标题" />
      </a-form-item>
      <a-form-item label="正文" name="body">
        <a-textarea v-model:value="form.body" :rows="6" placeholder="正文内容（支持介绍费等文案）" />
      </a-form-item>
      <a-form-item label="标签">
        <a-select v-model:value="form.tags" mode="tags" placeholder="选择或输入标签" style="width: 100%">
          <a-select-option v-for="t in tags" :key="t.id" :value="t.name">{{ t.name }}</a-select-option>
        </a-select>
      </a-form-item>
      <a-form-item label="城市">
        <a-cascader v-model:value="form.city" :options="cities" :field-names="{ label: 'name', value: 'id', children: 'children' }" placeholder="选择城市" style="width: 100%" />
      </a-form-item>
      <a-form-item label="展示资料" name="show" :rules="[{ required: true, message: '请上传展示图片' }]">
        <div class="file-grid">
          <a-upload list-type="picture-card" :before-upload="() => false" v-model:file-list="showList" multiple>
            <div><plus-outlined /><div>上传</div></div>
          </a-upload>
        </div>
        <div
          style="border:1px dashed #d9d9d9;border-radius:8px;padding:12px;text-align:center;cursor:pointer"
          @click="triggerShowUpload">
          或点击此处拖放图片批量上传（支持 JPG/PNG/WebP）
        </div>
        <input ref="showInput" type="file" accept="image/*" multiple style="display:none" @change="onShowFiles" />
      </a-form-item>
      <a-form-item label="验证视频（单独发送，紧跟上架消息）">
        <a-upload :before-upload="() => false" v-model:file-list="verifyList" :max-count="1" accept="video/*">
          <a-button><plus-outlined />选择验证视频</a-button>
        </a-upload>
      </a-form-item>
      <a-form-item label="目标频道">
        <a-select v-model:value="form.channel_ids" mode="multiple" placeholder="选择频道" style="width: 100%">
          <a-select-option v-for="c in channels" :key="c.id" :value="c.id">{{ c.name }}</a-select-option>
        </a-select>
        <div class="mt-8">
          <a-button type="link" @click="smartRecommend" style="padding: 0">智能推荐</a-button>
          <span class="hint" style="margin-left: 8px">按关键词/标签/城市/省份/价格自动匹配</span>
        </div>
      </a-form-item>
      <a-form-item label="定时上架">
        <a-date-picker v-model:value="form.scheduled_at" show-time placeholder="留空=立即草稿" style="width: 100%" />
      </a-form-item>
      <a-form-item label="客服备注（仅后台可见）">
        <a-textarea v-model:value="form.service_remark" :rows="2" />
      </a-form-item>
      <a-form-item :wrapper-col="{ offset: 4, span: 16 }">
        <a-space>
          <a-button type="primary" html-type="submit" :loading="loading">保存</a-button>
          <a-button @click="onPublish" :loading="loading">保存并发布</a-button>
        </a-space>
      </a-form-item>
    </a-form>
  </a-card>
      </a-tab-pane>
      <a-tab-pane key="batch" tab="批量导入">
        <a-card :bordered="true">
          <div
            style="border:1px dashed #d9d9d9;border-radius:8px;padding:32px;text-align:center;cursor:pointer"
            @click="triggerBatchUpload">
            <plus-outlined style="font-size: 32px; color: #999" />
            <p style="margin-top: 12px; color: #8a91a5">点击或拖拽 ZIP 压缩包到此处批量导入</p>
          </div>
          <input ref="batchInput" type="file" accept=".zip" style="display:none" @change="onBatchFile" />
          <div class="aq-tip" style="margin-top: 12px">ZIP 内每张图片将自动创建为一条草稿资料</div>
        </a-card>
      </a-tab-pane>
    </a-tabs>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import { message } from 'ant-design-vue';
import { PlusOutlined } from '@ant-design/icons-vue';
import { noteApi, metaApi, channelApi, mediaApi } from '@/api';

const loading = ref(false);
const tags = ref<any[]>([]);
const cities = ref<any[]>([]);
const channels = ref<any[]>([]);
const showList = ref<any[]>([]);
const verifyList = ref<any[]>([]);
const showInput = ref<HTMLInputElement | null>(null);
const batchInput = ref<HTMLInputElement | null>(null);

function triggerShowUpload() { showInput.value?.click(); }
function onShowFiles(e: Event) {
  const files = (e.target as HTMLInputElement).files;
  if (!files) return;
  for (const f of Array.from(files)) {
    showList.value.push({ uid: `${Date.now()}-${f.name}`, name: f.name, originFileObj: f, status: 'done' });
  }
}
function triggerBatchUpload() { batchInput.value?.click(); }
async function onBatchFile(e: Event) {
  const files = (e.target as HTMLInputElement).files;
  if (!files?.length) return;
  message.info(`已选择 ${files[0].name}，批量导入功能开发中`);
}
const form = reactive({
  title: '', body: '', tags: [] as string[], city: [] as number[],
  channel_ids: [] as number[], scheduled_at: null as any, service_remark: '',
});

onMounted(async () => {
  tags.value = await metaApi.tags();
  cities.value = await metaApi.cityTree();
  channels.value = await channelApi.list(true);
  // 默认选中的频道自动勾选，第二次上传不用重新选
  form.channel_ids = channels.value.filter((c: any) => c.isDefault).map((c: any) => c.id);
});
async function smartRecommend() {
  try {
    const r: any = await channelApi.recommendPreview({
      title: form.title, body: form.body, tags: form.tags,
    });
    form.channel_ids = r.channelIds || [];
    message.success(r.matchedRule ? '已按规则推荐频道' : '无规则命中，已回退默认频道');
  } catch (e: any) { message.error(e.message); }
}

async function buildPayload() {
  // 展示图 + 验证视频：逐个上传到 /api/media/materials，拿到 URL 后组装进笔记
  async function uploadList(list: any[], kind: string, mediaType: string) {
    const media: any[] = [];
    for (let i = 0; i < list.length; i++) {
      const f = list[i];
      let url = f.url;
      if (!url && f.originFileObj) {
        const res: any = await mediaApi.uploadMaterial(f.originFileObj, f.name || kind);
        url = res.url;
        f.url = url;
        f.status = 'done'; // 记下来，避免重复上传
      }
      if (url) media.push({ url, media_type: mediaType, kind, sort_order: i });
    }
    return media;
  }
  const media = [
    ...(await uploadList(showList.value, 'show', 'image')),
    ...(await uploadList(verifyList.value, 'verify', 'video')),
  ];
  return {
    title: form.title, body: form.body, tags: form.tags,
    city_id: form.city.length ? form.city[form.city.length - 1] : null,
    channel_ids: form.channel_ids,
    scheduled_at: form.scheduled_at ? form.scheduled_at.toISOString() : null,
    service_remark: form.service_remark,
    media,
  };
}
async function resetForm() {
  Object.assign(form, {
    title: '', body: '', tags: [], city: [], scheduled_at: null, service_remark: '',
    channel_ids: channels.value.filter((c: any) => c.isDefault).map((c: any) => c.id),
  });
  showList.value = []; verifyList.value = [];
}
async function onSubmit() {
  loading.value = true;
  try {
    await noteApi.create(await buildPayload());
    message.success('已保存草稿');
    resetForm();
  } catch (e: any) { message.error(e.message); } finally { loading.value = false; }
}
async function onPublish() {
  loading.value = true;
  try {
    const n: any = await noteApi.create(await buildPayload());
    await noteApi.publish(n.id);
    message.success('已发布');
    resetForm();
  } catch (e: any) { message.error(e.message); } finally { loading.value = false; }
}
</script>
