<template>
  <div class="page">
    <div class="page-header">
      <h2>定时任务详情</h2>
      <div class="page-actions">
        <a-button @click="handleBack">返回</a-button>
        <a-button type="outline" @click="handleRefresh">
          <template #icon><icon-refresh /></template>
          刷新
        </a-button>
        <a-button type="outline" @click="openHistory">
          <template #icon><icon-history /></template>
          历史记录
        </a-button>
        <a-button
          v-if="task.is_active"
          type="outline"
          status="warning"
          @click="handleToggleStatus"
          v-permission="{ resourceType: 'job', permission: 'change', resourceId: task?.id }"
        >
          <template #icon><icon-pause /></template>
          禁用
        </a-button>
        <a-button
          v-else
          type="outline"
          status="success"
          @click="handleToggleStatus"
          v-permission="{ resourceType: 'job', permission: 'change', resourceId: task?.id }"
        >
          <template #icon><icon-play-arrow /></template>
          启用
        </a-button>
        <a-button
          type="primary"
          @click="handleEdit"
          v-permission="{ resourceType: 'job', permission: 'change', resourceId: task?.id }"
        >
          <template #icon><icon-edit /></template>
          编辑
        </a-button>
      </div>
    </div>

    <a-spin :loading="loading" style="width: 100%">
      <a-row :gutter="16">
        <!-- 基本信息 -->
        <a-col :span="16">
          <a-card title="基本信息" class="detail-card">
            <a-descriptions :column="2" bordered>
              <a-descriptions-item label="任务名称">
                {{ task.name }}
              </a-descriptions-item>
              <a-descriptions-item label="状态">
                <a-tag v-if="task.is_active" color="green">启用</a-tag>
                <a-tag v-else color="red">禁用</a-tag>
              </a-descriptions-item>
              <a-descriptions-item label="执行方案">
                <a-link v-if="task.execution_plan" @click="handleViewPlan">
                  {{ task.plan_name || `方案ID: ${task.execution_plan}` }}
                </a-link>
                <span v-else>-</span>
              </a-descriptions-item>
              <a-descriptions-item label="模板名称">
                <a-link v-if="task.template_id" @click="handleViewTemplate">
                  {{ task.template_name || `模板ID: ${task.template_id}` }}
                </a-link>
                <span v-else>-</span>
              </a-descriptions-item>
              <a-descriptions-item label="Cron表达式">
                <code>{{ task.cron_expression }}</code>
              </a-descriptions-item>
              <a-descriptions-item label="时区">
                {{ task.timezone }}
              </a-descriptions-item>
              <a-descriptions-item label="创建人">
                {{ task.created_by_name }}
              </a-descriptions-item>
              <a-descriptions-item label="创建时间">
                {{ formatDateTime(task.created_at) }}
              </a-descriptions-item>
              <a-descriptions-item label="更新时间">
                {{ formatDateTime(task.updated_at) }}
              </a-descriptions-item>
              <a-descriptions-item label="下次执行时间">
                <span v-if="task.next_run_time">
                  {{ formatDateTime(task.next_run_time) }}
                </span>
                <span v-else style="color: #86909c">-</span>
              </a-descriptions-item>
            </a-descriptions>
            
            <div v-if="task.description" style="margin-top: 16px">
              <h4>描述</h4>
              <p>{{ task.description }}</p>
            </div>

            <GlobalVariablesPanel
              class="global-variables-section"
              :variables="effectiveVariables"
              title="执行变量"
              empty-text="暂无执行变量"
            />
          </a-card>
        </a-col>

        <!-- 统计信息 -->
        <a-col :span="8">
          <a-card title="执行统计" class="detail-card">
            <div class="stats-grid">
              <div class="stat-item">
                <div class="stat-value">{{ task.total_runs }}</div>
                <div class="stat-label">总执行次数</div>
              </div>
              <div class="stat-item">
                <div class="stat-value success">{{ task.success_runs }}</div>
                <div class="stat-label">成功次数</div>
              </div>
              <div class="stat-item">
                <div class="stat-value error">{{ task.failed_runs }}</div>
                <div class="stat-label">失败次数</div>
              </div>
              <div class="stat-item">
                <div class="stat-value">{{ task.success_rate }}%</div>
                <div class="stat-label">成功率</div>
              </div>
            </div>
            
            <div style="margin-top: 16px">
              <a-progress
                :percent="task.success_rate"
                :color="getProgressColor(task.success_rate)"
                size="large"
              />
            </div>
            
            <div v-if="task.last_run_time" style="margin-top: 16px">
              <h4>最后执行时间</h4>
              <p>{{ formatDateTime(task.last_run_time) }}</p>
            </div>
          </a-card>
        </a-col>
      </a-row>

      <!-- 执行历史 抽屉 -->
      <a-drawer
        v-model:visible="historyVisible"
        title="执行历史"
        width="70%"
        unmount-on-close
      >
        <div class="history-toolbar">
          <a-input
            v-model="historyFilters.keyword"
            allow-clear
            placeholder="搜索名称 / 执行ID"
            style="width: 240px"
            @press-enter="handleHistorySearch"
            @clear="handleHistorySearch"
          />
          <a-select
            v-model="historyFilters.status"
            allow-clear
            placeholder="状态"
            style="width: 140px"
            @change="handleHistorySearch"
            @clear="handleHistorySearch"
          >
            <a-option value="SUCCESS">成功</a-option>
            <a-option value="FAILED">失败</a-option>
            <a-option value="RUNNING">运行中</a-option>
            <a-option value="CANCELLED">已取消</a-option>
          </a-select>
        </div>

        <a-table
          :columns="historyColumns"
          :data="executionHistory"
          :loading="loadingHistory"
          :pagination="historyPagination"
          @page-change="handleHistoryPageChange"
          @page-size-change="handleHistoryPageSizeChange"
        >
          <template #status="{ record }">
            <a-tag v-if="record.status === 'SUCCESS'" color="green">成功</a-tag>
            <a-tag v-else-if="record.status === 'FAILED'" color="red">失败</a-tag>
            <a-tag v-else-if="record.status === 'RUNNING'" color="blue">运行中</a-tag>
            <a-tag v-else-if="record.status === 'CANCELLED'" color="orange">取消</a-tag>
            <a-tag v-else color="gray">{{ record.status }}</a-tag>
          </template>

          <template #duration="{ record }">
            <span v-if="record.duration">{{ formatDuration(record.duration) }}</span>
            <span v-else style="color: #86909c">-</span>
          </template>

          <template #actions="{ record }">
            <a-button
              type="text"
              size="small"
              @click="handleViewExecution(record)"
            >
              查看详情
            </a-button>
          </template>
        </a-table>
      </a-drawer>
    </a-spin>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Message, Modal } from '@arco-design/web-vue'
import type { TableColumnData } from '@arco-design/web-vue'
import {
  IconRefresh,
  IconEdit,
  IconPause,
  IconPlayArrow,
  IconHistory
} from '@arco-design/web-vue/es/icon'
import { scheduledJobApi } from '@/api/scheduler'
import { executionRecordApi } from '@/api/ops'
import GlobalVariablesPanel from '@/components/GlobalVariablesPanel.vue'

type ScheduledJob = {
  id: number
  name: string
  is_active: boolean
  cron_expression: string
  timezone: string
  next_run_time?: string
  description?: string
  total_runs?: number
  success_runs?: number
  failed_runs?: number
  success_rate?: number
  template_id?: number
  template_name?: string
  plan_name?: string
  execution_plan?: number
  execution_parameters?: Record<string, any>
  created_by_name?: string
  created_at?: string
  updated_at?: string
  last_run_time?: string
  [k: string]: any
}

type ExecutionHistoryItem = {
  id: number | string
  status: string
  start_time?: string
  end_time?: string
  duration?: number
  [k: string]: any
}

const route = useRoute()
const router = useRouter()

// 响应式数据
const loading = ref(false)
const loadingHistory = ref(false)
const historyVisible = ref(false)
const task = ref<ScheduledJob>({} as ScheduledJob)
const executionHistory = ref<ExecutionHistoryItem[]>([])

// 执行历史分页
const historyPagination = reactive({
  current: 1,
  pageSize: 10,
  total: 0,
  showTotal: true,
  showPageSize: true,
  pageSizeOptions: ['10', '20', '50']
})
const historyFilters = reactive({
  keyword: '',
  status: undefined as string | undefined
})

const effectiveVariables = computed(() => {
  return task.value?.execution_parameters || {}
})

// 执行历史表格列
const historyColumns: TableColumnData[] = [
  { title: '执行ID', dataIndex: 'execution_id', ellipsis: true, tooltip: true },
  { title: '名称', dataIndex: 'name', ellipsis: true, tooltip: true },
  { title: '状态', dataIndex: 'status', slotName: 'status', width: 100 },
  { title: '开始时间', dataIndex: 'started_at', width: 160 },
  { title: '结束时间', dataIndex: 'finished_at', width: 160 },
  { title: '耗时', dataIndex: 'duration', slotName: 'duration', width: 100 },
  { title: '操作', dataIndex: 'actions', slotName: 'actions', width: 120, fixed: 'right' }
]

// 获取任务详情
const fetchTask = async () => {
  loading.value = true
  try {
    const response = await scheduledJobApi.get(Number(route.params.id))
    task.value = response
  } catch (error) {
    console.error('获取任务详情失败:', error)
    Message.error('获取任务详情失败')
  } finally {
    loading.value = false
  }
}

// 获取执行历史
const fetchExecutionHistory = async () => {
  loadingHistory.value = true
  try {
    const params: any = {
      page: historyPagination.current,
      page_size: historyPagination.pageSize,
      scheduled_job_id: Number(route.params.id)  // 使用定时任务ID作为过滤条件
    }
    if (historyFilters.keyword) params.search = historyFilters.keyword
    if (historyFilters.status) params.status = historyFilters.status

    const response = await executionRecordApi.getRecords(params)
    executionHistory.value = response.results || []
    historyPagination.total = response.total || 0
  } catch (error) {
    console.error('获取执行历史失败:', error)
    Message.error('获取执行历史失败')
  } finally {
    loadingHistory.value = false
  }
}

// 处理函数
const handleBack = () => {
  router.push('/scheduled-tasks')
}

const handleRefresh = () => {
  fetchTask()
}

const handleEdit = () => {
  router.push(`/scheduled-tasks/${route.params.id}/edit`)
}

const handleToggleStatus = async () => {
  try {
    const action = task.value.is_active ? '禁用' : '启用'
    await Modal.confirm({
      title: `确认${action}任务`,
      content: `确定要${action}任务"${task.value.name}"吗？`,
      onOk: async () => {
        await scheduledJobApi.toggleStatus(Number(route.params.id), !task.value.is_active)
        Message.success(`${action}成功`)
        fetchTask()
      }
    })
  } catch (error) {
    console.error('切换任务状态失败:', error)
    Message.error('操作失败')
  }
}

const handleViewExecution = (record) => {
  router.push(`/execution-records/${record.id}`)
}

const handleViewPlan = () => {
  // if (!task.value || !task.value.execution_plan) return
  // router.push(`/execution-plans/detail/${task.value.execution_plan}`)
  if (!task.value || !task.value.execution_plan) return

  // 解析路由链接
  const routeUrl = router.resolve({
    path: `/execution-plans/detail/${task.value.execution_plan}`
  })

  // 在新标签页打开
  window.open(routeUrl.href, '_blank')
}

const handleViewTemplate = () => {
  // if (!task.value || !task.value.template_id) return
  // router.push(`/job-templates/detail/${task.value.template_id}`)
  if (!task.value || !task.value.template_id) return

  // 解析路由链接
  const routeUrl = router.resolve({
    path: `/job-templates/detail/${task.value.template_id}`
  })

  // 在新标签页打开
  window.open(routeUrl.href, '_blank')
}

const handleHistoryPageChange = (page: number | string) => {
  historyPagination.current = Number(page)
  fetchExecutionHistory()
}

const handleHistoryPageSizeChange = (pageSize: number | string) => {
  historyPagination.pageSize = Number(pageSize)
  historyPagination.current = 1
  fetchExecutionHistory()
}

const openHistory = () => {
  historyVisible.value = true
  historyPagination.current = 1
  fetchExecutionHistory()
}

const handleHistorySearch = () => {
  historyPagination.current = 1
  fetchExecutionHistory()
}

// 工具函数
const formatDateTime = (dateTime) => {
  if (!dateTime) return '-'
  return new Date(dateTime).toLocaleString('zh-CN')
}

const formatDuration = (seconds) => {
  if (!seconds) return '-'
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const secs = seconds % 60
  
  if (hours > 0) {
    return `${hours}h ${minutes}m ${secs}s`
  } else if (minutes > 0) {
    return `${minutes}m ${secs}s`
  } else {
    return `${secs}s`
  }
}

const getProgressColor = (percent) => {
  if (percent >= 90) return '#00b42a'
  if (percent >= 70) return '#ff7d00'
  return '#f53f3f'
}

// 生命周期
onMounted(() => {
  fetchTask()
  if (route.query.history === '1') {
    openHistory()
  }
})
</script>

<style scoped>
.page {
  padding: 16px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.page-header h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}

.page-actions {
  display: flex;
  gap: 12px;
}

.detail-card {
  margin-bottom: 16px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
  margin-bottom: 16px;
}

.global-variables-section {
  margin-top: 24px;
}

.stat-item {
  text-align: center;
  padding: 16px;
  background-color: #fafafa;
  border-radius: 6px;
}

.stat-value {
  font-size: 24px;
  font-weight: 600;
  margin-bottom: 4px;
}

.stat-value.success {
  color: #00b42a;
}

.stat-value.error {
  color: #f53f3f;
}

.stat-label {
  font-size: 12px;
  color: #86909c;
}

.history-toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
  align-items: center;
  flex-wrap: wrap;
}

/* 表格样式优化 */
:deep(.arco-table) {
  .arco-table-th {
    background-color: #fff;
  }
}
</style>
