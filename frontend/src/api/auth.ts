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
  refreshToken() {
    return http.post('/auth/refresh/')
  },

  // 获取当前用户信息
  getCurrentUser() {
    return http.get<User>('/auth/users/profile/')
  },

  // 获取用户列表（用于下拉选择）
  getUsers() {
    return http.get('/auth/users/')
  },

  // 获取认证配置
  getAuthConfig() {
    return http.get<AuthConfig>('/auth/users/auth_config/')
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
