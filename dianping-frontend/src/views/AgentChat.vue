<template>
  <div class="min-h-screen bg-gray-50 flex flex-col">
    <!-- Header -->
    <div class="bg-gradient-to-r from-indigo-500 to-purple-600 text-white py-6">
      <div class="container">
        <div class="flex items-center gap-3">
          <div class="w-12 h-12 rounded-xl bg-white/20 backdrop-blur flex items-center justify-center">
            <el-icon class="text-2xl"><Service /></el-icon>
          </div>
          <div>
            <h1 class="text-2xl font-bold">AI 美食助手</h1>
            <p class="text-sm text-indigo-100">告诉我你想吃什么，我帮你找到最合适的店</p>
          </div>
        </div>
      </div>
    </div>

    <!-- Chat Area -->
    <div class="flex-1 container max-w-3xl py-6">
      <div ref="chatContainer" class="space-y-4 mb-4">
        <!-- Welcome Message -->
        <div v-if="messages.length === 0" class="text-center py-16">
          <div class="w-20 h-20 rounded-full bg-indigo-100 flex items-center justify-center mx-auto mb-4">
            <el-icon class="text-4xl text-indigo-400"><Service /></el-icon>
          </div>
          <h2 class="text-xl font-semibold text-gray-700 mb-2">你好，我是 AI 美食助手</h2>
          <p class="text-gray-500 mb-6">试试这样问我：</p>
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 max-w-lg mx-auto">
            <button
              v-for="s in suggestions"
              :key="s"
              class="card p-3 text-left text-sm text-gray-600 hover:border-indigo-300 hover:bg-indigo-50 transition-colors"
              @click="sendMessage(s)"
            >
              <el-icon class="text-indigo-400 mr-1"><ChatDotRound /></el-icon>
              {{ s }}
            </button>
          </div>
        </div>

        <!-- Message Bubbles -->
        <template v-for="(msg, idx) in messages" :key="idx">
          <!-- User Message -->
          <div v-if="msg.role === 'user'" class="flex justify-end">
            <div class="bg-indigo-500 text-white rounded-2xl rounded-tr-md px-4 py-2.5 max-w-[80%]">
              <p class="text-sm">{{ msg.content }}</p>
            </div>
          </div>

          <!-- Assistant Message -->
          <div v-else class="flex justify-start">
            <div class="bg-white rounded-2xl rounded-tl-md px-4 py-3 max-w-[85%] shadow-sm border border-gray-100">
              <!-- Text Content -->
              <p v-if="msg.content" class="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">{{ msg.content }}</p>

              <!-- HITL Interrupt Options -->
              <div v-if="msg.options && msg.options.length > 0" class="mt-3 space-y-2">
                <button
                  v-for="opt in msg.options"
                  :key="opt"
                  class="block w-full text-left px-3 py-2 rounded-lg border border-indigo-200 hover:bg-indigo-50 text-sm text-gray-700 transition-colors"
                  @click="sendMessage(opt)"
                >
                  {{ opt }}
                </button>
              </div>

              <!-- Recommended Shops -->
              <div v-if="msg.shops && msg.shops.length > 0" class="mt-3 space-y-3">
                <div
                  v-for="shop in msg.shops"
                  :key="shop.id"
                  class="border border-gray-100 rounded-xl p-3 hover:border-indigo-200 hover:bg-indigo-50/30 transition-colors cursor-pointer"
                  @click="goToShop(shop.id)"
                >
                  <div class="flex items-start justify-between gap-2">
                    <div class="flex-1">
                      <p class="font-semibold text-gray-800">{{ shop.name }}</p>
                      <div class="flex items-center gap-3 mt-1 text-xs text-gray-500">
                        <span v-if="shop.avgPrice" class="flex items-center gap-0.5">
                          <el-icon><Coin /></el-icon>¥{{ shop.avgPrice }}/人
                        </span>
                        <span v-if="shop.score" class="flex items-center gap-0.5">
                          <el-icon class="text-yellow-500"><Star /></el-icon>{{ (shop.score / 10).toFixed(1) }}
                        </span>
                        <span v-if="shop.distance" class="flex items-center gap-0.5">
                          <el-icon><Location /></el-icon>{{ formatDistance(shop.distance) }}
                        </span>
                      </div>
                      <p v-if="shop.matchReason" class="text-xs text-indigo-500 mt-2 leading-relaxed">
                        <el-icon class="mr-0.5"><CircleCheckFilled /></el-icon>{{ shop.matchReason }}
                      </p>
                    </div>
                    <el-icon class="text-gray-300 mt-1"><ArrowRight /></el-icon>
                  </div>
                </div>
              </div>

              <!-- New Preferences Badge -->
              <div v-if="msg.newPreferences && msg.newPreferences.length > 0" class="mt-3 flex flex-wrap gap-1.5">
                <span class="text-xs text-gray-400">已记住你的偏好：</span>
                <el-tag v-for="pref in msg.newPreferences" :key="pref" type="primary" size="small" effect="plain">
                  {{ pref }}
                </el-tag>
              </div>

              <!-- Reflection Score -->
              <div v-if="msg.reflectionScore" class="mt-2 flex items-center gap-2 text-xs text-gray-400">
                <el-icon><DataAnalysis /></el-icon>
                <span>推荐置信度 {{ msg.reflectionScore }}/10</span>
                <span v-if="msg.reflectionNotes" class="truncate">· {{ msg.reflectionNotes }}</span>
              </div>
            </div>
          </div>
        </template>

        <!-- Loading Indicator -->
        <div v-if="chatLoading" class="flex justify-start">
          <div class="bg-white rounded-2xl rounded-tl-md px-4 py-3 shadow-sm border border-gray-100">
            <div class="flex items-center gap-2">
              <span class="flex gap-1">
                <span class="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style="animation-delay: 0s"></span>
                <span class="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style="animation-delay: 0.15s"></span>
                <span class="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style="animation-delay: 0.3s"></span>
              </span>
              <span class="text-xs text-gray-400">AI 正在思考...</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Input Area -->
    <div class="sticky bottom-0 bg-white border-t">
      <div class="container max-w-3xl py-4">
        <div class="flex gap-3">
          <el-input
            v-model="inputText"
            placeholder="输入你的需求，如：我在西湖区想吃日料，人均150以内"
            size="large"
            :disabled="chatLoading"
            @keyup.enter="handleSend"
          />
          <el-button
            type="primary"
            size="large"
            :loading="chatLoading"
            :icon="Promotion"
            @click="handleSend"
          >
            发送
          </el-button>
        </div>
        <p v-if="!userStore.isLoggedIn" class="text-xs text-gray-400 mt-2 text-center">
          <router-link to="/login" class="text-indigo-500 hover:underline">登录</router-link> 后可享受个性化推荐
        </p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { agent2Api } from '@/api/agent'
import { Promotion } from '@element-plus/icons-vue'
import type { AgentChatResponse, RecommendedShop } from '@/types'

const router = useRouter()
const userStore = useUserStore()

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  shops?: RecommendedShop[]
  options?: string[]
  newPreferences?: string[]
  reflectionScore?: number
  reflectionNotes?: string
}

const messages = ref<ChatMessage[]>([])
const inputText = ref('')
const chatLoading = ref(false)
const threadId = ref<string | undefined>(undefined)
const waitingForResume = ref(false) // HITL 中断状态：true 时下次发消息走 resume
const chatContainer = ref<HTMLElement | null>(null)

const suggestions = [
  '推荐几家杭州好吃的日料店',
  '我在西湖区，想吃人均100以内的火锅',
  '帮我找适合情侣约会的西餐厅',
  '有没有好吃又不贵的烧烤推荐？'
]

function scrollToBottom() {
  nextTick(() => {
    if (chatContainer.value) {
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight
    }
  })
}

async function sendMessage(text: string) {
  if (!text.trim() || chatLoading.value) return

  const userId = userStore.userInfo?.id || 0
  if (!userId || userId <= 0) {
    // 登录态校验失败：直接跳登录页并带 redirect
    router.push({ path: '/login', query: { redirect: '/agent' } })
    return
  }
  const isResume = waitingForResume.value && threadId.value

  // Add user message
  messages.value.push({ role: 'user', content: text })
  inputText.value = ''
  chatLoading.value = true
  scrollToBottom()

  try {
    let res
    if (isResume) {
      // HITL 恢复：走 resume 接口
      res = await agent2Api.resume({
        userId,
        threadId: threadId.value!,
        response: text
      })
    } else {
      // 正常对话：走 chat 接口
      res = await agent2Api.chat({
        userId,
        message: text,
        threadId: threadId.value
      })
    }

    const data = res.data as AgentChatResponse
    if (data.threadId) threadId.value = data.threadId

    handleAgentResponse(data)
  } catch (e: any) {
    const status = e?.response?.status
    const detail = e?.response?.data?.error || e?.message || ''
    let msg = ''
    if (!status) {
      msg = '无法连接到 AI 服务，请确认 Agent2 服务已启动（端口 8002）'
    } else if (status >= 500) {
      msg = `AI 服务内部错误（${status}）${detail ? '：' + detail : ''}`
    } else {
      msg = `请求失败（${status}）：${detail || '未知错误'}`
    }
    messages.value.push({ role: 'assistant', content: msg })
  } finally {
    chatLoading.value = false
    scrollToBottom()
  }
}

function handleAgentResponse(data: AgentChatResponse) {
  if (data.type === 'interrupt') {
    // HITL 中断：展示问题 + 选项，标记等待 resume
    waitingForResume.value = true
    messages.value.push({
      role: 'assistant',
      content: data.question || '需要更多信息',
      options: data.options
    })
  } else if (data.type === 'recommendation') {
    // 推荐结果：清除中断状态
    waitingForResume.value = false
    messages.value.push({
      role: 'assistant',
      content: data.finalRecommendation || '',
      shops: data.shops,
      newPreferences: data.newPreferences,
      reflectionScore: data.reflectionScore,
      reflectionNotes: data.reflectionNotes
    })
  } else if (data.type === 'error') {
    waitingForResume.value = false
    const errMsg = data.error || '发生未知错误'
    messages.value.push({
      role: 'assistant',
      content: errMsg.includes('Thread not found') || errMsg.includes('expired')
        ? '对话已过期，请重新描述你的需求'
        : `处理请求时出错：${errMsg}`
    })
  }
  scrollToBottom()
}

function handleSend() {
  if (!inputText.value.trim()) return
  sendMessage(inputText.value)
}

function goToShop(id: number) {
  router.push(`/shop/${id}`)
}

function formatDistance(meters: number): string {
  if (meters < 1000) return `${meters}m`
  return `${(meters / 1000).toFixed(1)}km`
}
</script>
