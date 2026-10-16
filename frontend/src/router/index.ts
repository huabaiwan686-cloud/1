import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router';
import { authApi } from '@/api';

export const routes: RouteRecordRaw[] = [
  { path: '/login', component: () => import('@/views/login.vue') },
  { path: '/', redirect: '/collector/upload' },
  { path: '/collector/upload', component: () => import('@/views/collector/upload.vue') },
  { path: '/collector/content', redirect: '/admin/notes' },
  { path: '/admin/notes', component: () => import('@/views/admin/notes.vue') },
  { path: '/admin/channels', component: () => import('@/views/admin/channels.vue') },
  { path: '/admin/message-push', component: () => import('@/views/admin/message-push.vue') },
  // 运营管理（meiren.pro 1:1）
  { path: '/admin/tg', component: () => import('@/views/admin/tg.vue') },
  // 全局设置：背景替换 / 循环发布
  { path: '/admin/global/bg-replace', component: () => import('@/views/admin/global-bg-replace.vue') },
  { path: '/admin/global/loop', component: () => import('@/views/admin/global-loop.vue') },
  { path: '/admin/bots', component: () => import('@/views/admin/bots.vue') },
  // 旧路由兼容重定向
];

const router = createRouter({ history: createWebHistory(), routes });

router.beforeEach(async (to) => {
  if (to.path !== '/login' && !localStorage.getItem('access_token')) {
    return '/login';
  }
  // 功能裁剪：只允许 4 个核心模块的路由
  const ALLOWED_PATHS = [
    '/login',
    '/',
    '/collector/upload',
    '/collector/content',
    '/admin/channels',
    '/admin/notes',
    '/admin/tg',
    '/admin/global/bg-replace',
    '/admin/global/loop',
    '/admin/message-push',
    '/admin/bots',
      // 重定向到 bg-replace
      // 重定向到 loop
  ];
  // 允许重定向目标
  const isAllowed = ALLOWED_PATHS.some(p => to.path === p || to.path.startsWith(p + '?'));
  if (!isAllowed && to.path !== '/login') {
    // 未授权页面重定向到资料库
    return '/collector/content';
  }
  // 权限：普通用户仅允许 /admin/notes（上下架），超管全部
  if (to.path.startsWith('/admin/')) {
    try {
      const me: any = await authApi.current();
      if (me.is_admin) { /* 全部放行 */ }
      else {
        if (to.path !== '/admin/notes') return '/admin/notes';
      }
    } catch { return '/login'; }
  }
  // 非会员禁止进入采集/发布端页面
  if (to.path.startsWith('/collector/') || to.path.startsWith('/publish/')) {
    try {
      const me: any = await authApi.current();
      if (!me.is_admin && !me.is_member) return '/admin/notes';
    } catch { return '/login'; }
  }
});

export default router;
