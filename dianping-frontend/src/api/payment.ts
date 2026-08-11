import { request } from '@/utils/request'
import type { PaymentDTO } from '@/types'

export const paymentApi = {
  pay(data: PaymentDTO) {
    return request.post<string>('/pay', data)
  },

  payNotify(tradeNo: string, orderId: number) {
    return request.post('/pay/notify', null, { params: { tradeNo, orderId } })
  },

  refund(orderId: number) {
    return request.post(`/pay/refund/${orderId}`)
  },

  refundCallback(tradeNo: string, orderId: number) {
    return request.post('/pay/refund/callback', null, { params: { tradeNo, orderId } })
  }
}
