import { request } from '@/utils/request'
import type { VoucherOrder } from '@/types'

export interface OrderDetail {
  order: VoucherOrder
  voucher?: any
  /** 是否仍处于异步落库窗口期（Redis pending 未写入 DB） */
  pending?: boolean
}

export const orderApi = {
  queryById(id: number) {
    return request.get<OrderDetail>(`/order/${id}`)
  },

  queryMyOrders(status?: number) {
    const params: any = {}
    if (status !== undefined) params.status = status
    return request.get<VoucherOrder[]>('/order/list', { params })
  },

  cancelOrder(id: number) {
    return request.post(`/order/cancel/${id}`)
  }
}
