<template>
  <div class="card p-4">
    <div class="flex items-center justify-between mb-4">
      <router-link :to="`/blog/${blog.id}`" class="flex items-center gap-3 hover:opacity-80 transition-opacity">
        <el-avatar :size="40" :src="blog.icon">
          {{ blog.name?.[0] || 'U' }}
        </el-avatar>
        <div>
          <div class="font-medium text-gray-800">{{ blog.name || '用户' + blog.userId }}</div>
          <div class="text-xs text-gray-400">{{ formatTime(blog.createTime) }}</div>
        </div>
      </router-link>
    </div>

    <router-link :to="`/blog/${blog.id}`" class="block mb-3">
      <h4 class="font-semibold text-lg mb-2 hover:text-primary-500 transition-colors">{{ blog.title }}</h4>
      <p class="text-gray-600 text-sm line-clamp-2 mb-3">{{ blog.content }}</p>
    </router-link>

    <div v-if="blog.images" class="grid gap-2 mb-3" :class="imageGridClass">
      <img
        v-for="(img, idx) in imageList"
        :key="idx"
        :src="img"
        :alt="blog.title"
        class="w-full aspect-square object-cover rounded-lg cursor-pointer hover:opacity-90 transition-opacity"
      />
    </div>

    <div class="flex items-center justify-between pt-3 border-t border-gray-100">
      <div class="flex items-center gap-4 text-gray-500">
        <button
          class="flex items-center gap-1 hover:text-primary-500 transition-colors"
          :class="{ 'text-primary-500': blog.isLike }"
          @click.stop="handleLike"
        >
          <el-icon><component :is="blog.isLike ? 'StarFilled' : 'Star'" /></el-icon>
          <span class="text-sm">{{ blog.liked || 0 }}</span>
        </button>
        <span class="flex items-center gap-1">
          <el-icon><ChatDotRound /></el-icon>
          <span class="text-sm">{{ blog.comments || 0 }}</span>
        </span>
      </div>
      <router-link v-if="blog.shopId" :to="`/shop/${blog.shopId}`" class="text-xs text-primary-500 hover:underline">
        查看商家
      </router-link>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Blog } from '@/types'
import { blogApi } from '@/api/blog'
import dayjs from 'dayjs'

const props = defineProps<{
  blog: Blog
}>()

const emit = defineEmits(['update:liked'])

const imageList = computed(() => {
  if (!props.blog.images) return []
  return props.blog.images.split(',').filter(Boolean).slice(0, 9)
})

const imageGridClass = computed(() => {
  const len = imageList.value.length
  if (len === 1) return 'grid-cols-1 max-w-md'
  if (len <= 4) return 'grid-cols-2'
  return 'grid-cols-3'
})

function formatTime(time: string) {
  return dayjs(time).format('YYYY-MM-DD HH:mm')
}

async function handleLike() {
  try {
    await blogApi.likeBlog(props.blog.id)
    emit('update:liked')
  } catch (e) {
    // handled by interceptor
  }
}
</script>

<style scoped>
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
