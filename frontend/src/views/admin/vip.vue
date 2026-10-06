<template>
  <div class="vip-page">
    <!-- 成功 Alert：ant-alert-success.ant-alert-with-description + 右侧 action 按钮 -->
    <a-alert
      type="success"
      show-icon
      message="VIP 会员"
      :description="sub.isActive ? `当前套餐：${sub.planName || sub.plan}，有效期至 ${sub.activeUntil || '—'}` : '开通 VIP 会员，解锁全部高级功能'"
      class="vip-alert"
    >
      <template #action>
        <div class="ant-alert-action">
          <a-button size="small" type="primary" @click="buy">立即开通</a-button>
        </div>
      </template>
    </a-alert>

    <!-- 套餐卡：嵌套 ant-col-8 卡片 -->
    <a-row :gutter="16" class="vip-plans">
      <a-col :span="8" v-for="p in plans" :key="p.id">
        <a-card
          :title="p.name"
          :style="p.id === 'free' || p.id === 'starter' ? 'border:1px dashed #dfe3eb' : ''"
          class="vip-plan-card"
        >
          <div class="vip-price">
            <span class="vip-price-old" v-if="p.oldPrice">{{ p.oldPrice }} USDT</span>
            <span class="vip-price-now">{{ p.price }} USDT</span>
            <a-tag color="red" v-if="p.tag">{{ p.tag }}</a-tag>
          </div>
          <p class="vip-days">{{ p.days }} 天</p>
          <ul class="vip-features">
            <li v-for="f in p.features" :key="f">{{ f }}</li>
          </ul>
          <a-button
            block
            ghost
            :type="p.id === sub.plan ? 'default' : 'primary'"
            class="ant-btn-background-ghost ant-btn-block"
            :disabled="p.id === sub.plan && sub.isActive"
            @click="buyPlan(p)"
          >
            {{ p.id === sub.plan && sub.isActive ? '当前套餐' : '立即开通' }}
          </a-button>
        </a-card>
      </a-col>
    </a-row>

    <!-- 邀请码：等宽字体 #2f55e0 20px -->
    <a-card title="邀请奖励" class="vip-invite">
      <a-space>
        <a-button @click="genCode">生成邀请码</a-button>
        <span v-if="inviteCode" class="vip-invite-code">{{ inviteCode }}</span>
      </a-space>
    </a-card>

    <!-- 订单表：订单号/支付方式/金额/状态/时间 -->
    <a-card title="订单记录" class="vip-orders">
      <a-table
        :columns="orderCols"
        :data-source="orders"
        row-key="orderNo"
        :pagination="{ pageSize: 10 }"
      />
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { message, Modal } from 'ant-design-vue';
import { vipApi, inviteApi } from '@/api';

const plans = ref<any[]>([]);
const sub = ref<any>({ plan: 'starter', isActive: false });
const orders = ref<any[]>([]);
const inviteCode = ref('');

const orderCols = [
  { title: '订单号', dataIndex: 'orderNo' },
  { title: '支付方式', dataIndex: 'payMethod' },
  { title: '金额', dataIndex: 'amountUsdt' },
  { title: '状态', dataIndex: 'status' },
  { title: '时间', dataIndex: 'createdAt', className: 'hide-mobile' },
];

async function load() {
  try {
    plans.value = await vipApi.plans();
  } catch { /* ignore */ }
  try {
    sub.value = await vipApi.subscription();
  } catch { /* ignore */ }
  try {
    orders.value = await vipApi.orders();
  } catch { /* ignore */ }
  try {
    const inv: any = await inviteApi.list();
    if (inv.records && inv.records.length) {
      inviteCode.value = inv.records[inv.records.length - 1].code || '';
    }
  } catch { /* ignore */ }
}

async function buyPlan(p: any) {
  await buy(p?.id || 'pro');
}

async function buy(planId = 'pro') {
  try {
    const order: any = await vipApi.createOrder(planId);
    const payInfo: any = await vipApi.payInfo();
    const addrLine = payInfo.configured
      ? `请向 TRC20 地址转账：${payInfo.address}`
      : '收款地址待配置，请联系管理员';
    Modal.info({ title: '订单已创建', content: `订单号 ${order.orderNo}，金额 ${order.amountUsdt} USDT。${addrLine}` });
    load();
  } catch (e: any) { message.error(e.message || '下单失败'); }
}

async function genCode() {
  const r: any = await inviteApi.generate();
  inviteCode.value = r.code;
  message.success('邀请码已生成');
}

onMounted(load);
</script>

<style scoped>
.vip-page {
  padding: 24px;
}
.vip-alert {
  margin-bottom: 16px;
}
/* 套餐价格：删除线 + 橙色 #e8590c */
.vip-price {
  margin-bottom: 8px;
}
.vip-price-old {
  text-decoration: line-through;
  color: rgba(0, 0, 0, 0.45);
  margin-right: 8px;
}
.vip-price-now {
  color: #e8590c;
  font-size: 20px;
  font-weight: 600;
  margin-right: 8px;
}
.vip-days {
  color: rgba(0, 0, 0, 0.45);
  margin-bottom: 12px;
}
.vip-features {
  padding-left: 20px;
  line-height: 1.8;
  margin-bottom: 16px;
  color: rgba(0, 0, 0, 0.65);
}
.vip-plans {
  margin-bottom: 16px;
}
.vip-invite {
  margin-bottom: 16px;
}
/* 邀请码：等宽字体 #2f55e0 20px */
.vip-invite-code {
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', monospace;
  color: #2f55e0;
  font-size: 20px;
  letter-spacing: 2px;
}
</style>
