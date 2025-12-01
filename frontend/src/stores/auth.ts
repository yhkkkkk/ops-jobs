import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { User, LoginParams, LoginResult } from '@/types'
import { authApi } from '@/api/auth'

export const useAuthStore = defineStore('auth', () => {
  // 状态
  const token = ref<string>('')
  const refreshToken = ref<string>('')
  const user = ref<User | null>(null)
  const loading = ref(false)
  const refreshing = ref(false) // 新增：用于控制并发刷新

  // 计算属性
  const isAuthenticated = computed(() => !!token.value && !!user.value)
  const isAdmin = computed(() => user.value?.is_superuser || false)
  const isStaff = computed(() => user.value?.is_staff || false)

  // 初始化
  const init = async () => {
    // 优先从sessionStorage恢复（当前会话）
    let savedToken = sessionStorage.getItem('access_token')
    let savedRefreshToken = sessionStorage.getItem('refresh_token')
    let savedUser = sessionStorage.getItem('user')

    // 如果sessionStorage没有，检查localStorage（记住登录）
    if (!savedToken) {
      const rememberLogin = localStorage.getItem('remember_login')
      if (rememberLogin === 'true') {
        savedToken = localStorage.getItem('access_token')
        savedRefreshToken = localStorage.getItem('refresh_token')
        savedUser = localStorage.getItem('user')

        // 将数据同步到sessionStorage
        if (savedToken) {
          sessionStorage.setItem('access_token', savedToken)
          sessionStorage.setItem('refresh_token', savedRefreshToken || '')
          sessionStorage.setItem('user', savedUser || '')
        }
      }
    }

    if (savedToken) {
      token.value = savedToken
    }
    if (savedRefreshToken) {
      refreshToken.value = savedRefreshToken
    }
    if (savedUser) {
      try {
        user.value = JSON.parse(savedUser)
        
        // 如果用户已登录，初始化权限存储
        if (user.value) {
          await initPermissions()
        }
      } catch (error) {
        console.error('解析用户信息失败:', error)
        clearStorage()
      }
    }
  }

  /**
   * 初始化权限存储
   */
  const initPermissions = async () => {
    try {
      // 延迟导入避免循环依赖
      const { usePermissionsStore } = await import('./permissions')
      const permissionsStore = usePermissionsStore()
      await permissionsStore.fetchUserPermissions()
    } catch (error) {
      console.error('初始化权限失败:', error)
    }
  }

  // 登录
  const login = async (params: LoginParams & { remember?: boolean }): Promise<void> => {
    loading.value = true
    try {
      const result: LoginResult = await authApi.login(params)

      // 保存token和用户信息
      token.value = result.access_token
      refreshToken.value = result.refresh_token
      user.value = result.user

      // 始终保存到sessionStorage（当前会话）
      sessionStorage.setItem('access_token', result.access_token)
      sessionStorage.setItem('refresh_token', result.refresh_token)
      sessionStorage.setItem('user', JSON.stringify(result.user))

      // 如果选择记住登录，也保存到localStorage
      if (params.remember) {
        localStorage.setItem('remember_login', 'true')
        localStorage.setItem('access_token', result.access_token)
        localStorage.setItem('refresh_token', result.refresh_token)
        localStorage.setItem('user', JSON.stringify(result.user))
      } else {
        // 清除localStorage中的记住登录标记
        localStorage.removeItem('remember_login')
        localStorage.removeItem('refresh_token')
        localStorage.removeItem('user')
      }

      // 登录成功后初始化权限
      await initPermissions()
    } finally {
      loading.value = false
    }
  }

  // 登出
  const logout = async (): Promise<void> => {
    try {
      // 调用后端登出接口
      await authApi.logout()
    } catch (error) {
      console.error('登出请求失败:', error)
    } finally {
      // 清除本地状态
      clearState()
    }
  }

  // 刷新token
  const refreshAccessToken = async (): Promise<string> => {
    // 防止并发刷新
    if (refreshing.value) {
      // 等待正在进行的刷新完成
      return new Promise((resolve, reject) => {
        let attempts = 0
        const maxAttempts = 50 // 最多等待5秒
        
        const checkRefreshing = () => {
          attempts++
          if (!refreshing.value) {
            if (token.value) {
              resolve(token.value)
            } else {
              reject(new Error('刷新失败'))
            }
          } else if (attempts >= maxAttempts) {
            reject(new Error('刷新超时'))
          } else {
            setTimeout(checkRefreshing, 100)
          }
        }
        checkRefreshing()
      })
    }

    refreshing.value = true
    
    try {
      if (!refreshToken.value) {
        throw new Error('没有refresh token')
      }

      const result = await authApi.refreshToken(refreshToken.value)
      token.value = result.access_token
      sessionStorage.setItem('access_token', result.access_token)

      // 如果记住登录，也更新localStorage
      if (localStorage.getItem('remember_login') === 'true') {
        localStorage.setItem('access_token', result.access_token)
      }

      return result.access_token
    } catch (error: any) {
      console.error('刷新token失败:', error)
      
      // 根据错误类型决定是否重试
      if (error.message?.includes('网络连接失败') || 
          error.message?.includes('请求失败') ||
          !error.response) {
        // 网络错误，尝试重试一次
        try {
          console.warn('网络错误，尝试重试刷新token...')
          await new Promise(resolve => setTimeout(resolve, 1000)) // 等待1秒
          const result = await authApi.refreshToken(refreshToken.value!)
          token.value = result.access_token
          sessionStorage.setItem('access_token', result.access_token)
          
          if (localStorage.getItem('remember_login') === 'true') {
            localStorage.setItem('access_token', result.access_token)
          }
          
          return result.access_token
        } catch (retryError) {
          console.error('重试刷新token失败:', retryError)
          clearState()
          throw retryError
        }
      } else {
        // 其他错误（如token无效、服务器错误等），清除状态
        clearState()
        throw error
      }
    } finally {
      refreshing.value = false
    }
  }

  // 获取用户信息
  const fetchUserInfo = async (): Promise<void> => {
    try {
      const userInfo = await authApi.getUserInfo()
      user.value = userInfo
      sessionStorage.setItem('user', JSON.stringify(userInfo))
    } catch (error) {
      console.error('获取用户信息失败:', error)
      throw error
    }
  }

  // 清除状态
  const clearState = () => {
    token.value = ''
    refreshToken.value = ''
    user.value = null
    clearStorage()
  }

  // 清除存储
  const clearStorage = () => {
    // 清除sessionStorage
    sessionStorage.removeItem('access_token')
    sessionStorage.removeItem('refresh_token')
    sessionStorage.removeItem('user')

    // 清除localStorage
    localStorage.removeItem('remember_login')
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    localStorage.removeItem('user')
  }

  // 检查token是否过期
  const isTokenExpired = (): boolean => {
    if (!token.value) return true
    
    try {
      const payload = JSON.parse(atob(token.value.split('.')[1]))
      const exp = payload.exp * 1000 // 转换为毫秒
      return Date.now() >= exp
    } catch (error) {
      console.error('解析token失败:', error)
      return true
    }
  }

  return {
    // 状态
    token,
    refreshToken,
    user,
    loading,
    
    // 计算属性
    isAuthenticated,
    isAdmin,
    isStaff,
    
    // 方法
    init,
    login,
    logout,
    refreshAccessToken,
    fetchUserInfo,
    clearState,
    isTokenExpired,
  }
})
