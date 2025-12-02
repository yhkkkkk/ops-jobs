import { http } from '@/utils/request'
import type { LoginParams, LoginResult, User } from '@/types'

export const authApi = {
  // 用户登录
  login(data: { username: string; password: string }) {
    return http.post('/auth/login/', data)
  },

  // 用户登出
  logout(refreshToken?: string) {
    return http.post('/auth/logout/', refreshToken ? { refresh: refreshToken } : {})
  },

  // 刷新访问令牌
  refreshToken() {
    return http.post('/auth/refresh/')
  },

  // 获取当前用户信息
  getCurrentUser() {
    return http.get('/auth/user/')
  },

  // 获取用户列表（用于下拉选择）
  getUsers() {
    return http.get('/auth/users/')
  },
}
