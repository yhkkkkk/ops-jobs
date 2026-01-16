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

    <!-- 活动与收藏区域：我的收藏（左） + 最近执行（右） -->
    <a-row :gutter="24" class="activity-row" style="margin-top:12px;">
      <a-col :span="14">
        <a-card class="favorites-card">
          <template #title>
            <span class="chart-title">我的收藏</span>
          </template>
          <div v-loading="loadingFavorites">
            <div v-if="myFavorites.length === 0" class="text-gray-400">你还没有收藏任何项目</div>
            <a-list v-else bordered>
              <a-list-item v-for="item in myFavorites" :key="item.type + '-' + item.id">
                <div style="display: flex; justify-content: space-between; align-items: center; width: 100%">
                  <a @click="() => router.push(item.url)" style="flex: 1">{{ item.name }}</a>
                  <a-tag size="small" :color="getFavoriteTypeColor(item.type)">
                    {{ item.typeDisplay }}
                  </a-tag>
                </div>
              </a-list-item>
            </a-list>
          </div>
        </a-card>
      </a-col>

      <a-col :span="10">
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
            <div style="text-align:right;margin-top:8px">
              <a-button type="text" @click="() => router.push('/execution-records')">更多执行记录</a-button>
            </div>
          </div>
        </a-card>
      </a-col>
    </a-row>

  </div>
</template>

<script lang="ts" setup>
import { ref, reactive, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import {
  IconFile,
  IconSettings,
  IconSchedule,
  IconComputer,
  IconCheck,
  IconClose,
  IconLoading
} from '@arco-design/web-vue/es/icon'
import { dashboardApi } from '@/api/dashboard'
import { favoriteApi } from '@/api/ops'
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
const executionPlans = ref([])
const loadingPlans = ref(false)

// 我的收藏列表（展示少量常用收藏）
const myFavorites = ref([])
const loadingFavorites = ref(false)

const fetchFavorites = async () => {
  loadingFavorites.value = true
  try {
    // 获取所有类型的收藏（限制少量）
    const response = await favoriteApi.getFavorites({ page_size: 10 })
    const favItems = response.data?.results || response.data || response.results || response || []

    // 直接使用API返回的数据，包含名称和类型
    myFavorites.value = favItems.slice(0, 10).map(item => ({
      id: item.object_id,
      name: item.object_name || `${item.favorite_type_display} #${item.object_id}`,
      type: item.favorite_type,
      typeDisplay: item.favorite_type_display,
      url: getFavoriteUrl(item.favorite_type, item.object_id)
    }))
  } catch (e) {
    console.error('加载收藏失败:', e)
    myFavorites.value = []
  } finally {
    loadingFavorites.value = false
  }
}

// 根据收藏类型生成URL
const getFavoriteUrl = (favoriteType: string, objectId: number): string => {
  switch (favoriteType) {
    case 'job_template':
      return `/job-templates/detail/${objectId}`
    case 'script_template':
      return `/script-templates/detail/${objectId}`
    case 'execution_plan':
      return `/execution-plans/detail/${objectId}`
    default:
      return `/${favoriteType}s/detail/${objectId}`
  }
}

// 获取统计数据
const fetchStats = async () => {
  loadingStats.value = true
  try {
    const response = await dashboardApi.getOverview()
    const content = response.data || response

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
    const response = await dashboardApi.getRecentActivity()
    const content = response.data || response

    // content can be different shapes: array, { activities: [...] }, { results: [...] }
    let activities: any[] = []
    if (!content) {
      activities = []
    } else if (Array.isArray(content)) {
      activities = content
    } else if (Array.isArray(content.activities)) {
      activities = content.activities
    } else if (Array.isArray(content.results)) {
      activities = content.results
    } else if (Array.isArray(content.items)) {
      activities = content.items
    } else {
      // fallback: try to find any array-valued prop
      const arr = Object.values(content).find(v => Array.isArray(v))
      activities = Array.isArray(arr) ? arr : []
    }

    console.debug('dashboard: recent activities fetched', activities.length)

    // 过滤出执行类型的活动，最多10条
    const executionActivities = activities.filter((activity: any) => activity && activity.type === 'execution').slice(0, 10)

    if (executionActivities.length > 0) {
      recentExecutions.value = executionActivities.map((activity: any) => ({
        id: activity.id,
        job_name: activity.description || activity.action || '未知任务',
        status: (activity.status || '').toString().toUpperCase() || 'UNKNOWN',
        start_time: activity.created_at || activity.timestamp || activity.time
      }))
    } else {
      // 如果没有执行记录，显示最近的活动（最多10条）
      recentExecutions.value = activities.slice(0, 10).map((activity: any) => ({
        id: activity.id,
        job_name: activity.description || activity.action || '系统活动',
        status: 'INFO',
        start_time: activity.created_at || activity.timestamp || activity.time
      }))
    }
  } catch (error: any) {
    console.error('获取执行记录失败:', error)
    const errMsg = error?.message || '获取执行记录失败'
    Message.error(errMsg)
    recentExecutions.value = []
  } finally {
    loadingExecutions.value = false
  }
}

// 获取执行方案列表
const fetchExecutionPlans = async () => {
  loadingPlans.value = true
  try {
    const response = await dashboardApi.getExecutionPlans()
    const plans = response.data || response
    executionPlans.value = plans || []
  } catch (error) {
    console.error('获取执行方案列表失败:', error)
    Message.error('获取执行方案列表失败: ' + error.message)
  } finally {
    loadingPlans.value = false
  }
}


// 刷新所有数据
const refreshAllData = async () => {
  await Promise.allSettled([
    fetchStats(),
    fetchRecentExecutions(),
    fetchExecutionPlans(),
    fetchFavorites()
  ])
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

const navigateToScriptTemplates = () => {
  router.push('/script-templates')
}

// Helpers for execution status display
const getStatusColor = (status: string) => {
  const s = (status || '').toString().toUpperCase()
  if (s === 'SUCCESS') return 'green'
  if (s === 'FAILURE' || s === 'ERROR') return 'red'
  if (s === 'RUNNING') return 'blue'
  if (s === 'PENDING') return 'orange'
  return 'gray'
}

const getStatusText = (status: string) => {
  const s = (status || '').toString().toUpperCase()
  switch (s) {
    case 'SUCCESS': return '成功'
    case 'FAILURE':
    case 'ERROR': return '失败'
    case 'RUNNING': return '进行中'
    case 'PENDING': return '等待'
    default: return '未知'
  }
}

const getStatusStyle = (status: string) => {
  const color = getStatusColor(status)
  return {
    background: color,
    color: '#fff',
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center'
  }
}

const formatDateTime = (t: string | number | undefined) => {
  if (!t) return ''
  try {
    const d = new Date(t)
    return d.toLocaleString()
  } catch {
    return String(t)
  }
}

// 获取收藏类型标签颜色
const getFavoriteTypeColor = (type: string) => {
  const colorMap = {
    'job_template': 'blue',
    'script_template': 'green',
    'execution_plan': 'orange'
  }
  return colorMap[type] || 'gray'
}

// 生命周期
onMounted(async () => {
  try {
    await refreshAllData()
  } catch (e) {
    console.error('refreshAllData failed:', e)
  }
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

.quick-actions-row {
  margin-bottom: 20px;
}

.quick-actions-card {
  transition: all 0.3s ease;
}

.quick-actions-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
}

.quick-actions {
  padding: 20px;
  text-align: center;
}

.activity-row {
  margin-bottom: 20px;
}

.activity-card {
  height: 550px;
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