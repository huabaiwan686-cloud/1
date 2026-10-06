import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router';
import { authApi } from '@/api';

export const routes: RouteRecordRaw[] = [
  { path: '/login', component: () => import('@/views/login.vue') },
  { path: '/', redirect: '/collector/upload' },
  { path: '/collector/upload', component: () => import('@/views/collector/upload.vue') },
  { path: '/collector/content', component: () => import('@/views/collector/content.vue') },
  { path: '/collector/records', component: () => import('@/views/collector/records.vue') },
  { path: '/admin/notes', component: () => import('@/views/admin/notes.vue') },
  { path: '/admin/collection', component: () => import('@/views/admin/collection.vue') },
  { path: '/admin/collection/review', component: () => import('@/views/admin/collection-review.vue') },
  { path: '/admin/channels', component: () => import('@/views/admin/channels.vue') },
  { path: '/admin/message-push', component: () => import('@/views/admin/message-push.vue') },
  { path: '/publish/message-push', component: () => import('@/views/publish/message-push.vue') },
  { path: '/admin/group-listen', component: () => import('@/views/admin/group-listen.vue') },
  { path: '/publish/group-listen', component: () => import('@/views/publish/group-listen.vue') },
  { path: '/admin/accounts/protocol', component: () => import('@/views/admin/accounts/protocol.vue') },
  { path: '/admin/accounts/bots', component: () => import('@/views/admin/accounts/bots.vue') },
  { path: '/admin/accounts/xc-cms-binding', component: () => import('@/views/admin/accounts/binding.vue') },
  { path: '/admin/accounts/two-way-bots', component: () => import('@/views/admin/accounts/two-way.vue') },
  {
    path: '/admin/accounts/platform-cooperation',
    component: () => import('@/views/admin/accounts/cooperation.vue'),
  },
  { path: '/admin/accounts/friends', component: () => import('@/views/admin/accounts/friends.vue') },
  { path: '/admin/users', component: () => import('@/views/admin/users.vue') },
  { path: '/admin/vip', component: () => import('@/views/admin/vip.vue') },
  { path: '/admin/announcements', component: () => import('@/views/admin/announcements.vue') },
  { path: '/admin/dashboard', component: () => import('@/views/admin/dashboard.vue') },
  { path: '/admin/logs', component: () => import('@/views/admin/logs.vue') },
  // 全局设置：背景替换 / 混淆 / 循环发布
  { path: '/admin/global/bg-replace', component: () => import('@/views/admin/global-bg-replace.vue') },
  { path: '/admin/global/confuse', component: () => import('@/views/admin/global-confuse.vue') },
  { path: '/admin/global/loop', component: () => import('@/views/admin/global-loop.vue') },
  // 旧路由兼容重定向
  { path: '/admin/backgrounds', redirect: '/admin/global/bg-replace' },
  { path: '/admin/publish-config', redirect: '/admin/global/loop' },
];

const router = createRouter({ history: createWebHistory(), routes });

router.beforeEach(async (to) => {
  if (to.path !== '/login' && !localStorage.getItem('access_token')) {
    return '/login';
  }
  // 三级权限：普通用户仅允许 /admin/notes（上下架），会员不允许 /admin/users，超管全部
  if (to.path.startsWith('/admin/')) {
    try {
      const me: any = await authApi.current();
      if (me.isAdmin) { /* 全部放行 */ }
      else if (me.isMember) {
        if (to.path === '/admin/users') return '/admin/dashboard';
      } else {
        if (to.path !== '/admin/notes') return '/admin/notes';
      }
    } catch { return '/login'; }
  }
  // 非会员禁止进入采集/发布端页面
  if (to.path.startsWith('/collector/') || to.path.startsWith('/publish/')) {
    try {
      const me: any = await authApi.current();
      if (!me.isAdmin && !me.isMember) return '/admin/notes';
    } catch { return '/login'; }
  }
});

export default router;
