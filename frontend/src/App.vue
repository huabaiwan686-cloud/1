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
        <a-space>
          <span>{{ username }}</span>
          <a-button size="small" @click="logout">退出</a-button>
        </a-space>
      </a-layout-header>
      <a-layout-content class="content">
        <router-view />
      </a-layout-content>
    </a-layout>
  </a-layout>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { authApi } from '@/api';

const route = useRoute();
const router = useRouter();
const collapsed = ref(false);
const menus = ref<any[]>([]);
const selected = ref<string[]>([]);
const username = ref('');

const isLoginPage = computed(() => route.path === '/login');

function onMenu({ key }: any) { router.push(key); }
function logout() {
  authApi.logout().finally(() => {
    localStorage.removeItem('access_token');
    router.push('/login');
  });
}

watch(() => route.path, (p) => { selected.value = [p]; }, { immediate: true });

onMounted(async () => {
  if (isLoginPage.value) return;
  try {
    menus.value = await authApi.menu();
    const me: any = await authApi.current();
    username.value = me.username;
  } catch { /* 401 由 request 拦截器跳登录 */ }
});
</script>

<style scoped>
.logo { color: #fff; text-align: center; padding: 16px 0; font-weight: bold; }
.header { background: #fff; padding: 0 24px; display: flex; justify-content: flex-end; align-items: center; }
.content { margin: 16px; background: #fff; padding: 16px; min-height: 80vh; }
</style>
