import axios, { type AxiosInstance, type AxiosRequestConfig, type AxiosResponse } from 'axios'
import { Message } from '@arco-design/web-vue'
import { useAuthStore } from '@/stores/auth'
import type { ApiResponse } from '@/types'
import { API_BASE_URL } from '@/utils/env'

// 全局错误消息去重
let currentErrorMessages = new Set<string>()
let isRedirecting = false // 防止重复跳转

// 清理错误消息的定时器
const clearErrorMessage = (message: string) => {
  setTimeout(() => {
    currentErrorMessages.delete(message)
  }, 5000) // 5秒后清除消息，允许再次显示
}

// 显示唯一错误消息
const showUniqueErrorMessage = (message: string, type: 'error' | 'warning' = 'error') => {
  if (!currentErrorMessages.has(message)) {
    currentErrorMessages.add(message)
    if (type === 'error') {
      Message.error(message)
    } else {
      Message.warning(message)
    }
    clearErrorMessage(message)
  }
}

// 判断是否是公共接口（不需要认证的接口）
const isPublicEndpoint = (url?: string): boolean => {
  if (!url) return false
  return url.includes('/auth/login/') ||
         url.includes('/auth/users/auth_config/') ||
         url.includes('/captcha/')
}

// 创建axios实例
const request: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  withCredentials: true, // 启用Cookie支持，用于Session
  headers: {
    'Content-Type': 'application/json',
  },
})

// 请求拦截器
request.interceptors.request.use(
  async (config) => {
    const authStore = useAuthStore()

    // 添加认证jwt token（仅对需要认证的接口）
    if (!isPublicEndpoint(config.url) && authStore.token) {
      config.headers.Authorization = `Bearer ${authStore.token}`
    }

    return config
  },
  (error) => {
    console.error('请求错误:', error)
    return Promise.reject(error)
  }
)

// 响应拦截器
request.interceptors.response.use(
  (response: AxiosResponse<ApiResponse>) => {
    const { data, config } = response

    // 如果是blob响应，直接返回data（文件内容）
    if (config.responseType === 'blob') {
      return data
    }

    // 特殊处理：SimpleJWT 刷新接口不返回标准 {success, content}
    if (config.url?.includes('/auth/refresh/')) {
      return data
    }

    // 检查业务状态码
    if (data.success) {
      return data.content
    }
    return Promise.reject(new Error(data.message || '请求失败'))
  },
  async (error) => {

    console.error('响应错误:', error)

    if (error.response) {
      const { status, data } = error.response
      
      // 检查是否是刷新token的请求
      const isRefreshTokenRequest = error.config?.url?.includes('/auth/refresh/')
      
      switch (status) {
        case 401:
          // 如果是公共认证接口，直接返回错误，不触发跳转
          if (isPublicEndpoint(error.config?.url)) {
            return Promise.reject(error)
          }
          
          // 如果当前在登录页面，不触发跳转逻辑
          if (window.location.pathname === '/login') {
            return Promise.reject(error)
          }
          
          // 如果是刷新token失败，提供更详细的错误信息
          if (isRefreshTokenRequest) {
            if (data?.detail) {
              return Promise.reject(new Error(`Token刷新失败: ${data.detail}`))
            } else if (data?.message) {
              return Promise.reject(new Error(`Token刷新失败: ${data.message}`))
            } else {
              return Promise.reject(new Error('Token已过期或无效，请重新登录'))
            }
          }
          
          // 尝试自动刷新token
          const authStore = useAuthStore()
          if (authStore.refreshToken && !isRedirecting) {
            isRedirecting = true
            
            try {
              console.log('API请求401错误，尝试自动刷新token...')
              const newToken = await authStore.refreshAccessToken()
              console.log('token刷新成功，重试原请求')
              
              // 更新请求头并重试原请求
              if (error.config) {
                error.config.headers.Authorization = `Bearer ${newToken}`
                isRedirecting = false
                return request(error.config)  // 重试原请求
              }
              
              isRedirecting = false
              return Promise.reject(error)
            } catch (refreshError) {
              console.warn('自动刷新token失败:', refreshError)
              
              // 刷新失败，显示错误信息并跳转登录页面
              showUniqueErrorMessage('登录已过期，正在跳转到登录页面...', 'warning')
              
              authStore.logout().then(() => {
                // 跳转到登录页面，保存当前路径用于登录后重定向
                const currentPath = window.location.pathname + window.location.search
                if (currentPath !== '/login') {
                  window.location.href = `/login?redirect=${encodeURIComponent(currentPath)}`
                }
              }).finally(() => {
                // 2秒后重置跳转标志，防止长时间锁定
                setTimeout(() => {
                  isRedirecting = false
                }, 2000)
              })
            }
          } else if (!isRedirecting) {
            // 没有refresh token或已经在处理中，直接跳转登录
            isRedirecting = true
            showUniqueErrorMessage('登录已过期，正在跳转到登录页面...', 'warning')
            
            authStore.logout().then(() => {
              const currentPath = window.location.pathname + window.location.search
              if (currentPath !== '/login') {
                window.location.href = `/login?redirect=${encodeURIComponent(currentPath)}`
              }
            }).finally(() => {
              setTimeout(() => {
                isRedirecting = false
              }, 2000)
            })
          }
          break
        case 403:
          return Promise.reject(new Error('权限不足'))
        case 404:
          return Promise.reject(new Error('请求的资源不存在'))
        case 500:
          // 如果是刷新token失败，提供更友好的错误信息
          if (isRefreshTokenRequest) {
            return Promise.reject(new Error('服务器内部错误，请稍后重试'))
          }
          return Promise.reject(new Error('服务器内部错误'))
        default:
          return Promise.reject(new Error(data?.message || `请求失败 (${status})`))
      }
    } else if (error.request) {
      // 网络连接失败
      const errorMsg = '网络连接失败，请检查网络'
      return Promise.reject(new Error(errorMsg))
    } else {
      // 请求配置错误
      const errorMsg = '请求配置错误'
      return Promise.reject(new Error(errorMsg))
    }
    
    return Promise.reject(error)
  }
)

// 封装常用请求方法
export const http = {
  get<T = any>(url: string, config?: AxiosRequestConfig): Promise<T> {
    return request.get(url, config)
  },
  
  post<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    return request.post(url, data, config)
  },
  
  put<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    return request.put(url, data, config)
  },
  
  patch<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    return request.patch(url, data, config)
  },
  
  delete<T = any>(url: string, config?: AxiosRequestConfig): Promise<T> {
    return request.delete(url, config)
  },
}

export default request
