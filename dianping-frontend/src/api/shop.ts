import { request } from '@/utils/request'
import type { Shop } from '@/types'

export const shopApi = {
  queryById(id: number) {
    return request.get<Shop>(`/shop/${id}`)
  },

  saveShop(data: Partial<Shop>) {
    return request.post<number>('/shop', data)
  },

  updateShop(data: Partial<Shop>) {
    return request.put('/shop', data)
  },

  queryByType(typeId: number, current = 1, x?: number, y?: number) {
    const params: any = { typeId, current }
    if (x !== undefined) params.x = x
    if (y !== undefined) params.y = y
    return request.get<Shop[]>('/shop/of/type', { params })
  },

  queryByName(name?: string, current = 1) {
    return request.get<Shop[]>('/shop/of/name', { params: { name, current } })
  }
}
