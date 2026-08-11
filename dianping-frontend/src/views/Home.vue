<template>
  <div>
    <!-- Hero Banner -->
    <section class="bg-gradient-to-r from-primary-500 to-primary-600 text-white py-16">
      <div class="container">
        <div class="max-w-2xl">
          <h1 class="text-4xl font-bold mb-4">发现身边的美好生活</h1>
          <p class="text-lg text-primary-100 mb-8">
            数百万商家真实评价，千万用户的吃喝玩乐指南
          </p>
          <div class="flex gap-4 flex-wrap">
            <router-link to="/shop" class="bg-white text-primary-600 px-6 py-3 rounded-lg font-semibold hover:bg-primary-50 transition-colors">
              查找商家
            </router-link>
            <router-link to="/seckill" class="border border-white text-white px-6 py-3 rounded-lg font-semibold hover:bg-white/10 transition-colors">
              限时秒杀
            </router-link>
          </div>
        </div>
      </div>
    </section>

    <!-- Category Navigation -->
    <section class="container -mt-8">
      <div class="card p-6">
        <h2 class="text-lg font-semibold mb-4">分类导航</h2>
        <div class="grid grid-cols-4 sm:grid-cols-6 md:grid-cols-8 lg:grid-cols-10 gap-4">
          <button
            v-for="type in shopStore.shopTypes"
            :key="type.id"
            class="flex flex-col items-center gap-2 p-3 rounded-lg hover:bg-primary-50 transition-colors group"
            @click="goToShopList(type.id)"
          >
            <div class="w-12 h-12 rounded-full bg-primary-100 group-hover:bg-primary-200 transition-colors flex items-center justify-center">
              <img v-if="type.icon" :src="type.icon" :alt="type.name" class="w-6 h-6" />
              <el-icon v-else class="text-primary-500 text-xl"><Shop /></el-icon>
            </div>
            <span class="text-xs text-gray-600">{{ type.name }}</span>
          </button>
        </div>
      </div>
    </section>

    <!-- Hot Shops -->
    <section class="container py-12">
      <div class="flex items-center justify-between mb-6">
        <div>
          <h2 class="text-2xl font-bold mb-1">热门推荐</h2>
          <p class="text-gray-500">精选优质商家，为你推荐</p>
        </div>
        <router-link to="/shop" class="text-primary-500 hover:underline text-sm flex items-center gap-1">
          查看更多 <el-icon><ArrowRight /></el-icon>
        </router-link>
      </div>

      <div v-if="loading" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        <div v-for="i in 8" :key="i" class="card h-72 animate-pulse bg-gray-200"></div>
      </div>

      <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        <ShopCard v-for="shop in shops" :key="shop.id" :shop="shop" />
      </div>
    </section>

    <!-- Hot Blogs -->
    <section class="bg-white py-12">
      <div class="container">
        <div class="flex items-center justify-between mb-6">
          <div>
            <h2 class="text-2xl font-bold mb-1">探店笔记</h2>
            <p class="text-gray-500">真实用户分享，发现隐藏好店</p>
          </div>
          <router-link to="/blog" class="text-primary-500 hover:underline text-sm flex items-center gap-1">
            查看更多 <el-icon><ArrowRight /></el-icon>
          </router-link>
        </div>

        <div v-if="blogLoading" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <div v-for="i in 6" :key="i" class="card h-64 animate-pulse bg-gray-200"></div>
        </div>

        <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <BlogCard v-for="blog in blogs" :key="blog.id" :blog="blog" @update:liked="reloadBlogs" />
        </div>
      </div>
    </section>

    <!-- Seckill Preview -->
    <section class="container py-12">
      <div class="card p-6 bg-gradient-to-r from-red-50 to-orange-50 border border-red-100">
        <div class="flex items-center justify-between mb-6">
          <div class="flex items-center gap-3">
            <div class="w-10 h-10 rounded-lg bg-red-500 flex items-center justify-center text-white">
              <el-icon class="text-xl"><Lightning /></el-icon>
            </div>
            <div>
              <h2 class="text-2xl font-bold text-gray-800">限时秒杀</h2>
              <p class="text-sm text-gray-500">超值优惠券，手慢无</p>
            </div>
            <div class="ml-6 flex items-center gap-1 text-red-500">
              <span class="text-sm font-semibold">距结束</span>
              <el-tag type="danger" effect="dark">{{ countdownText }}</el-tag>
            </div>
          </div>
          <router-link to="/seckill" class="btn-primary">
            全部秒杀 <el-icon class="ml-1"><ArrowRight /></el-icon>
          </router-link>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import ShopCard from '@/components/shop/ShopCard.vue'
import BlogCard from '@/components/blog/BlogCard.vue'
import { shopApi } from '@/api/shop'
import { blogApi } from '@/api/blog'
import { useShopStore } from '@/stores/shop'
import type { Shop, Blog } from '@/types'

const router = useRouter()
const shopStore = useShopStore()

const shops = ref<Shop[]>([])
const blogs = ref<Blog[]>([])
const loading = ref(true)
const blogLoading = ref(true)

const countdownEnd = ref(Date.now() + 3600000 * 2)
const now = ref(Date.now())
let timer: number | null = null

const countdownText = ref('')

function updateCountdown() {
  now.value = Date.now()
  const diff = countdownEnd.value - now.value
  if (diff <= 0) {
    countdownEnd.value = Date.now() + 3600000 * 2
    return
  }
  const hours = Math.floor(diff / 3600000).toString().padStart(2, '0')
  const mins = Math.floor((diff % 3600000) / 60000).toString().padStart(2, '0')
  const secs = Math.floor((diff % 60000) / 1000).toString().padStart(2, '0')
  countdownText.value = `${hours}:${mins}:${secs}`
}

onMounted(async () => {
  timer = window.setInterval(updateCountdown, 1000)
  updateCountdown()
  await Promise.all([loadShops(), loadBlogs()])
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})

async function loadShops() {
  loading.value = true
  try {
    const res = await shopApi.queryByType(1, 1)
    shops.value = (res.data as Shop[]) || []
  } finally {
    loading.value = false
  }
}

async function loadBlogs() {
  blogLoading.value = true
  try {
    const res = await blogApi.queryHotBlog(1)
    blogs.value = (res.data as Blog[]) || []
  } finally {
    blogLoading.value = false
  }
}

function reloadBlogs() {
  loadBlogs()
}

function goToShopList(typeId: number) {
  router.push({ path: '/shop', query: { typeId: typeId.toString() } })
}
</script>
