import { request } from '@/utils/request'
import type { ShopType } from '@/types'

export const shopTypeApi = {
  queryTypeList() {
    return request.get<ShopType[]>('/shop-type/list')
  }
}
