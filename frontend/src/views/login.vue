<template>
  <div class="pro-login-page">
    <a-card class="pro-login-card" :bordered="false">
      <div class="pro-login-brand">
        <span class="pro-logo-badge">灰</span>
        <h1 class="pro-login-title">{{ mode === 'login' ? '欢迎回来' : '注册新账号' }}</h1>
        <div class="pro-login-sub">小灰机 · 商家后台</div>
      </div>
      <a-form v-if="mode === 'login'" :model="form" @finish="onLogin" style="margin-top: 24px">
        <a-form-item name="username" :rules="[{ required: true, message: '请输入账号' }]">
          <a-input v-model:value="form.username" placeholder="账号" size="large" />
        </a-form-item>
        <a-form-item name="password" :rules="[{ required: true, message: '请输入密码' }]">
          <a-input-password v-model:value="form.password" placeholder="密码" size="large" />
        </a-form-item>
        <a-form-item>
          <a-button type="primary" html-type="submit" block :loading="loading">登 录</a-button>
        </a-form-item>
        <a-form-item style="text-align: center; margin-bottom: 0">
          <a @click="mode = 'register'">没有账号？点此注册</a>
        </a-form-item>
      </a-form>
      <a-form v-else :model="regForm" @finish="onRegister" style="margin-top: 24px">
        <a-form-item name="username" :rules="[{ required: true, message: '请输入账号' }]">
          <a-input v-model:value="regForm.username" placeholder="设置登录账号" size="large" />
        </a-form-item>
        <a-form-item name="password" :rules="[{ required: true, message: '请输入密码' }, { min: 6, message: '至少 6 位' }]">
          <a-input-password v-model:value="regForm.password" placeholder="设置密码（至少 6 位）" size="large" />
        </a-form-item>
        <a-form-item name="invite_code" :rules="[{ required: true, message: '请输入邀请码' }]">
          <a-input v-model:value="regForm.invite_code" placeholder="邀请码（找管理员获取）" size="large" />
        </a-form-item>
        <a-form-item>
          <a-button type="primary" html-type="submit" block :loading="loading">注 册</a-button>
        </a-form-item>
        <a-form-item style="text-align: center; margin-bottom: 0">
          <a @click="mode = 'login'">已有账号？返回登录</a>
        </a-form-item>
      </a-form>
    </a-card>
    <div class="pro-login-foot">© 2026 小灰机 · 商家后台</div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue';
import { useRouter } from 'vue-router';
import { message } from 'ant-design-vue';
import { authApi } from '@/api';

const router = useRouter();
const loading = ref(false);
const mode = ref<'login' | 'register'>('login');
const form = reactive({ username: '', password: '' });
const regForm = reactive({ username: '', password: '', invite_code: '' });

async function onLogin() {
  loading.value = true;
  try {
    const data: any = await authApi.login(form.username, form.password);
    localStorage.setItem('access_token', data.accessToken);
    localStorage.setItem('refresh_token', data.refreshToken);
    message.success('登录成功');
    router.push('/admin/notes');
  } catch (e: any) {
    message.error(e.message || '登录失败');
  } finally {
    loading.value = false;
  }
}

async function onRegister() {
  loading.value = true;
  try {
    await authApi.register(regForm);
    message.success('注册成功，请登录');
    form.username = regForm.username;
    form.password = '';
    mode.value = 'login';
  } catch (e: any) {
    message.error(e.message || '注册失败');
  } finally {
    loading.value = false;
  }
}
</script>
