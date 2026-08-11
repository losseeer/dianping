import axios from 'axios'
import type {
  ReviewSummary,
  AgentChatRequest,
  AgentResumeRequest,
  AgentChatResponse
} from '@/types'

// Agent 服务不走 Java 后端的 Result 包装，使用独立 axios 实例
const agentHttp = axios.create({
  timeout: 60000 // Agent 涉及 LLM 调用，超时设长一些
})

// ============================================================
// Agent1: 评价摘要（端口 8001）
// ============================================================

export const agent1Api = {
  /** 获取商铺评价摘要 */
  getReviewSummary(shopId: number) {
    return agentHttp.post<ReviewSummary>('/agent1/summary', { shopId })
  }
}

// ============================================================
// Agent2: 商铺推荐对话（端口 8002）
// ============================================================

export const agent2Api = {
  /** 发送对话消息 */
  chat(data: AgentChatRequest) {
    return agentHttp.post<AgentChatResponse>('/agent2/chat', data)
  },

  /** 恢复中断的对话（HITL） */
  resume(data: AgentResumeRequest) {
    return agentHttp.post<AgentChatResponse>('/agent2/chat/resume', data)
  }
}
