<template>
  <a-config-provider :theme="antdTheme">
  <router-view v-if="isLoginPage" />
  <a-layout v-else style="min-height: 100vh">
    <div v-if="isMobile && !collapsed" class="mobile-sider-mask" @click="collapsed = true" />
    <a-layout-sider
      class="pro-sider"
      collapsible
      v-model:collapsed="collapsed"
      width="200"
      :trigger="null"
    >
      <div class="pro-logo" :class="{ collapsed }">
        <span v-if="!collapsed" class="pro-logo-title">小灰机管理平台</span>
      </div>
      <a-menu
        v-model:selectedKeys="selected"
        mode="inline"
        theme="light"
        @click="onMenu"
      >
        <template v-for="g in menus" :key="g.title">
          <a-menu-item-group :title="g.title">
            <a-menu-item v-for="c in g.children" :key="c.path">{{ c.title }}</a-menu-item>
          </a-menu-item-group>
        </template>
      </a-menu>
    </a-layout-sider>
    <a-layout>
      <a-layout-header class="pro-header">
        <span class="trigger-btn" @click="collapsed = !collapsed">
          <menu-outlined v-if="collapsed" />
          <menu-fold-outlined v-else />
        </span>
        <span class="pro-app-title">小灰机管理平台</span>
        <div class="pro-header-right">
          <span class="vip-badge" @click="router.push('/admin/vip')">VIP</span>
          <span class="pro-username">
            <span class="uname">{{ username || '主账号' }}</span>
          </span>
          <span class="pro-version">v1.0.0</span>
          <span class="pro-doc-link" @click="router.push('/admin/announcements')">使用说明</span>
          <span class="pro-doc-link" @click="logout">退出</span>
        </div>
      </a-layout-header>
      <a-layout-content class="pro-content">
        <router-view />
      </a-layout-content>
      <!-- 移动端底部导航 -->
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
  </a-config-provider>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import {
  MenuOutlined, MenuFoldOutlined,
  HomeOutlined, UploadOutlined, FileTextOutlined, BellOutlined, UserOutlined,
} from '@ant-design/icons-vue';
import { authApi, announceApi } from '@/api';

// meiren.pro 主题 token（live browser 逆向确认）
const antdTheme = {
  token: {
    colorPrimary: '#1677ff',
    colorSuccess: '#52c41a',
    colorError: '#ff4d4f',
    colorWarning: '#faad14',
    colorInfo: '#1677ff',
    borderRadius: 6,
    borderRadiusLG: 8,
    fontFamily: '-apple-system, "PingFang SC", "Microsoft YaHei", sans-serif',
    colorText: 'rgba(0, 0, 0, 0.88)',
    colorTextSecondary: 'rgba(0, 0, 0, 0.45)',
    colorBorder: '#f0f0f0',
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
// meiren.pro 1:1 菜单（24 项，3 分组）
// 路由复用现有页面，不存在的指向占位页
const MEIREN_MENUS = [
  {
    title: '运营管理',
    children: [
      { path: '/admin/dashboard', title: '工作台' },
      { path: '/admin/users', title: '用户管理' },
      { path: '/admin/customer', title: '客户管理' },
      { path: '/admin/message-push', title: '群发管理' },
      { path: '/admin/logs', title: '发送记录' },
      { path: '/admin/dedup', title: '去重记录' },
    ],
  },
  {
    title: '配置管理',
    children: [
      { path: '/admin/city', title: '城市管理' },
      { path: '/collector/content', title: '资料库' },
      { path: '/admin/phrases', title: '话术库' },
      { path: '/admin/accounts/protocol', title: '协议号管理' },
      { path: '/admin/collection', title: '采集源管理' },
      { path: '/admin/sensitive', title: '敏感词管理' },
      { path: '/admin/message-push', title: '消息推送配置' },
      { path: '/admin/global/loop', title: '定时任务管理' },
      { path: '/admin/accounts/protocol', title: 'TG 账号管理' },
      { path: '/admin/tg-groups', title: 'TG 群组管理' },
      { path: '/admin/announcements', title: '公告管理' },
    ],
  },
  {
    title: '内容管理',
    children: [
      { path: '/admin/ads', title: '广告管理' },
      { path: '/admin/accounts/two-way-bots', title: '自动回复管理' },
      { path: '/admin/collection/review', title: '采集审核' },
      { path: '/admin/group-listen', title: '关键词管理' },
      { path: '/admin/blacklist', title: '黑名单管理' },
      { path: '/admin/global/confuse', title: '系统配置' },
      { path: '/admin/logs', title: '操作日志' },
    ],
  },
];
// 会员不可见
const MEMBER_HIDDEN = ['/admin/users'];
// 普通用户仅可见
const USER_ONLY = ['/admin/notes'];

const menus = ref<any[]>([]);
const selected = ref<string[]>([]);
const username = ref('');
const annQueue = ref<any[]>([]);
const annCurrent = ref<any>({});
const annVisible = ref(false);

function isTabActive(path: string) {
  const p = route.path;
  if (p === path) return true;
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
    const me: any = await authApi.current();
    username.value = me.username;
    // 按权限过滤 meiren 菜单（前端静态，不再依赖后端 /menu/all）
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
