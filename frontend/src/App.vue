<template>
  <a-config-provider :theme="antdTheme" :locale="zhCN">
  <router-view v-if="isLoginPage" />
  <a-layout v-else style="min-height: 100vh">
    <!-- 移动端遮罩 -->
    <div v-if="isMobile && !collapsed" class="mobile-sider-mask" @click="collapsed = true" />
    <a-layout-sider
      class="pro-sider"
      v-model:collapsed="collapsed"
      :collapsedWidth="isMobile ? 0 : 200"
      width="200"
      :trigger="null"
    >
      <div class="pro-logo">
        <span class="pro-logo-title">管理平台</span>
      </div>
      <a-menu
        v-model:selectedKeys="selected"
        mode="inline"
        theme="light"
        @click="onMenu"
      >
        <a-sub-menu v-for="g in menus" :key="g.title" :title="g.title">
          <a-menu-item
            v-for="c in g.children"
            :key="c.path"
            :data-menu-id="c.path"
            class="pro-menu-item"
          >{{ c.title }}</a-menu-item>
        </a-sub-menu>
      </a-menu>
    </a-layout-sider>
    <a-layout>
      <a-layout-header class="pro-header">
        <span v-if="isMobile" class="trigger-btn" @click="collapsed = !collapsed">
          <menu-outlined />
        </span>
        <span class="pro-page-title">{{ pageTitle }}</span>
        <div class="pro-header-right">
          <span class="pro-account-type">{{ username || '主账号' }}</span>
          <span class="pro-version">v6.3</span>
          <a class="topbar-docs" href="/docs/" target="_blank">📖 使用说明</a>
          <a-button type="link" size="small" @click="logout"><span>退出</span></a-button>
        </div>
      </a-layout-header>
      <a-layout-content class="pro-content">
        <main class="ant-layout-content content-area">
          <router-view />
        </main>
      </a-layout-content>
    </a-layout>
    <a-modal v-model:open="annVisible" :title="annCurrent.title" @ok="dismissAnn" ok-text="知道了">
      <div style="white-space: pre-wrap">{{ annCurrent.content }}</div>
    </a-modal>
  </a-layout>
  </a-config-provider>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { MenuOutlined } from '@ant-design/icons-vue';
import { authApi } from './api';
import zhCN from 'ant-design-vue/es/locale/zh_CN';

// antd v5 默认主题 token（REVERSE_ENGINEERING.md 实测值）
const antdTheme = {
  token: {
    colorPrimary: '#1677ff',
    colorSuccess: '#52c41a',
    colorError: '#ff4d4f',
    colorWarning: '#faad14',
    colorInfo: '#1677ff',
    borderRadius: 6,
    borderRadiusLG: 8,
    fontFamily: "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,'Noto Sans',sans-serif",
    fontSize: 14,
    colorText: 'rgba(0, 0, 0, 0.88)',
    colorTextSecondary: 'rgba(0, 0, 0, 0.45)',
    colorBorder: '#d9d9d9',
    colorSplit: '#f0f0f0',
  },
  components: {
    Card: { borderRadiusLG: 8 },
    Modal: { borderRadiusLG: 8 },
    Table: { headerBg: '#fafafa', borderRadiusLG: 8 },
    Tag: { borderRadiusSM: 4 },
    Button: { borderRadius: 6 },
    Input: { borderRadius: 6 },
  },
};

const route = useRoute();
const router = useRouter();
// meiren 无折叠功能；移动端默认收起（抽屉式），桌面端默认展开
const collapsed = ref(typeof window !== 'undefined' ? window.innerWidth < 768 : false);
const isMobile = ref(typeof window !== 'undefined' ? window.innerWidth < 768 : false);

// meiren.pro 1:1 菜单（REVERSE_ENGINEERING.md §2，4 分组 24 项）
// 路由复用现有页面
const MEIREN_MENUS = [
  {
    title: '上下架',
    children: [
      { path: '/collector/upload', title: '素材上传' },
      { path: '/admin/notes', title: '资料库' },
      { path: '/admin/channels', title: '上架频道' },
      { path: '/admin/bots', title: 'Bot 管理' },
    ],
  },
  {
    title: '协议号',
    children: [
      { path: '/admin/tg', title: '协议号管理' },
    ],
  },
  {
    title: '全局抠图',
    children: [
      { path: '/admin/global/bg-replace', title: '全局抠图' },
    ],
  },
  {
    title: '全局循环',
    children: [
      { path: '/admin/global/loop', title: '全局循环' },
    ],
  },
  {
    title: '群聊推送',
    children: [
      { path: '/admin/message-push', title: '群聊推送' },
    ],
  },
];
// 会员不可见

// 顶栏左标题：按路由显示页面名
const PAGE_TITLES: Record<string, string> = {
  '/admin/channels/up': '上架频道',
  '/admin/channels/down': '下架频道',
  '/admin/tg': '协议号',
  '/admin/global/bg-replace': '全局抠图',
  '/collector/content': '资料库',
  '/admin/message-push': '消息推送',
  '/collector/upload': '素材上传',
  '/admin/bots': 'Bot 管理',
};
const pageTitle = computed(() => PAGE_TITLES[route.path] || '管理平台');

const menus = ref<any[]>([]);
const selected = ref<string[]>([]);
const username = ref('');
const annQueue = ref<any[]>([]);
const annCurrent = ref<any>({});
const annVisible = ref(false);

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


const isLoginPage = computed(() => route.path === '/login');

function onMenu({ key }: any) {
  router.push(key);
  if (isMobile.value) collapsed.value = true;
}
function logout() {
  authApi.logout().finally(() => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    menus.value = [];
    username.value = '';
    router.push('/login');
  });
}

watch(() => route.path, (p) => { selected.value = [p]; }, { immediate: true });

async function loadUserState() {
  if (isLoginPage.value) return;
  if (!localStorage.getItem('access_token')) return;
  try {
    const me: any = await authApi.current();
    username.value = me.username;
    // 按权限过滤 meiren 菜单（前端静态）
    // 会员管理仅超管 dah86586 可见
    const SUPER_ADMIN = 'dah86586';
    const filterSuperOnly = (menus: any[]) => menus.map(g => ({
      ...g,
      children: g.children,
    })).filter(g => g.children.length > 0);
    if (me.is_admin) {
      if (me.username === SUPER_ADMIN) {
        menus.value = MEIREN_MENUS;
      } else {
        menus.value = filterSuperOnly(MEIREN_MENUS);
      }
    } else if (me.is_member) {
      menus.value = filterSuperOnly(MEIREN_MENUS.map(g => ({
        ...g,
      })).filter(g => g.children.length > 0));
    } else {
      menus.value = [{ title: '运营管理', children: [{ path: '/admin/notes', title: '上下架' }] }];
    }
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
</style>
