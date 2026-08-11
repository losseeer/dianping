<template>
  <div class="min-h-screen bg-gray-50 flex items-center justify-center py-12 px-4">
    <div class="card p-8 w-full max-w-md">
      <div class="text-center mb-8">
        <div class="w-16 h-16 bg-primary-500 rounded-2xl flex items-center justify-center mx-auto mb-4">
          <span class="text-2xl font-bold text-white">点</span>
        </div>
        <h1 class="text-2xl font-bold mb-2">{{ loginMode === 'code' ? '手机号登录' : '密码登录' }}</h1>
        <p class="text-gray-500 text-sm">欢迎使用点评</p>
      </div>

      <el-form ref="formRef" :model="form" :rules="rules" @submit.prevent="handleLogin">
        <el-form-item prop="phone">
          <el-input
            v-model="form.phone"
            placeholder="请输入手机号"
            size="large"
            maxlength="11"
          >
            <template #prefix>
              <el-icon><Phone /></el-icon>
            </template>
          </el-input>
        </el-form-item>

        <el-form-item v-if="loginMode === 'code'" prop="code">
          <div class="flex gap-2">
            <el-input
              v-model="form.code"
              placeholder="请输入验证码"
              size="large"
              maxlength="6"
              class="flex-1"
            >
              <template #prefix>
                <el-icon><Key /></el-icon>
              </template>
            </el-input>
            <el-button
              size="large"
              type="primary"
              :disabled="codeLoading || countdown > 0"
              @click="handleSendCode"
            >
              <span v-if="countdown > 0">{{ countdown }}s</span>
              <span v-else>{{ codeLoading ? '发送中' : '获取验证码' }}</span>
            </el-button>
          </div>
        </el-form-item>

        <el-form-item v-else prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="请输入密码"
            size="large"
            show-password
          >
            <template #prefix>
              <el-icon><Lock /></el-icon>
            </template>
          </el-input>
        </el-form-item>

        <el-button
          type="primary"
          size="large"
          class="w-full"
          :loading="loading"
          @click="handleLogin"
        >
          {{ loading ? '登录中...' : '登 录' }}
        </el-button>
      </el-form>

      <div class="flex justify-between items-center mt-6 text-sm">
        <button class="text-primary-500 hover:underline" @click="toggleMode">
          {{ loginMode === 'code' ? '密码登录' : '验证码登录' }}
        </button>
        <a href="#" class="text-gray-500 hover:text-primary-500">忘记密码？</a>
      </div>

      <div class="mt-8 pt-6 border-t border-gray-100">
        <p class="text-center text-xs text-gray-400 mb-4">其他登录方式</p>
        <div class="flex justify-center gap-6">
          <button class="w-10 h-10 rounded-full bg-green-50 flex items-center justify-center hover:bg-green-100 transition-colors">
            <span class="text-green-600 font-bold text-sm">微</span>
          </button>
          <button class="w-10 h-10 rounded-full bg-blue-50 flex items-center justify-center hover:bg-blue-100 transition-colors">
            <span class="text-blue-600 font-bold text-sm">Q</span>
          </button>
          <button class="w-10 h-10 rounded-full bg-red-50 flex items-center justify-center hover:bg-red-100 transition-colors">
            <span class="text-red-600 font-bold text-sm">微</span>
          </button>
        </div>
      </div>

      <p class="text-center text-xs text-gray-400 mt-6">
        登录即代表同意 <a href="#" class="text-primary-500">用户协议</a> 和 <a href="#" class="text-primary-500">隐私政策</a>
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { ElForm, ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const loginMode = ref<'code' | 'password'>('code')
const formRef = ref<FormInstance>()
const loading = ref(false)
const codeLoading = ref(false)
const countdown = ref(0)

let countdownTimer: number | null = null

const form = reactive({
  phone: '',
  code: '',
  password: ''
})

const rules: FormRules = {
  phone: [
    { required: true, message: '请输入手机号', trigger: 'blur' },
    { pattern: /^1[3-9]\d{9}$/, message: '手机号格式不正确', trigger: 'blur' }
  ],
  code: [
    { required: true, message: '请输入验证码', trigger: 'blur' },
    { len: 6, message: '验证码为6位数字', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少6位', trigger: 'blur' }
  ]
}

function toggleMode() {
  loginMode.value = loginMode.value === 'code' ? 'password' : 'code'
  form.code = ''
  form.password = ''
}

async function handleSendCode() {
  if (!/^1[3-9]\d{9}$/.test(form.phone)) {
    ElMessage.error('请输入正确的手机号')
    return
  }
  try {
    codeLoading.value = true
    await userStore.sendCode(form.phone)
    countdown.value = 60
    countdownTimer = window.setInterval(() => {
      countdown.value--
      if (countdown.value <= 0 && countdownTimer) {
        clearInterval(countdownTimer)
      }
    }, 1000)
  } finally {
    codeLoading.value = false
  }
}

async function handleLogin() {
  await formRef.value?.validate()
  loading.value = true
  try {
    if (loginMode.value === 'code') {
      await userStore.login(form.phone, form.code || '')
    } else {
      await userStore.loginWithPassword(form.phone, form.password || '')
    }
    const redirect = route.query.redirect as string || '/'
    router.push(redirect)
  } finally {
    loading.value = false
  }
}

onUnmounted(() => {
  if (countdownTimer) clearInterval(countdownTimer)
})
</script>
