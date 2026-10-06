<template>
  <router-view v-if="isLoginPage" />
  <a-layout v-else style="min-height: 100vh">
    <a-layout-sider collapsible v-model:collapsed="collapsed" width="220">
      <div class="logo">小灰机 · 商家后台</div>
      <a-menu v-model:selectedKeys="selected" mode="inline" theme="dark" @click="onMenu">
        <template v-for="m in menus" :key="m.path">
          <a-sub-menu v-if="m.children" :key="m.path" :title="m.title">
            <a-menu-item v-for="c in m.children" :key="c.path">{{ c.title }}</a-menu-item>
          </a-sub-menu>
          <a-menu-item v-else :key="m.path">{{ m.title }}</a-menu-item>
        </template>
      </a-menu>
    </a-layout-sider>
    <a-layout>
      <a-layout-header class="header">
        <a-button type="text" @click="collapsed = !collapsed" style="font-size: 18px; padding: 0 12px;">
          <menu-outlined v-if="collapsed" />
          <menu-fold-outlined v-else />
        </a-button>
        <div style="flex: 1" />
        <a-space>
          <span>{{ username }}</span>
          <a-button size="small" @click="logout">退出</a-button>
        </a-space>
      </a-layout-header>
      <a-layout-content class="content">
        <router-view />
      </a-layout-content>
      <!-- 移动端底部导航 -->
      <div v-if="isMobile" class="mobile-tabbar">
        <div
          v-for="t in tabItems" :key="t.path"
          class="tab-item" :class="{ active: selected.includes(t.path) }"
          @click="router.push(t.path)"
        >
          <div class="tab-icon"><component :is="t.icon" /></div>
          <div class="tab-label">{{ t.title }}</div>
        </div>
      </div>
    </a-layout>
    <a-modal v-model:open="annVisible" :title="annCurrent.title" @ok="dismissAnn" ok-text="知道了">
      <div style="white-space: pre-wrap">{{ annCurrent.content }}</div>
    </a-modal>
  </a-layout>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { MenuOutlined, MenuFoldOutlined, HomeOutlined, UploadOutlined, FileTextOutlined, UserOutlined } from '@ant-design/icons-vue';
import { authApi, announceApi } from '@/api';

const route = useRoute();
const router = useRouter();
// 移动端默认收起侧边栏，桌面端默认展开
const collapsed = ref(typeof window !== 'undefined' ? window.innerWidth < 768 : false);
const isMobile = ref(typeof window !== 'undefined' ? window.innerWidth < 768 : false);
// 底部导航：工作台 / 上传 / 笔记 / 我的
const tabItems = [
  { path: '/admin/dashboard', title: '工作台', icon: HomeOutlined },
  { path: '/collector/upload', title: '上传', icon: UploadOutlined },
  { path: '/admin/notes', title: '笔记', icon: FileTextOutlined },
  { path: '/admin/vip', title: '我的', icon: UserOutlined },
];
const menus = ref<any[]>([]);
const selected = ref<string[]>([]);
const username = ref('');
const annQueue = ref<any[]>([]);
const annCurrent = ref<any>({});
const annVisible = ref(false);

function dismissAnn() {
  try { localStorage.setItem('ann_read_' + annCurrent.value.id, '1'); } catch { /* ignore */ }
  annVisible.value = false;
  showNextAnn();
}
function showNextAnn() {
  const next = annQueue.value.shift();
  if (next) { annCurrent.value = next; annVisible.value = true; }
}
async function loadAnnouncements() {
  try {
    const list: any[] = await announceApi.active();
    annQueue.value = list.filter((a: any) => {
      try { return !localStorage.getItem('ann_read_' + a.id); } catch { return true; }
    });
    showNextAnn();
  } catch { /* ignore */ }
}

const isLoginPage = computed(() => route.path === '/login');

function onMenu({ key }: any) { router.push(key); }
function logout() {
  authApi.logout().finally(() => {
    localStorage.removeItem('access_token');
    menus.value = [];
    username.value = '';
    router.push('/login');
  });
}

watch(() => route.path, (p) => { selected.value = [p]; }, { immediate: true });

// 登录后从 /login 进入后台时需加载菜单（onMounted 在登录页已执行过）
async function loadUserState() {
  if (isLoginPage.value) return;
  if (!localStorage.getItem('access_token')) return;
  try {
    menus.value = await authApi.menu();
    const me: any = await authApi.current();
    username.value = me.username;
    loadAnnouncements();
  } catch { /* 401 由 request 拦截器跳登录 */ }
}
watch(() => route.path, () => { loadUserState(); });
onMounted(() => { loadUserState(); });
</script>

<style scoped>
.logo { color: #fff; text-align: center; padding: 16px 0; font-weight: bold; }
.header { background: #fff; padding: 0 16px 0 0; display: flex; align-items: center; }
.content { margin: 16px; background: #fff; padding: 16px; min-height: 80vh; }
.mobile-tabbar {
  display: none;
  position: fixed; bottom: 0; left: 0; right: 0; z-index: 100;
  background: #fff; border-top: 1px solid #f0f0f0;
  padding-bottom: env(safe-area-inset-bottom);
}
.tab-item {
  flex: 1; text-align: center; padding: 8px 0 6px;
  color: #999; font-size: 12px; cursor: pointer;
}
.tab-item.active { color: #1890ff; }
.tab-icon { font-size: 20px; margin-bottom: 2px; }
@media (max-width: 768px) {
  .mobile-tabbar { display: flex; }
  .content { margin: 8px; padding: 12px; margin-bottom: 70px; }
  .ant-layout-sider { position: fixed !important; z-index: 101; height: 100vh; }
}
</style>
