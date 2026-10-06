import type { RouteRecordRaw } from 'vue-router';

export const routes: RouteRecordRaw[] = [
  { path: '/login', component: () => import('@/views/login.vue'), meta: { public: true } },
  { path: '/', redirect: '/collector/upload' },
  { path: '/collector/upload', component: () => import('@/views/collector/upload.vue') },
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
  { path: '/admin/dashboard', component: () => import('@/views/admin/dashboard.vue') },
  { path: '/admin/logs', component: () => import('@/views/admin/logs.vue') },
];
