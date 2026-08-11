<template>
  <div class="container py-8">
    <!-- Search Header -->
    <div class="card p-6 mb-6">
      <el-input
        v-model="keyword"
        placeholder="搜索商家名称、菜品、地址..."
        size="large"
        @keyup.enter="handleSearch"
      >
        <template #prefix>
          <el-icon class="text-xl text-gray-400"><Search /></el-icon>
        </template>
        <template #append>
          <el-button type="primary" :loading="loading" @click="handleSearch">搜索</el-button>
        </template>
      </el-input>

      <div class="flex flex-wrap gap-4 mt-4">
        <div>
          <span class="text-sm text-gray-500 mr-2">分类：</span>
          <el-select
            v-model="filterTypeId"
            placeholder="全部"
            clearable
            size="default"
            style="width: 140px"
            @change="handleSearch"
          >
            <el-option
              v-for="type in shopStore.shopTypes"
              :key="type.id"
              :label="type.name"
              :value="type.id"
            />
          </el-select>
        </div>
        <div>
          <span class="text-sm text-gray-500 mr-2">商圈：</span>
          <el-input
            v-model="filterArea"
            placeholder="如：陆家嘴"
            size="default"
            style="width: 180px"
            @keyup.enter="handleSearch"
          />
        </div>
      </div>
    </div>

    <!-- Search Status -->
    <div v-if="hasSearched" class="mb-4">
      <p class="text-sm text-gray-500">
        搜索 "<span class="text-primary-500 font-semibold">{{ keyword }}</span>"
        <span v-if="filterTypeId" class="ml-2">
          分类: <span class="text-primary-500">{{ getTypeName(filterTypeId) }}</span>
        </span>
        <span v-if="filterArea" class="ml-2">
          商圈: <span class="text-primary-500">{{ filterArea }}</span>
        </span>
        找到 <span class="text-primary-500 font-semibold">{{ results.length }}</span> 个结果
      </p>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
      <div v-for="i in 8" :key="i" class="card h-80 animate-pulse bg-gray-200"></div>
    </div>

    <!-- Empty State -->
    <div v-else-if="hasSearched && results.length === 0" class="text-center py-20">
      <el-icon class="text-6xl text-gray-300 mb-4"><Search /></el-icon>
      <p class="text-gray-500 mb-2">没有找到相关结果</p>
      <p class="text-sm text-gray-400 mb-4">试试换个关键词或减少筛选条件</p>
      <div class="flex justify-center gap-2">
        <el-button @click="keyword = ''; filterTypeId = null; filterArea = ''">清空条件</el-button>
        <el-button type="primary" @click="$router.push('/shop')">浏览全部商家</el-button>
      </div>
    </div>

    <!-- Initial State -->
    <div v-else-if="!hasSearched" class="card p-12 text-center">
      <el-icon class="text-6xl text-primary-300 mb-4"><Search /></el-icon>
      <h2 class="text-xl font-semibold text-gray-700 mb-2">开始搜索</h2>
      <p class="text-gray-500 mb-6">输入关键词查找你想要的商家</p>
      <div class="flex flex-wrap justify-center gap-2">
        <span class="text-sm text-gray-400">大家都在搜：</span>
        <button
          v-for="tag in hotTags"
          :key="tag"
          class="px-3 py-1 bg-gray-100 hover:bg-primary-50 hover:text-primary-500 rounded-full text-sm text-gray-600 transition-colors"
          @click="quickSearch(tag)"
        >
          {{ tag }}
        </button>
      </div>
    </div>

    <!-- Results -->
    <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
      <ShopCard v-for="shop in results" :key="shop.id" :shop="shop" />
    </div>

    <!-- Pagination -->
    <div v-if="hasSearched && results.length > 0" class="flex justify-center mt-8">
      <el-pagination
        v-model:current-page="current"
        :page-size="pageSize"
        :total="total"
        layout="prev, pager, next"
        @current-change="handleSearch"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import ShopCard from '@/components/shop/ShopCard.vue'
import { shopSearchApi } from '@/api/shopSearch'
import { useShopStore } from '@/stores/shop'
import type { Shop } from '@/types'

const route = useRoute()
const shopStore = useShopStore()

const keyword = ref('')
const filterTypeId = ref<number | null>(null)
const filterArea = ref('')
const current = ref(1)
const pageSize = 20
const total = ref(0)
const loading = ref(false)
const hasSearched = ref(false)
const results = ref<Shop[]>([])

const hotTags = ['火锅', '奶茶', '日料', '烧烤', '咖啡', '蛋糕', '川菜', '粤菜', '西餐', '下午茶']

onMounted(() => {
  const q = route.query.keyword as string
  if (q) {
    keyword.value = q
    handleSearch()
  }
})

function getTypeName(id: number) {
  const type = shopStore.shopTypes.find(t => t.id === id)
  return type?.name || ''
}

function quickSearch(tag: string) {
  keyword.value = tag
  handleSearch()
}

async function handleSearch() {
  if (!keyword.value.trim()) return
  loading.value = true
  hasSearched.value = true
  try {
    const { list, total } = await shopSearchApi.search(
      keyword.value,
      filterTypeId.value || undefined,
      filterArea.value || undefined,
      current.value,
      pageSize
    )
    results.value = list
    total.value = total || list.length
  } finally {
    loading.value = false
  }
}
</script>
