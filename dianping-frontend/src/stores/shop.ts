import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { ShopType } from '@/types'
import { shopTypeApi } from '@/api/shopType'

export const useShopStore = defineStore('shop', () => {
  const shopTypes = ref<ShopType[]>([])
  const loaded = ref(false)

  async function loadShopTypes() {
    if (loaded.value) return
    try {
      const res = await shopTypeApi.queryTypeList()
      shopTypes.value = (res.data as ShopType[]) || []
      loaded.value = true
    } catch (e) {
      console.error('加载商铺类型失败', e)
    }
  }

  return {
    shopTypes,
    loaded,
    loadShopTypes
  }
})
