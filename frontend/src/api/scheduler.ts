/**
 * 调度管理API
 */
import request from '@/utils/request'

// 定时任务API
export const scheduledJobApi = {
  // 获取定时任务列表
  list(params?: any) {
    return request({
      url: '/scheduler/scheduled-jobs/',
      method: 'get',
      params
    })
  },

  // 获取定时任务详情
  get(id: number) {
    return request({
      url: `/scheduler/scheduled-jobs/${id}/`,
      method: 'get'
    })
  },

  // 创建定时任务
  create(data: any) {
    return request({
      url: '/scheduler/scheduled-jobs/',
      method: 'post',
      data
    })
  },

  // 更新定时任务
  update(id: number, data: any) {
    return request({
      url: `/scheduler/scheduled-jobs/${id}/`,
      method: 'put',
      data
    })
  },

  // 部分更新定时任务
  patch(id: number, data: any) {
    return request({
      url: `/scheduler/scheduled-jobs/${id}/`,
      method: 'patch',
      data
    })
  },

  // 删除定时任务
  delete(id: number) {
    return request({
      url: `/scheduler/scheduled-jobs/${id}/`,
      method: 'delete'
    })
  },

  // 切换任务状态
  toggleStatus(id: number, isActive: boolean) {
    return request({
      url: `/scheduler/scheduled-jobs/${id}/`,
      method: 'patch',
      data: { is_active: isActive }
    })
  },

  // 立即执行任务
  executeNow(id: number) {
    return request({
      url: `/scheduler/scheduled-jobs/${id}/execute/`,
      method: 'post'
    })
  },



  // 获取统计信息
  getStatistics() {
    return request({
      url: '/scheduler/scheduled-jobs/statistics/',
      method: 'get'
    })
  }
}

// 执行方案API（用于选择器）
export const executionPlanApi = {
  // 获取执行方案列表（简化版，用于选择器）
  list(params?: any) {
    return request({
      url: '/templates/plans/',
      method: 'get',
      params
    })
  }
}

// Cron表达式工具API（本地验证）
export const cronApi = {
  // 本地验证Cron表达式
  validate(expression: string) {
    return new Promise((resolve, reject) => {
      try {
        // 简单的Cron表达式格式验证
        const parts = expression.trim().split(/\s+/)
        if (parts.length !== 5) {
          reject(new Error('Cron表达式必须包含5个字段：分 时 日 月 周'))
          return
        }

        // 验证每个字段的基本格式
        const [minute, hour, day, month, weekday] = parts

        if (!isValidCronField(minute, 0, 59) ||
            !isValidCronField(hour, 0, 23) ||
            !isValidCronField(day, 1, 31) ||
            !isValidCronField(month, 1, 12) ||
            !isValidCronField(weekday, 0, 7)) {
          reject(new Error('Cron表达式字段值超出有效范围'))
          return
        }

        resolve({ valid: true })
      } catch (error) {
        reject(error)
      }
    })
  },

  // 获取Cron表达式描述
  describe(expression: string) {
    return new Promise((resolve) => {
      const description = getCronDescription(expression)
      resolve({ data: { description } })
    })
  },

  // 获取下次执行时间（模拟）
  getNextRuns(expression: string, count: number = 5) {
    return new Promise((resolve) => {
      const nextRuns = generateNextRuns(expression, count)
      resolve({ data: { next_runs: nextRuns } })
    })
  }
}

// 辅助函数：验证Cron字段
function isValidCronField(field: string, min: number, max: number): boolean {
  if (field === '*') return true

  // 处理范围 (如 1-5)
  if (field.includes('-')) {
    const [start, end] = field.split('-').map(Number)
    return start >= min && end <= max && start <= end
  }

  // 处理列表 (如 1,3,5)
  if (field.includes(',')) {
    const values = field.split(',').map(Number)
    return values.every(val => val >= min && val <= max)
  }

  // 处理步长 (如 */5)
  if (field.includes('/')) {
    const [base, step] = field.split('/')
    if (base === '*') return Number(step) > 0
    return isValidCronField(base, min, max) && Number(step) > 0
  }

  // 单个数值
  const num = Number(field)
  return !isNaN(num) && num >= min && num <= max
}

// 辅助函数：获取Cron描述
function getCronDescription(expression: string): string {
  const parts = expression.split(' ')
  if (parts.length !== 5) return expression

  const [minute, hour, day, month, weekday] = parts

  if (minute === '0' && hour !== '*' && day === '*' && month === '*' && weekday === '*') {
    return `每天${hour}点执行`
  }
  if (minute !== '*' && hour !== '*' && day === '*' && month === '*' && weekday === '*') {
    return `每天${hour}:${minute.padStart(2, '0')}执行`
  }
  if (minute === '0' && hour === '0' && day === '*' && month === '*' && weekday !== '*') {
    const weekdays = ['日', '一', '二', '三', '四', '五', '六', '日']
    return `每周${weekdays[Number(weekday)]}午夜执行`
  }

  return expression
}

// 辅助函数：生成下次执行时间（简单模拟）
function generateNextRuns(expression: string, count: number): string[] {
  const now = new Date()
  const runs: string[] = []

  for (let i = 0; i < count; i++) {
    const nextTime = new Date(now.getTime() + (i + 1) * 24 * 60 * 60 * 1000) // 简单的每天递增
    runs.push(nextTime.toISOString())
  }

  return runs
}
