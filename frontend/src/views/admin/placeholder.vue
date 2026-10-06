<template>
  <div class="page">
    <div class="page-title">{{ title }}</div>
    <div class="page-subtitle">功能开发中，敬请期待</div>
    <a-card style="margin-top: 16px">
      <a-empty description="该功能正在按 meiren.pro 规范复刻中" />
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useRoute } from 'vue-router';

const route = useRoute();
const title = computed(() => (route.meta.title as string) || '功能页');
</script>

<style scoped>
.page-title { font-size: 20px; font-weight: 600; }
.page-subtitle { font-size: 14px; color: #8a91a5; margin-top: 4px; }
</style>
