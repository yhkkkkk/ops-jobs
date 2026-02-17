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

            <ExecutionVariablesPanel
              :variables="effectiveVariables"
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

    </a-spin>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Message, Modal } from '@arco-design/web-vue'
import {
  IconRefresh,
  IconEdit,
  IconPause,
  IconPlayArrow
} from '@arco-design/web-vue/es/icon'
import { scheduledJobApi } from '@/api/scheduler'
import ExecutionVariablesPanel from '@/components/ExecutionVariablesPanel.vue'

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

const route = useRoute()
const router = useRouter()

// 响应式数据
const loading = ref(false)
const task = ref<ScheduledJob>({} as ScheduledJob)

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
