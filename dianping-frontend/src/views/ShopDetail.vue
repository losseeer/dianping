<template>
  <div v-if="loading" class="container py-8">
    <div class="card h-96 animate-pulse bg-gray-200"></div>
  </div>

  <div v-else-if="shop" class="min-h-screen bg-gray-50">
    <!-- Shop Header -->
    <div class="bg-white border-b">
      <div class="container py-6">
        <div class="flex flex-col lg:flex-row gap-6">
          <div class="relative lg:w-96 h-64 lg:h-72 rounded-xl overflow-hidden bg-gray-100 flex-shrink-0">
            <img
              v-if="mainImage"
              :src="mainImage"
              :alt="shop.name"
              class="w-full h-full object-cover"
            />
            <div v-else class="w-full h-full flex items-center justify-center bg-gradient-to-br from-primary-100 to-primary-200">
              <el-icon class="text-7xl text-primary-400"><Shop /></el-icon>
            </div>
            <div class="absolute bottom-3 right-3 bg-white/90 backdrop-blur rounded-lg px-3 py-1.5 flex items-center gap-1">
              <el-icon class="text-yellow-500"><Star /></el-icon>
              <span class="font-semibold">{{ (shop.score / 10).toFixed(1) }}</span>
              <span class="text-xs text-gray-500">分</span>
            </div>
          </div>

          <div class="flex-1">
            <div class="flex items-start justify-between gap-4 mb-4">
              <div>
                <h1 class="text-2xl font-bold mb-2">{{ shop.name }}</h1>
                <div class="flex flex-wrap items-center gap-3 text-sm text-gray-500">
                  <span class="flex items-center gap-1">
                    <el-icon><Location /></el-icon>
                    {{ shop.area }}
                  </span>
                  <span class="flex items-center gap-1">
                    <el-icon><Phone /></el-icon>
                    {{ shop.address }}
                  </span>
                  <span class="flex items-center gap-1">
                    <el-icon><Clock /></el-icon>
                    {{ shop.openHours || '暂无营业时间' }}
                  </span>
                </div>
              </div>
              <div class="flex flex-col items-end">
                <div class="flex items-baseline gap-1">
                  <span class="text-gray-500 text-sm">¥</span>
                  <span class="text-2xl font-bold text-primary-500">{{ shop.avgPrice }}</span>
                  <span class="text-gray-500 text-sm">/人</span>
                </div>
                <div class="text-xs text-gray-400 mt-1">
                  月售{{ shop.sold || 0 }} · 评论{{ shop.comments || 0 }}
                </div>
              </div>
            </div>

            <div v-if="imageList.length > 1" class="flex gap-2 mb-4 overflow-x-auto pb-2">
              <button
                v-for="(img, idx) in imageList"
                :key="idx"
                class="w-16 h-16 rounded-lg overflow-hidden flex-shrink-0 border-2 transition-colors"
                :class="idx === 0 ? 'border-primary-500' : 'border-transparent hover:border-primary-300'"
                @click="selectImage(idx)"
              >
                <img :src="img" class="w-full h-full object-cover" />
              </button>
            </div>

            <div class="flex flex-wrap gap-3">
              <button class="btn-primary flex items-center gap-1">
                <el-icon><Phone /></el-icon>
                联系商家
              </button>
              <button class="btn-outline flex items-center gap-1">
                <el-icon><Location /></el-icon>
                导航前往
              </button>
              <button class="btn-outline flex items-center gap-1">
                <el-icon><Collection /></el-icon>
                收藏
              </button>
              <router-link
                to="/blog/create"
                class="btn-outline flex items-center gap-1"
              >
                <el-icon><Edit /></el-icon>
                写点评
              </router-link>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="container py-8">
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <!-- Main Content -->
        <div class="lg:col-span-2 space-y-6">
          <!-- AI Review Summary (Agent1) -->
          <div class="card p-6 bg-gradient-to-br from-indigo-50 to-purple-50 border border-indigo-100">
            <div class="flex items-center justify-between mb-4">
              <h2 class="text-xl font-bold flex items-center gap-2">
                <el-icon class="text-indigo-500"><MagicStick /></el-icon>
                AI 评价摘要
              </h2>
              <button
                v-if="!summary && !summaryLoading"
                class="btn-primary text-sm flex items-center gap-1"
                @click="loadReviewSummary"
              >
                <el-icon><MagicStick /></el-icon>
                生成 AI 摘要
              </button>
            </div>

            <!-- Loading -->
            <div v-if="summaryLoading" class="flex items-center gap-3 py-8 text-indigo-500">
              <el-icon class="is-loading text-2xl"><Loading /></el-icon>
              <span class="text-sm">AI 正在分析全部评价，请稍候...</span>
            </div>

            <!-- Summary Content -->
            <div v-else-if="summary" class="space-y-4">
              <!-- Stats Row -->
              <div class="grid grid-cols-3 gap-4">
                <div class="text-center bg-white rounded-lg p-3">
                  <el-progress
                    type="dashboard"
                    :percentage="Math.round(summary.positiveRate * 100)"
                    :width="70"
                    :color="summary.positiveRate >= 0.7 ? '#67c23a' : '#e6a23c'"
                  />
                  <p class="text-xs text-gray-500 mt-1">好评率</p>
                </div>
                <div class="text-center bg-white rounded-lg p-3 flex flex-col justify-center">
                  <p class="text-2xl font-bold text-indigo-500">{{ summary.totalReviews }}</p>
                  <p class="text-xs text-gray-500">评价总数</p>
                </div>
                <div class="text-center bg-white rounded-lg p-3 flex flex-col justify-center">
                  <p class="text-2xl font-bold text-indigo-500">{{ summary.avgLikedPerReview }}</p>
                  <p class="text-xs text-gray-500">平均点赞</p>
                </div>
              </div>

              <!-- Pros & Cons -->
              <div class="grid grid-cols-2 gap-4">
                <div class="bg-green-50 rounded-lg p-3">
                  <p class="text-sm font-semibold text-green-600 mb-2 flex items-center gap-1">
                    <el-icon><CircleCheckFilled /></el-icon> 优点
                  </p>
                  <div class="flex flex-wrap gap-1.5">
                    <el-tag v-for="pro in summary.topPros" :key="pro" type="success" size="small" effect="plain">
                      {{ pro }}
                    </el-tag>
                  </div>
                </div>
                <div class="bg-red-50 rounded-lg p-3">
                  <p class="text-sm font-semibold text-red-500 mb-2 flex items-center gap-1">
                    <el-icon><CircleCloseFilled /></el-icon> 缺点
                  </p>
                  <div class="flex flex-wrap gap-1.5">
                    <el-tag v-for="con in summary.topCons" :key="con" type="danger" size="small" effect="plain">
                      {{ con }}
                    </el-tag>
                  </div>
                </div>
              </div>

              <!-- Key Phrases -->
              <div v-if="summary.keyPhrases.length > 0">
                <p class="text-sm font-semibold text-gray-600 mb-2">高频关键词</p>
                <div class="flex flex-wrap gap-1.5">
                  <el-tag v-for="phrase in summary.keyPhrases" :key="phrase" type="primary" size="small">
                    {{ phrase }}
                  </el-tag>
                </div>
              </div>

              <!-- LLM Recommendation -->
              <div class="bg-white rounded-lg p-4 border border-indigo-100">
                <p class="text-sm font-semibold text-indigo-600 mb-2 flex items-center gap-1">
                  <el-icon><ChatLineSquare /></el-icon> AI 综合建议
                </p>
                <p class="text-sm text-gray-700 leading-relaxed">{{ summary.recommendation }}</p>
                <div class="mt-3 pt-3 border-t border-gray-100 flex items-center gap-2 text-xs text-gray-500">
                  <el-rate :model-value="summary.scoreBreakdown.overall" disabled allow-half size="small" />
                  <span>{{ summary.scoreBreakdown.interpretation }}</span>
                </div>
              </div>
            </div>

            <!-- Empty State -->
            <div v-else class="text-center py-6 text-gray-400">
              <el-icon class="text-4xl mb-2"><MagicStick /></el-icon>
              <p class="text-sm">点击"生成 AI 摘要"，让 AI 帮你快速了解全部评价</p>
            </div>
          </div>

          <!-- Vouchers Section -->
          <div class="card p-6">
            <div class="flex items-center justify-between mb-4">
              <h2 class="text-xl font-bold flex items-center gap-2">
                <el-icon class="text-primary-500"><Tickets /></el-icon>
                优惠券
              </h2>
            </div>

            <div v-if="voucherLoading" class="grid gap-4">
              <div v-for="i in 2" :key="i" class="h-32 animate-pulse bg-gray-100 rounded-lg"></div>
            </div>

            <div v-else-if="vouchers.length > 0" class="grid gap-4">
              <VoucherCard
                v-for="v in vouchers"
                :key="v.id"
                :voucher="v"
                @seckill="handleSeckill"
                @buy="handleBuyVoucher"
              />
            </div>

            <div v-else class="text-center py-10 text-gray-400">
              <el-icon class="text-4xl mb-2"><Tickets /></el-icon>
              <p>暂无优惠券</p>
            </div>
          </div>

          <!-- Blogs Section -->
          <div class="card p-6">
            <div class="flex items-center justify-between mb-4">
              <h2 class="text-xl font-bold flex items-center gap-2">
                <el-icon class="text-primary-500"><ChatDotRound /></el-icon>
                用户评价 ({{ blogs.length }})
              </h2>
              <router-link
                to="/blog/create"
                class="text-sm text-primary-500 hover:underline"
              >
                写一条评价
              </router-link>
            </div>

            <div v-if="blogLoading" class="grid gap-4">
              <div v-for="i in 3" :key="i" class="h-48 animate-pulse bg-gray-100 rounded-lg"></div>
            </div>

            <div v-else-if="blogs.length > 0" class="grid gap-4">
              <BlogCard
                v-for="blog in blogs"
                :key="blog.id"
                :blog="blog"
                @update:liked="loadBlogs"
              />
            </div>

            <div v-else class="text-center py-10 text-gray-400">
              <el-icon class="text-4xl mb-2"><ChatDotRound /></el-icon>
              <p>暂无评价，快来写第一条吧！</p>
            </div>
          </div>
        </div>

        <!-- Sidebar -->
        <div class="space-y-6">
          <div class="card p-6">
            <h3 class="font-semibold mb-4 flex items-center gap-2">
              <el-icon><InfoFilled /></el-icon>
              商家信息
            </h3>
            <div class="space-y-3 text-sm">
              <div class="flex gap-3">
                <span class="text-gray-500 w-16 flex-shrink-0">地址</span>
                <span>{{ shop.area }} · {{ shop.address }}</span>
              </div>
              <div class="flex gap-3">
                <span class="text-gray-500 w-16 flex-shrink-0">营业</span>
                <span>{{ shop.openHours || '暂无' }}</span>
              </div>
              <div class="flex gap-3">
                <span class="text-gray-500 w-16 flex-shrink-0">电话</span>
                <span>400-888-8888</span>
              </div>
              <div v-if="shop.x && shop.y" class="flex gap-3">
                <span class="text-gray-500 w-16 flex-shrink-0">坐标</span>
                <span>{{ shop.x.toFixed(4) }}, {{ shop.y.toFixed(4) }}</span>
              </div>
            </div>
          </div>

          <div class="card p-6 bg-gradient-to-br from-primary-50 to-orange-50">
            <h3 class="font-semibold mb-3 text-primary-700">温馨提示</h3>
            <ul class="space-y-2 text-sm text-gray-600">
              <li class="flex items-start gap-2">
                <el-icon class="text-primary-500 mt-0.5 flex-shrink-0"><CircleCheck /></el-icon>
                <span>秒杀优惠券数量有限，抢完即止</span>
              </li>
              <li class="flex items-start gap-2">
                <el-icon class="text-primary-500 mt-0.5 flex-shrink-0"><CircleCheck /></el-icon>
                <span>购买后请在有效期内使用，过期不退</span>
              </li>
              <li class="flex items-start gap-2">
                <el-icon class="text-primary-500 mt-0.5 flex-shrink-0"><CircleCheck /></el-icon>
                <span>遇到问题可联系商家或客服</span>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  </div>

  <div v-else class="container py-20 text-center">
    <el-icon class="text-6xl text-gray-300 mb-4"><Warning /></el-icon>
    <p class="text-gray-500 mb-4">商家不存在或已下架</p>
    <router-link to="/shop" class="btn-primary">返回商家列表</router-link>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import ShopCard from '@/components/shop/ShopCard.vue'
import BlogCard from '@/components/blog/BlogCard.vue'
import VoucherCard from '@/components/voucher/VoucherCard.vue'
import { shopApi } from '@/api/shop'
import { voucherApi } from '@/api/voucher'
import { voucherOrderApi } from '@/api/voucherOrder'
import { paymentApi } from '@/api/payment'
import { orderApi } from '@/api/order'
import { blogApi } from '@/api/blog'
import { agent1Api } from '@/api/agent'
import type { Shop, Voucher, Blog, ReviewSummary } from '@/types'
import { ElMessage, ElMessageBox } from 'element-plus'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const shop = ref<Shop | null>(null)
const loading = ref(true)
const vouchers = ref<Voucher[]>([])
const voucherLoading = ref(true)
const blogs = ref<Blog[]>([])
const blogLoading = ref(true)
const currentImageIdx = ref(0)
const summary = ref<ReviewSummary | null>(null)
const summaryLoading = ref(false)

const shopId = computed(() => Number(route.params.id))

const imageList = computed(() => {
  if (!shop.value?.images) return []
  return shop.value.images.split(',').filter(Boolean)
})

const mainImage = computed(() => imageList.value[currentImageIdx.value] || '')

function selectImage(idx: number) {
  currentImageIdx.value = idx
}

onMounted(async () => {
  await Promise.all([loadShop(), loadVouchers(), loadBlogs()])
})

async function loadShop() {
  loading.value = true
  try {
    const res = await shopApi.queryById(shopId.value)
    shop.value = res.data as Shop
  } finally {
    loading.value = false
  }
}

async function loadVouchers() {
  voucherLoading.value = true
  try {
    const res = await voucherApi.queryVoucherOfShop(shopId.value)
    vouchers.value = (res.data as Voucher[]) || []
  } finally {
    voucherLoading.value = false
  }
}

async function loadBlogs() {
  blogLoading.value = true
  try {
    const res = await blogApi.queryByShopId(shopId.value, 1)
    blogs.value = (res.data as Blog[]) || []
  } finally {
    blogLoading.value = false
  }
}

async function loadReviewSummary() {
  summaryLoading.value = true
  summary.value = null
  try {
    const res = await agent1Api.getReviewSummary(shopId.value)
    summary.value = res.data
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error || 'AI 摘要生成失败，请确认 Agent1 服务已启动')
  } finally {
    summaryLoading.value = false
  }
}

async function waitOrderReady(orderId: number, maxTimes = 8, intervalMs = 500): Promise<void> {
  for (let i = 0; i < maxTimes; i++) {
    try {
      const res = await orderApi.queryById(orderId)
      const detail = (res.data as any) || {}
      if (!detail.pending) return
    } catch (e) {
      // ignore
    }
    await new Promise(resolve => setTimeout(resolve, intervalMs))
  }
}

async function handleSeckill(voucherId: number) {
  if (!userStore.isLoggedIn) {
    router.push({ path: '/login', query: { redirect: route.fullPath } })
    return
  }
  try {
    await ElMessageBox.confirm('确定要抢购该秒杀优惠券吗？', '确认抢购', {
      type: 'warning'
    })
    const res = await voucherOrderApi.seckillVoucher(voucherId)
    const orderId = res.data as number
    ElMessage.success('抢购成功！正在完成订单创建...')
    try {
      await waitOrderReady(orderId)
      await paymentApi.pay({ orderId, payType: 1 })
      ElMessage.success('支付成功！')
      router.push('/orders')
    } catch (e) {
      ElMessage.warning('请前往订单页面完成支付')
      router.push('/orders')
    }
  } catch (e) {
    // cancelled or error
  }
}

async function handleBuyVoucher(voucherId: number) {
  handleSeckill(voucherId)
}
</script>
