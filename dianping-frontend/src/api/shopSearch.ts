import { request } from '@/utils/request'
import type { Shop } from '@/types'

interface ShopSearchResponse {
  list: Shop[]
  total: number
  took: number
  current: number
  size: number
}

const _EM_RE = /<\/?em>/g

function stripEmTags(shops: Shop[]): Shop[] {
  // ES highlight 会在 name/area/address 中插入 <em>...</em> 高亮标签
  // Search 结果列表不需要高亮渲染，直接剥离，避免原始 tag 显示成文本
  return shops.map(s => ({
    ...s,
    name: s.name ? s.name.replace(_EM_RE, '') : s.name,
    area: s.area ? s.area.replace(_EM_RE, '') : s.area,
    address: s.address ? s.address.replace(_EM_RE, '') : s.address,
  }))
}

export const shopSearchApi = {
  async search(keyword: string, typeId?: number, area?: string, current = 1, size = 10) {
    const params: any = { keyword, current, size }
    if (typeId !== undefined) params.typeId = typeId
    if (area !== undefined) params.area = area
    const res = await request.get<ShopSearchResponse>('/shop/search', { params })
    // request 拦截器返回 Result<T> = { success, data, errorMsg }
    // /shop/search 的 data 是 ShopSearchResponse = { list, total, took, current, size }
    const data = (res.data as ShopSearchResponse) || {}
    return {
      list: stripEmTags((data.list || []) as Shop[]),
      total: data.total ?? 0,
      took: data.took ?? 0,
    }
  },

  syncShopToEs() {
    return request.post('/shop/search/sync')
  },

  importShop(shop: Shop) {
    return request.post('/shop/search/import', shop)
  }
}
