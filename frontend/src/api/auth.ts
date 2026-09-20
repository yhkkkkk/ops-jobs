import { http } from '@/utils/request'
import type { LoginParams, LoginResult, User, AuthConfig } from '@/types'

export const authApi = {
  // 用户登录
  login(data: LoginParams) {
    return http.post<LoginResult>('/auth/login/', data)
  },

  // 用户登出
  logout(refreshToken?: string) {
    return http.post('/auth/logout/', refreshToken ? { refresh: refreshToken } : {})
  },

  // 刷新访问令牌
  refreshToken(refreshToken: string) {
    return http.post('/auth/refresh/', { refresh: refreshToken })
  },

  // 获取当前用户信息
  getCurrentUser() {
    return http.get<User>('/auth/users/profile/')
  },

  // 获取用户列表（管理页和下拉选择共用）
  getUsers(params?: { page?: number; page_size?: number; search?: string }) {
    // 后端生产接口返回分页对象；保留 any 兼容旧的下拉选择 mock 数组响应。
    return http.get<any>('/auth/users/', { params })
  },

  // 更新用户资料（后端仅允许资料字段，管理员状态不会通过此接口修改）
  updateUser(id: number, data: {
    first_name?: string
    last_name?: string
    email?: string
    phone?: string
    department?: string
    position?: string
  }) {
    return http.patch<User>(`/auth/users/${id}/`, data)
  },

  // 获取认证配置
  getAuthConfig() {
    return http.get<AuthConfig>('/auth/users/auth_config/')
  },

  // 获取当前用户信息（兼容旧命名）
  getUserInfo() {
    return this.getCurrentUser()
  },

  // 检查用户是否需要2FA验证（登录前）
  check2FARequired(data: { username: string; password: string }) {
    return http.post<{ requires_2fa: boolean }>('/auth/check-2fa/', data)
  },
}

// 验证码API
export const captchaApi = {
  // 获取验证码
  getCaptcha() {
    return http.get<{
      enabled: boolean
      captcha_key?: string
      captcha_image?: string
    }>('/captcha/')
  },
}

// 2FA API
export const twoFactorApi = {
  // 获取2FA设置信息
  getSetup() {
    return http.get<{
      secret: string
      qr_code: string
      config_url: string
    }>('/auth/2fa/setup/')
  },

  // 验证并启用2FA
  verify(otp_token: string) {
    return http.post<{
      backup_tokens: string[]
    }>('/auth/2fa/verify/', { otp_token })
  },

  // 获取2FA状态
  getStatus() {
    return http.get<{
      enabled: boolean
      device_count: number
    }>('/auth/2fa/status/')
  },

  // 禁用2FA
  disable() {
    return http.post('/auth/2fa/disable/')
  },
}
