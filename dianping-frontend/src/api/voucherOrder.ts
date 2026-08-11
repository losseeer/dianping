import { request } from '@/utils/request'

export const voucherOrderApi = {
  seckillVoucher(voucherId: number) {
    return request.post<number>(`/voucher-order/seckill/${voucherId}`)
  }
}
