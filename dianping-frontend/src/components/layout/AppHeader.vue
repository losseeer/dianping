<template>
  <header class="bg-white shadow-sm sticky top-0 z-50">
    <div class="container">
      <div class="flex items-center justify-between h-16">
        <div class="flex items-center gap-8">
          <router-link to="/" class="flex items-center gap-2">
            <span class="text-2xl font-bold text-primary-600">点评</span>
            <span class="text-sm text-gray-500">发现美好生活</span>
          </router-link>
          <nav class="hidden md:flex items-center gap-6">
            <router-link to="/" class="text-gray-700 hover:text-primary-500 transition-colors">首页</router-link>
            <router-link to="/shop" class="text-gray-700 hover:text-primary-500 transition-colors">找商家</router-link>
            <router-link to="/seckill" class="text-gray-700 hover:text-primary-500 transition-colors">限时秒杀</router-link>
            <router-link to="/blog" class="text-gray-700 hover:text-primary-500 transition-colors">探店笔记</router-link>
            <router-link to="/agent" class="text-gray-700 hover:text-primary-500 transition-colors flex items-center gap-1">
              <el-icon><Service /></el-icon>AI助手
            </router-link>
          </nav>
        </div>

        <div class="flex items-center gap-4">
          <el-input
            v-model="searchKeyword"
            placeholder="搜索商家、美食..."
            class="w-64"
            @keyup.enter="handleSearch"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>

          <template v-if="userStore.isLoggedIn">
            <router-link
              to="/blog/create"
              class="hidden sm:inline-flex items-center gap-1 btn-primary"
            >
              <el-icon><Edit /></el-icon>
              <span>写点评</span>
            </router-link>

            <el-dropdown @command="handleCommand">
              <div class="flex items-center gap-2 cursor-pointer hover:bg-gray-50 rounded-lg px-3 py-2">
                <el-avatar :size="32" :src="userStore.userInfo?.icon || placeholderIcon">
                  {{ userStore.userInfo?.nickName?.[0] || 'U' }}
                </el-avatar>
                <span class="hidden sm:inline text-sm text-gray-700">{{ userStore.userInfo?.nickName || '用户' }}</span>
              </div>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="profile">
                    <el-icon><User /></el-icon>个人中心
                  </el-dropdown-item>
                  <el-dropdown-item command="orders">
                    <el-icon><Tickets /></el-icon>我的订单
                  </el-dropdown-item>
                  <el-dropdown-item command="my-blog">
                    <el-icon><Document /></el-icon>我的笔记
                  </el-dropdown-item>
                  <el-dropdown-item divided command="logout">
                    <el-icon><SwitchButton /></el-icon>退出登录
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>

          <template v-else>
            <router-link to="/login" class="text-gray-700 hover:text-primary-500 transition-colors">登录</router-link>
            <router-link to="/login" class="btn-primary">注册</router-link>
          </template>
        </div>
      </div>
    </div>
  </header>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { ElMessage, ElMessageBox } from 'element-plus'

const router = useRouter()
const userStore = useUserStore()
const searchKeyword = ref('')

const placeholderIcon = 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCA0MCA0MCI+PGNpcmNsZSBjeD0iMjAiIGN5PSIyMCIgcj0iMjAiIGZpbGw9IiNmOTczMTYiLz48dGV4dCB4PSIyMCIgeT0iMjYiIGZvbnQtc2l6ZT0iMTYiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGZpbGw9IndoaXRlIiBmb250LWZhbWlseT0ic2Fucy1zZXJpZiIgZm9udC13ZWlnaHQ9ImJvbGQiPlU8L3RleHQ+PC9zdmc+'

function handleSearch() {
  if (searchKeyword.value.trim()) {
    router.push({ path: '/search', query: { keyword: searchKeyword.value } })
  }
}

async function handleCommand(command: string) {
  switch (command) {
    case 'profile':
      router.push('/profile')
      break
    case 'orders':
      router.push('/orders')
      break
    case 'my-blog':
      router.push('/blog')
      break
    case 'logout':
      try {
        await ElMessageBox.confirm('确定要退出登录吗？', '提示', {
          type: 'warning'
        })
        await userStore.logout()
        router.push('/')
      } catch (e) {
        // cancel
      }
      break
  }
}
</script>
