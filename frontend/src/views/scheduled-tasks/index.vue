<template>
  <div
    class="scheduled-tasks-page"
    v-page-permissions="{
      resourceType: 'job',
      permissions: ['view', 'add', 'change', 'delete', 'execute'],
      resourceIds: tasks.map(t => t.id)
    }"
  >
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-content">
        <div class="header-left">
          <h2>定时任务</h2>
          <p class="header-desc">创建和管理基于执行方案的定时调度任务</p>
        </div>
        <div class="header-right">
          <a-space>
            <a-button @click="handleRefresh">
              <template #icon>
                <icon-refresh />
              </template>
              刷新
            </a-button>
            <a-button
              type="primary"
              @click="handleCreate"
              v-permission="{ resourceType: 'job', permission: 'add' }"
            >
              <template #icon>
                <icon-plus />
              </template>
              新建任务
            </a-button>
          </a-space>
        </div>
      </div>
    </div>

    <!-- 搜索和筛选 -->
    <a-card class="mb-4">
      <a-form :model="searchForm" layout="inline">
        <a-form-item label="任务名称">
          <a-input
            v-model="searchForm.name"
            placeholder="请输入任务名称"
            allow-clear
            @press-enter="handleSearch"
            @clear="handleSearch"
            style="width: 200px"
          />
        </a-form-item>
        <a-form-item label="执行方案">
          <a-input
            v-model="searchForm.plan_name"
            placeholder="请输入执行方案名称"
            allow-clear
            @press-enter="handleSearch"
            @clear="handleSearch"
            style="width: 200px"
          />
        </a-form-item>
        <a-form-item label="状态">
          <a-select
            v-model="searchForm.is_active"
            placeholder="请选择状态"
            allow-clear
            @change="handleSearch"
            @clear="handleSearch"
            style="width: 120px"
          >
            <a-option :value="true">启用</a-option>
            <a-option :value="false">禁用</a-option>
          </a-select>
        </a-form-item>
        <a-form-item label="创建者">
          <a-select
            v-model="searchForm.created_by"
            placeholder="请输入创建者姓名"
            allow-clear
            show-search
            filter-option="false"
            @search="handleCreatorSearch"
            @change="handleSearch"
            @clear="handleSearch"
            style="width: 120px"
          >
            <a-option
              v-for="user in filteredCreators"
              :key="user.id"
              :value="user.id"
            >
              {{ user.name }}
            </a-option>
          </a-select>
        </a-form-item>
        <a-form-item>
          <a-button type="primary" @click="handleSearch">
            <template #icon><icon-search /></template>
            搜索
          </a-button>
          <a-button @click="handleReset">
            <template #icon><icon-refresh /></template>
            重置
          </a-button>
        </a-form-item>
      </a-form>
    </a-card>

    <!-- 任务列表 -->
    <a-card>
      <a-table
        :columns="columns"
        :data="tasks"
        :loading="loading"
        :pagination="pagination"
        :scroll="{ x: 1420 }"
        @page-change="handlePageChange"
        @page-size-change="handlePageSizeChange"
      >
        <template #status="{ record }">
          <a-tag v-if="record.is_active" color="green">启用</a-tag>
          <a-tag v-else color="red">禁用</a-tag>
        </template>

        <template #cron_expression="{ record }">
          <a-tooltip :content="getCronDescription(record.cron_expression)">
            <code>{{ record.cron_expression }}</code>
          </a-tooltip>
        </template>

        <template #success_rate="{ record }">
          <a-progress
            :percent="record.success_rate"
            :color="getProgressColor(record.success_rate)"
            size="small"
            :show-text="false"
          />
          <span style="margin-left: 8px">{{ record.success_rate }}%</span>
        </template>

        <template #execution_stats="{ record }">
          <div class="stats-cell">
            <div>总计: {{ record.total_runs }}</div>
            <div>成功: <span style="color: #00b42a">{{ record.success_runs }}</span></div>
            <div>失败: <span style="color: #f53f3f">{{ record.failed_runs }}</span></div>
          </div>
        </template>

        <template #next_run_time="{ record }">
          <span v-if="record.next_run_time">
            {{ formatDateTime(record.next_run_time) }}
          </span>
          <span v-else style="color: #86909c">-</span>
        </template>

        <template #created_at="{ record }">
          <div>
            <div>{{ formatDateTime(record.created_at) }}</div>
            <div style="color: #86909c; font-size: 12px">{{ record.created_by_name }}</div>
          </div>
        </template>

        <template #actions="{ record }">
          <a-space>
            <a-button type="text" size="small" @click="handleView(record)">
              <template #icon>
                <icon-eye />
              </template>
              查看
            </a-button>
            <a-button
              type="text"
              size="small"
              @click="handleEdit(record)"
              v-permission="{ resourceType: 'job', permission: 'change', resourceId: record.id }"
            >
              <template #icon>
                <icon-edit />
              </template>
              编辑
            </a-button>
            <a-dropdown>
              <a-button type="text" size="small">
                <template #icon>
                  <icon-more />
                </template>
              </a-button>
              <template #content>
                <a-doption
                  v-if="record.is_active"
                  :class="['text-orange-500', { 'disabled-option': !canChangeTask(record.id) }]"
                  @click="handleClickToggleStatus(record)"
                >
                  <template #icon>
                    <icon-pause />
                  </template>
                  禁用
                </a-doption>
                <a-doption
                  v-else
                  :class="['text-green-500', { 'disabled-option': !canChangeTask(record.id) }]"
                  @click="handleClickToggleStatus(record)"
                >
                  <template #icon>
                    <icon-play-arrow />
                  </template>
                  启用
                </a-doption>
                <a-doption
                  :class="['text-red-500', { 'disabled-option': !canDeleteTask(record.id) }]"
                  @click="handleClickDeleteTask(record)"
                >
                  <template #icon>
                    <icon-delete />
                  </template>
                  删除
                </a-doption>
              </template>
            </a-dropdown>
          </a-space>
        </template>
      </a-table>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { Message, Modal } from '@arco-design/web-vue'
import {
  IconRefresh,
  IconPlus,
  IconSearch,
  IconEye,
  IconEdit,
  IconDelete,
  IconPause,
  IconPlayArrow,
  IconMore
} from '@arco-design/web-vue/es/icon'
import { useRouter } from 'vue-router'
import { scheduledJobApi } from '@/api/scheduler'
import { usePermissionsStore } from '@/stores/permissions'
import type { ScheduledJob } from '@/types'

const router = useRouter()
const loading = ref(false)
const tasks = ref<ScheduledJob[]>([])
const permissionsStore = usePermissionsStore()

// 搜索表单
const searchForm = reactive({
  name: '',
  plan_name: '',
  is_active: undefined,
  created_by: undefined as number | undefined
})

// 可用用户列表（创建者）
const availableUsers = ref<Array<{id: number, username: string, name: string}>>([])

// 创建者搜索过滤结果
const filteredCreators = ref<Array<{id: number, username: string, name: string}>>([])

// 分页配置
const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  showTotal: true,
  showPageSize: true,
  pageSizeOptions: ['10', '20', '50', '100']
})

// 表格列配置
const columns = [
  {
    title: '任务名称',
    dataIndex: 'name',
    key: 'name',
    width: 150,
    ellipsis: true,
    tooltip: true
  },
  {
    title: '执行方案',
    dataIndex: 'plan_name',
    key: 'plan_name',
    width: 150,
    ellipsis: true,
    tooltip: true
  },
  {
    title: '模板名称',
    dataIndex: 'template_name',
    key: 'template_name',
    width: 150,
    ellipsis: true,
    tooltip: true
  },
  {
    title: '状态',
    dataIndex: 'is_active',
    key: 'status',
    slotName: 'status',
    width: 80,
    align: 'center'
  },
  {
    title: 'Cron表达式',
    dataIndex: 'cron_expression',
    key: 'cron_expression',
    slotName: 'cron_expression',
    width: 150
  },
  {
    title: '成功率',
    key: 'success_rate',
    slotName: 'success_rate',
    width: 120,
    align: 'center'
  },
  {
    title: '执行统计',
    key: 'execution_stats',
    slotName: 'execution_stats',
    width: 120,
    align: 'center'
  },
  {
    title: '下次执行',
    dataIndex: 'next_run_time',
    key: 'next_run_time',
    slotName: 'next_run_time',
    width: 150
  },
  {
    title: '创建信息',
    dataIndex: 'created_at',
    key: 'created_at',
    slotName: 'created_at',
    width: 150
  },
  {
    title: '操作',
    key: 'actions',
    slotName: 'actions',
    width: 250,
    fixed: 'right'
  }
]

// 获取可用用户列表（创建者）
const fetchAvailableUsers = async () => {
  try {
    // 从当前任务列表中提取唯一用户列表
    if (tasks.value.length > 0) {
      const userMap = new Map<number, { id: number; username: string; name: string }>()
      tasks.value.forEach(task => {
        if (task.created_by && task.created_by_name) {
          userMap.set(task.created_by, {
            id: task.created_by,
            username: task.created_by_name,
            name: task.created_by_name
          })
        }
      })
      availableUsers.value = Array.from(userMap.values()).sort((a, b) => a.name.localeCompare(b.name))
      // 初始化过滤结果为全部用户
      filteredCreators.value = [...availableUsers.value]
    }
  } catch (error) {
    console.error('获取用户列表失败:', error)
  }
}

// 处理创建者搜索
const handleCreatorSearch = (searchValue: string) => {
  if (!searchValue.trim()) {
    filteredCreators.value = [...availableUsers.value]
    return
  }

  const searchTerm = searchValue.toLowerCase().trim()
  filteredCreators.value = availableUsers.value.filter(user =>
    user.name.toLowerCase().includes(searchTerm) ||
    user.username.toLowerCase().includes(searchTerm)
  )
}

// 获取定时任务列表
const fetchTasks = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.current,
      page_size: pagination.pageSize,
      name: searchForm.name || undefined,
      plan_name: searchForm.plan_name || undefined,
      is_active: searchForm.is_active || undefined,
      created_by: searchForm.created_by || undefined,
    }

    // 过滤空值
    Object.keys(params).forEach(key => {
      if (params[key] === undefined ||
          (Array.isArray(params[key]) && params[key].length === 0)) {
        delete params[key]
      }
    })

    const response = await scheduledJobApi.list(params)
    tasks.value = response.results || []
    pagination.total = response.total || 0

    // 提取用户列表
    fetchAvailableUsers()
  } catch (error) {
    console.error('获取定时任务列表失败:', error)
  } finally {
    loading.value = false
  }
}

// 搜索
const handleSearch = (): void => {
  pagination.current = 1
  fetchTasks()
}

// 重置搜索
const handleReset = (): void => {
  Object.keys(searchForm).forEach(key => {
    searchForm[key] = key === 'is_active' || key === 'created_by' ? undefined : ''
  })
  // 重置创建者过滤
  filteredCreators.value = [...availableUsers.value]
  pagination.current = 1
  fetchTasks()
}

// 刷新
const handleRefresh = (): void => {
  fetchTasks()
}

// 分页处理
const handlePageChange = (page: number): void => {
  pagination.current = page
  fetchTasks()
}

const handlePageSizeChange = (pageSize: number): void => {
  pagination.pageSize = pageSize
  pagination.current = 1
  fetchTasks()
}

// 创建任务
const handleCreate = (): void => {
  router.push('/scheduled-tasks/create')
}

// 查看任务
const handleView = (record: ScheduledJob): void => {
  router.push(`/scheduled-tasks/detail/${record.id}`)
}

// 编辑任务
const handleEdit = (record: ScheduledJob): void => {
  router.push(`/scheduled-tasks/${record.id}/edit`)
}

// 切换任务状态
const handleToggleStatus = async (record: ScheduledJob): Promise<void> => {
  try {
    const action = record.is_active ? '禁用' : '启用'
    await Modal.confirm({
      title: `确认${action}任务`,
      content: `确定要${action}任务"${record.name}"吗？`,
      onOk: async () => {
        await scheduledJobApi.toggleStatus(record.id, !record.is_active)
        Message.success(`${action}成功`)
        fetchTasks()
      }
    })
  } catch (error) {
    console.error('切换任务状态失败:', error)
    // 错误消息已由HTTP拦截器处理，这里不再重复显示
  }
}

const handleClickToggleStatus = (record: ScheduledJob): void => {
  if (!canChangeTask(record.id)) {
    Message.warning('没有权限执行此操作，请联系管理员开放权限')
    return
  }
  handleToggleStatus(record)
}

// 删除任务
const handleDelete = async (record: ScheduledJob): Promise<void> => {
  try {
    await Modal.confirm({
      title: '确认删除',
      content: `确定要删除任务"${record.name}"吗？此操作不可恢复。`,
      onOk: async () => {
        await scheduledJobApi.delete(record.id)
        Message.success('删除成功')
        fetchTasks()
      }
    })
  } catch (error) {
    console.error('删除任务失败:', error)
  }
}

const handleClickDeleteTask = (record: ScheduledJob): void => {
  if (!canDeleteTask(record.id)) {
    Message.warning('没有权限执行此操作，请联系管理员开放权限')
    return
  }
  handleDelete(record)
}

// 工具函数
const formatDateTime = (dateTime: string): string => {
  if (!dateTime) return '-'
  return new Date(dateTime).toLocaleString('zh-CN')
}

const getCronDescription = (cronExpression: string): string => {
  // 简单的cron表达式描述
  const parts = cronExpression.split(' ')
  if (parts.length !== 5) return cronExpression

  const [minute, hour, day, month, weekday] = parts

  if (minute === '0' && hour !== '*' && day === '*' && month === '*' && weekday === '*') {
    return `每天${hour}点执行`
  }
  if (minute !== '*' && hour !== '*' && day === '*' && month === '*' && weekday === '*') {
    return `每天${hour}:${minute.padStart(2, '0')}执行`
  }
  return cronExpression
}

const getProgressColor = (percent: number): string => {
  if (percent >= 90) return '#00b42a'
  if (percent >= 70) return '#ff7d00'
  return '#f53f3f'
}

const canChangeTask = (taskId: number): boolean => {
  if (permissionsStore.isSuperUser) return true
  return (
    permissionsStore.hasPermission('job', 'change', taskId) ||
    permissionsStore.hasPermission('job', 'change')
  )
}

const canDeleteTask = (taskId: number): boolean => {
  if (permissionsStore.isSuperUser) return true
  return (
    permissionsStore.hasPermission('job', 'delete', taskId) ||
    permissionsStore.hasPermission('job', 'delete')
  )
}

// 生命周期
onMounted(() => {
  fetchTasks()
})
</script>

<style scoped>
.scheduled-tasks-page {
  padding: 0;
}

.page-header {
  background: white;
  border-radius: 6px;
  margin-bottom: 16px;
  padding: 20px 24px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.header-left h2 {
  margin: 0 0 4px 0;
  font-size: 20px;
  font-weight: 600;
  color: var(--color-text-1);
}

.header-desc {
  margin: 0;
  color: var(--color-text-3);
  font-size: 14px;
}

.mb-4 {
  margin-bottom: 16px;
}

.stats-cell {
  font-size: 12px;
  line-height: 1.4;
}

.stats-cell > div {
  margin-bottom: 2px;
}

.stats-cell > div:last-child {
  margin-bottom: 0;
}

.disabled-option {
  opacity: 0.5;
  cursor: not-allowed;
}

/* 表格样式优化 */
:deep(.arco-table) {
  .arco-table-th {
    background-color: #fff;
  }

  /* 隐藏表头的滚动条 */
  .arco-table-header {
    overflow-x: hidden !important;
  }

  /* 确保只有表体有滚动条 */
  .arco-table-body {
    overflow-x: auto;
  }
}
</style>
