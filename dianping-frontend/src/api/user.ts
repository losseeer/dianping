import { request } from '@/utils/request'
import type { LoginFormDTO, User, UserDTO, UserInfo } from '@/types'

export const userApi = {
  sendCode(phone: string) {
    return request.post('/user/code', null, { params: { phone } })
  },

  login(data: LoginFormDTO) {
    return request.post<string>('/user/login', data)
  },

  logout() {
    return request.post('/user/logout')
  },

  me() {
    return request.get<UserDTO>('/user/me')
  },

  info(id: number) {
    return request.get<UserInfo>(`/user/info/${id}`)
  },

  queryById(id: number) {
    return request.get<UserDTO>(`/user/${id}`)
  },

  sign() {
    return request.post('/user/sign')
  },

  signCount() {
    return request.get<number>('/user/sign/count')
  }
}
