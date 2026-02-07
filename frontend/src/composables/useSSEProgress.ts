import { ref, reactive, onUnmounted } from 'vue'
import { Message } from '@arco-design/web-vue'
import { SSE } from 'sse.js'

// SSE 进度数据类型
export interface ProgressLog {
  host_name: string
  host_ip: string
  content: string
  log_type: string
  timestamp: string
}

export interface ProgressState {
  total: number
  completed: number
  success_count: number
  failed_count: number
  status: string
  message: string
  logs: ProgressLog[]
}

// SSE 配置
export interface SSEProgressConfig {
  /** SSE 端点路径（不含基础URL） */
  endpoint: string
  /** 进度状态ref */
  progress: ProgressState
  /** SSE EventSource 实例 */
  eventSource: any
  /** 终态状态集合 */
  terminalStatuses?: Set<string>
  /** 最大日志条数 */
  maxLogs?: number
  /** 成功回调 */
  onSuccess?: () => void
  /** 错误回调 */
  onError?: (error: string) => void
  /** 进度更新回调 */
  onProgress?: (data: any) => void
  /** 日志回调 */
  onLog?: (log: ProgressLog) => void
}

// 默认终态集合
const DEFAULT_TERMINAL_STATUSES = new Set([
  'completed', 'completed_with_errors', 'failed', 'success', 'error', 'stopped'
])

// 获取认证 token
const getAccessToken = (): string => {
  // 尝试从多个存储获取 token
  const token = 
    (window as any).authStore?.token ||
    sessionStorage.getItem('access_token') ||
    localStorage.getItem('access_token') ||
    ''
  return token
}

// 构建 SSE URL
export const buildSseUrl = (path: string): string => {
  // 如果是完整 URL，直接返回
  if (path.startsWith('http://') || path.startsWith('https://') || path.startsWith('//')) {
    return path
  }
  // 移除开头的斜杠
  const normalizedPath = path.startsWith('/') ? path.slice(1) : path
  // 获取当前基础路径
  const basePath = (import.meta.env.BASE_URL || '/').replace(/\/$/, '')
  return `${basePath}${basePath ? '/' : ''}api/realtime/sse/${normalizedPath}`
}

/**
 * SSE 进度 Composable
 * 封装 SSE 连接的通用逻辑，支持安装、卸载、批量操作等场景
 */
export function useSSEProgress(config: SSEProgressConfig) {
  const {
    endpoint,
    progress,
    eventSource,
    terminalStatuses = DEFAULT_TERMINAL_STATUSES,
    maxLogs = 500,
    onSuccess,
    onError,
    onProgress,
    onLog
  } = config

  // 状态
  const isConnected = ref(false)
  const connectionError = ref<string | null>(null)

  // 重置进度状态
  const resetProgress = (status: string = 'idle', message: string = '') => {
    progress.total = 0
    progress.completed = 0
    progress.success_count = 0
    progress.failed_count = 0
    progress.status = status
    progress.message = message
    progress.logs = []
  }

  // 关闭连接
  const closeConnection = () => {
    if (eventSource.value) {
      try {
        eventSource.value.autoReconnect = false
        eventSource.value.close()
      } catch (e) {
        console.warn('关闭 SSE 连接失败:', e)
      }
      eventSource.value = null
    }
    isConnected.value = false
  }

  // 添加日志（带自动清理）
  const addLog = (log: ProgressLog) => {
    progress.logs.push(log)
    // 限制日志数量，保留最近 N 条
    if (progress.logs.length > maxLogs) {
      progress.logs = progress.logs.slice(-maxLogs)
    }
    onLog?.(log)
  }

  // 处理状态消息
  const handleStatusMessage = (data: any) => {
    progress.total = data.total || data.total_hosts || 0
    progress.completed = data.completed || 0
    progress.success_count = data.success_count || data.success_hosts || 0
    progress.failed_count = data.failed_count || data.failed_hosts || 0
    progress.status = data.status || 'running'
    progress.message = data.message || ''

    // 检测终态
    const statusValue = (data.status || '').toLowerCase()
    if (terminalStatuses.has(statusValue)) {
      console.log(`任务已达终态: ${statusValue}，关闭 SSE 连接`)
      closeConnection()
      onSuccess?.()
    }

    onProgress?.(data)
  }

  // 处理日志消息
  const handleLogMessage = (data: any) => {
    const log: ProgressLog = {
      host_name: data.host_name || '',
      host_ip: data.host_ip || '',
      content: data.content || '',
      log_type: data.log_type || 'info',
      timestamp: data.timestamp || new Date().toISOString()
    }
    addLog(log)
  }

  // 处理错误消息
  const handleErrorMessage = (data: any) => {
    progress.status = 'error'
    progress.message = data.message || '发生错误'
    addLog({
      host_name: '',
      host_ip: '',
      content: data.message || '发生错误',
      log_type: 'error',
      timestamp: new Date().toISOString()
    })
    connectionError.value = data.message
    onError?.(data.message)
  }

  // 建立 SSE 连接
  const connect = (taskId: string, customStatus?: string) => {
    // 关闭之前的连接
    closeConnection()

    // 重置进度
    resetProgress(customStatus || 'running', '正在连接...')
    connectionError.value = null

    // 获取 token
    const token = getAccessToken()
    const sseUrl = buildSseUrl(`${endpoint}${taskId}/`)

    // 检查 SSE 是否可用
    if (typeof SSE === 'undefined') {
      Message.error('SSE 库未加载，请确保已引入 sse.js')
      connectionError.value = 'SSE 库未加载'
      return
    }

    // 使用 sse.js 建立连接
    const es = new SSE(sseUrl, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      start: true,
      debug: process.env.NODE_ENV === 'development',
      autoReconnect: true,
      reconnectDelay: 3000,
      maxRetries: 3,
      withCredentials: true
    })

    eventSource.value = es
    isConnected.value = true

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)

        if (data.type === 'connection_established') {
          progress.message = data.message || '已连接到进度流'
          progress.status = 'running'
        } else if (data.type === 'status') {
          handleStatusMessage(data)
        } else if (data.type === 'log') {
          handleLogMessage(data)
        } else if (data.type === 'error') {
          handleErrorMessage(data)
        } else if (data.type === 'heartbeat') {
          // 心跳消息，保持连接活跃
          console.debug('收到 SSE 心跳')
        } else {
          // 未知消息类型，记录调试信息
          console.debug('收到未知 SSE 消息类型:', data.type)
        }
      } catch (e) {
        console.error('解析 SSE 消息失败:', e)
      }
    }

    es.onerror = (error: any) => {
      console.error('SSE 连接错误:', error)
      connectionError.value = 'SSE 连接错误'
      isConnected.value = false

      // 如果不是终态，提示用户
      if (!terminalStatuses.has(progress.status)) {
        Message.error('SSE 连接错误，请检查网络')
      }
    }

    es.onopen = () => {
      console.log('SSE 连接已建立')
      isConnected.value = true
      connectionError.value = null
    }
  }

  // 组件卸载时自动关闭连接
  onUnmounted(() => {
    closeConnection()
  })

  return {
    isConnected,
    connectionError,
    resetProgress,
    closeConnection,
    connect,
    addLog,
    handleStatusMessage,
    handleLogMessage,
    handleErrorMessage
  }
}

/**
 * 创建进度状态对象的工厂函数
 */
export const createProgressState = (): ProgressState => ({
  total: 0,
  completed: 0,
  success_count: 0,
  failed_count: 0,
  status: 'idle',
  message: '',
  logs: []
})

/**
 * 预定义的进度配置工厂
 */
export const createProgressConfig = (
  endpoint: string,
  progress: ProgressState,
  eventSource: any,
  options: {
    terminalStatuses?: Set<string>
    maxLogs?: number
    onSuccess?: () => void
    onError?: (error: string) => void
    onProgress?: (data: any) => void
    onLog?: (log: ProgressLog) => void
  } = {}
): SSEProgressConfig => ({
  endpoint,
  progress,
  eventSource,
  ...options
})
