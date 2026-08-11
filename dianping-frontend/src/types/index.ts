export interface Result<T = any> {
  success: boolean
  errorMsg: string | null
  data: T
  total: number | null
}

export interface User {
  id: number
  phone: string
  nickName: string
  icon: string
}

export interface UserDTO {
  id: number
  nickName: string
  icon: string
}

export interface UserInfo {
  userId: number
  city: string
  introduce: string
  fans: number
  followee: number
  gender: number
  birthday: string
  credits: number
  level: number
}

export interface LoginFormDTO {
  phone: string
  code?: string
  password?: string
}

export interface Shop {
  id: number
  name: string
  typeId: number
  images: string
  area: string
  address: string
  x: number
  y: number
  avgPrice: number
  sold: number
  comments: number
  score: number
  openHours: string
  createTime: string
  updateTime: string
  distance?: number
}

export interface ShopType {
  id: number
  name: string
  icon: string
  sort: number
}

export interface Voucher {
  id: number
  shopId: number
  title: string
  subTitle: string
  rules: string
  payValue: number
  actualValue: number
  type: number
  status: number
  stock?: number
  beginTime?: string
  endTime?: string
  createTime: string
  updateTime: string
}

export interface SeckillVoucher {
  voucherId: number
  stock: number
  beginTime: string
  endTime: string
}

export interface Blog {
  id: number
  shopId: number
  userId: number
  icon?: string
  name?: string
  isLike?: boolean
  title: string
  images: string
  content: string
  liked: number
  comments: number
  createTime: string
  updateTime: string
}

export interface BlogComments {
  id: number
  blogId: number
  userId: number
  content: string
  createTime: string
}

export interface Follow {
  id: number
  userId: number
  followUserId: number
  createTime: string
}

export interface VoucherOrder {
  id: number | string
  userId: number | string
  voucherId: number | string
  payType?: number
  status?: number
  createTime?: string
  payTime?: string
  useTime?: string
  refundTime?: string
  /** 是否仍处于异步落库窗口期（Redis pending 未写入 DB），后端 queryById 透传 */
  pending?: boolean
  /** 联表优惠券信息（列表接口按需拼装；金额取 voucher.payValue/100 展示） */
  voucher?: {
    id: number | string
    title?: string
    subTitle?: string
    payValue?: number
    actualValue?: number
    shopId?: number | string
    type?: number
  }
}

export interface PayLog {
  orderNo: number
  userId: number
  amount: number
  paymentType: number
  tradeNo: string
  status: number
  payTime?: string
  refundTime?: string
  createTime?: string
}

export interface PaymentDTO {
  orderId: number
  payType: number
}

export interface ScrollResult {
  list: any[]
  minTime: number
  offset: number
}

export enum PayType {
  BALANCE = 1,
  ALIPAY = 2,
  WECHAT = 3
}

export enum OrderStatus {
  UNPAID = 1,
  PAID = 2,
  USED = 3,
  REFUNDED = 4,
  CANCELLED = 5
}

// ============================================================
// Agent1: 评价摘要
// ============================================================

export interface ReviewSummary {
  shopId: number
  shopName: string
  totalReviews: number
  positiveRate: number
  avgLikedPerReview: number
  topPros: string[]
  topCons: string[]
  keyPhrases: string[]
  recommendation: string
  scoreBreakdown: {
    overall: number
    interpretation: string
  }
}

// ============================================================
// Agent2: 商铺推荐对话
// ============================================================

export interface AgentChatRequest {
  userId: number
  message: string
  x?: number
  y?: number
  threadId?: string
}

export interface AgentResumeRequest {
  userId: number
  threadId: string
  response: string
  x?: number
  y?: number
}

export interface RecommendedShop {
  id: number
  name: string
  score?: number
  avgPrice?: number
  distance?: number
  matchReason?: string
  [key: string]: any
}

export interface AgentChatResponse {
  type: 'recommendation' | 'interrupt' | 'error'
  // recommendation
  shops?: RecommendedShop[]
  finalRecommendation?: string
  memoryUpdated?: boolean
  newPreferences?: string[]
  reflectionScore?: number
  reflectionNotes?: string
  trajectoryId?: string
  // interrupt
  question?: string
  options?: string[]
  // shared
  threadId?: string
  error?: string
}
