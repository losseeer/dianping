<template>
  <div class="container py-8 max-w-3xl">
    <div class="card p-6">
      <h1 class="text-2xl font-bold mb-6 flex items-center gap-2">
        <el-icon class="text-primary-500"><EditPen /></el-icon>
        发布探店笔记
      </h1>

      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <el-form-item label="关联商家（可选）" prop="shopId">
          <el-select
            v-model="form.shopId"
            placeholder="搜索并选择探店的商家"
            filterable
            remote
            :remote-method="searchShops"
            :loading="shopSearchLoading"
            clearable
            style="width: 100%"
          >
            <el-option
              v-for="shop in shopOptions"
              :key="shop.id"
              :label="shop.name"
              :value="shop.id"
            >
              <div class="flex items-center justify-between">
                <span>{{ shop.name }}</span>
                <span class="text-xs text-gray-400">{{ shop.area }}</span>
              </div>
            </el-option>
          </el-select>
        </el-form-item>

        <el-form-item label="笔记标题" prop="title">
          <el-input
            v-model="form.title"
            placeholder="起一个吸引人的标题..."
            maxlength="50"
            show-word-limit
            size="large"
          />
        </el-form-item>

        <el-form-item label="上传图片（最多9张）">
          <el-upload
            :action="uploadAction"
            list-type="picture-card"
            :auto-upload="false"
            :file-list="fileList"
            :limit="9"
            :on-change="handleFileChange"
            :on-remove="handleFileRemove"
            :on-preview="handlePreview"
            accept="image/*"
            multiple
          >
            <el-icon class="text-2xl text-gray-400"><Plus /></el-icon>
            <div class="text-xs text-gray-500 mt-1">添加图片</div>
          </el-upload>
          <p class="text-xs text-gray-400 mt-2">支持 JPG/PNG 格式，单张不超过 5MB</p>
        </el-form-item>

        <el-form-item label="笔记内容" prop="content">
          <el-input
            v-model="form.content"
            type="textarea"
            :rows="10"
            placeholder="分享你的探店体验：环境、菜品、服务、性价比..."
            maxlength="2000"
            show-word-limit
          />
        </el-form-item>

        <el-form-item label="评分（可选）">
          <el-rate
            v-model="form.rating"
            :max="5"
            size="large"
            show-text
            :texts="['差评', '一般', '还行', '推荐', '超赞']"
          />
        </el-form-item>

        <el-form-item>
          <div class="flex gap-4">
            <el-button
              type="primary"
              size="large"
              :loading="submitting"
              @click="handleSubmit"
            >
              <el-icon class="mr-1"><Promotion /></el-icon>
              发布笔记
            </el-button>
            <el-button size="large" @click="saveDraft">
              保存草稿
            </el-button>
            <el-button size="large" @click="$router.back()">
              取消
            </el-button>
          </div>
        </el-form-item>
      </el-form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { useRouter } from 'vue-router'
import { blogApi } from '@/api/blog'
import { shopApi } from '@/api/shop'
import type { UploadFile } from 'element-plus'
import { ElForm, ElMessage } from 'element-plus'
import type { FormInstance, FormRules, UploadUserFile } from 'element-plus'
import type { Shop } from '@/types'

const router = useRouter()
const formRef = ref<FormInstance>()
const submitting = ref(false)
const shopSearchLoading = ref(false)
const shopOptions = ref<Shop[]>([])
const fileList = ref<UploadUserFile[]>([])

const uploadAction = '/api/upload/blog'

const form = reactive({
  shopId: undefined as number | undefined,
  title: '',
  content: '',
  rating: 5
})

const rules: FormRules = {
  title: [
    { required: true, message: '请输入笔记标题', trigger: 'blur' },
    { min: 5, max: 50, message: '标题长度5-50字符', trigger: 'blur' }
  ],
  content: [
    { required: true, message: '请输入笔记内容', trigger: 'blur' },
    { min: 20, message: '内容至少20字，多多分享哦~', trigger: 'blur' }
  ]
}

async function searchShops(keyword: string) {
  if (!keyword.trim()) {
    shopOptions.value = []
    return
  }
  shopSearchLoading.value = true
  try {
    const res = await shopApi.queryByName(keyword, 1)
    shopOptions.value = (res.data as Shop[]) || []
  } finally {
    shopSearchLoading.value = false
  }
}

function handleFileChange(file: UploadFile) {
  if (file.size && file.size > 5 * 1024 * 1024) {
    ElMessage.warning('图片大小不能超过 5MB')
    return
  }
}

function handleFileRemove(_: UploadFile) {
  // file list auto updated
}

function handlePreview(_: UploadFile) {
  // preview logic
}

function getImagesFromFiles(): string {
  // In production, upload files to server first and get URLs
  // For now, return placeholder URLs based on index
  const mockUrls: string[] = []
  fileList.value.forEach((_, idx) => {
    mockUrls.push(`https://picsum.photos/seed/${Date.now() + idx}/600/400`)
  })
  return mockUrls.join(',')
}

async function handleSubmit() {
  await formRef.value?.validate()
  submitting.value = true
  try {
    const blogData: any = {
      title: form.title,
      content: form.content,
      liked: 0,
      comments: 0
    }
    if (form.shopId) {
      blogData.shopId = form.shopId
    }
    const images = getImagesFromFiles()
    if (images) {
      blogData.images = images
    }
    const res = await blogApi.saveBlog(blogData)
    ElMessage.success('发布成功！')
    const blogId = res.data as number
    router.push(`/blog/${blogId}`)
  } finally {
    submitting.value = false
  }
}

function saveDraft() {
  ElMessage.success('草稿已保存')
}
</script>
