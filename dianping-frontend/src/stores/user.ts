import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { UserDTO } from '@/types'
import { userApi } from '@/api/user'
import { ElMessage } from 'element-plus'

export const useUserStore = defineStore('user', () => {
  const token = ref<string | null>(localStorage.getItem('token'))
  const savedUserInfo = localStorage.getItem('userInfo')
  const userInfo = ref<UserDTO | null>(savedUserInfo ? JSON.parse(savedUserInfo) : null)

  const isLoggedIn = computed(() => !!token.value)

  async function sendCode(phone: string) {
    await userApi.sendCode(phone)
    ElMessage.success('验证码已发送')
  }

  async function login(phone: string, code: string) {
    const res = await userApi.login({ phone, code })
    if (res.data) {
      token.value = res.data as unknown as string
      localStorage.setItem('token', res.data as unknown as string)
      await fetchUserInfo()
    }
    ElMessage.success('登录成功')
  }

  async function loginWithPassword(phone: string, password: string) {
    const res = await userApi.login({ phone, password })
    if (res.data) {
      token.value = res.data as unknown as string
      localStorage.setItem('token', res.data as unknown as string)
      await fetchUserInfo()
    }
    ElMessage.success('登录成功')
  }

  async function fetchUserInfo() {
    try {
      const res = await userApi.me()
      userInfo.value = res.data as UserDTO
      localStorage.setItem('userInfo', JSON.stringify(res.data))
    } catch (e) {
      console.error('获取用户信息失败', e)
    }
  }

  async function logout() {
    try {
      await userApi.logout()
    } finally {
      token.value = null
      userInfo.value = null
      localStorage.removeItem('token')
      localStorage.removeItem('userInfo')
    }
    ElMessage.success('已退出登录')
  }

  async function sign() {
    const res = await userApi.sign()
    return res
  }

  async function getSignCount() {
    const res = await userApi.signCount()
    return res.data as number
  }

  return {
    token,
    userInfo,
    isLoggedIn,
    sendCode,
    login,
    loginWithPassword,
    fetchUserInfo,
    logout,
    sign,
    getSignCount
  }
})
