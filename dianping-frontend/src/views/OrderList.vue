<template>
  <div class="container py-8">
    <h1 class="text-2xl font-bold mb-6 flex items-center gap-2">
      <el-icon class="text-primary-500"><Tickets /></el-icon>
      我的订单
    </h1>

    <div class="card overflow-hidden mb-6">
      <div class="flex border-b overflow-x-auto">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          class="px-6 py-4 text-sm font-medium whitespace-nowrap transition-colors border-b-2"
          :class="activeTab === tab.key ? 'border-primary-500 text-primary-500' : 'border-transparent text-gray-600 hover:text-primary-500'"
          @click="activeTab = tab.key; loadOrders()"
        >
          {{ tab.label }}
          <span v-if="getCount(tab.key) > 0" class="ml-1 px-1.5 py-0.5 bg-red-100 text-red-500 rounded-full text-xs">
            {{ getCount(tab.key) }}
          </span>
        </button>
      </div>
    </div>

    <div v-if="loading" class="space-y-4">
      <div v-for="i in 3" :key="i" class="card h-40 animate-pulse bg-gray-200"></div>
    </div>

    <div v-else-if="orders.length > 0" class="space-y-4">
      <div v-for="order in orders" :key="order.id" class="card overflow-hidden">
        <!-- Order Header -->
        <div class="flex items-center justify-between px-6 py-3 bg-gray-50 border-b">
          <div class="flex items-center gap-4 text-sm">
            <span class="text-gray-500">订单号：{{ order.id }}</span>
            <span class="text-gray-400">|</span>
            <span class="text-gray-500">{{ formatTime(order.createTime) }}</span>
            <el-tag v-if="order.pending" size="small" type="info" effect="dark" class="ml-2">创建中</el-tag>
          </div>
          <el-tag
            :type="getStatusType(order.status)"
            effect="light"
            size="small"
          >
            {{ getStatusText(order.status) }}
          </el-tag>
        </div>

        <!-- Order Body -->
        <div class="p-6 flex flex-col sm:flex-row gap-4 items-start sm:items-center">
          <div class="w-full sm:w-16 h-16 rounded-lg bg-primary-100 flex items-center justify-center flex-shrink-0">
            <el-icon class="text-3xl text-primary-400"><Tickets /></el-icon>
          </div>
          <div class="flex-1 min-w-0">
            <h3 class="font-semibold mb-1">{{ getOrderTitle(order) }}</h3>
            <div class="text-sm text-gray-500 space-y-0.5">
              <p>支付方式：{{ getPayTypeText(order.payType) }}</p>
              <p v-if="order.payTime">支付时间：{{ formatTime(order.payTime) }}</p>
              <p v-if="order.useTime">核销时间：{{ formatTime(order.useTime) }}</p>
              <p v-if="order.refundTime">退款时间：{{ formatTime(order.refundTime) }}</p>
            </div>
          </div>
          <div class="flex flex-col items-end">
            <div class="flex items-baseline gap-1">
              <span class="text-xs text-red-500">¥</span>
              <span class="price-text text-xl">{{ getOrderAmount(order) }}</span>
            </div>
          </div>
        </div>

        <!-- Order Footer -->
        <div class="flex flex-wrap gap-2 justify-end px-6 py-4 bg-gray-50 border-t">
          <el-button size="small" @click="viewDetail(order)">
            查看详情
          </el-button>

          <template v-if="order.status === 1">
            <el-button
              size="small"
              type="primary"
              @click="handlePay(order)"
            >
              立即支付
            </el-button>
            <el-button
              size="small"
              type="danger"
              plain
              @click="handleCancel(order)"
            >
              取消订单
            </el-button>
          </template>

          <template v-else-if="order.status === 2">
            <el-button
              size="small"
              type="warning"
              @click="handleRefund(order)"
            >
              申请退款
            </el-button>
          </template>

          <el-button size="small" @click="viewShop(order)">
            查看商家
          </el-button>
        </div>
      </div>
    </div>

    <div v-else class="card p-16 text-center">
      <el-icon class="text-6xl text-gray-300 mb-4"><Tickets /></el-icon>
      <p class="text-gray-500 mb-4">暂无{{ getTabLabel(activeTab) }}订单</p>
      <router-link to="/seckill" class="btn-primary">
        去抢购优惠券
      </router-link>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { orderApi } from '@/api/order'
import { paymentApi } from '@/api/payment'
import type { VoucherOrder } from '@/types'
import { ElMessage, ElMessageBox } from 'element-plus'
import dayjs from 'dayjs'

const router = useRouter()

const activeTab = ref<number | 'all'>('all')
const loading = ref(true)
const orders = ref<VoucherOrder[]>([])
const allOrders = ref<VoucherOrder[]>([])

const tabs = [
  { key: 'all' as const, label: '全部订单' },
  { key: 1, label: '待支付' },
  { key: 2, label: '待使用' },
  { key: 3, label: '已使用' },
  { key: 4, label: '已取消' },
  { key: 5, label: '退款中' },
  { key: 6, label: '已退款' }
]

onMounted(loadOrders)
watch(activeTab, loadOrders)

function getErrorMsg(e: any): string | null {
  return e?.message || e?.response?.data?.errorMsg || null
}
/** 判断后端返回的错误信息是否属于"订单创建中/仍未落库"，可以安全重试 */
function isCreatingOrderError(e: any): boolean {
  const msg = getErrorMsg(e)
  if (!msg) return false
  return msg.includes('订单创建中') || msg.includes('稍后再试')
}

/** 支付接口重试：对"创建中"最多重试 3 次 */
async function payWithRetry(order: VoucherOrder, max = 3, intervalMs = 600) {
  let lastErr: any = null
  for (let i = 0; i < max; i++) {
    try {
      return await paymentApi.pay({ orderId: order.id, payType: 1 })
    } catch (e) {
      lastErr = e
      if (!isCreatingOrderError(e) || i === max - 1) break
      await new Promise(resolve => setTimeout(resolve, intervalMs))
    }
  }
  throw lastErr
}

/** 取消订单接口重试：对"创建中"最多重试 3 次 */
async function cancelWithRetry(order: VoucherOrder, max = 3, intervalMs = 600) {
  let lastErr: any = null
  for (let i = 0; i < max; i++) {
    try {
      return await orderApi.cancelOrder(order.id)
    } catch (e) {
      lastErr = e
      if (!isCreatingOrderError(e) || i === max - 1) break
      await new Promise(resolve => setTimeout(resolve, intervalMs))
    }
  }
  throw lastErr
}

function getCount(status: number | 'all') {
  if (status === 'all') return allOrders.value.length
  return allOrders.value.filter(o => o.status === status).length
}

function getTabLabel(key: number | 'all') {
  return tabs.find(t => t.key === key)?.label || ''
}

async function loadOrders() {
  loading.value = true
  try {
    const res = await orderApi.queryMyOrders(activeTab.value === 'all' ? undefined : activeTab.value as number)
    orders.value = (res.data as VoucherOrder[]) || []
    if (activeTab.value === 'all') {
      allOrders.value = [...orders.value]
    }
  } finally {
    loading.value = false
  }
}

function formatTime(t?: string) {
  if (!t) return '-'
  return dayjs(t).format('YYYY-MM-DD HH:mm')
}

function getStatusType(status?: number) {
  switch (status) {
    case 1: return 'warning'
    case 2: return 'success'
    case 3: return 'info'
    case 4: return 'danger'
    case 5: return 'warning'
    case 6: return 'info'
    default: return 'info'
  }
}

function getStatusText(status?: number) {
  switch (status) {
    case 1: return '待支付'
    case 2: return '待使用'
    case 3: return '已使用'
    case 4: return '已取消'
    case 5: return '退款中'
    case 6: return '已退款'
    default: return '未知'
  }
}

function getPayTypeText(type?: number) {
  switch (type) {
    case 1: return '余额支付'
    case 2: return '支付宝'
    case 3: return '微信支付'
    default: return '待支付'
  }
}

function getOrderTitle(order: VoucherOrder) {
  // 优先展示联表优惠券标题，否则兜底为订单号占位
  return order.voucher?.title?.trim() || `优惠券订单 #${order.id}`
}

function getOrderAmount(order: VoucherOrder) {
  // 金额单位：分 → 元（后端 payValue 为分）；联表无信息时兜底为 0.00
  const fen = Number(order.voucher?.payValue ?? 0)
  if (!Number.isFinite(fen) || fen <= 0) return '0.00'
  return (fen / 100).toFixed(2)
}

function viewDetail(order: VoucherOrder) {
  ElMessage.info(`查看订单详情：${order.id}`)
}

function viewShop(_order: VoucherOrder) {
  router.push('/shop')
}

async function handlePay(order: VoucherOrder) {
  try {
    await ElMessageBox.confirm('确认使用余额支付该订单？', '确认支付', {
      type: 'warning'
    })
    await payWithRetry(order)
    ElMessage.success('支付成功！')
    loadOrders()
  } catch (e) {
    // cancelled or failed
  }
}

async function handleCancel(order: VoucherOrder) {
  try {
    await ElMessageBox.confirm('确定要取消该订单吗？', '取消订单', {
      type: 'warning'
    })
    await cancelWithRetry(order)
    ElMessage.success('订单已取消')
    loadOrders()
  } catch (e) {
    // cancelled
  }
}

async function handleRefund(order: VoucherOrder) {
  try {
    await ElMessageBox.confirm(
      '申请退款后，款项将在1-3个工作日内原路返还，确定申请吗？',
      '申请退款',
      { type: 'warning' }
    )
    await paymentApi.refund(order.id)
    ElMessage.success('退款申请已提交')
    loadOrders()
  } catch (e) {
    // cancelled
  }
}
</script>
