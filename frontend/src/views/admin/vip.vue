<template>
  <div>
    <a-row :gutter="16" style="margin-bottom: 16px">
      <a-col :span="12" v-for="p in plans" :key="p.id">
        <a-card :title="p.name">
          <p>价格：{{ p.price }} USDT / {{ p.days }} 天</p>
          <ul><li v-for="f in p.features" :key="f">{{ f }}</li></ul>
          <a-button v-if="p.id === 'pro'" type="primary" @click="buy">开通 PRO</a-button>
          <a-tag v-else color="green">当前：{{ sub.plan }}</a-tag>
        </a-card>
      </a-col>
    </a-row>
    <a-card title="我的订阅">
      <p>套餐：{{ sub.plan }} ｜ 有效期至：{{ sub.activeUntil || '—' }} ｜
        <a-tag :color="sub.isActive ? 'green' : 'default'">{{ sub.isActive ? '生效中' : '未生效' }}</a-tag>
      </p>
      <p>本月图片额度剩余：{{ quota.totalLeft }}</p>
    </a-card>
    <a-divider>邀请奖励</a-divider>
    <a-space style="margin-bottom: 16px">
      <a-button @click="genCode">生成邀请码</a-button>
      <span v-if="inviteCode">邀请码：<a-tag color="blue">{{ inviteCode }}</a-tag></span>
    </a-space>
    <a-table :columns="cols" :data-source="records" row-key="code" size="small" />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { message, Modal } from 'ant-design-vue';
import { vipApi, inviteApi } from '@/api';

const plans = ref<any[]>([]);
const sub = ref<any>({ plan: 'starter' });
const quota = ref<any>({ totalLeft: 0 });
const inviteCode = ref('');
const records = ref<any[]>([]);
const cols = [
  { title: '邀请码', dataIndex: 'code', width: 120 },
  { title: '被邀请人', dataIndex: 'invitee' },
  { title: 'TG 绑定', dataIndex: 'tgBound', width: 90 },
  { title: '奖励天数', dataIndex: 'rewardDays', width: 100 },
];

async function load() {
  plans.value = await vipApi.plans();
  sub.value = await vipApi.subscription();
  quota.value = await vipApi.quota();
  const inv: any = await inviteApi.list();
  records.value = inv.records;
}
async function buy() {
  const order: any = await vipApi.createOrder();
  Modal.info({ title: '订单已创建', content: `订单号 ${order.orderNo}，请支付 ${order.amountUsdt} USDT（待接支付网关）` });
}
async function genCode() {
  const r: any = await inviteApi.generate();
  inviteCode.value = r.code; message.success('邀请码已生成');
}
onMounted(load);
</script>
