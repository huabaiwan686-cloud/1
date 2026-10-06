<template>
  <div class="review" tabindex="0" @keydown="onKey">
    <!-- 顶部：进度 + 操作 -->
    <div class="topbar">
      <div class="progress-wrap">
        <div class="progress-info">
          <span>待审核 <b>{{ queue.length }}</b></span>
          <span class="done">今日已审 {{ doneCount }}</span>
        </div>
        <a-progress :percent="percent" :show-info="false" stroke-color="#1677ff" />
      </div>
      <a-space>
        <a-button @click="approveAll" :disabled="!queue.length">全部通过</a-button>
        <a-button @click="reload">刷新队列</a-button>
      </a-space>
    </div>

    <!-- 空队列 -->
    <div v-if="!current && !loading" class="empty">
      <check-circle-outlined style="font-size: 56px; color: #52c41a" />
      <h3>审核队列已清空</h3>
      <p>所有采集到的资料都处理完了，喝杯茶吧</p>
      <a-button type="primary" @click="reload">重新加载</a-button>
    </div>

    <a-spin :spinning="loading">
      <div v-if="current" class="main">
        <!-- 大图区 -->
        <div class="img-pane">
          <a-carousel v-if="media.length" arrows :key="current.id">
            <div v-for="m in media" :key="m.id" class="slide">
              <img :src="m.url" @error="onImgError" />
            </div>
          </a-carousel>
          <div v-else class="noimg">无图片资料</div>
          <div class="media-dots" v-if="media.length > 1">{{ media.length }} 张图片，左右切换</div>
        </div>
        <!-- 信息区 -->
        <div class="info-pane">
          <div class="info-head">
            <h2>{{ current.title || '无标题' }}</h2>
            <a-tag color="orange">待审核</a-tag>
          </div>
          <a-descriptions :column="1" size="small" class="meta">
            <a-descriptions-item label="标签">{{ (current.tags || []).join('、') || '—' }}</a-descriptions-item>
            <a-descriptions-item label="来源">{{ current.source }}</a-descriptions-item>
            <a-descriptions-item label="采集时间">{{ (current.createdAt || '').slice(0, 16).replace('T', ' ') }}</a-descriptions-item>
          </a-descriptions>
          <div class="body-label">正文</div>
          <pre class="body">{{ current.body || '（无正文）' }}</pre>
        </div>
      </div>
    </a-spin>

    <!-- 底部操作条 -->
    <div v-if="current" class="actionbar">
      <a-button size="large" danger @click="reject" class="act-btn">← 拒绝</a-button>
      <a-button size="large" @click="skip" class="act-btn">跳过 ↓</a-button>
      <a-button size="large" type="primary" @click="approve" class="act-btn">通过 →</a-button>
    </div>
    <div v-if="current" class="kbd-hint">键盘快捷键：← 拒绝　→ 通过　↓ 跳过</div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue';
import { message, Modal } from 'ant-design-vue';
import { CheckCircleOutlined } from '@ant-design/icons-vue';
import { noteApi } from '@/api';

const queue = ref<any[]>([]);
const loading = ref(false);
const doneCount = ref(0);
const totalCount = ref(0);

const current = computed(() => queue.value[0] || null);
const media = computed(() => (current.value?.media || []).filter((m: any) => m.kind !== 'verify'));
const percent = computed(() =>
  totalCount.value ? Math.round((doneCount.value / totalCount.value) * 100) : 0,
);

async function reload() {
  loading.value = true;
  try {
    const data: any = await noteApi.list({ status: 'pending', page: 1, page_size: 500 });
    queue.value = data.list;
    totalCount.value = data.total;
    doneCount.value = 0;
  } finally {
    loading.value = false;
  }
}

async function decide(approveIt: boolean) {
  if (!current.value) return;
  const id = current.value.id;
  if (approveIt) await noteApi.approve(id);
  else await noteApi.reject(id);
  queue.value.shift();
  doneCount.value += 1;
}
function approve() { decide(true).then(() => message.success('已通过并发布')); }
function reject() { decide(false).then(() => message.info('已拒绝（移入下架）')); }
function skip() {
  if (!queue.value.length) return;
  queue.value.push(queue.value.shift());
}

function approveAll() {
  Modal.confirm({
    title: `确认通过全部 ${queue.value.length} 条？`,
    onOk: async () => {
      const ids = queue.value.map((n) => n.id);
      const res: any = await noteApi.batch(ids, 'publish');
      message.success(`已通过 ${res.count} 条`);
      queue.value = [];
      doneCount.value = totalCount.value;
    },
  });
}

function onKey(e: KeyboardEvent) {
  if (e.key === 'ArrowRight') approve();
  else if (e.key === 'ArrowLeft') reject();
  else if (e.key === 'ArrowDown') { e.preventDefault(); skip(); }
}

function onImgError(e: Event) {
  (e.target as HTMLImageElement).style.display = 'none';
}

onMounted(() => {
  reload();
  window.addEventListener('keydown', onKey);
});
onUnmounted(() => {
  window.removeEventListener('keydown', onKey);
});
</script>

<style scoped>
.review { max-width: 1200px; margin: 0 auto; outline: none; }
.topbar {
  display: flex; align-items: center; gap: 16px; margin-bottom: 16px;
}
.progress-wrap { flex: 1; }
.progress-info { display: flex; gap: 16px; margin-bottom: 4px; font-size: 14px; }
.progress-info b { color: #1677ff; font-size: 16px; }
.progress-info .done { color: #52c41a; }
.main {
  display: flex; gap: 20px; background: #fff;
  border: 1px solid #f0f0f0; border-radius: 10px; overflow: hidden;
}
.img-pane { flex: 3; background: #000; min-height: 480px; position: relative; }
.slide { text-align: center; }
.slide img { max-height: 62vh; min-height: 480px; max-width: 100%; object-fit: contain; margin: 0 auto; }
.noimg {
  height: 480px; display: flex; align-items: center; justify-content: center;
  color: #666; background: #141414;
}
.media-dots {
  position: absolute; bottom: 10px; width: 100%; text-align: center;
  color: rgba(255, 255, 255, 0.75); font-size: 12px;
}
.info-pane { flex: 2; padding: 20px; display: flex; flex-direction: column; min-width: 0; }
.info-head { display: flex; align-items: center; gap: 10px; }
.info-head h2 { margin: 0; font-size: 20px; }
.meta { margin: 12px 0; }
.body-label { font-size: 13px; color: #999; margin-bottom: 6px; }
.body {
  flex: 1; white-space: pre-wrap; word-break: break-word;
  background: #fafafa; border-radius: 8px; padding: 14px;
  max-height: 46vh; overflow: auto; margin: 0; font-size: 14px; line-height: 1.7;
}
.actionbar {
  display: flex; gap: 16px; justify-content: center;
  margin-top: 20px;
}
.act-btn { min-width: 160px; height: 48px; font-size: 16px; border-radius: 8px; }
.kbd-hint { text-align: center; color: #bbb; font-size: 12px; margin-top: 10px; }
.empty { text-align: center; padding: 80px 0; }
.empty h3 { margin: 16px 0 8px; }
.empty p { color: #999; margin-bottom: 20px; }
@media (max-width: 768px) {
  .main { flex-direction: column; }
  .slide img { min-height: 300px; }
  .act-btn { min-width: 0; flex: 1; }
  .topbar { flex-wrap: wrap; }
}
</style>
