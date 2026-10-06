<template>
  <div class="login-page">
    <a-card title="小灰机 · 商家后台" class="login-card">
      <a-form :model="form" @finish="onLogin">
        <a-form-item name="username" :rules="[{ required: true, message: '请输入账号' }]">
          <a-input v-model:value="form.username" placeholder="账号" />
        </a-form-item>
        <a-form-item name="password" :rules="[{ required: true, message: '请输入密码' }]">
          <a-input-password v-model:value="form.password" placeholder="密码" />
        </a-form-item>
        <a-form-item>
          <a-button type="primary" html-type="submit" block :loading="loading">登录</a-button>
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
const form = reactive({ username: '', password: '' });

async function onLogin() {
  loading.value = true;
  try {
    const data: any = await authApi.login(form.username, form.password);
    localStorage.setItem('access_token', data.accessToken);
    localStorage.setItem('refresh_token', data.refreshToken);
    message.success('登录成功');
    router.push('/collector/upload');
  } catch (e: any) {
    message.error(e.message || '登录失败');
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.login-page { display: flex; justify-content: center; padding-top: 15vh; }
.login-card { width: 360px; }
</style>
