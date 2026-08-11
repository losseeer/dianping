import { request } from '@/utils/request'

export const uploadApi = {
  uploadBlog(file: File) {
    const formData = new FormData()
    formData.append('file', file)
    return request.post<string>('/upload/blog', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  }
}
