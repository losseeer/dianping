<template>
  <div class="container py-8">
    <!-- Tabs -->
    <div class="card p-2 mb-6 inline-flex">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        class="px-6 py-2 rounded-lg transition-colors text-sm font-medium"
        :class="activeTab === tab.key ? 'bg-primary-500 text-white' : 'hover:bg-gray-100 text-gray-600'"
        @click="activeTab = tab.key; current = 1; loadData()"
      >
        <el-icon class="mr-1" style="vertical-align: -2px">
          <component :is="tab.icon" />
        </el-icon>
        {{ tab.label }}
      </button>
    </div>

    <!-- Content -->
    <div v-if="loading" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      <div v-for="i in 6" :key="i" class="card h-64 animate-pulse bg-gray-200"></div>
    </div>

    <div v-else-if="blogs.length > 0" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      <BlogCard
        v-for="blog in blogs"
        :key="blog.id"
        :blog="blog"
        @update:liked="loadData"
      />
    </div>

    <div v-else class="card p-16 text-center">
      <el-icon class="text-6xl text-gray-300 mb-4"><Document /></el-icon>
      <p class="text-gray-500 mb-4">
        {{ activeTab === 'hot' ? '暂无热门笔记' : activeTab === 'follow' ? '关注的人还没有发布笔记' : '你还没有发布笔记' }}
      </p>
      <router-link v-if="activeTab === 'mine'" to="/blog/create" class="btn-primary">
        <el-icon class="mr-1"><Edit /></el-icon>
        去写第一篇
      </router-link>
    </div>

    <!-- Pagination -->
    <div v-if="blogs.length > 0" class="flex justify-center mt-8">
      <el-pagination
        v-model:current-page="current"
        :page-size="10"
        :total="total"
        layout="prev, pager, next"
        @current-change="loadData"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import BlogCard from '@/components/blog/BlogCard.vue'
import { blogApi } from '@/api/blog'
import { useUserStore } from '@/stores/user'
import type { Blog } from '@/types'

const userStore = useUserStore()

const activeTab = ref('hot')
const current = ref(1)
const total = ref(0)
const blogs = ref<Blog[]>([])
const loading = ref(true)

const tabs = computed(() => {
  const base = [
    { key: 'hot', label: '热门推荐', icon: 'HotWater' },
    { key: 'new', label: '最新发布', icon: 'Clock' }
  ]
  if (userStore.isLoggedIn) {
    base.push({ key: 'follow', label: '关注动态', icon: 'UserFilled' })
    base.push({ key: 'mine', label: '我的笔记', icon: 'Document' })
  }
  return base
})

onMounted(loadData)

watch([activeTab], () => {
  current.value = 1
  loadData()
})

async function loadData() {
  loading.value = true
  try {
    let res
    switch (activeTab.value) {
      case 'hot':
      case 'new':
        res = await blogApi.queryHotBlog(current.value)
        break
      case 'mine':
        res = await blogApi.queryMyBlog(current.value)
        break
      case 'follow':
        res = await blogApi.queryBlogOfFollow(Date.now(), 0)
        break
    }
    blogs.value = (res?.data as Blog[]) || []
    total.value = blogs.value.length >= 10 ? current.value * 10 + 1 : (current.value - 1) * 10 + blogs.value.length
  } finally {
    loading.value = false
  }
}
</script>
