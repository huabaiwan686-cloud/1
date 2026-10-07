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
        <span class="pro-logo-title">小灰机管理平台</span>
      </div>
      <a-menu
        v-model:selectedKeys="selected"
        mode="inline"
        theme="light"
        @click="onMenu"
      >
        <template v-for="g in menus" :key="g.title">
          <a-menu-item-group :title="g.title">
            <a-menu-item
              v-for="c in g.children"
              :key="c.path"
              :data-menu-id="c.path"
              class="pro-menu-item"
            >{{ c.title }}</a-menu-item>
          </a-menu-item-group>
        </template>
      </a-menu>
    </a-layout-sider>
    <a-layout>
      <a-layout-header class="pro-header">
        <span v-if="isMobile" class="trigger-btn" @click="collapsed = !collapsed">
          <menu-outlined />
        </span>
        <span class="pro-page-title">{{ pageTitle }}</span>
        <div class="pro-header-right">
          <span class="vip-trial-badge">试用 26 天</span>
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
import zhCN from 'ant-design-vue/es/locale/zh_CN';
import { authApi, announceApi } from '@/api';

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
      { path: '/collector/content', title: '资料库' },
      { path: '/collector/records', title: '采集记录' },
      { path: '/admin/channels', title: '上架频道' },
      { path: '/admin/records', title: '发送记录' },
      { path: '/admin/notes', title: '上下架管理' },
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
];
// 会员不可见
const MEMBER_HIDDEN = ['/admin/users'];

// 顶栏左标题：按路由显示页面名
const PAGE_TITLES: Record<string, string> = {
  '/admin/dashboard': '小灰机管理平台',
  '/admin/vip': 'VIP 会员',
  '/admin/users': '用户管理',
  '/admin/channels/up': '上架频道',
  '/admin/channels/down': '下架频道',
  '/admin/tg': '协议号',
  '/admin/relay': '自动转发',
  '/admin/records': '发送记录',
  '/admin/group-listen': '关键词监控',
  '/admin/global/confuse': '防扫图',
  '/admin/settings': '系统设置',
  '/admin/collection': '代理采集',
  '/admin/antidedup': '防去重',
  '/admin/dedup': '去重记录',
  '/collector/content': '资料库',
  '/admin/collection/review': '采集审核',
  '/admin/message-push': '消息推送',
  '/admin/friends': '好友关注',
  '/admin/tags': '标签库',
  '/collector/upload': '素材上传',
  '/admin/distribution': '分发规则',
  '/admin/bots': 'Bot 管理',
  '/admin/group-listen-manage': '群监听',
  '/admin/accounts/two-way-bots': '双向机器人',
};
const pageTitle = computed(() => PAGE_TITLES[route.path] || '小灰机管理平台');

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

async function loadUserState() {
  if (isLoginPage.value) return;
  if (!localStorage.getItem('access_token')) return;
  try {
    const me: any = await authApi.current();
    username.value = me.username;
    // 按权限过滤 meiren 菜单（前端静态）
    if (me.isAdmin) {
      menus.value = MEIREN_MENUS;
    } else if (me.isMember) {
      menus.value = MEIREN_MENUS.map(g => ({
        ...g,
        children: g.children.filter((c: any) => !MEMBER_HIDDEN.includes(c.path)),
      })).filter(g => g.children.length > 0);
    } else {
      menus.value = [{ title: '运营管理', children: [{ path: '/admin/notes', title: '上下架' }] }];
    }
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
</style>
