import { request } from '@/utils/request'

export const followApi = {
  follow(followUserId: number) {
    return request.put(`/follow/${followUserId}`)
  },

  isFollow(followUserId: number) {
    return request.get<boolean>(`/follow/or/not/${followUserId}`)
  },

  followCommons(id: number) {
    return request.get('/follow/common/' + id)
  }
}
