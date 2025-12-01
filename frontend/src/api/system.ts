/**
 * 系统配置相关API
 */
import { http } from '@/utils/request'

export interface SystemConfig {
  id: number
  key: string
  value: any
  description: string
  category: string
  category_display: string
  is_active: boolean
  created_at: string
  updated_at: string
  updated_by_name: string
}

export interface TaskConfig {
  max_concurrent_jobs: number
  job_timeout: number
  retry_attempts: number
  cleanup_days: number
}

export interface NotificationConfig {
  email_enabled: boolean
  webhook_enabled: boolean
  levels: string[]
  email_recipients: string[]
}

export const systemConfigApi = {
  // 获取所有配置
  getConfigs: (params?: any) => {
    return http.get<{
      results: SystemConfig[]
      total: number
    }>('/system/configs/', { params })
  },

  // 获取单个配置
  getConfig: (id: number) => {
    return http.get<SystemConfig>(`/system/configs/${id}/`)
  },

  // 创建配置
  createConfig: (data: Partial<SystemConfig>) => {
    return http.post<SystemConfig>('/system/configs/', data)
  },

  // 更新配置
  updateConfig: (id: number, data: Partial<SystemConfig>) => {
    return http.put<SystemConfig>(`/system/configs/${id}/`, data)
  },

  // 删除配置
  deleteConfig: (id: number) => {
    return http.delete(`/system/configs/${id}/`)
  },

  // 按分类获取配置
  getConfigsByCategory: (category: string) => {
    return http.get<{
      category: string
      configs: Record<string, any>
    }>('/system/configs/by_category/', { params: { category } })
  },

  // 批量更新配置
  batchUpdateConfigs: (configs: Array<{ key: string; value: any; description?: string }>) => {
    return http.post<SystemConfig[]>('/system/configs/batch_update/', { configs })
  },

  // 获取任务配置
  getTaskConfig: () => {
    return http.get<TaskConfig>('/system/configs/task_config/')
  },

  // 更新任务配置
  updateTaskConfig: (data: TaskConfig) => {
    return http.post<TaskConfig>('/system/configs/update_task_config/', data)
  },

  // 获取通知配置
  getNotificationConfig: () => {
    return http.get<NotificationConfig>('/system/configs/notification_config/')
  },

  // 更新通知配置
  updateNotificationConfig: (data: NotificationConfig) => {
    return http.post<NotificationConfig>('/system/configs/update_notification_config/', data)
  }
}
