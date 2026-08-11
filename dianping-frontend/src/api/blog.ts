import { request } from '@/utils/request'
import type { Blog } from '@/types'

export const blogApi = {
  saveBlog(data: Partial<Blog>) {
    return request.post<number>('/blog', data)
  },

  likeBlog(id: number) {
    return request.put(`/blog/like/${id}`)
  },

  queryMyBlog(current = 1) {
    return request.get<Blog[]>('/blog/of/me', { params: { current } })
  },

  queryHotBlog(current = 1) {
    return request.get<Blog[]>('/blog/hot', { params: { current } })
  },

  queryById(id: number) {
    return request.get<Blog>(`/blog/${id}`)
  },

  queryBlogLikes(id: number) {
    return request.get(`/blog/likes/${id}`)
  },

  queryByUserId(userId: number, current = 1) {
    return request.get<Blog[]>('/blog/of/user', { params: { id: userId, current } })
  },

  queryByShopId(shopId: number, current = 1) {
    return request.get<Blog[]>('/blog/of/shop', { params: { shopId, current } })
  },

  queryBlogOfFollow(max: number, offset = 0) {
    return request.get('/blog/of/follow', { params: { lastId: max, offset } })
  }
}
