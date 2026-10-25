<template>
  <div class="page">
    <div class="page-header">
      <h2>执行方案定时任务详情</h2>
      <div class="page-actions">
        <n-button @click="handleBack">返回</n-button>
        <n-button secondary @click="handleRefresh">
          <template #icon><RefreshCw  /></template>
          刷新
        </n-button>
        <n-button
          v-if="task.is_active" 
         type="warning"
          @click="handleToggleStatus"
          v-permission="{ resourceType: 'job', permission: 'change', resourceId: task?.id }"
        >
          <template #icon><Pause /></template>
          禁用
        </n-button>
        <n-button
          v-else 
         type="success"
          @click="handleToggleStatus"
          v-permission="{ resourceType: 'job', permission: 'change', resourceId: task?.id }"
        >
          <template #icon><Play /></template>
          启用
        </n-button>
        <n-button
          type="primary"
          @click="handleEdit"
          v-permission="{ resourceType: 'job', permission: 'change', resourceId: task?.id }"
        >
          <template #icon><Pencil  /></template>
          编辑
        </n-button>
      </div>
    </div>

    <div class="detail-body" :aria-busy="loading">
      <div v-if="loading" class="detail-loading">
        <n-spin size="medium" />
      </div>
      <div class="form-grid-row">
        <!-- 基本信息 -->
        <div class="form-grid-col" style="grid-column: span 16">
          <n-card title="基本信息" class="detail-card">
            <n-descriptions :column="2" bordered>
              <n-descriptions-item label="任务名称">
                {{ task.name }}
              </n-descriptions-item>
              <n-descriptions-item label="状态">
                <n-tag v-if="task.is_active" type="success">启用</n-tag>
                <n-tag v-else type="error">禁用</n-tag>
              </n-descriptions-item>
              <n-descriptions-item label="执行方案">
                <n-button text size="small" v-if="task.execution_plan" @click="handleViewPlan">
                  {{ task.plan_name || `方案ID: ${task.execution_plan}` }}
                </n-button>
                <span v-else>-</span>
              </n-descriptions-item>
              <n-descriptions-item label="模板名称">
                <n-button text size="small" v-if="task.template_id" @click="handleViewTemplate">
                  {{ task.template_name || `模板ID: ${task.template_id}` }}
                </n-button>
                <span v-else>-</span>
              </n-descriptions-item>
              <n-descriptions-item label="Cron表达式">
                <div class="cron-row">
                  <code>{{ task.cron_expression }}</code>
                  <n-tooltip>
                    <template #trigger>
                      <n-button
                        text
                        size="tiny"
                        class="cron-copy-btn"
                        :disabled="!task.cron_expression"
                        @click="handleCopyCron"
                      >
                        <template #icon><Copy /></template>
                      </n-button>
                    </template>
                    复制
                  </n-tooltip>
                </div>
              </n-descriptions-item>
              <n-descriptions-item label="时区">
                {{ task.timezone }}
              </n-descriptions-item>
              <n-descriptions-item label="创建人">
                {{ task.created_by_name }}
              </n-descriptions-item>
              <n-descriptions-item label="创建时间">
                {{ formatDateTime(task.created_at) }}
              </n-descriptions-item>
              <n-descriptions-item label="更新时间">
                {{ formatDateTime(task.updated_at) }}
              </n-descriptions-item>
              <n-descriptions-item label="最近执行结果">
                <n-tag
                  v-if="task.last_execution_status"
                  :type="getExecutionStatusColor(task.last_execution_status) as any"
                >
                  {{ getExecutionStatusText(task.last_execution_status) }}
                </n-tag>
                <span v-else style="color: #86909c">暂无</span>
              </n-descriptions-item>
            </n-descriptions>
            
            <div v-if="task.description" style="margin-top: 16px">
              <h4>描述</h4>
              <p>{{ task.description }}</p>
            </div>

            <ExecutionVariablesPanel
              :variables="effectiveVariables"
            />
          </n-card>
        </div>

        <!-- 统计信息 -->
        <div class="form-grid-col" style="grid-column: span 8">
          <n-card title="执行统计" class="detail-card">
            <div class="stats-grid">
              <div class="stat-item">
                <div class="stat-value">{{ task.total_runs ?? 0 }}</div>
                <div class="stat-label">总执行次数</div>
              </div>
              <div class="stat-item">
                <div class="stat-value success">{{ task.success_runs ?? 0 }}</div>
                <div class="stat-label">成功次数</div>
              </div>
              <div class="stat-item">
                <div class="stat-value error">{{ task.failed_runs ?? 0 }}</div>
                <div class="stat-label">失败次数</div>
              </div>
              <div class="stat-item">
                <div class="stat-value">{{ task.success_rate ?? 0 }}%</div>
                <div class="stat-label">成功率</div>
              </div>
            </div>
            
            <div style="margin-top: 16px">
              <n-progress
                type="line"
                :percentage="Number(task.success_rate ?? 0)"
                :color="getProgressColor(Number(task.success_rate ?? 0))"
                :height="10"
              />
            </div>
            
            <div v-if="task.last_execution_at" style="margin-top: 16px">
              <h4>最后执行时间</h4>
              <p>{{ formatDateTime(task.last_execution_at) }}</p>
            </div>
          </n-card>
        </div>
      </div>

    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { DataTableColumns } from 'naive-ui'
import { scheduledJobApi } from '@/api/scheduler'
import ExecutionVariablesPanel from '@/components/ExecutionVariablesPanel.vue'
import { NButton, NCard, NDescriptions, NDescriptionsItem, NProgress, NSpin, NTag, NTooltip, useDialog, useMessage } from 'naive-ui'
import { Copy, Pause, Pencil, Play, RefreshCw } from 'lucide-vue-next'

type ScheduledJob = {
  id: number
  name: string
  is_active: boolean
  cron_expression: string
  timezone: string
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
  last_execution_status?: string
  last_execution_at?: string
  [k: string]: any
}

const dialog = useDialog()
const message = useMessage()
const route = useRoute()
const router = useRouter()

// 响应式数据
const loading = ref(false)
const task = ref<ScheduledJob>({} as ScheduledJob)

const effectiveVariables = computed(() => {
  return task.value?.execution_parameters || {}
})

// 执行历史表格列
const historyColumns: DataTableColumns<any> = [
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
    message.error('获取任务详情失败')
  } finally {
    loading.value = false
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
    await dialog.warning({
      title: `确认${action}任务`,
      content: `确定要${action}任务"${task.value.name}"吗？`,
      onPositiveClick: async () => {
        await scheduledJobApi.toggleStatus(Number(route.params.id), !task.value.is_active)
        message.success(`${action}成功`)
        fetchTask()
      }
    })
  } catch (error) {
    console.error('切换任务状态失败:', error)
    message.error('操作失败')
  }
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

const handleCopyCron = async () => {
  const cron = task.value?.cron_expression
  if (!cron) {
    message.warning('Cron 表达式为空')
    return
  }
  try {
    await navigator.clipboard.writeText(cron)
    message.success('已复制')
  } catch (error) {
    try {
      const input = document.createElement('input')
      input.value = cron
      document.body.appendChild(input)
      input.select()
      document.execCommand('copy')
      document.body.removeChild(input)
      message.success('已复制')
    } catch (fallbackError) {
      console.error('复制失败:', fallbackError)
      message.error('复制失败')
    }
  }
}

// 工具函数
const formatDateTime = (dateTime) => {
  if (!dateTime) return '-'
  return new Date(dateTime).toLocaleString('zh-CN')
}

const getExecutionStatusText = (status?: string) => {
  const map: Record<string, string> = {
    pending: '等待中',
    running: '执行中',
    success: '成功',
    failed: '失败',
    cancelled: '已取消',
    timeout: '超时',
    paused: '已暂停',
    retrying: '重试中'
  }
  return status ? (map[status] || status) : '暂无'
}

const getExecutionStatusColor = (status?: string) => {
  const map: Record<string, string> = {
    pending: 'gray',
    running: 'blue',
    success: 'green',
    failed: 'red',
    cancelled: 'orange',
    timeout: 'red',
    paused: 'orange',
    retrying: 'purple'
  }
  return status ? (map[status] || 'gray') : 'gray'
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
})
</script>

<style scoped>
.page {
  padding: 16px;
}

.detail-body {
  position: relative;
  min-height: 240px;
}

.detail-loading {
  position: absolute;
  inset: 0;
  z-index: 2;
  display: grid;
  place-items: center;
  background: rgb(255 255 255 / 65%);
  pointer-events: none;
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

.cron-row {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.cron-copy-btn {
  padding: 0 4px;
  height: 22px;
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

</style>
