/**
 * 调度管理API
 */
import request, { http } from '@/utils/request'

// 定时任务API
export const scheduledJobApi = {
  // 获取定时任务列表
  list(params?: any) {
    return http.get('/scheduler/scheduled-jobs/', { params })
  },

  // 获取定时任务详情
  get(id: number) {
    return http.get(`/scheduler/scheduled-jobs/${id}/`)
  },

  // 创建定时任务
  create(data: any) {
    return http.post('/scheduler/scheduled-jobs/', data)
  },

  // 更新定时任务
  update(id: number, data: any) {
    return http.put(`/scheduler/scheduled-jobs/${id}/`, data)
  },

  // 部分更新定时任务
  patch(id: number, data: any) {
    return http.patch(`/scheduler/scheduled-jobs/${id}/`, data)
  },

  // 删除定时任务
  delete(id: number) {
    return http.delete(`/scheduler/scheduled-jobs/${id}/`)
  },

  // 切换任务状态
  toggleStatus(id: number, isActive: boolean) {
    return http.patch(`/scheduler/scheduled-jobs/${id}/`, { is_active: isActive })
  },

  // 立即执行任务
  executeNow(id: number) {
    return http.post(`/scheduler/scheduled-jobs/${id}/execute/`)
  },



  // 获取统计信息
  getStatistics() {
    return http.get('/scheduler/scheduled-jobs/statistics/')
  }
}

// 执行方案API（用于选择器）
export const executionPlanApi = {
  // 获取执行方案列表（简化版，用于选择器）
  list(params?: any) {
    return http.get('/job-templates/plans/', { params })
  },

  // 获取执行方案详情
  get(id: number) {
    return http.get(`/job-templates/plans/${id}/`)
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

// 辅助函数：判断某个值是否匹配 Cron 字段
function matchCronField(value: number, field: string, min: number, max: number): boolean {
  if (field === '*') return true

  // 支持逗号列表，如 "1,3,5"
  const parts = field.split(',')

  const matchSinglePart = (part: string): boolean => {
    // 处理步长 (如 */5 或 1-10/2)
    if (part.includes('/')) {
      const [base, stepStr] = part.split('/')
      const step = Number(stepStr)
      if (!step || step <= 0) return false

      if (base === '*') {
        return (value - min) % step === 0
      }

      // 处理范围 + 步长 (如 1-10/2)
      if (base.includes('-')) {
        const [startStr, endStr] = base.split('-')
        const start = Number(startStr)
        const end = Number(endStr)
        if (isNaN(start) || isNaN(end)) return false
        if (value < start || value > end) return false
        return (value - start) % step === 0
      }

      // 单值 + 步长其实意义不大，这里按单值处理
      const baseVal = Number(base)
      if (isNaN(baseVal)) return false
      return value === baseVal
    }

    // 处理范围 (如 1-5)
    if (part.includes('-')) {
      const [startStr, endStr] = part.split('-')
      const start = Number(startStr)
      const end = Number(endStr)
      if (isNaN(start) || isNaN(end)) return false
      return value >= start && value <= end
    }

    // 单个数值
    const num = Number(part)
    if (isNaN(num)) return false
    return value === num
  }

  return parts.some(p => matchSinglePart(p))
}

// 辅助函数：生成下次执行时间（基于简单 Cron 解析）
function generateNextRuns(expression: string, count: number): string[] {
  const parts = expression.trim().split(/\s+/)
  if (parts.length !== 5) {
    return []
  }

  const [minuteField, hourField, dayField, monthField, weekdayField] = parts

  const runs: string[] = []
  const now = new Date()

  // 从下一分钟开始计算，避免当前时间已经过了本分钟
  let current = new Date(now.getTime())
  current.setSeconds(0, 0)
  current.setMinutes(current.getMinutes() + 1)

  // 安全上限：最多遍历约 2 年的分钟数，防止死循环
  const maxAttempts = 60 * 24 * 365 * 2
  let attempts = 0

  while (runs.length < count && attempts < maxAttempts) {
    attempts += 1

    const minute = current.getMinutes()
    const hour = current.getHours()
    const dayOfMonth = current.getDate()
    const month = current.getMonth() + 1 // JS 月份从 0 开始
    let dayOfWeek = current.getDay() // 0-6，0 是周日

    // 在 Cron 里，通常 0 或 7 表示周日，这里我们统一用 0-6，周日为 0
    // 匹配时如果字段里写了 7，在验证阶段已经通过，所以这里仍按 7 处理

    const minuteMatch = matchCronField(minute, minuteField, 0, 59)
    const hourMatch = matchCronField(hour, hourField, 0, 23)
    const dayMatch = matchCronField(dayOfMonth, dayField, 1, 31)
    const monthMatch = matchCronField(month, monthField, 1, 12)

    // weekday 字段：0-6 或 0-7，这里按 0-6 处理，7 当作 0 已由校验保证
    const weekdayMatch = matchCronField(dayOfWeek, weekdayField, 0, 7)

    // 大多数 Cron 实现中，"日" 与 "周" 字段满足其一即可；这里采用相同策略：
    // - 如果 dayField 和 weekdayField 都是 '*'，则不限制
    // - 否则二者至少有一个匹配
    let dayAndWeekOk = true
    if (dayField !== '*' || weekdayField !== '*') {
      dayAndWeekOk = (dayField === '*' || dayMatch) || (weekdayField === '*' || weekdayMatch)
    }

    if (minuteMatch && hourMatch && monthMatch && dayAndWeekOk) {
      runs.push(current.toISOString())
    }

    // 前进到下一分钟
    current = new Date(current.getTime() + 60 * 1000)
  }

  return runs
}
