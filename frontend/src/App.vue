<template>
  <router-view v-if="isLoginPage" />
  <a-layout v-else style="min-height: 100vh">
    <div v-if="isMobile && !collapsed" class="mobile-sider-mask" @click="collapsed = true" />
    <a-layout-sider
      class="pro-sider"
      collapsible
      v-model:collapsed="collapsed"
      width="220"
      :trigger="null"
    >
      <div class="pro-logo" :class="{ collapsed }">
        <span class="pro-logo-badge">灰</span>
        <span v-if="!collapsed" style="margin-left: 12px">
          <span class="pro-logo-title">小灰机</span>
          <span class="pro-logo-sub">商家后台</span>
        </span>
      </div>
      <a-menu
        v-model:selectedKeys="selected"
        mode="inline"
        theme="dark"
        @click="onMenu"
      >
        <template v-for="m in menus" :key="m.path">
          <a-sub-menu v-if="m.children" :key="m.path" :title="m.title">
            <a-menu-item v-for="c in m.children" :key="c.path">{{ c.title }}</a-menu-item>
          </a-sub-menu>
          <a-menu-item v-else :key="m.path">{{ m.title }}</a-menu-item>
        </template>
      </a-menu>
    </a-layout-sider>
    <a-layout>
      <a-layout-header class="pro-header">
        <span class="trigger-btn" @click="collapsed = !collapsed">
          <menu-outlined v-if="collapsed" />
          <menu-fold-outlined v-else />
        </span>
        <span class="pro-app-title">小灰机 · 商家后台</span>
        <div class="pro-header-right">
          <span class="pro-username">
            <span class="pro-avatar">{{ username ? username.slice(0, 1).toUpperCase() : 'U' }}</span>
            <span class="uname">{{ username }}</span>
          </span>
          <a-button size="small" @click="logout">退出</a-button>
        </div>
      </a-layout-header>
      <a-layout-content class="pro-content">
        <router-view />
      </a-layout-content>
      <!-- 移动端底部导航（App 风 5 Tab） -->
      <div v-if="isMobile" class="mobile-tabbar">
        <div
          v-for="t in tabItems" :key="t.path"
          class="tab-item" :class="{ active: isTabActive(t.path) }"
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
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import {
  MenuOutlined, MenuFoldOutlined,
  HomeOutlined, UploadOutlined, FileTextOutlined,
  BellOutlined, UserOutlined,
} from '@ant-design/icons-vue';
import { authApi, announceApi } from '@/api';

const route = useRoute();
const router = useRouter();
// 移动端默认收起侧边栏，桌面端默认展开
const collapsed = ref(typeof window !== 'undefined' ? window.innerWidth < 768 : false);
const isMobile = ref(typeof window !== 'undefined' ? window.innerWidth < 768 : false);
// 底部导航 5 Tab：工作台 / 上传 / 笔记 / 消息 / 我的
const tabItems = [
  { path: '/admin/dashboard', title: '工作台', icon: HomeOutlined },
  { path: '/collector/upload', title: '上传', icon: UploadOutlined },
  { path: '/admin/notes', title: '笔记', icon: FileTextOutlined },
  { path: '/admin/announcements', title: '消息', icon: BellOutlined },
  { path: '/admin/vip', title: '我的', icon: UserOutlined },
];
const menus = ref<any[]>([]);
const selected = ref<string[]>([]);
const username = ref('');
const annQueue = ref<any[]>([]);
const annCurrent = ref<any>({});
const annVisible = ref(false);

function isTabActive(path: string) {
  const p = route.path;
  if (p === path) return true;
  // 子路由也算选中（如 /admin/announcements/xxx）
  if (path !== '/admin/dashboard' && p.startsWith(path + '/')) return true;
  return false;
}

function onResize() {
  const mobile = window.innerWidth < 768;
  if (mobile !== isMobile.value) {
    isMobile.value = mobile;
    collapsed.value = mobile;
  }
}

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

function onMenu({ key }: any) {
  router.push(key);
  if (isMobile.value) collapsed.value = true;
}
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
onMounted(() => {
  loadUserState();
  window.addEventListener('resize', onResize);
});
onUnmounted(() => {
  window.removeEventListener('resize', onResize);
});
</script>

<style scoped>
/* TabBar 基础样式（颜色由 theme.css 深色主题接管） */
.mobile-tabbar {
  display: none;
}
@media (max-width: 768px) {
  .mobile-tabbar {
    display: flex;
  }
}
</style>
