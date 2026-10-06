<template>
  <div>
    <h2>笔记列表</h2>
    <a-space style="margin-bottom: 16px">
      <a-input-search v-model:value="keyword" placeholder="搜索" @search="load" style="width: 200px" />
      <a-button type="primary" @click="load">刷新</a-button>
    </a-space>
    <a-spin :spinning="loading">
      <div v-if="!list.length && !loading">暂无数据</div>
      <a-list v-else :data-source="list" bordered>
        <template #renderItem="{ item }">
          <a-list-item>{{ item.title || ('ID: ' + item.id) }}</a-list-item>
        </template>
      </a-list>
    </a-spin>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { noteApi } from '@/api';

const list = ref<any[]>([]);
const loading = ref(false);
const keyword = ref('');

async function load() {
  loading.value = true;
  try {
    const data: any = await noteApi.list({ keyword: keyword.value, page: 1, page_size: 20 });
    list.value = data.list || [];
  } catch (e) {
    console.error(e);
  } finally {
    loading.value = false;
  }
}

onMounted(() => { load(); });
</script>
