<template>
  <div v-if="loading" class="container py-8">
    <div class="card h-96 animate-pulse bg-gray-200"></div>
  </div>

  <div v-else-if="blog" class="container py-8">
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div class="lg:col-span-2">
        <div class="card p-6">
          <!-- Author -->
          <div class="flex items-center justify-between mb-6 pb-6 border-b">
            <div class="flex items-center gap-3">
              <el-avatar :size="48" :src="blog.icon">
                {{ blog.name?.[0] || 'U' }}
              </el-avatar>
              <div>
                <div class="font-semibold text-gray-800">{{ blog.name || '用户' + blog.userId }}</div>
                <div class="text-xs text-gray-400">{{ formatTime(blog.createTime) }}</div>
              </div>
            </div>
            <button class="btn-outline text-sm" v-if="blog.shopId">
              <el-icon class="mr-1"><Location /></el-icon>
              <router-link :to="`/shop/${blog.shopId}`">查看商家</router-link>
            </button>
          </div>

          <!-- Content -->
          <h1 class="text-2xl font-bold mb-4">{{ blog.title }}</h1>

          <div v-if="imageList.length > 0" class="mb-6">
            <div class="grid gap-3" :class="imageGridClass">
              <img
                v-for="(img, idx) in imageList"
                :key="idx"
                :src="img"
                :alt="`图片${idx + 1}`"
                class="w-full object-cover rounded-lg cursor-pointer hover:opacity-90 transition-opacity"
                :class="imageList.length === 1 ? 'max-h-96 aspect-auto' : 'aspect-square'"
              />
            </div>
          </div>

          <div class="prose prose-sm max-w-none mb-6 whitespace-pre-wrap text-gray-700 leading-relaxed">
            {{ blog.content }}
          </div>

          <!-- Actions -->
          <div class="flex items-center gap-4 pt-6 border-t">
            <button
              class="flex items-center gap-2 px-4 py-2 rounded-full transition-colors"
              :class="blog.isLike ? 'bg-primary-50 text-primary-500' : 'bg-gray-100 hover:bg-gray-200 text-gray-600'"
              @click="handleLike"
            >
              <el-icon class="text-xl">
                <component :is="blog.isLike ? 'StarFilled' : 'Star'" />
              </el-icon>
              <span class="font-medium">{{ blog.liked || 0 }}</span>
            </button>
            <button class="flex items-center gap-2 px-4 py-2 rounded-full bg-gray-100 hover:bg-gray-200 text-gray-600 transition-colors">
              <el-icon class="text-xl"><ChatDotRound /></el-icon>
              <span class="font-medium">{{ blog.comments || 0 }}</span>
            </button>
            <button class="flex items-center gap-2 px-4 py-2 rounded-full bg-gray-100 hover:bg-gray-200 text-gray-600 transition-colors">
              <el-icon class="text-xl"><Share /></el-icon>
              <span class="font-medium">分享</span>
            </button>
            <div class="ml-auto flex items-center gap-2 text-sm text-gray-500">
              <el-icon><View /></el-icon>
              <span>浏览 {{ blog.liked * 10 + 100 }}</span>
            </div>
          </div>
        </div>

        <!-- Comments Section -->
        <div class="card p-6 mt-6">
          <h3 class="font-semibold text-lg mb-4">评论 ({{ blog.comments || 0 }})</h3>

          <div class="mb-6 pb-6 border-b">
            <div class="flex gap-3">
              <el-avatar :size="36" :src="userStore.userInfo?.icon">
                {{ userStore.userInfo?.nickName?.[0] || 'U' }}
              </el-avatar>
              <div class="flex-1">
                <el-input
                  v-model="newComment"
                  type="textarea"
                  :rows="2"
                  placeholder="写下你的评论..."
                  :disabled="!userStore.isLoggedIn"
                />
                <div class="flex justify-end mt-2">
                  <el-button
                    type="primary"
                    size="small"
                    :disabled="!newComment.trim() || !userStore.isLoggedIn"
                    @click="submitComment"
                  >
                    发布评论
                  </el-button>
                </div>
                <p v-if="!userStore.isLoggedIn" class="text-xs text-gray-400 mt-1">
                  请先 <router-link to="/login" class="text-primary-500">登录</router-link> 后发表评论
                </p>
              </div>
            </div>
          </div>

          <div v-if="comments.length === 0" class="text-center py-8 text-gray-400">
            <el-icon class="text-4xl mb-2"><ChatDotRound /></el-icon>
            <p>暂无评论，快来抢沙发吧！</p>
          </div>

          <div v-else class="space-y-4">
            <div v-for="c in comments" :key="c.id" class="flex gap-3">
              <el-avatar :size="36">
                {{ ('用户' + c.userId)?.[0] || 'U' }}
              </el-avatar>
              <div class="flex-1">
                <div class="flex items-center gap-2 mb-1">
                  <span class="font-medium text-sm">用户{{ c.userId }}</span>
                  <span class="text-xs text-gray-400">{{ formatTime(c.createTime) }}</span>
                </div>
                <p class="text-gray-700 text-sm">{{ c.content }}</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Sidebar -->
      <div class="space-y-6">
        <div v-if="blog.shopId" class="card p-6">
          <h3 class="font-semibold mb-4 flex items-center gap-2">
            <el-icon class="text-primary-500"><Shop /></el-icon>
            探店商家
          </h3>
          <div v-if="shop" class="flex gap-3">
            <div class="w-20 h-20 rounded-lg bg-gray-100 overflow-hidden flex-shrink-0">
              <img v-if="getFirstImage(shop.images)" :src="getFirstImage(shop.images)" class="w-full h-full object-cover" />
              <div v-else class="w-full h-full flex items-center justify-center bg-primary-100">
                <el-icon class="text-primary-400 text-2xl"><Shop /></el-icon>
              </div>
            </div>
            <div class="flex-1 min-w-0">
              <router-link :to="`/shop/${shop.id}`" class="font-medium hover:text-primary-500 line-clamp-1">{{ shop.name }}</router-link>
              <div class="flex items-center gap-1 text-sm text-yellow-500 mt-1">
                <el-icon><Star /></el-icon>
                <span>{{ (shop.score / 10).toFixed(1) }}</span>
              </div>
              <p class="text-sm text-gray-500 mt-1">¥{{ shop.avgPrice }}/人</p>
            </div>
          </div>
        </div>

        <div class="card p-6">
          <h3 class="font-semibold mb-4">推荐阅读</h3>
          <div class="space-y-3">
            <div v-for="i in 3" :key="i" class="flex gap-3 cursor-pointer hover:bg-gray-50 p-2 rounded-lg transition-colors">
              <div class="w-16 h-16 rounded-lg bg-gray-200 flex-shrink-0"></div>
              <div>
                <p class="text-sm font-medium line-clamp-2">更多精彩探店笔记推荐内容展示...</p>
                <p class="text-xs text-gray-400 mt-1">1天前</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <div v-else class="container py-20 text-center">
    <el-icon class="text-6xl text-gray-300 mb-4"><Warning /></el-icon>
    <p class="text-gray-500 mb-4">笔记不存在或已删除</p>
    <router-link to="/blog" class="btn-primary">返回笔记列表</router-link>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { blogApi } from '@/api/blog'
import { shopApi } from '@/api/shop'
import type { Blog, Shop, BlogComments } from '@/types'
import dayjs from 'dayjs'
import { ElMessage } from 'element-plus'

const route = useRoute()
const userStore = useUserStore()

const blogId = computed(() => Number(route.params.id))
const blog = ref<Blog | null>(null)
const shop = ref<Shop | null>(null)
const loading = ref(true)
const newComment = ref('')
const comments = ref<BlogComments[]>([])

const imageList = computed(() => {
  if (!blog.value?.images) return []
  return blog.value.images.split(',').filter(Boolean)
})

const imageGridClass = computed(() => {
  const len = imageList.value.length
  if (len === 1) return 'grid-cols-1'
  if (len <= 4) return 'grid-cols-2'
  return 'grid-cols-3'
})

function formatTime(t: string) {
  return dayjs(t).format('YYYY-MM-DD HH:mm')
}

function getFirstImage(images: string) {
  if (!images) return ''
  return images.split(',')[0]
}

onMounted(async () => {
  try {
    const res = await blogApi.queryById(blogId.value)
    blog.value = res.data as Blog
    if (blog.value?.shopId) {
      const shopRes = await shopApi.queryById(blog.value.shopId)
      shop.value = shopRes.data as Shop
    }
  } finally {
    loading.value = false
  }
})

async function handleLike() {
  if (!blog.value) return
  try {
    await blogApi.likeBlog(blog.value.id)
    const res = await blogApi.queryById(blog.value.id)
    blog.value = res.data as Blog
  } catch (e) {
    // handled
  }
}

function submitComment() {
  if (!newComment.value.trim()) return
  comments.value.unshift({
    id: Date.now(),
    blogId: blogId.value,
    userId: userStore.userInfo?.id || 0,
    content: newComment.value,
    createTime: new Date().toISOString()
  })
  if (blog.value) {
    blog.value.comments = (blog.value.comments || 0) + 1
  }
  newComment.value = ''
  ElMessage.success('评论发表成功')
}
</script>

<style scoped>
.line-clamp-1 {
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
