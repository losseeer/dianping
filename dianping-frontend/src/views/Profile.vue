<template>
  <div class="container py-8">
    <div class="grid grid-cols-1 lg:grid-cols-4 gap-6">
      <!-- Sidebar -->
      <div class="lg:col-span-1">
        <div class="card p-6 mb-6">
          <div class="flex flex-col items-center text-center mb-6">
            <el-avatar :size="80" :src="userStore.userInfo?.icon" class="mb-3">
              {{ userStore.userInfo?.nickName?.[0] || 'U' }}
            </el-avatar>
            <h2 class="text-xl font-bold mb-1">{{ userStore.userInfo?.nickName || '用户' }}</h2>
            <p class="text-sm text-gray-500">ID: {{ userStore.userInfo?.id || '-' }}</p>
          </div>

          <div class="grid grid-cols-3 gap-2 mb-6 text-center">
            <div class="p-2 bg-gray-50 rounded-lg">
              <div class="text-lg font-bold text-primary-500">{{ stats.follows }}</div>
              <div class="text-xs text-gray-500">关注</div>
            </div>
            <div class="p-2 bg-gray-50 rounded-lg">
              <div class="text-lg font-bold text-primary-500">{{ stats.fans }}</div>
              <div class="text-xs text-gray-500">粉丝</div>
            </div>
            <div class="p-2 bg-gray-50 rounded-lg">
              <div class="text-lg font-bold text-primary-500">{{ stats.blogs }}</div>
              <div class="text-xs text-gray-500">笔记</div>
            </div>
          </div>

          <div class="space-y-1">
            <button
              v-for="item in menuItems"
              :key="item.key"
              class="w-full flex items-center gap-3 px-4 py-2.5 rounded-lg text-left transition-colors"
              :class="activeMenu === item.key ? 'bg-primary-50 text-primary-600' : 'hover:bg-gray-50 text-gray-700'"
              @click="activeMenu = item.key"
            >
              <el-icon><component :is="item.icon" /></el-icon>
              <span class="text-sm">{{ item.label }}</span>
            </button>
          </div>
        </div>
      </div>

      <!-- Main Content -->
      <div class="lg:col-span-3">
        <!-- Profile -->
        <div v-if="activeMenu === 'profile'" class="card p-6">
          <h3 class="text-lg font-semibold mb-6 flex items-center gap-2">
            <el-icon class="text-primary-500"><User /></el-icon>
            个人资料
          </h3>
          <el-form label-position="top" class="max-w-md">
            <el-form-item label="昵称">
              <el-input :value="userStore.userInfo?.nickName" placeholder="设置昵称" />
            </el-form-item>
            <el-form-item label="个人简介">
              <el-input type="textarea" :rows="3" placeholder="介绍一下自己..." />
            </el-form-item>
            <el-form-item label="性别">
              <el-radio-group>
                <el-radio :value="1">男</el-radio>
                <el-radio :value="2">女</el-radio>
                <el-radio :value="0">保密</el-radio>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="生日">
              <el-date-picker type="date" placeholder="选择日期" style="width: 100%" />
            </el-form-item>
            <el-form-item label="所在城市">
              <el-input placeholder="选择城市" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary">保存修改</el-button>
            </el-form-item>
          </el-form>
        </div>

        <!-- Sign-in -->
        <div v-else-if="activeMenu === 'sign'" class="card p-6">
          <h3 class="text-lg font-semibold mb-6 flex items-center gap-2">
            <el-icon class="text-primary-500"><Calendar /></el-icon>
            每日签到
          </h3>

          <div class="bg-gradient-to-br from-primary-50 to-orange-50 rounded-xl p-6 mb-6">
            <div class="flex items-center justify-between">
              <div>
                <p class="text-sm text-gray-600 mb-1">本月连续签到</p>
                <p class="text-4xl font-bold text-primary-600">{{ signCount }} <span class="text-lg font-normal">天</span></p>
                <p class="text-xs text-gray-500 mt-2">累计签到 {{ signCount * 5 }} 积分</p>
              </div>
              <el-button
                type="primary"
                size="large"
                round
                :loading="signing"
                :disabled="signed"
                @click="handleSign"
              >
                {{ signed ? '今日已签到' : '立即签到' }}
              </el-button>
            </div>
          </div>

          <div class="grid grid-cols-7 gap-2">
            <div
              v-for="(day, idx) in weekDays"
              :key="idx"
              class="aspect-square rounded-lg flex flex-col items-center justify-center text-xs"
              :class="day.signed ? 'bg-primary-500 text-white' : 'bg-gray-50 text-gray-500'"
            >
              <div>{{ day.name }}</div>
              <div class="text-lg font-semibold mt-1">{{ day.signed ? '✓' : day.date }}</div>
            </div>
          </div>
        </div>

        <!-- Favorites -->
        <div v-else-if="activeMenu === 'favorites'" class="card p-6">
          <h3 class="text-lg font-semibold mb-6 flex items-center gap-2">
            <el-icon class="text-primary-500"><StarFilled /></el-icon>
            我的收藏
          </h3>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div v-for="i in 4" :key="i" class="flex gap-3 p-3 rounded-lg hover:bg-gray-50 cursor-pointer transition-colors">
              <div class="w-20 h-20 rounded-lg bg-gray-200"></div>
              <div class="flex-1">
                <h4 class="font-medium mb-1">示例商家名称 {{ i }}</h4>
                <div class="flex items-center gap-1 text-sm text-yellow-500 mb-1">
                  <el-icon><Star /></el-icon>
                  <span>4.{{ i + 5 }}</span>
                </div>
                <p class="text-sm text-gray-500">¥{{ 50 + i * 20 }}/人</p>
              </div>
            </div>
          </div>
        </div>

        <!-- Orders -->
        <div v-else-if="activeMenu === 'orders'" class="card p-6">
          <div class="flex items-center justify-between mb-6">
            <h3 class="text-lg font-semibold flex items-center gap-2">
              <el-icon class="text-primary-500"><Tickets /></el-icon>
              我的订单
            </h3>
            <router-link to="/orders" class="text-sm text-primary-500 hover:underline">查看全部</router-link>
          </div>
          <router-link to="/orders">
            <div class="grid grid-cols-4 gap-4 text-center">
              <div class="p-6 bg-gray-50 rounded-lg hover:bg-primary-50 transition-colors">
                <div class="text-3xl font-bold text-primary-500 mb-1">2</div>
                <div class="text-sm text-gray-600">待支付</div>
              </div>
              <div class="p-6 bg-gray-50 rounded-lg hover:bg-primary-50 transition-colors">
                <div class="text-3xl font-bold text-primary-500 mb-1">5</div>
                <div class="text-sm text-gray-600">待使用</div>
              </div>
              <div class="p-6 bg-gray-50 rounded-lg hover:bg-primary-50 transition-colors">
                <div class="text-3xl font-bold text-primary-500 mb-1">12</div>
                <div class="text-sm text-gray-600">已使用</div>
              </div>
              <div class="p-6 bg-gray-50 rounded-lg hover:bg-primary-50 transition-colors">
                <div class="text-3xl font-bold text-primary-500 mb-1">1</div>
                <div class="text-sm text-gray-600">退款/售后</div>
              </div>
            </div>
          </router-link>
        </div>

        <!-- Settings -->
        <div v-else-if="activeMenu === 'settings'" class="card p-6">
          <h3 class="text-lg font-semibold mb-6 flex items-center gap-2">
            <el-icon class="text-primary-500"><Setting /></el-icon>
            账号设置
          </h3>
          <div class="max-w-md space-y-4">
            <div class="flex items-center justify-between p-4 rounded-lg hover:bg-gray-50 cursor-pointer">
              <div>
                <div class="font-medium">修改手机号</div>
                <div class="text-sm text-gray-500">当前绑定：138****8888</div>
              </div>
              <el-icon class="text-gray-400"><ArrowRight /></el-icon>
            </div>
            <div class="flex items-center justify-between p-4 rounded-lg hover:bg-gray-50 cursor-pointer">
              <div>
                <div class="font-medium">修改密码</div>
                <div class="text-sm text-gray-500">上次修改：30天前</div>
              </div>
              <el-icon class="text-gray-400"><ArrowRight /></el-icon>
            </div>
            <div class="flex items-center justify-between p-4 rounded-lg hover:bg-gray-50 cursor-pointer">
              <div>
                <div class="font-medium">消息通知</div>
                <div class="text-sm text-gray-500">已开启推送通知</div>
              </div>
              <el-switch :model-value="true" />
            </div>
            <div class="flex items-center justify-between p-4 rounded-lg hover:bg-gray-50 cursor-pointer">
              <div>
                <div class="font-medium">隐私设置</div>
                <div class="text-sm text-gray-500">管理个人隐私</div>
              </div>
              <el-icon class="text-gray-400"><ArrowRight /></el-icon>
            </div>
            <button class="w-full mt-6 p-3 rounded-lg text-red-500 hover:bg-red-50 transition-colors border border-red-200" @click="handleLogout">
              退出登录
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { ElMessage, ElMessageBox } from 'element-plus'

const router = useRouter()
const userStore = useUserStore()

const activeMenu = ref('profile')
const signCount = ref(0)
const signed = ref(false)
const signing = ref(false)

const stats = reactive({
  follows: 12,
  fans: 8,
  blogs: 15
})

const weekDays = Array.from({ length: 7 }, (_, i) => ({
  name: ['一', '二', '三', '四', '五', '六', '日'][i],
  date: i + 1,
  signed: i < 3
}))

const menuItems = [
  { key: 'profile', label: '个人资料', icon: 'User' },
  { key: 'sign', label: '每日签到', icon: 'Calendar' },
  { key: 'orders', label: '我的订单', icon: 'Tickets' },
  { key: 'favorites', label: '我的收藏', icon: 'StarFilled' },
  { key: 'settings', label: '账号设置', icon: 'Setting' }
]

onMounted(async () => {
  try {
    signCount.value = await userStore.getSignCount()
  } catch (e) {
    // ignore
  }
})

async function handleSign() {
  if (signed.value) return
  signing.value = true
  try {
    await userStore.sign()
    signCount.value += 1
    signed.value = true
    ElMessage.success('签到成功！获得5积分')
  } finally {
    signing.value = false
  }
}

async function handleLogout() {
  try {
    await ElMessageBox.confirm('确定要退出登录吗？', '提示', {
      type: 'warning'
    })
    await userStore.logout()
    router.push('/')
  } catch (e) {
    // cancel
  }
}
</script>
