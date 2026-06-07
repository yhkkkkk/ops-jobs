<template>
  <div class="dashboard app-page">
    <div class="app-page-header">
      <div>
        <p class="app-page-eyebrow">JOB WORKSPACE</p>
        <h1 class="app-page-title">作业平台总览</h1>
        <p class="app-page-desc">
          聚合作业模板、执行方案、定时任务和主机覆盖情况，帮助值班人员快速判断今天该先处理什么。
        </p>
      </div>
      <a-space>
        <a-button @click="refreshAllData" :loading="loadingStats || loadingExecutions || loadingFavorites">
          刷新数据
        </a-button>
        <a-button type="primary" @click="() => router.push('/quick-execute')">
          快速执行
        </a-button>
      </a-space>
    </div>

    <div class="app-metric-grid">
      <button
        v-for="card in metricCards"
        :key="card.key"
        class="app-card app-metric-card metric-button"
        type="button"
        @click="card.onClick"
      >
        <div class="app-metric-top">
          <div>
            <p class="app-metric-label">{{ card.title }}</p>
            <div class="app-metric-value">{{ card.value }}</div>
          </div>
          <span class="app-metric-icon">
            <component :is="card.icon" />
          </span>
        </div>
        <p class="app-metric-note">{{ card.note }}</p>
      </button>
    </div>

    <div class="dashboard-grid">
      <a-card class="workflow-card" :bordered="false">
        <div class="app-section-title">
          <div>
            <h3>作业链路</h3>
            <p>从模板到执行记录的关键入口。</p>
          </div>
        </div>

        <div class="workflow-list">
          <button class="workflow-item" type="button" @click="navigateToScriptTemplates">
            <span class="workflow-index">01</span>
            <div>
              <strong>脚本模板</strong>
              <p>维护可复用脚本与版本。</p>
            </div>
          </button>
          <button class="workflow-item" type="button" @click="navigateToTemplates">
            <span class="workflow-index">02</span>
            <div>
              <strong>作业模板</strong>
              <p>组合脚本、文件分发和变量。</p>
            </div>
          </button>
          <button class="workflow-item" type="button" @click="navigateToPlans">
            <span class="workflow-index">03</span>
            <div>
              <strong>执行方案</strong>
              <p>绑定目标主机和执行策略。</p>
            </div>
          </button>
          <button class="workflow-item" type="button" @click="() => router.push('/execution-records')">
            <span class="workflow-index">04</span>
            <div>
              <strong>执行记录</strong>
              <p>审计、重试和结果回溯。</p>
            </div>
          </button>
        </div>
      </a-card>

      <a-card class="health-card" :bordered="false">
        <div class="app-section-title">
          <div>
            <h3>资源健康</h3>
            <p>基于当前主机与调度数据的轻量概览。</p>
          </div>
        </div>

        <div class="health-panel">
          <div class="health-number">{{ hostOnlineRate }}%</div>
          <div>
            <div class="health-title">主机在线率</div>
            <div class="health-desc">在线 {{ debugStats.onlineHosts }} 台 / 总计 {{ debugStats.hosts }} 台</div>
          </div>
        </div>
        <div class="health-bars">
          <div class="health-bar-row">
            <span>在线主机</span>
            <div class="bar-track">
              <div class="bar-fill success" :style="{ width: `${hostOnlineRate}%` }"></div>
            </div>
            <strong>{{ debugStats.onlineHosts }}</strong>
          </div>
          <div class="health-bar-row">
            <span>离线主机</span>
            <div class="bar-track">
              <div class="bar-fill muted" :style="{ width: `${offlineHostRate}%` }"></div>
            </div>
            <strong>{{ debugStats.offlineHosts }}</strong>
          </div>
          <div class="health-bar-row">
            <span>活跃调度</span>
            <div class="bar-track">
              <div class="bar-fill accent" :style="{ width: `${activeScheduleRate}%` }"></div>
            </div>
            <strong>{{ debugStats.activeScheduledJobs }}</strong>
          </div>
        </div>
      </a-card>
    </div>

    <div class="activity-grid">
      <a-card class="favorites-card" :bordered="false">
        <div class="app-section-title">
          <div>
            <h3>我的收藏</h3>
            <p>常用模板和方案入口。</p>
          </div>
        </div>
        <a-spin :loading="loadingFavorites" class="dashboard-spin">
          <div v-if="myFavorites.length === 0" class="app-empty">暂无收藏项目</div>
          <div v-else class="favorite-list">
            <button
              v-for="item in myFavorites"
              :key="item.type + '-' + item.id"
              class="favorite-item"
              type="button"
              @click="() => router.push(item.url)"
            >
              <span>{{ item.name }}</span>
              <a-tag size="small" :color="getFavoriteTypeColor(item.type)">
                {{ item.typeDisplay }}
              </a-tag>
            </button>
          </div>
        </a-spin>
      </a-card>

      <a-card class="activity-card" :bordered="false">
        <div class="app-section-title">
          <div>
            <h3>最近操作</h3>
            <p>最近执行与系统活动。</p>
          </div>
          <a-button type="text" size="small" @click="() => router.push('/execution-records')">
            查看全部
          </a-button>
        </div>
        <a-spin :loading="loadingExecutions" class="dashboard-spin">
        <div class="execution-list">
          <div v-if="recentExecutions.length === 0" class="app-empty">暂无最近操作</div>
          <template v-else>
            <div
              v-for="item in recentExecutions"
              :key="item.id"
              class="execution-item"
            >
              <div class="execution-avatar" :class="getStatusClass(item.status)">
                <icon-check v-if="item.status === 'SUCCESS'" />
                <icon-close v-else-if="item.status === 'FAILURE' || item.status === 'ERROR'" />
                <icon-loading v-else-if="item.status === 'RUNNING'" />
                <icon-schedule v-else-if="item.status === 'PENDING'" />
                <icon-settings v-else />
              </div>
              <div class="execution-content">
                <div class="execution-header">
                  <span class="execution-name">{{ item.job_name }}</span>
                  <span class="app-status-pill" :class="getStatusClass(item.status)">
                    {{ getStatusText(item.status) }}
                  </span>
                </div>
                <div class="execution-time">{{ formatDateTime(item.start_time) || '-' }}</div>
              </div>
            </div>
          </template>
        </div>
        </a-spin>
      </a-card>
    </div>
  </div>
</template>

<script lang="ts" setup>
import { ref, reactive, computed, onMounted } from 'vue'
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

const router = useRouter()

const stats = reactive({
  templates: 0,
  plans: 0,
  scheduledJobs: 0,
  activeScheduledJobs: 0,
  hosts: 0,
  onlineHosts: 0
})

const debugStats = computed(() => ({
  templates: stats.templates,
  plans: stats.plans,
  scheduledJobs: stats.scheduledJobs,
  activeScheduledJobs: stats.activeScheduledJobs,
  hosts: stats.hosts,
  onlineHosts: stats.onlineHosts,
  offlineHosts: Math.max(stats.hosts - stats.onlineHosts, 0)
}))

const hostOnlineRate = computed(() => {
  if (!debugStats.value.hosts) return 0
  return Math.round((debugStats.value.onlineHosts / debugStats.value.hosts) * 100)
})

const offlineHostRate = computed(() => Math.max(100 - hostOnlineRate.value, 0))

const activeScheduleRate = computed(() => {
  if (!debugStats.value.scheduledJobs) return 0
  return Math.round((debugStats.value.activeScheduledJobs / debugStats.value.scheduledJobs) * 100)
})

const recentExecutions = ref<any[]>([])
const loadingExecutions = ref(false)
const loadingStats = ref(false)
const executionPlans = ref<any[]>([])
const loadingPlans = ref(false)
const myFavorites = ref<any[]>([])
const loadingFavorites = ref(false)

const metricCards = computed(() => [
  {
    key: 'templates',
    title: '作业模板',
    value: debugStats.value.templates,
    note: '沉淀为标准化作业入口',
    icon: IconFile,
    onClick: navigateToTemplates
  },
  {
    key: 'plans',
    title: '执行方案',
    value: debugStats.value.plans,
    note: '可直接发起或调度的方案',
    icon: IconSettings,
    onClick: navigateToPlans
  },
  {
    key: 'scheduled',
    title: '定时任务',
    value: debugStats.value.scheduledJobs,
    note: `活跃 ${debugStats.value.activeScheduledJobs} 个`,
    icon: IconSchedule,
    onClick: navigateToScheduledJobs
  },
  {
    key: 'hosts',
    title: '主机覆盖',
    value: debugStats.value.hosts,
    note: `在线 ${debugStats.value.onlineHosts} 台，离线 ${debugStats.value.offlineHosts} 台`,
    icon: IconComputer,
    onClick: navigateToHosts
  }
])

const fetchFavorites = async () => {
  loadingFavorites.value = true
  try {
    const response: any = await favoriteApi.getFavorites({ page_size: 10 })
    const favItems = response.data?.results || response.data || response.results || response || []

    myFavorites.value = favItems.slice(0, 10).map((item: any) => ({
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

const fetchStats = async () => {
  loadingStats.value = true
  try {
    const response: any = await dashboardApi.getOverview()
    const content = response.data || response

    stats.templates = content.resources?.job_templates?.total || 0
    stats.plans = content.resources?.execution_plans?.total || 0
    stats.scheduledJobs = content.scheduled_overview?.total || 0
    stats.activeScheduledJobs = content.scheduled_overview?.active || 0
    stats.hosts = content.resources?.hosts?.total || 0
    stats.onlineHosts = content.resources?.hosts?.online || 0
  } catch (error) {
    console.error('获取统计数据失败:', error)
    Message.error(`获取统计数据失败: ${error instanceof Error ? error.message : String(error)}`)
  } finally {
    loadingStats.value = false
  }
}

const fetchRecentExecutions = async () => {
  loadingExecutions.value = true
  try {
    const response: any = await dashboardApi.getRecentActivity()
    const content = response.data || response

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
      const arr = Object.values(content).find(v => Array.isArray(v))
      activities = Array.isArray(arr) ? arr : []
    }

    const executionActivities = activities.filter((activity: any) => activity && activity.type === 'execution').slice(0, 10)

    if (executionActivities.length > 0) {
      recentExecutions.value = executionActivities.map((activity: any) => ({
        id: activity.id,
        job_name: activity.description || activity.action || '未知任务',
        status: (activity.status || '').toString().toUpperCase() || 'UNKNOWN',
        start_time: activity.created_at || activity.timestamp || activity.time
      }))
    } else {
      recentExecutions.value = activities.slice(0, 10).map((activity: any) => ({
        id: activity.id,
        job_name: activity.description || activity.action || '系统活动',
        status: 'INFO',
        start_time: activity.created_at || activity.timestamp || activity.time
      }))
    }
  } catch (error: any) {
    console.error('获取执行记录失败:', error)
    Message.error(error?.message || '获取执行记录失败')
    recentExecutions.value = []
  } finally {
    loadingExecutions.value = false
  }
}

const fetchExecutionPlans = async () => {
  loadingPlans.value = true
  try {
    const response: any = await dashboardApi.getExecutionPlans()
    executionPlans.value = response.data || response || []
  } catch (error) {
    console.error('获取执行方案列表失败:', error)
    Message.error(`获取执行方案列表失败: ${error instanceof Error ? error.message : String(error)}`)
  } finally {
    loadingPlans.value = false
  }
}

const refreshAllData = async () => {
  await Promise.allSettled([
    fetchStats(),
    fetchRecentExecutions(),
    fetchExecutionPlans(),
    fetchFavorites()
  ])
}

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

const getStatusColor = (status: string) => {
  const s = (status || '').toString().toUpperCase()
  if (s === 'SUCCESS') return 'green'
  if (s === 'FAILURE' || s === 'ERROR') return 'red'
  if (s === 'RUNNING') return 'blue'
  if (s === 'PENDING') return 'orange'
  return 'gray'
}

const getStatusClass = (status: string) => {
  const s = (status || '').toString().toUpperCase()
  if (s === 'SUCCESS') return 'app-status-success'
  if (s === 'FAILURE' || s === 'ERROR') return 'app-status-danger'
  if (s === 'RUNNING' || s === 'PENDING') return 'app-status-warn'
  return 'app-status-muted'
}

const getStatusText = (status: string) => {
  const s = (status || '').toString().toUpperCase()
  switch (s) {
    case 'SUCCESS': return '成功'
    case 'FAILURE':
    case 'ERROR': return '失败'
    case 'RUNNING': return '进行中'
    case 'PENDING': return '等待'
    case 'INFO': return '活动'
    default: return '未知'
  }
}

const formatDateTime = (t: string | number | undefined) => {
  if (!t) return ''
  try {
    return new Date(t).toLocaleString()
  } catch {
    return String(t)
  }
}

const getFavoriteTypeColor = (type: string) => {
  const colorMap: Record<string, string> = {
    job_template: 'blue',
    script_template: 'green',
    execution_plan: 'orange'
  }
  return colorMap[type] || 'gray'
}

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
  padding: 0;
}

.metric-button {
  width: 100%;
  border: 1px solid var(--app-border);
  text-align: left;
}

.dashboard-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(320px, 0.85fr);
  gap: 20px;
}

.workflow-card,
.health-card,
.favorites-card,
.activity-card {
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-md);
  background: var(--app-surface);
  box-shadow: var(--app-shadow-sm);
}

.workflow-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.workflow-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  width: 100%;
  padding: 16px;
  color: var(--app-fg);
  background: var(--app-surface-soft);
  border: 1px solid transparent;
  border-radius: var(--app-radius-sm);
  text-align: left;
  cursor: pointer;
  transition: border-color 160ms ease, background 160ms ease;
}

.workflow-item:hover {
  background: var(--app-accent-soft);
  border-color: color-mix(in srgb, var(--app-accent) 28%, var(--app-border));
}

.workflow-index {
  color: var(--app-accent);
  font-family: var(--app-mono);
  font-size: 12px;
  font-weight: 700;
}

.workflow-item strong {
  display: block;
  font-size: 14px;
  line-height: 1.4;
}

.workflow-item p {
  margin: 4px 0 0;
  color: var(--app-muted);
  font-size: 12px;
  line-height: 1.5;
}

.health-panel {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px;
  background: var(--app-surface-soft);
  border-radius: var(--app-radius-sm);
}

.health-number {
  color: var(--app-accent);
  font-family: var(--app-mono);
  font-size: 40px;
  line-height: 1;
  font-weight: 750;
}

.health-title {
  color: var(--app-fg);
  font-size: 14px;
  font-weight: 650;
}

.health-desc {
  margin-top: 4px;
  color: var(--app-muted);
  font-size: 12px;
}

.health-bars {
  display: grid;
  gap: 12px;
  margin-top: 18px;
}

.health-bar-row {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr) 40px;
  align-items: center;
  gap: 12px;
  color: var(--app-muted);
  font-size: 12px;
}

.health-bar-row strong {
  color: var(--app-fg);
  font-family: var(--app-mono);
  text-align: right;
}

.bar-track {
  height: 8px;
  overflow: hidden;
  background: var(--app-surface-muted);
  border-radius: 999px;
}

.bar-fill {
  height: 100%;
  min-width: 4px;
  border-radius: inherit;
}

.bar-fill.success {
  background: var(--app-success);
}

.bar-fill.muted {
  background: var(--app-meta);
}

.bar-fill.accent {
  background: var(--app-accent);
}

.activity-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(360px, 0.9fr);
  gap: 20px;
}

.dashboard-spin {
  display: block;
  width: 100%;
}

.favorite-list {
  display: grid;
  gap: 8px;
}

.favorite-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 12px 0;
  color: var(--app-fg);
  background: transparent;
  border: 0;
  border-bottom: 1px solid var(--app-border);
  text-align: left;
  cursor: pointer;
}

.favorite-item:last-child {
  border-bottom: 0;
}

.favorite-item span:first-child {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.execution-list {
  display: grid;
}

.execution-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 13px 0;
  border-bottom: 1px solid var(--app-border);
}

.execution-item:last-child {
  border-bottom: 0;
}

.execution-avatar {
  display: inline-flex;
  width: 28px;
  height: 28px;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  border-radius: 999px;
  font-size: 14px;
}

.execution-content {
  min-width: 0;
  flex: 1;
}

.execution-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.execution-name {
  min-width: 0;
  overflow: hidden;
  color: var(--app-fg);
  font-size: 14px;
  font-weight: 550;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.execution-time {
  margin-top: 4px;
  color: var(--app-meta);
  font-family: var(--app-mono);
  font-size: 12px;
}

@media (max-width: 1180px) {
  .dashboard-grid,
  .activity-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .workflow-list {
    grid-template-columns: 1fr;
  }

  .health-panel {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
