<template>
  <div class="dashboard">
    <!-- 统计卡片 -->
    <a-row :gutter="16" class="stats-row">
      <a-col :span="6">
        <a-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon">
              <icon-file />
            </div>
            <div class="stat-info">
              <div class="stat-title">作业模板</div>
              <div class="stat-value clickable-value" @click="navigateToTemplates">{{ debugStats.templates }}</div>
              <div class="stat-desc">
                可用模板:{{ debugStats.templates }}
              </div>
            </div>
          </div>
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon">
              <icon-settings />
            </div>
            <div class="stat-info">
              <div class="stat-title">执行方案</div>
              <div class="stat-value clickable-value" @click="navigateToPlans">{{ debugStats.plans }}</div>
              <div class="stat-desc">
                可用方案:{{ debugStats.plans }}
              </div>
            </div>
          </div>
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon">
              <icon-schedule />
            </div>
            <div class="stat-info">
              <div class="stat-title">定时任务</div>
              <div class="stat-value clickable-value" @click="navigateToScheduledJobs">{{ debugStats.scheduledJobs }}</div>
              <div class="stat-desc">
                活跃:{{ debugStats.activeScheduledJobs }} | 总计:{{ debugStats.scheduledJobs }}
              </div>
            </div>
          </div>
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon">
              <icon-computer />
            </div>
            <div class="stat-info">
              <div class="stat-title">主机数量</div>
              <div class="stat-value clickable-value" @click="navigateToHosts">{{ debugStats.hosts }}</div>
              <div class="stat-desc">
                在线:{{ debugStats.onlineHosts }} | 离线:{{ debugStats.offlineHosts }}
              </div>
            </div>
          </div>
        </a-card>
      </a-col>
    </a-row>

    <!-- 任务执行趋势图表 -->
    <a-row :gutter="16" class="charts-row">
      <a-col :span="24">
        <a-card class="chart-card">
          <template #title>
            <div class="chart-header">
              <span class="chart-title">任务执行趋势</span>
              <div class="chart-filters">
                <a-space>
                  <a-select
                    v-model="trendFilters.timeRange"
                    placeholder="时间范围"
                    style="width: 120px"
                    @change="updateTrendChart"
                  >
                    <a-option value="today">今日</a-option>
                    <a-option value="week">本周</a-option>
                    <a-option value="month">本月</a-option>
                    <a-option value="custom">自定义</a-option>
                  </a-select>
                  <a-range-picker
                    v-if="trendFilters.timeRange === 'custom'"
                    v-model="trendFilters.dateRange"
                    @change="updateTrendChart"
                    style="width: 240px"
                  />
                  <a-select
                    v-model="trendFilters.planId"
                    placeholder="执行方案"
                    allow-clear
                    style="width: 200px"
                    @change="updateTrendChart"
                  >
                    <a-option
                      v-for="plan in executionPlans"
                      :key="plan.id"
                      :value="plan.id"
                    >
                      {{ plan.name }} ({{ plan.execution_count }}次)
                    </a-option>
                  </a-select>
                </a-space>
              </div>
            </div>
          </template>
          <div ref="executionTrendChart" class="chart-container"></div>
        </a-card>
      </a-col>
    </a-row>

    <!-- 执行成功率趋势图表 -->
    <a-row :gutter="16" class="charts-row">
      <a-col :span="24">
        <a-card class="chart-card">
          <template #title>
            <div class="chart-header">
              <span class="chart-title">执行成功率趋势</span>
              <div class="chart-filters">
                <a-space>
                  <a-select
                    v-model="successRateFilters.timeRange"
                    placeholder="时间范围"
                    style="width: 120px"
                    @change="updateSuccessRateChart"
                  >
                    <a-option value="today">今日</a-option>
                    <a-option value="week">本周</a-option>
                    <a-option value="month">本月</a-option>
                    <a-option value="custom">自定义</a-option>
                  </a-select>
                  <a-range-picker
                    v-if="successRateFilters.timeRange === 'custom'"
                    v-model="successRateFilters.dateRange"
                    @change="updateSuccessRateChart"
                    style="width: 240px"
                  />
                </a-space>
              </div>
            </div>
          </template>
          <div ref="successRateChart" class="chart-container"></div>
        </a-card>
      </a-col>
    </a-row>

    <!-- 任务执行Top20图表 -->
    <a-row :gutter="16" class="charts-row">
      <a-col :span="24">
        <a-card class="chart-card">
          <template #title>
            <div class="chart-header">
              <span class="chart-title">任务执行Top20</span>
              <div class="chart-filters">
                <a-space>
                  <a-select
                    v-model="topFilters.timeRange"
                    placeholder="时间范围"
                    style="width: 120px"
                    @change="updateTopChart"
                  >
                    <a-option value="today">今日</a-option>
                    <a-option value="week">本周</a-option>
                    <a-option value="month">本月</a-option>
                    <a-option value="custom">自定义</a-option>
                  </a-select>
                  <a-range-picker
                    v-if="topFilters.timeRange === 'custom'"
                    v-model="topFilters.dateRange"
                    @change="updateTopChart"
                    style="width: 240px"
                  />
                  <a-select
                    v-model="topFilters.sortBy"
                    placeholder="排序方式"
                    style="width: 120px"
                    @change="updateTopChart"
                  >
                    <a-option value="count">执行次数</a-option>
                    <a-option value="success_rate">成功率</a-option>
                    <a-option value="avg_duration">平均耗时</a-option>
                  </a-select>
                </a-space>
              </div>
            </div>
          </template>
          <div ref="topExecutionChart" class="chart-container"></div>
        </a-card>
      </a-col>
    </a-row>

    <!-- 其他图表 -->
    <a-row :gutter="16" class="charts-row">
      <a-col :span="8">
        <a-card class="chart-card">
          <template #title>
            <span class="chart-title">任务状态分布</span>
          </template>
          <div ref="statusDistributionChart" class="chart-container"></div>
        </a-card>
      </a-col>
      <a-col :span="8">
        <a-card class="chart-card">
          <template #title>
            <span class="chart-title">模板分类统计</span>
          </template>
          <div ref="templateCategoryChart" class="chart-container"></div>
        </a-card>
      </a-col>
      <a-col :span="8">
        <a-card class="chart-card">
          <template #title>
            <span class="chart-title">主机状态分布</span>
          </template>
          <div ref="hostStatusChart" class="chart-container"></div>
        </a-card>
      </a-col>
    </a-row>

    <!-- 热力图和其他图表 -->
    <a-row :gutter="16" class="charts-row">
      <a-col :span="24">
        <a-card class="chart-card">
          <template #title>
            <span class="chart-title">任务执行热力图</span>
          </template>
          <div ref="heatmapChart" class="chart-container"></div>
        </a-card>
      </a-col>
    </a-row>

    <!-- 最近活动 -->
    <a-row :gutter="16" class="activity-row">
      <a-col :span="12">
        <a-card class="activity-card">
          <template #title>
            <span class="chart-title">最近操作</span>
          </template>
          <div class="execution-list" v-loading="loadingExecutions">
            <div
              v-for="item in recentExecutions"
              :key="item.id"
              class="execution-item"
            >
              <div class="execution-avatar">
                <a-avatar :style="getStatusStyle(item.status)" size="small">
                  <icon-check v-if="item.status === 'SUCCESS'" />
                  <icon-close v-else-if="item.status === 'FAILURE'" />
                  <icon-loading v-else-if="item.status === 'RUNNING'" />
                  <icon-schedule v-else-if="item.status === 'PENDING'" />
                  <icon-settings v-else />
                </a-avatar>
              </div>
              <div class="execution-content">
                <div class="execution-header">
                  <span class="execution-name">{{ item.job_name }}</span>
                  <a-tag :color="getStatusColor(item.status)" size="small">
                    {{ getStatusText(item.status) }}
                  </a-tag>
                </div>
                <div class="execution-time">
                  {{ formatDateTime(item.start_time) }}
                </div>
              </div>
            </div>
          </div>
        </a-card>
      </a-col>
      <a-col :span="12">
        <a-card class="activity-card">
          <template #title>
            <span class="chart-title">系统状态</span>
          </template>
          <a-descriptions :column="1" bordered>
            <a-descriptions-item label="系统版本">
              <a-tag color="blue">v1.0.0</a-tag>
            </a-descriptions-item>
            <a-descriptions-item label="运行时间">
              {{ systemInfo.uptime }}
            </a-descriptions-item>
            <a-descriptions-item label="CPU使用率">
              <div style="display: flex; align-items: center; width: 100%;">
                <div style="flex: 1; height: 8px; background: #f0f0f0; border-radius: 4px; margin-right: 10px; overflow: hidden;">
                  <div :style="`width: ${Math.min(systemInfo.cpu, 100)}%; height: 100%; background: ${systemInfo.cpu > 80 ? '#ff4d4f' : systemInfo.cpu > 60 ? '#faad14' : '#52c41a'}; transition: width 0.3s ease;`"></div>
                </div>
                <span style="color: #666; min-width: 40px;">{{ systemInfo.cpu }}%</span>
              </div>
            </a-descriptions-item>
            <a-descriptions-item label="内存使用率">
              <div style="display: flex; align-items: center; width: 100%;">
                <div style="flex: 1; height: 8px; background: #f0f0f0; border-radius: 4px; margin-right: 10px; overflow: hidden;">
                  <div :style="`width: ${Math.min(systemInfo.memory, 100)}%; height: 100%; background: ${systemInfo.memory > 80 ? '#ff4d4f' : systemInfo.memory > 60 ? '#faad14' : '#52c41a'}; transition: width 0.3s ease;`"></div>
                </div>
                <span style="color: #666; min-width: 40px;">{{ systemInfo.memory }}%</span>
              </div>
            </a-descriptions-item>
            <a-descriptions-item label="磁盘使用率">
              <div style="display: flex; align-items: center; width: 100%;">
                <div style="flex: 1; height: 8px; background: #f0f0f0; border-radius: 4px; margin-right: 10px; overflow: hidden;">
                  <div :style="`width: ${Math.min(systemInfo.disk, 100)}%; height: 100%; background: ${systemInfo.disk > 80 ? '#ff4d4f' : systemInfo.disk > 60 ? '#faad14' : '#52c41a'}; transition: width 0.3s ease;`"></div>
                </div>
                <span style="color: #666; min-width: 40px;">{{ systemInfo.disk }}%</span>
              </div>
            </a-descriptions-item>
          </a-descriptions>
        </a-card>
      </a-col>
    </a-row>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import {
  IconFile,
  IconSettings,
  IconSchedule,
  IconComputer,
  IconCheck,
  IconClose,
  IconLoading,
  IconArrowUp,
  IconArrowDown
} from '@arco-design/web-vue/es/icon'
import * as echarts from 'echarts'
import { dashboardApi } from '@/api/dashboard'
import { Message } from '@arco-design/web-vue'

// 路由
const router = useRouter()

// 响应式数据
const stats = reactive({
  templates: 0,
  plans: 0,
  scheduledJobs: 0,
  activeScheduledJobs: 0,
  hosts: 0,
  onlineHosts: 0
})

// 统计数据的计算属性
const debugStats = computed(() => {
  return {
    templates: stats.templates,
    plans: stats.plans,
    scheduledJobs: stats.scheduledJobs,
    activeScheduledJobs: stats.activeScheduledJobs,
    hosts: stats.hosts,
    onlineHosts: stats.onlineHosts,
    offlineHosts: stats.hosts - stats.onlineHosts
  }
})

const recentExecutions = ref([])
const loadingExecutions = ref(false)
const loadingStats = ref(false)
const loadingSystemInfo = ref(false)
const executionPlans = ref([])
const loadingPlans = ref(false)

const systemInfo = reactive({
  uptime: '0天0小时',
  cpu: 0,
  memory: 0,
  disk: 0
})

// 图表引用
const executionTrendChart = ref()
const statusDistributionChart = ref()
const templateCategoryChart = ref()
const hostStatusChart = ref()
const successRateChart = ref()
const topExecutionChart = ref()
const heatmapChart = ref()

// 过滤器数据
const trendFilters = reactive({
  timeRange: 'week',
  dateRange: [],
  planId: ''  // 按执行方案过滤
})

const successRateFilters = reactive({
  timeRange: 'week',
  dateRange: []
})

const topFilters = reactive({
  timeRange: 'week',
  dateRange: [],
  sortBy: 'count'
})

// 获取统计数据
const fetchStats = async () => {
  loadingStats.value = true
  try {
    const content = await dashboardApi.getOverview()

    // 直接赋值，确保响应式更新
    const newTemplates = content.resources?.job_templates?.total || 0
    const newPlans = content.resources?.execution_plans?.total || 0
    const newScheduledJobs = content.scheduled_overview?.total || 0
    const newActiveScheduledJobs = content.scheduled_overview?.active || 0
    const newHosts = content.resources?.hosts?.total || 0
    const newOnlineHosts = content.resources?.hosts?.online || 0

    // 强制更新响应式数据
    stats.templates = newTemplates
    stats.plans = newPlans
    stats.scheduledJobs = newScheduledJobs
    stats.activeScheduledJobs = newActiveScheduledJobs
    stats.hosts = newHosts
    stats.onlineHosts = newOnlineHosts
  } catch (error) {
    console.error('获取统计数据失败:', error)
    Message.error('获取统计数据失败: ' + error.message)
  } finally {
    loadingStats.value = false
  }
}

// 获取最近执行记录
const fetchRecentExecutions = async () => {
  loadingExecutions.value = true
  try {
    const content = await dashboardApi.getRecentActivity()

    const activities = content.activities || []

      // 过滤出执行类型的活动
      const executionActivities = activities.filter(
        activity => activity.type === 'execution'
      ).slice(0, 5) // 只取前5条

      // 转换为前端需要的格式
      recentExecutions.value = executionActivities.map(activity => ({
        id: activity.id,
        job_name: activity.description || '未知任务',
        status: activity.status?.toUpperCase() || 'UNKNOWN',
        start_time: activity.created_at
      }))

      // 如果没有执行记录，显示所有活动
      if (executionActivities.length === 0) {
        recentExecutions.value = activities.slice(0, 5).map(activity => ({
          id: activity.id,
          job_name: activity.description || activity.action || '系统活动',
          status: 'INFO',
          start_time: activity.created_at
        }))
      }
  } catch (error) {
    console.error('获取执行记录失败:', error)
    Message.error('获取执行记录失败: ' + error.message)
  } finally {
    loadingExecutions.value = false
  }
}

// 获取系统信息
const fetchSystemInfo = async () => {
  loadingSystemInfo.value = true
  try {
    const systemData = await dashboardApi.getSystemStatus()
    const sysInfo = systemData.system_info || {}

    // 使用真实的系统信息
    systemInfo.cpu = Math.round(sysInfo.cpu_percent || 0)
    systemInfo.memory = Math.round(sysInfo.memory_percent || 0)
    systemInfo.disk = Math.round(sysInfo.disk_usage || 0)

    if (sysInfo.uptime) {
      systemInfo.uptime = sysInfo.uptime
    }
  } catch (error) {
    console.error('获取系统信息失败:', error)
    Message.error('获取系统信息失败: ' + error.message)
  } finally {
    loadingSystemInfo.value = false
  }
}

// 获取执行方案列表
const fetchExecutionPlans = async () => {
  loadingPlans.value = true
  try {
    const plans = await dashboardApi.getExecutionPlans()
    executionPlans.value = plans || []
  } catch (error) {
    console.error('获取执行方案列表失败:', error)
    Message.error('获取执行方案列表失败: ' + error.message)
  } finally {
    loadingPlans.value = false
  }
}

// 初始化图表
const initCharts = async () => {
  await nextTick()

  // 并行初始化所有图表，互不影响
  await Promise.allSettled([
    initExecutionTrendChart(),
    initStatusDistributionChart(),
    initTemplateCategoryChart(),
    initHostStatusChart(),
    initSuccessRateChart(),
    initTopExecutionChart(),
    initHeatmapChart()
  ])
}

// 执行趋势图
const initExecutionTrendChart = async () => {
  if (!executionTrendChart.value) return

  try {
    const chart = echarts.init(executionTrendChart.value)

    // 构建过滤器参数
    const params = {
      time_range: trendFilters.timeRange,
      plan_id: trendFilters.planId || undefined
    }

    // 如果是自定义时间范围，添加日期参数
    if (trendFilters.timeRange === 'custom' && trendFilters.dateRange && trendFilters.dateRange.length === 2) {
      // 格式化日期为 YYYY-MM-DD 格式
      const formatDate = (date) => {
        if (!date) return ''
        if (typeof date === 'string') return date
        if (date instanceof Date) {
          return date.toISOString().split('T')[0]
        }
        // 处理 moment 对象
        if (date.format) {
          return date.format('YYYY-MM-DD')
        }
        return date
      }
      params.start_date = formatDate(trendFilters.dateRange[0])
      params.end_date = formatDate(trendFilters.dateRange[1])
    }

    // 获取真实的执行趋势数据
    let data = [] // 默认空数据

    try {
      data = await dashboardApi.getExecutionTrend(params)

    } catch (error) {
      console.warn('获取执行趋势数据失败，使用空数据:', error)
      data = []
    }

    const dates = data.map(item => item.date)
    const totalData = data.map(item => item.total)
    const successData = data.map(item => item.success)
    const failedData = data.map(item => item.failed)

    // 计算Y轴最大值，确保有足够的空间显示数据
    const maxValue = Math.max(...totalData, ...successData, ...failedData)
    const yAxisMax = maxValue > 0 ? Math.ceil(maxValue * 1.1) : 10 // 给10%的缓冲空间，最小为10

    const option = {
      tooltip: { 
        animation: true,
        animationDuration: 1000,
        animationEasing: 'cubicInOut',
        animationDurationUpdate: 1000,
        animationEasingUpdate: 'cubicInOut',
        trigger: 'axis',
        backgroundColor: 'rgba(255, 255, 255, 0.95)',
        borderColor: '#e8e8e8',
        borderWidth: 1,
        // textStyle: { color: '#333', fontSize: 12 },
        textStyle: {
          fontSize: 14,
          color: 'rgba(0, 0, 0, 0.75)'
        },
        padding: [8, 12],
        shadowColor: 'rgba(0, 0, 0, 0.08)',
        shadowBlur: 16,
        shadowOffsetX: 0,
        shadowOffsetY: 4,
        extraCssText: 'box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);'
      },
      legend: { 
        data: ['成功', '失败'],
        top: 15,
        left: 'center',
        // textStyle: { color: '#666', fontSize: 14 },
        textStyle: {
          fontSize: 14,
          color: 'rgba(0, 0, 0, 0.75)'
        },
        itemGap: 20,
        itemWidth: 12,
        itemHeight: 8,
        icon: 'roundRect'
      },
      grid: {
        left: '5%',
        right: '5%',
        bottom: '8%',
        top: '20%',
        containLabel: true
      },
      xAxis: { 
        type: 'category', 
        data: dates,
        axisLine: { lineStyle: { color: '#e8e8e8' } },
        axisTick: { lineStyle: { color: '#e8e8e8' } },
        axisLabel: { color: '#666', fontSize: 11, margin: 8 }
      },
      yAxis: { 
        type: 'value',
        min: 0,
        max: yAxisMax,
        interval: Math.ceil(yAxisMax / 5), // 动态计算间隔，分成5个区间
        axisLine: { lineStyle: { color: '#e8e8e8' } },
        axisTick: { lineStyle: { color: '#e8e8e8' } },
        axisLabel: { color: '#666', fontSize: 12 },
        splitLine: { 
          show: true,
          lineStyle: { 
            color: '#f0f0f0',
            type: 'dashed',
            width: 1,
            opacity: 0.8
          }
        }
      },
      series: [
        { 
          name: '成功', 
          data: successData, 
          type: 'line', 
          smooth: true, 
          symbol: 'circle',
          symbolSize: 5,
          itemStyle: { color: '#52c41a' },
          lineStyle: { width: 2.5, color: '#52c41a' },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(82, 196, 26, 0.25)' },
                { offset: 1, color: 'rgba(82, 196, 26, 0.05)' }
              ]
            }
          }
        },
        { 
          name: '失败', 
          data: failedData, 
          type: 'line', 
          smooth: true, 
          symbol: 'circle',
          symbolSize: 5,
          itemStyle: { color: '#ff4d4f' },
          lineStyle: { width: 2.5, color: '#ff4d4f' },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(255, 77, 79, 0.25)' },
                { offset: 1, color: 'rgba(255, 77, 79, 0.05)' }
              ]
            }
          }
        }
      ]
    }
    chart.setOption(option)
  } catch (error) {
    console.error('初始化执行趋势图失败:', error)
  }
}

// 状态分布图
const initStatusDistributionChart = async () => {
  if (!statusDistributionChart.value) return

  try {
    const chart = echarts.init(statusDistributionChart.value)

    // 获取真实的状态分布数据
    let data = [] // 默认空数据

    try {
      const content = await dashboardApi.getStatusDistribution()

      // 为数据添加样式配置
      const statusColors = {
        'success': '#52c41a',
        'failed': '#ff4d4f',
        'running': '#1890ff',
        'pending': '#fa8c16',
        'cancelled': '#d9d9d9'
      }

      data = content.map(item => ({
        ...item,
        itemStyle: item.itemStyle || {
          color: statusColors[item.status] || '#d9d9d9'
        }
      }))
    } catch (error) {
      console.error('获取状态分布数据失败:', error)
      data = []
    }

    const option = {
      tooltip: { 
        trigger: 'item',
        backgroundColor: 'rgba(255, 255, 255, 0.9)',
        borderColor: '#e8e8e8',
        textStyle: { color: '#333' }
      },
      series: [{
        type: 'pie',
        radius: '70%',
        center: ['50%', '50%'],
        data: data,
        label: {
          show: true,
          position: 'outside',
          formatter: '{b}: {c} ({d}%)',
          color: '#666'
        },
        labelLine: {
          show: true,
          lineStyle: { color: '#e8e8e8' }
        }
      }]
    }
    chart.setOption(option)
  } catch (error) {
    console.error('初始化状态分布图失败:', error)
  }
}

// 模板分类图
const initTemplateCategoryChart = async () => {
  if (!templateCategoryChart.value) return

  try {
    const chart = echarts.init(templateCategoryChart.value)

    // 获取真实的模板分类数据
    let data = [] // 默认空数据

    try {
      const content = await dashboardApi.getTemplateCategoryStats()

      // 为数据添加样式配置
      const colors = ['#1890ff', '#52c41a', '#fa8c16', '#722ed1', '#eb2f96', '#13c2c2']

      data = content.map((item, index) => ({
        ...item,
        itemStyle: item.itemStyle || {
          color: colors[index % colors.length]
        }
      }))
    } catch (error) {
      console.warn('获取模板分类数据失败，使用空数据:', error)
    }

    const option = {
      tooltip: { trigger: 'item' },
      series: [{
        type: 'pie',
        radius: ['40%', '70%'],
        data: data
      }]
    }
    chart.setOption(option)
  } catch (error) {
    console.error('初始化模板分类图失败:', error)
  }
}

// 主机状态图
const initHostStatusChart = async () => {
  if (!hostStatusChart.value) return

  try {
    const chart = echarts.init(hostStatusChart.value)

    // 获取真实的主机状态数据
    let data = [] // 默认空数据

    try {
      const content = await dashboardApi.getHostStatusStats()

      // 为数据添加样式配置
      const statusColors = {
        'online': '#52c41a',
        'offline': '#ff4d4f',
        'error': '#fa541c',
        'unknown': '#d9d9d9'
      }

      data = content.map(item => ({
        ...item,
        itemStyle: item.itemStyle || {
          color: statusColors[item.status] || '#d9d9d9'
        }
      }))
    } catch (error) {
      console.warn('获取主机状态数据失败，使用空数据:', error)
    }

    const option = {
      tooltip: { trigger: 'item' },
      series: [{
        type: 'pie',
        radius: '60%',
        data: data
      }]
    }
    chart.setOption(option)
  } catch (error) {
    console.error('初始化主机状态图失败:', error)
  }
}

// 成功率趋势图
const initSuccessRateChart = async () => {
  if (!successRateChart.value) return

  try {
    // 构建过滤器参数
    const params = {
      time_range: successRateFilters.timeRange
    }

    // 如果是自定义时间范围，添加日期参数
    if (successRateFilters.timeRange === 'custom' && successRateFilters.dateRange && successRateFilters.dateRange.length === 2) {
      // 格式化日期为 YYYY-MM-DD 格式
      const formatDate = (date) => {
        if (!date) return ''
        if (typeof date === 'string') return date
        if (date instanceof Date) {
          return date.toISOString().split('T')[0]
        }
        // 处理 moment 对象
        if (date.format) {
          return date.format('YYYY-MM-DD')
        }
        return date
      }
      params.start_date = formatDate(successRateFilters.dateRange[0])
      params.end_date = formatDate(successRateFilters.dateRange[1])
    }

    // 获取真实的执行趋势数据
    const trendData = await dashboardApi.getExecutionTrend(params)

    // 计算每天的成功率
    const successRates = []
    const labels = []

    if (trendData && trendData.length > 0) {
      trendData.forEach(item => {
        labels.push(item.date)
        // 计算当天的成功率
        const successRate = item.total > 0 ? Math.round((item.success / item.total) * 100) : 0
        successRates.push(successRate)
      })
    } else {
      // 没有数据时显示默认标签和0值
      const defaultLabels = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
      labels.push(...defaultLabels)
      successRates.push(...new Array(7).fill(0))
    }

    const chart = echarts.init(successRateChart.value)
    const option = {
      tooltip: {
        trigger: 'axis',
        formatter: '{b}: {c}%'
      },
      xAxis: { type: 'category', data: labels },
      yAxis: { type: 'value', max: 100, axisLabel: { formatter: '{value}%' } },
      series: [{
        data: successRates,
        type: 'line',
        smooth: true,
        itemStyle: { color: '#52c41a' },
        areaStyle: { opacity: 0.3 }
      }]
    }
    chart.setOption(option)
  } catch (error) {
    console.error('获取成功率趋势数据失败:', error)
  }
}

// 热力图
const initHeatmapChart = async () => {
  if (!heatmapChart.value) return

  const chart = echarts.init(heatmapChart.value)

  // 时间轴数据 - 更美观的时间格式
  const hours = []
  const days = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
  for (let i = 0; i < 24; i++) {
    hours.push(String(i).padStart(2, '0') + ':00')
  }

  let data = []
  let maxValue = 0

  try {
    // 尝试获取真实的热力图数据
    const heatmapData = await dashboardApi.getExecutionHeatmap()
    data = heatmapData || []

    // 计算最大值用于颜色映射
    if (data.length > 0) {
      maxValue = Math.max(...data.map(item => item[2]))
    }
  } catch (error) {
    console.warn('获取热力图数据失败，使用空数据:', error)
    // 使用空数据而不是随机数据
    for (let i = 0; i < 7; i++) {
      for (let j = 0; j < 24; j++) {
        data.push([j, i, 0])
      }
    }
  }

  const option = {
    tooltip: {
      position: 'top',
      backgroundColor: 'rgba(50, 50, 50, 0.9)',
      borderColor: '#333',
      borderWidth: 1,
      textStyle: {
        color: '#fff',
        fontSize: 12
      },
      formatter: function (params) {
        const hour = hours[params.data[0]]
        const day = days[params.data[1]]
        const count = params.data[2]
        return `${day} ${hour}<br/>执行次数: <strong>${count}</strong>`
      }
    },
    grid: {
      height: '65%',
      top: '8%',
      left: '8%',
      right: '8%',
      bottom: '20%'
    },
    xAxis: {
      type: 'category',
      data: hours,
      position: 'top',
      splitArea: {
        show: true,
        areaStyle: {
          color: ['rgba(250,250,250,0.1)', 'rgba(200,200,200,0.1)']
        }
      },
      axisLine: {
        show: false
      },
      axisTick: {
        show: false
      },
      axisLabel: {
        fontSize: 11,
        color: '#666',
        interval: 1 // 显示所有标签
      }
    },
    yAxis: {
      type: 'category',
      data: days,
      splitArea: {
        show: true,
        areaStyle: {
          color: ['rgba(250,250,250,0.1)', 'rgba(200,200,200,0.1)']
        }
      },
      axisLine: {
        show: false
      },
      axisTick: {
        show: false
      },
      axisLabel: {
        fontSize: 12,
        color: '#333',
        fontWeight: 'bold'
      }
    },
    visualMap: {
      min: 0,
      max: Math.max(maxValue, 10),
      calculable: true,
      orient: 'horizontal',
      left: 'center',
      bottom: '5%',
      inRange: {
        color: ['#ebedf0', '#c6e48b', '#7bc96f', '#239a3b', '#196127']
      },
      text: ['高', '低'],
      textStyle: {
        color: '#666',
        fontSize: 11
      },
      itemWidth: 15,
      itemHeight: 15
    },
    series: [{
      type: 'heatmap',
      data: data,
      label: {
        show: true,
        fontSize: 10,
        color: '#333',
        formatter: function (params) {
          return params.data[2] > 0 ? params.data[2] : ''
        }
      },
      emphasis: {
        itemStyle: {
          shadowBlur: 10,
          shadowColor: 'rgba(0, 0, 0, 0.5)'
        }
      },
      itemStyle: {
        borderRadius: 2,
        borderWidth: 1,
        borderColor: '#fff'
      }
    }]
  }
  chart.setOption(option)
}

// 工具函数
const formatDateTime = (dateTime) => {
  if (!dateTime) return '-'
  return new Date(dateTime).toLocaleString('zh-CN')
}

const getStatusColor = (status) => {
  const colors = {
    'SUCCESS': 'green',
    'FAILURE': 'red',
    'RUNNING': 'blue',
    'PENDING': 'orange',
    'CANCELLED': 'gray',
    'INFO': 'purple',
    'UNKNOWN': 'gray'
  }
  return colors[status] || 'gray'
}

const getStatusText = (status) => {
  const texts = {
    'SUCCESS': '成功',
    'FAILURE': '失败',
    'RUNNING': '运行中',
    'PENDING': '等待中',
    'CANCELLED': '已取消',
    'INFO': '系统活动',
    'UNKNOWN': '未知操作'
  }
  return texts[status] || '未知操作'
}

const getStatusStyle = (status) => {
  const colors = {
    'SUCCESS': { backgroundColor: '#52c41a' },
    'FAILURE': { backgroundColor: '#ff4d4f' },
    'RUNNING': { backgroundColor: '#1890ff' },
    'PENDING': { backgroundColor: '#fa8c16' },
    'CANCELLED': { backgroundColor: '#d9d9d9' },
    'INFO': { backgroundColor: '#722ed1' },
    'UNKNOWN': { backgroundColor: '#8c8c8c' }
  }
  return colors[status] || { backgroundColor: '#8c8c8c' }
}

// 导航方法
const navigateToTemplates = () => {
  router.push('/job-templates')
}

const navigateToPlans = () => {
  router.push('/execution-plans')
}

const navigateToScheduledJobs = () => {
  router.push('/scheduled-tasks')
}

const navigateToHosts = () => {
  router.push('/hosts')
}

// 图表更新方法
const updateTrendChart = () => {
  // 重新初始化任务执行趋势图表
  initExecutionTrendChart()
}

const updateSuccessRateChart = () => {
  // 重新初始化成功率趋势图表
  initSuccessRateChart()
}

const updateTopChart = () => {
  // 重新初始化Top20图表
  initTopExecutionChart()
}

// 初始化Top20图表
const initTopExecutionChart = async () => {
  if (!topExecutionChart.value) return

  try {
    const chart = echarts.init(topExecutionChart.value)
    
    // 响应式处理
    const resizeHandler = () => {
      chart.resize()
    }
    window.addEventListener('resize', resizeHandler)
    
    // 组件卸载时移除监听器
    onUnmounted(() => {
      window.removeEventListener('resize', resizeHandler)
      chart.dispose()
    })

    // 构建过滤器参数
    const params = {
      time_range: topFilters.timeRange,
      sort_by: topFilters.sortBy
    }

    // 如果是自定义时间范围，添加日期参数
    if (topFilters.timeRange === 'custom' && topFilters.dateRange && topFilters.dateRange.length === 2) {
      // 格式化日期为 YYYY-MM-DD 格式
      const formatDate = (date) => {
        if (!date) return ''
        if (typeof date === 'string') return date
        if (date instanceof Date) {
          return date.toISOString().split('T')[0]
        }
        // 处理 moment 对象
        if (date.format) {
          return date.format('YYYY-MM-DD')
        }
        return date
      }
      params.start_date = formatDate(topFilters.dateRange[0])
      params.end_date = formatDate(topFilters.dateRange[1])
    }

    // 获取真实的Top20执行数据
    let data = []

    try {
      data = await dashboardApi.getTopExecutions(params)
    } catch (error) {
      console.error('获取Top20执行数据失败:', error)
    }

    // 根据排序方式排序数据
    let sortedData = [...data]
  if (topFilters.sortBy === 'success_rate') {
    sortedData.sort((a, b) => b.success_rate - a.success_rate)
  } else if (topFilters.sortBy === 'avg_duration') {
    sortedData.sort((a, b) => a.avg_duration - b.avg_duration)
  } else {
    sortedData.sort((a, b) => b.count - a.count)
  }

  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'shadow'
      },
      formatter: function(params) {
        const data = params[0]
        const item = sortedData[data.dataIndex]
        return `
          <div style="padding: 8px;">
            <div style="font-weight: bold; margin-bottom: 4px;">${item.name}</div>
            <div>执行次数: ${item.count}</div>
            <div>成功率: ${item.success_rate}%</div>
            <div>平均耗时: ${item.avg_duration}s</div>
          </div>
        `
      }
    },
    grid: {
      left: '8%',
      right: '8%',
      bottom: '8%',
      top: '5%',
      containLabel: true
    },
    xAxis: {
      type: 'value',
      name: topFilters.sortBy === 'success_rate' ? '成功率(%)' :
            topFilters.sortBy === 'avg_duration' ? '平均耗时(s)' : '执行次数',
      nameLocation: 'middle',
      nameGap: 30,
      nameTextStyle: {
        fontSize: 12,
        color: '#666'
      }
    },
    yAxis: {
      type: 'category',
      data: sortedData.map(item => item.name),
      axisLabel: {
        width: 120,
        overflow: 'truncate',
        ellipsis: '...',
        fontSize: 11,
        color: '#333',
        lineHeight: 16,
        formatter: function(value) {
          // 如果名称过长，截断并添加省略号
          if (value && value.length > 15) {
            return value.substring(0, 15) + '...'
          }
          return value || '未知任务'
        }
      },
      axisTick: {
        show: false
      },
      axisLine: {
        show: false
      }
    },
    series: [{
      type: 'bar',
      data: sortedData.map(item => {
        if (topFilters.sortBy === 'success_rate') {
          return item.success_rate
        } else if (topFilters.sortBy === 'avg_duration') {
          return item.avg_duration
        } else {
          return item.count
        }
      }),
      itemStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
          { offset: 0, color: '#83bff6' },
          { offset: 0.5, color: '#188df0' },
          { offset: 1, color: '#188df0' }
        ])
      },
      emphasis: {
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
            { offset: 0, color: '#2378f7' },
            { offset: 0.7, color: '#2378f7' },
            { offset: 1, color: '#83bff6' }
          ])
        }
      }
    }]
  }

  chart.setOption(option)
  } catch (error) {
    console.error('初始化Top20执行图失败:', error)
  }
}

// 刷新所有数据
const refreshAllData = async () => {
  await Promise.allSettled([
    fetchStats(),
    fetchRecentExecutions(),
    fetchSystemInfo(),
    fetchExecutionPlans(),
    initCharts()
  ])
}

// 生命周期
onMounted(async () => {
  await refreshAllData()
})
</script>

<style scoped>
.dashboard {
  padding: 20px;
}

.stats-row {
  margin-bottom: 20px;
}

.stat-card {
  border-radius: 4px;
  border: 1px solid #e8e8e8;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  transition: all 0.3s ease;
  overflow: hidden;
  background: white;
}

.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
}

.stat-content {
  display: flex;
  align-items: center;
  padding: 20px;
}

.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: 8px;
  background: #f5f5f5;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  margin-right: 16px;
  color: #333;
}

.stat-info {
  flex: 1;
  text-align: left;
}

.stat-title {
  font-size: 14px;
  color: #666;
  margin-bottom: 8px;
  font-weight: 500;
}

.stat-value {
  font-size: 28px;
  font-weight: 600;
  line-height: 1;
  margin-bottom: 8px;
  color: #333;
}

.stat-value.clickable-value {
  color: #1890ff;
  cursor: pointer;
  transition: all 0.3s ease;
  border-radius: 4px;
  padding: 2px 4px;
  margin-bottom: 8px;
  display: inline-block;
}

.stat-value.clickable-value:hover {
  color: #1890ff;
  background-color: transparent;
  transform: none;
}

.stat-value.clickable-value:active {
  color: #1890ff;
  background-color: transparent;
  transform: none;
}

.stat-desc {
  font-size: 12px;
  color: #999;
  line-height: 1.4;
}

.stat-trend {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  font-weight: 500;
}

.stat-trend.up {
  color: rgba(255, 255, 255, 0.9);
}

.stat-trend.down {
  color: rgba(255, 255, 255, 0.7);
}

.charts-row {
  margin-bottom: 20px;
}

.chart-card {
  height: 450px;
  transition: all 0.3s ease;
  border-radius: 4px;
  border: 1px solid #e8e8e8;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%);
  overflow: hidden;
}

.chart-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 8px 25px rgba(0, 0, 0, 0.15);
  border-color: #d9d9d9;
}

.chart-card .arco-card-header {
  background: linear-gradient(90deg, #f0f2f5 0%, #fafafa 100%);
  border-bottom: 2px solid #e8e8e8;
  padding: 16px 20px;
}

.chart-card .arco-card-header .arco-card-header-title {
  font-size: 16px;
  font-weight: 600;
  color: #262626;
  display: flex;
  align-items: center;
}

.chart-card .arco-card-header .arco-card-header-title::before {
  content: '';
  width: 4px;
  height: 18px;
  background: linear-gradient(135deg, #1890ff, #36cfc9);
  border-radius: 2px;
  margin-right: 10px;
}

.chart-container {
  height: 360px;
  width: 100%;
  padding: 10px;
}

.activity-row {
  margin-bottom: 20px;
}

.activity-card {
  height: 400px;
  transition: all 0.3s ease;
}

.activity-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
}

.execution-list {
  padding: 0;
}

.execution-item {
  display: flex;
  align-items: flex-start;
  padding: 12px 0;
  border-bottom: 1px solid var(--color-border-2);
  gap: 12px;
}

.execution-item:last-child {
  border-bottom: none;
}

.execution-avatar {
  flex-shrink: 0;
  margin-top: 2px;
}

.execution-content {
  flex: 1;
  min-width: 0;
}

.execution-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
  gap: 8px;
}

.execution-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text-1);
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.execution-time {
  font-size: 12px;
  color: var(--color-text-3);
  line-height: 1.4;
}

/* 图表头部样式 */
.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.chart-title {
  font-size: 16px;
  font-weight: 600;
  color: #262626;
  display: flex;
  align-items: center;
}

.chart-title::before {
  content: '';
  width: 4px;
  height: 18px;
  background: linear-gradient(135deg, #1890ff, #36cfc9);
  border-radius: 2px;
  margin-right: 10px;
}

.chart-filters {
  display: flex;
  align-items: center;
  gap: 8px;
}

.chart-filters .arco-select,
.chart-filters .arco-range-picker {
  font-size: 12px;
}
</style>
