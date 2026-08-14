<template>
  <div class="bg-gradient-to-r from-red-50 via-orange-50 to-yellow-50 min-h-screen">
    <!-- Header -->
    <div class="bg-gradient-to-r from-red-500 via-red-600 to-orange-500 text-white py-10">
      <div class="container">
        <div class="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div>
            <div class="flex items-center gap-3 mb-2">
              <div class="w-12 h-12 rounded-xl bg-white/20 backdrop-blur flex items-center justify-center">
                <el-icon class="text-3xl"><Lightning /></el-icon>
              </div>
              <h1 class="text-3xl md:text-4xl font-bold">限时秒杀</h1>
            </div>
            <p class="text-red-100">超值优惠券，每日限时开抢，手慢无！</p>
          </div>
          <div class="bg-white/15 backdrop-blur rounded-2xl px-6 py-4">
            <div class="text-xs text-red-100 mb-2">距离本场结束</div>
            <div class="flex items-center gap-2">
              <div class="bg-black/30 rounded-lg px-3 py-2 text-2xl font-bold tabular-nums">
                {{ countdown.hours }}
              </div>
              <span class="text-xl font-bold">:</span>
              <div class="bg-black/30 rounded-lg px-3 py-2 text-2xl font-bold tabular-nums">
                {{ countdown.mins }}
              </div>
              <span class="text-xl font-bold">:</span>
              <div class="bg-black/30 rounded-lg px-3 py-2 text-2xl font-bold tabular-nums">
                {{ countdown.secs }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="container py-8">
      <!-- Tabs -->
      <div class="card p-2 mb-6 inline-flex">
        <button
          v-for="s in sessions"
          :key="s.id"
          class="px-6 py-2.5 rounded-lg transition-all text-sm font-medium"
          :class="activeSession === s.id ? 'bg-red-500 text-white shadow-md' : (s.active ? 'text-red-500 hover:bg-red-50' : 'text-gray-500 hover:bg-gray-50')"
          @click="activeSession = s.id"
        >
          <span class="block">{{ s.time }}</span>
          <span v-if="s.active && activeSession !== s.id" class="text-xs opacity-80">进行中</span>
          <span v-else-if="s.upcoming" class="text-xs opacity-80">即将开始</span>
          <span v-else-if="s.ended" class="text-xs opacity-80">已结束</span>
        </button>
      </div>

      <!-- Voucher List -->
      <div v-if="loading" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <div v-for="i in 6" :key="i" class="card h-56 animate-pulse bg-gray-200"></div>
      </div>

      <div v-else-if="seckillVouchers.length > 0" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <div
          v-for="voucher in seckillVouchers"
          :key="voucher.id"
          class="card overflow-hidden hover:shadow-xl transition-all duration-300 border-2 border-transparent hover:border-red-200"
        >
          <!-- Top Banner -->
          <div class="bg-gradient-to-r from-red-500 to-orange-500 px-4 py-2 text-white flex items-center justify-between">
            <div class="flex items-center gap-2">
              <el-icon><Lightning /></el-icon>
              <span class="font-semibold">限时秒杀</span>
            </div>
            <el-tag size="small" effect="dark" type="warning">
              仅剩 {{ voucher.stock ?? Math.floor(Math.random() * 50) + 5 }} 张
            </el-tag>
          </div>

          <div class="p-5">
            <div class="flex items-start justify-between mb-4">
              <div class="flex-1 pr-3">
                <h3 class="font-bold text-lg mb-1 line-clamp-1">{{ voucher.title }}</h3>
                <p class="text-sm text-gray-500 line-clamp-1">{{ voucher.subTitle || '超值优惠券，不容错过' }}</p>
              </div>
              <div class="text-right flex-shrink-0">
                <div class="flex items-baseline gap-0.5 justify-end">
                  <span class="text-xs text-red-500">¥</span>
                  <span class="text-3xl font-bold text-red-500">{{ getPayValue(voucher) }}</span>
                </div>
                <div class="old-price">¥{{ getActualValue(voucher) }}</div>
              </div>
            </div>

            <!-- Discount Tag -->
            <div class="flex items-center gap-2 mb-4">
              <el-tag type="danger" effect="plain" size="small">
                {{ getDiscount(voucher) }}折优惠
              </el-tag>
              <el-tag type="warning" effect="plain" size="small">
                立省¥{{ getSave(voucher) }}
              </el-tag>
            </div>

            <!-- Progress -->
            <div class="mb-4">
              <el-progress
                :percentage="getSoldPercent(voucher)"
                :stroke-width="8"
                color="#ef4444"
                :show-text="false"
              />
              <div class="flex justify-between text-xs mt-1">
                <span class="text-gray-500">已抢{{ getSoldPercent(voucher) }}%</span>
                <span class="text-red-500 font-medium">{{ voucher.stock ?? 20 }} 张剩余</span>
              </div>
            </div>

            <!-- Info -->
            <div class="text-xs text-gray-500 mb-4 border-t pt-3">
              <div v-if="voucher.beginTime && voucher.endTime" class="mb-1">
                <span class="font-medium">有效期：</span>{{ formatDate(voucher.beginTime) }} - {{ formatDate(voucher.endTime) }}
              </div>
              <div><span class="font-medium">规则：</span>{{ voucher.rules || '全场通用，无门槛' }}</div>
            </div>

            <button
              class="w-full bg-gradient-to-r from-red-500 to-orange-500 text-white py-3 rounded-lg font-semibold hover:shadow-lg hover:from-red-600 hover:to-orange-600 transition-all active:scale-95"
              :disabled="(voucher.stock ?? 0) <= 0"
              @click="handleSeckill(voucher.id)"
            >
              <template v-if="(voucher.stock ?? 0) > 0">
                <el-icon class="mr-1"><Lightning /></el-icon>
                立即抢购
              </template>
              <template v-else>
                已抢光
              </template>
            </button>
          </div>
        </div>
      </div>

      <div v-else class="card p-16 text-center">
        <el-icon class="text-6xl text-gray-300 mb-4"><Clock /></el-icon>
        <p class="text-gray-500 mb-2">当前场次暂无秒杀商品</p>
        <p class="text-sm text-gray-400 mb-6">请关注下一场秒杀，记得提前设好闹钟哦~</p>
        <div class="flex justify-center gap-4">
          <router-link to="/shop" class="btn-outline">浏览商家</router-link>
          <router-link to="/" class="btn-primary">返回首页</router-link>
        </div>
      </div>

      <!-- Tips -->
      <div class="card p-6 mt-10 bg-gradient-to-br from-white to-orange-50">
        <h3 class="font-semibold mb-4 flex items-center gap-2">
          <el-icon class="text-orange-500"><Warning /></el-icon>
          秒杀须知
        </h3>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6 text-sm text-gray-600">
          <div class="flex gap-3">
            <div class="w-8 h-8 rounded-full bg-red-100 flex items-center justify-center text-red-500 flex-shrink-0 font-bold">1</div>
            <div>
              <div class="font-medium text-gray-800 mb-1">数量有限</div>
              <p>秒杀优惠券数量有限，先到先得，每人限购1张</p>
            </div>
          </div>
          <div class="flex gap-3">
            <div class="w-8 h-8 rounded-full bg-orange-100 flex items-center justify-center text-orange-500 flex-shrink-0 font-bold">2</div>
            <div>
              <div class="font-medium text-gray-800 mb-1">及时支付</div>
              <p>下单后请在15分钟内完成支付，超时订单将自动取消</p>
            </div>
          </div>
          <div class="flex gap-3">
            <div class="w-8 h-8 rounded-full bg-yellow-100 flex items-center justify-center text-yellow-600 flex-shrink-0 font-bold">3</div>
            <div>
              <div class="font-medium text-gray-800 mb-1">有效期内使用</div>
              <p>请在券面有效期内使用，过期未使用不支持退款</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { voucherApi } from '@/api/voucher'
import { voucherOrderApi } from '@/api/voucherOrder'
import type { Voucher } from '@/types'
import { ElMessage, ElMessageBox } from 'element-plus'
import dayjs from 'dayjs'

const router = useRouter()
const userStore = useUserStore()

const loading = ref(true)
const allVouchers = ref<Voucher[]>([])
const seckillVouchers = ref<Voucher[]>([])
const activeSession = ref('all')

const now = ref(Date.now())
let timer: number | null = null

/**
 * 场次：根据后端返回的秒杀券 beginTime 真实分档
 *   all    — 全部秒杀
 *   now    — 已开抢（beginTime <= 今天）
 *   soon   — 即将开始（近期的）
 */
const sessions = computed(() => {
  const list = allVouchers.value
  const minBegin = list.length ? Math.min(...list.map(v => dayjs(v.beginTime).valueOf())) : Date.now()
  const maxEnd = list.length ? Math.max(...list.map(v => dayjs(v.endTime).valueOf())) : Date.now()
  const hour = dayjs().hour()
  return [
    {
      id: 'all',
      time: '全部专场',
      active: true,
      upcoming: false,
      ended: false,
      begin: minBegin,
      end: maxEnd
    },
    {
      id: '08',
      time: '08:00场',
      active: hour >= 8 && hour < 12,
      upcoming: hour < 8,
      ended: hour >= 12,
      begin: dayjs().hour(8).minute(0).second(0).valueOf(),
      end: dayjs().hour(12).minute(0).second(0).valueOf()
    },
    {
      id: '12',
      time: '12:00场',
      active: hour >= 12 && hour < 18,
      upcoming: hour >= 8 && hour < 12,
      ended: hour >= 18,
      begin: dayjs().hour(12).minute(0).second(0).valueOf(),
      end: dayjs().hour(18).minute(0).second(0).valueOf()
    },
    {
      id: '18',
      time: '18:00场',
      active: hour >= 18 || hour < 8,
      upcoming: hour >= 12 && hour < 18,
      ended: false,
      begin: dayjs().hour(18).minute(0).second(0).valueOf(),
      end: dayjs().hour(23).minute(59).second(59).valueOf()
    }
  ]
})

const countdown = reactive({
  hours: '00',
  mins: '00',
  secs: '00'
})

/**
 * 倒计时基准：
 *   - 如果有已开始（进行中）的秒杀券 → 以 max(endTime) 为目标（距本场结束）
 *   - 如果秒杀券都还没开始 → 以 min(beginTime) 为目标（距开抢）
 *   - 全部结束 → 00:00:00
 */
function updateCountdown() {
  now.value = Date.now()
  let target = 0
  const activeVouchers = seckillVouchers.value.length ? seckillVouchers.value : allVouchers.value
  const running = activeVouchers.filter(v => {
    const b = dayjs(v.beginTime).valueOf()
    const e = dayjs(v.endTime).valueOf()
    return now.value >= b && now.value < e
  })
  const upcoming = activeVouchers.filter(v => now.value < dayjs(v.beginTime).valueOf())
  if (running.length) {
    target = Math.max(...running.map(v => dayjs(v.endTime).valueOf()))
  } else if (upcoming.length) {
    target = Math.min(...upcoming.map(v => dayjs(v.beginTime).valueOf()))
  } else {
    target = 0
  }
  let diff = target - now.value
  if (diff <= 0) diff = 0
  const h = Math.floor(diff / 3600000)
  const m = Math.floor((diff % 3600000) / 60000)
  const s = Math.floor((diff % 60000) / 1000)
  countdown.hours = h.toString().padStart(2, '0')
  countdown.mins = m.toString().padStart(2, '0')
  countdown.secs = s.toString().padStart(2, '0')
}

onMounted(async () => {
  timer = window.setInterval(updateCountdown, 1000)
  await loadVouchers()
  updateCountdown()
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})

async function loadVouchers() {
  loading.value = true
  try {
    // 秒杀专场：跨商家查询全部 type=1 的秒杀券
    const res = await voucherApi.queryAllSeckillVoucher()
    allVouchers.value = (res.data as Voucher[]) || []
    seckillVouchers.value = filterBySession(allVouchers.value, activeSession.value)
    if (seckillVouchers.value.length === 0) {
      seckillVouchers.value = allVouchers.value
    }
  } catch (e) {
    // 仅在接口完全失败时给出最简兜底
    seckillVouchers.value = allVouchers.value = []
  } finally {
    loading.value = false
  }
}

function filterBySession(list: Voucher[], sessionId: string): Voucher[] {
  if (sessionId === 'all' || !list.length) return list.slice()
  const sess = sessions.value.find(s => s.id === sessionId)
  if (!sess) return list.slice()
  return list.filter(v => {
    const b = dayjs(v.beginTime).valueOf()
    const e = dayjs(v.endTime).valueOf()
    // 只要券的 [begin,end) 时间区间与会场时间段有交集
    return !(e < sess.begin || b > sess.end)
  })
}

// 当用户点不同场次时重新过滤
function onSessionChange(id: string) {
  activeSession.value = id
  seckillVouchers.value = filterBySession(allVouchers.value, id)
}
// 给 template 用（上面 sessions 没有 @click 处理，这里补上引用）
// 但 sessions 是 computed，template 里点击是对 activeSession 赋值——直接监听 activeSession 也可以
import { watch } from 'vue'
watch(activeSession, (id) => {
  seckillVouchers.value = filterBySession(allVouchers.value, id)
})

function getPayValue(v: Voucher) {
  return ((v.payValue || 0) / 100).toFixed(0)
}
function getActualValue(v: Voucher) {
  return ((v.actualValue || 0) / 100).toFixed(0)
}
function getDiscount(v: Voucher) {
  const actual = v.actualValue || 1
  const pay = v.payValue || 0
  return (pay / actual * 10).toFixed(1)
}
function getSave(v: Voucher) {
  return (((v.actualValue || 0) - (v.payValue || 0)) / 100).toFixed(0)
}
/**
 * 已售百分比：基于库存和随机种子做稳定估算
 * - 库存越少 → 越接近售罄
 * - 基于 voucher.id 做稳定 hash 避免每次刷新跳动
 */
function getSoldPercent(v: Voucher) {
  const stock = Math.max(0, v.stock ?? 0)
  const hash = ((v.id * 2654435761) >>> 0) % 30 // 0~29 区间
  const baseSold = stock === 0 ? 100 : Math.max(10, 70 - stock + hash)
  return Math.min(99, Math.max(5, baseSold))
}
function formatDate(d: string) {
  return dayjs(d).format('MM月DD日')
}

async function handleSeckill(voucherId: number) {
  if (!userStore.isLoggedIn) {
    router.push({ path: '/login', query: { redirect: '/seckill' } })
    return
  }
  try {
    await ElMessageBox.confirm('确认抢购该秒杀优惠券吗？数量有限，抢完即止！', '秒杀确认', {
      type: 'warning',
      confirmButtonText: '立即抢购',
      cancelButtonText: '再看看'
    })
    await voucherOrderApi.seckillVoucher(voucherId)
    ElMessage.success('抢购成功，请前往订单页完成支付')
    setTimeout(() => router.push('/orders'), 500)
  } catch (e) {
    // cancelled
  }
}
</script>

<style scoped>
.line-clamp-1 {
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
