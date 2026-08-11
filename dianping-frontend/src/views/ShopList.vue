<template>
  <div class="container py-8">
    <!-- Filter Bar -->
    <div class="card p-4 mb-6 sticky top-16 z-30 bg-white/95 backdrop-blur">
      <div class="flex flex-wrap items-center gap-4">
        <div class="flex items-center gap-2 overflow-x-auto pb-2 sm:pb-0">
          <button
            class="px-4 py-2 rounded-full text-sm whitespace-nowrap transition-colors"
            :class="currentTypeId === null ? 'bg-primary-500 text-white' : 'bg-gray-100 hover:bg-gray-200 text-gray-700'"
            @click="currentTypeId = null; loadShops()"
          >
            全部
          </button>
          <button
            v-for="type in shopStore.shopTypes"
            :key="type.id"
            class="px-4 py-2 rounded-full text-sm whitespace-nowrap transition-colors"
            :class="currentTypeId === type.id ? 'bg-primary-500 text-white' : 'bg-gray-100 hover:bg-gray-200 text-gray-700'"
            @click="currentTypeId = type.id; loadShops()"
          >
            {{ type.name }}
          </button>
        </div>

        <div class="flex items-center gap-2 ml-auto">
          <el-select v-model="sortBy" size="default" @change="loadShops" style="width: 140px">
            <el-option label="默认排序" value="default" />
            <el-option label="评分优先" value="score" />
            <el-option label="销量优先" value="sold" />
            <el-option label="价格低到高" value="price_asc" />
            <el-option label="价格高到低" value="price_desc" />
          </el-select>
        </div>
      </div>
    </div>

    <!-- Results -->
    <div v-if="loading" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
      <div v-for="i in 12" :key="i" class="card h-80 animate-pulse bg-gray-200"></div>
    </div>

    <div v-else-if="shops.length > 0">
      <div class="mb-4 text-sm text-gray-500">
        共找到 <span class="text-primary-500 font-semibold">{{ shops.length }}</span> 家商家
      </div>
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
        <ShopCard v-for="shop in sortedShops" :key="shop.id" :shop="shop" />
      </div>

      <div class="flex justify-center mt-8">
        <el-pagination
          v-model:current-page="current"
          :page-size="pageSize"
          :total="total"
          layout="prev, pager, next"
          @current-change="handlePageChange"
        />
      </div>
    </div>

    <div v-else class="text-center py-20">
      <el-icon class="text-6xl text-gray-300 mb-4"><Search /></el-icon>
      <p class="text-gray-500 mb-4">暂无商家数据</p>
      <router-link to="/" class="btn-primary">返回首页</router-link>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import ShopCard from '@/components/shop/ShopCard.vue'
import { shopApi } from '@/api/shop'
import { useShopStore } from '@/stores/shop'
import type { Shop } from '@/types'

const route = useRoute()
const shopStore = useShopStore()

const currentTypeId = ref<number | null>(null)
const sortBy = ref('default')
const current = ref(1)
const pageSize = 12
const total = ref(0)
const shops = ref<Shop[]>([])
const loading = ref(true)

const sortedShops = computed(() => {
  const list = [...shops.value]
  switch (sortBy.value) {
    case 'score':
      return list.sort((a, b) => (b.score || 0) - (a.score || 0))
    case 'sold':
      return list.sort((a, b) => (b.sold || 0) - (a.sold || 0))
    case 'price_asc':
      return list.sort((a, b) => (a.avgPrice || 0) - (b.avgPrice || 0))
    case 'price_desc':
      return list.sort((a, b) => (b.avgPrice || 0) - (a.avgPrice || 0))
    default:
      return list
  }
})

onMounted(() => {
  const qType = route.query.typeId
  if (qType) {
    currentTypeId.value = Number(qType)
  }
  loadShops()
})

watch(() => route.query.typeId, (newVal) => {
  if (newVal) {
    currentTypeId.value = Number(newVal)
    current.value = 1
    loadShops()
  }
})

async function loadShops() {
  loading.value = true
  try {
    if (currentTypeId.value !== null) {
      const res = await shopApi.queryByType(currentTypeId.value, current.value)
      shops.value = (res.data as Shop[]) || []
    } else {
      const res = await shopApi.queryByName(undefined, current.value)
      shops.value = (res.data as Shop[]) || []
    }
    total.value = (shops.value.length >= pageSize ? current.value * pageSize + 1 : (current.value - 1) * pageSize + shops.value.length)
  } finally {
    loading.value = false
  }
}

function handlePageChange(p: number) {
  current.value = p
  loadShops()
  window.scrollTo({ top: 0, behavior: 'smooth' })
}
</script>
