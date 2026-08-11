<template>
  <div class="card p-4 hover:shadow-md transition-all">
    <div class="flex justify-between items-start mb-3">
      <div class="flex-1">
        <div class="flex items-center gap-2 mb-2">
          <el-tag
            v-if="voucher.type === 1"
            type="danger"
            effect="dark"
            size="small"
            class="animate-pulse"
          >
            秒杀中
          </el-tag>
          <el-tag v-else type="warning" size="small">优惠券</el-tag>
        </div>
        <h4 class="font-semibold text-lg mb-1">{{ voucher.title }}</h4>
        <p class="text-sm text-gray-500">{{ voucher.subTitle }}</p>
      </div>
      <div class="text-right">
        <div class="flex items-baseline gap-1 justify-end">
          <span class="text-xs text-red-500">¥</span>
          <span class="price-text text-2xl">{{ (voucher.payValue || 0) / 100 }}</span>
        </div>
        <div class="old-price">¥{{ (voucher.actualValue || 0) / 100 }}</div>
      </div>
    </div>

    <div class="text-xs text-gray-500 mb-3 border-t pt-3">
      <div class="mb-1"><span class="font-medium">使用规则：</span>{{ voucher.rules || '无特殊限制' }}</div>
      <div v-if="voucher.beginTime && voucher.endTime">
        <span class="font-medium">有效期：</span>{{ formatDate(voucher.beginTime) }} 至 {{ formatDate(voucher.endTime) }}
      </div>
      <div v-if="voucher.stock !== undefined">
        <span class="font-medium">剩余库存：</span>
        <span :class="voucher.stock < 10 ? 'text-red-500 font-semibold' : ''">{{ voucher.stock }} 张</span>
      </div>
    </div>

    <div v-if="voucher.type === 1 && voucher.endTime" class="mb-3">
      <el-progress
        :percentage="seckillProgress"
        :stroke-width="6"
        :color="seckillProgress > 90 ? '#ef4444' : '#f97316'"
      />
      <div class="flex justify-between text-xs text-gray-500 mt-1">
        <span>距结束 {{ countdownText }}</span>
        <span>已抢{{ 100 - seckillProgress }}%</span>
      </div>
    </div>

    <div class="flex gap-2">
      <button
        v-if="voucher.type === 1"
        class="flex-1 btn-primary"
        :disabled="!canSeckill"
        @click="$emit('seckill', voucher.id)"
      >
        <el-icon class="mr-1"><Lightning /></el-icon>
        立即抢购
      </button>
      <button v-else class="flex-1 btn-outline" @click="$emit('buy', voucher.id)">
        立即购买
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import type { Voucher } from '@/types'
import dayjs from 'dayjs'

const props = defineProps<{
  voucher: Voucher
}>()

defineEmits<{
  (e: 'seckill', id: number): void
  (e: 'buy', id: number): void
}>()

const now = ref(Date.now())
let timer: number | null = null

onMounted(() => {
  timer = window.setInterval(() => {
    now.value = Date.now()
  }, 1000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})

const canSeckill = computed(() => {
  if (props.voucher.type !== 1) return false
  if (props.voucher.stock !== undefined && props.voucher.stock <= 0) return false
  if (props.voucher.beginTime && dayjs(props.voucher.beginTime).valueOf() > now.value) return false
  if (props.voucher.endTime && dayjs(props.voucher.endTime).valueOf() < now.value) return false
  return true
})

const seckillProgress = computed(() => {
  const total = 100
  const stock = props.voucher.stock ?? 0
  return Math.min(100, Math.max(0, total - stock))
})

const countdownText = computed(() => {
  if (!props.voucher.endTime) return ''
  const diff = dayjs(props.voucher.endTime).valueOf() - now.value
  if (diff <= 0) return '已结束'
  const hours = Math.floor(diff / 3600000)
  const mins = Math.floor((diff % 3600000) / 60000)
  const secs = Math.floor((diff % 60000) / 1000)
  if (hours > 0) return `${hours}时${mins}分${secs}秒`
  if (mins > 0) return `${mins}分${secs}秒`
  return `${secs}秒`
})

function formatDate(date: string) {
  return dayjs(date).format('MM-DD HH:mm')
}
</script>
