import { request } from '@/utils/request'
import type { Voucher } from '@/types'

export const voucherApi = {
  addVoucher(data: Partial<Voucher>) {
    return request.post<number>('/voucher', data)
  },

  addSeckillVoucher(data: Partial<Voucher>) {
    return request.post<number>('/voucher/seckill', data)
  },

  queryVoucherOfShop(shopId: number) {
    return request.get<Voucher[]>(`/voucher/list/${shopId}`)
  },

  /**
   * 秒杀专场：查询全部有效秒杀券（跨店铺）
   * 后端已 INNER JOIN tb_seckill_voucher，返回 stock / beginTime / endTime
   */
  queryAllSeckillVoucher() {
    return request.get<Voucher[]>('/voucher/seckill/list')
  }
}
