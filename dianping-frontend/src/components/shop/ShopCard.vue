<template>
  <router-link :to="`/shop/${shop.id}`" class="card block overflow-hidden hover:shadow-lg transition-all duration-300 group">
    <div class="relative h-48 overflow-hidden bg-gray-100">
      <img
        v-if="shop.images"
        :src="getFirstImage(shop.images)"
        :alt="shop.name"
        class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
      />
      <div v-else class="w-full h-full flex items-center justify-center bg-gradient-to-br from-primary-100 to-primary-200">
        <el-icon class="text-5xl text-primary-400"><Shop /></el-icon>
      </div>
      <div class="absolute top-2 right-2 bg-white/90 backdrop-blur rounded-full px-2 py-1 flex items-center gap-1">
        <el-icon class="text-yellow-500 text-sm"><Star /></el-icon>
        <span class="text-sm font-semibold">{{ (shop.score / 10).toFixed(1) }}</span>
      </div>
      <div v-if="shop.distance !== undefined" class="absolute bottom-2 right-2 bg-black/60 backdrop-blur text-white rounded-full px-2 py-1 text-xs">
        {{ formatDistance(shop.distance) }}
      </div>
    </div>
    <div class="p-4">
      <h3 class="font-semibold text-lg mb-1 truncate group-hover:text-primary-500 transition-colors">{{ shop.name }}</h3>
      <div class="flex items-center gap-2 text-sm text-gray-500 mb-2">
        <el-icon class="text-xs"><Location /></el-icon>
        <span class="truncate">{{ shop.area }} · {{ shop.address }}</span>
      </div>
      <div class="flex items-center justify-between">
        <div class="flex items-baseline gap-2">
          <span class="price-text text-xl">¥{{ shop.avgPrice }}</span>
          <span class="text-gray-400 text-xs">人均</span>
        </div>
        <div class="text-sm text-gray-500">
          <span class="mr-3">月售{{ shop.sold || 0 }}</span>
          <span>评论{{ shop.comments || 0 }}</span>
        </div>
      </div>
    </div>
  </router-link>
</template>

<script setup lang="ts">
import type { Shop } from '@/types'

defineProps<{
  shop: Shop
}>()

function getFirstImage(images: string) {
  if (!images) return ''
  const first = images.split(',')[0]
  return first
}

function formatDistance(meters: number) {
  if (meters < 1000) return `${meters.toFixed(0)}m`
  return `${(meters / 1000).toFixed(2)}km`
}
</script>
