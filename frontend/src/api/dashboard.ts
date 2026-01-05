/**
 * Dashboard API
 */
import request from '@/utils/request'

export const dashboardApi = {
  // 获取概览数据
  getOverview() {
    return request({
      url: '/dashboard/overview/',
      method: 'get'
    })
  },

  // 获取统计数据
  getStatistics() {
    return request({
      url: '/dashboard/statistics/',
      method: 'get'
    })
  },

  // 获取最近活动
  getRecentActivity() {
    return request({
      url: '/dashboard/recent_activities/',
      method: 'get'
    })
  },

  // 获取系统状态
  getSystemStatus() {
    return request({
      url: '/dashboard/system_status/',
      method: 'get'
    })
  },

  // 获取执行趋势数据
  getExecutionTrend(params = {}) {
    return request({
      url: '/dashboard/execution_trend/',
      method: 'get',
      params
    })
  },

  // 获取任务状态分布
  getStatusDistribution() {
    return request({
      url: '/dashboard/status_distribution/',
      method: 'get'
    })
  },

  // 获取模板分类统计
  getTemplateCategoryStats() {
    return request({
      url: '/dashboard/template_category_stats/',
      method: 'get'
    })
  },

  // 获取主机状态统计
  getHostStatusStats() {
    return request({
      url: '/dashboard/host_status_stats/',
      method: 'get'
    })
  },

  // 获取执行热力图数据
  getExecutionHeatmap(params = {}) {
    return request({
      url: '/dashboard/execution_heatmap/',
      method: 'get',
      params
    })
  },

  // 运维台概览（Ops dashboard）
  getOpsOverview() {
    return request({
      url: '/dashboard/ops_overview/',
      method: 'get'
    })
  },

  // 获取Top20执行统计
  getTopExecutions(params = {}) {
    return request({
      url: '/dashboard/top_executions/',
      method: 'get',
      params
    })
  },

  // 获取执行方案列表
  getExecutionPlans() {
    return request({
      url: '/dashboard/execution_plans/',
      method: 'get'
    })
  }
,
  // 获取任务延时趋势（p50/p95）
  getLatencyTrend(params = {}) {
    return request({
      url: '/dashboard/ops_latency_trend/',
      method: 'get',
      params
    })
  }
}
