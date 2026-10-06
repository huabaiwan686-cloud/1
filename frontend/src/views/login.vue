<template>
  <div class="login-page">
    <a-card :title="mode === 'login' ? '小灰机 · 商家后台' : '注册新账号'" class="login-card">
      <a-form v-if="mode === 'login'" :model="form" @finish="onLogin">
        <a-form-item name="username" :rules="[{ required: true, message: '请输入账号' }]">
          <a-input v-model:value="form.username" placeholder="账号" />
        </a-form-item>
        <a-form-item name="password" :rules="[{ required: true, message: '请输入密码' }]">
          <a-input-password v-model:value="form.password" placeholder="密码" />
        </a-form-item>
        <a-form-item>
          <a-button type="primary" html-type="submit" block :loading="loading">登录</a-button>
        </a-form-item>
        <a-form-item style="text-align: center; margin-bottom: 0">
          <a @click="mode = 'register'">没有账号？点此注册</a>
        </a-form-item>
      </a-form>
      <a-form v-else :model="regForm" @finish="onRegister">
        <a-form-item name="username" :rules="[{ required: true, message: '请输入账号' }]">
          <a-input v-model:value="regForm.username" placeholder="设置登录账号" />
        </a-form-item>
        <a-form-item name="password" :rules="[{ required: true, message: '请输入密码' }, { min: 6, message: '至少 6 位' }]">
          <a-input-password v-model:value="regForm.password" placeholder="设置密码（至少 6 位）" />
        </a-form-item>
        <a-form-item name="invite_code" :rules="[{ required: true, message: '请输入邀请码' }]">
          <a-input v-model:value="regForm.invite_code" placeholder="邀请码（找管理员获取）" />
        </a-form-item>
        <a-form-item>
          <a-button type="primary" html-type="submit" block :loading="loading">注册</a-button>
        </a-form-item>
        <a-form-item style="text-align: center; margin-bottom: 0">
          <a @click="mode = 'login'">已有账号？返回登录</a>
        </a-form-item>
      </a-form>
    </a-card>
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

<style scoped>
.login-page { display: flex; justify-content: center; padding-top: 15vh; }
.login-card { width: 360px; }
</style>
