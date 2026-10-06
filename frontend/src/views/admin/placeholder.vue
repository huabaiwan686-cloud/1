<template>
  <a-card :title="title" :bordered="true">
    <a-empty description="功能开发中" />
  </a-card>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useRoute } from 'vue-router';

const route = useRoute();
const title = computed(() => (route.meta.title as string) || '功能页');
</script>
