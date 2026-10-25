<template>
  <div
    class="app-page scheduled-tasks-page"
    v-page-permissions="{
      resourceType: 'job',
      permissions: ['view', 'add', 'change', 'delete', 'execute'],
      resourceIds: tasks.map(t => t.id)
    }"
  >
    <PageHeader
      eyebrow="调度任务"
      title="执行方案定时任务"
      description="创建和管理执行方案定时任务，跟踪最近执行结果和稳定性。"
    >
      <template #actions>
        <n-space>
          <n-button @click="handleRefresh">
            <template #icon>
              <RefreshCw  />
            </template>
            刷新
          </n-button>
          <n-button
            type="primary"
            @click="handleCreate"
            v-permission="{ resourceType: 'job', permission: 'add' }"
          >
            <template #icon>
              <Plus  />
            </template>
            新建任务
          </n-button>
        </n-space>
      </template>
    </PageHeader>

    <DataToolbar
      title="筛选执行方案定时任务"
      description="按任务、执行方案、状态和维护人定位调度配置。"
      :active-count="scheduledTaskActiveFilterCount"
    >
      <div class="app-filter-grid">
        <n-input
          v-model:value="searchForm.name"
          placeholder="任务名称"
          clearable
          @press-enter="handleSearch"
          @clear="handleSearch"
        />
        <n-input
          v-model:value="searchForm.plan_name"
          placeholder="执行方案"
          clearable
          @press-enter="handleSearch"
          @clear="handleSearch"
        />
        <n-select
          :value="(searchForm.is_active as any)"
          placeholder="状态"
          clearable
          :options="[{ label: '启用', value: true }, { label: '停用', value: false }] as any"
          @update:value="(v: any) => { searchForm.is_active = v; handleSearch() }"
        />
        <n-select
          v-model:value="searchForm.created_by"
          placeholder="创建者"
          clearable
          filterable
          remote
          :options="(filteredCreators || []).map((u: any) => ({ label: u.name, value: u.id }))"
          @search="handleCreatorSearch"
          @update:value="handleSearch"
        />
        <n-select
          v-model:value="searchForm.updated_by"
          placeholder="更新者"
          clearable
          filterable
          remote
          :options="(filteredUpdaters || []).map((u: any) => ({ label: u.name, value: u.id }))"
          @search="handleUpdaterSearch"
          @update:value="handleSearch"
        />
        <div class="app-filter-grid__actions">
          <n-space>
            <n-button type="primary" @click="handleSearch">
              <template #icon><Search  /></template>
              搜索
            </n-button>
            <n-button @click="handleReset">
              <template #icon><RefreshCw  /></template>
              重置
            </n-button>
          </n-space>
        </div>
      </div>
      <ActiveFiltersBar
        :items="activeFilterItems"
        @clear="handleClearFilter"
        @clear-all="handleReset"
      />
    </DataToolbar>

    <DetailPanel
      title="任务列表"
      :description="`共 ${pagination.total} 个任务，当前页 ${tasks.length} 个`"
    >
      <n-data-table
        class="schedule-data-table"
        :columns="columns"
        :data="tasks"
        :loading="loading"
        :pagination="tablePagination"
        remote
      />
    </DetailPanel>

    <!-- 历史记录抽屉 -->
      <n-drawer
        v-model:show="historyVisible"
        :title="currentHistoryJob ? `执行历史 - ${currentHistoryJob.name}` : '执行历史'"
        width="70%"
       
      ><n-drawer-content>
      <div class="history-toolbar">
        <n-input
          v-model:value="historyFilters.keyword"
          clearable
          placeholder="搜索名称 / 执行ID"
          style="width: 240px"
          @press-enter="handleHistorySearch"
          @clear="handleHistorySearch"
        />
                <n-select
          v-model:value="historyFilters.status"
          clearable
          placeholder="状态"
          style="width: 140px"
          @change="handleHistorySearch"
          @clear="handleHistorySearch" :options="selectOptions1" />
                <n-select
          v-model:value="historyFilters.quick_range"
          clearable
          placeholder="时间范围"
          style="width: 140px"
          @change="handleQuickRangeChange"
          @clear="handleQuickRangeClear" :options="selectOptions2" />
        <n-date-picker
          v-model:formatted-value="historyFilters.range"
          type="datetimerange"
          style="width: 320px"
          value-format="yyyy-MM-dd HH:mm:ss"
          clearable
          @change="handleRangeChange"
        />
      </div>

      <n-data-table
        :columns="historyTableColumns"
        :data="historyRecords"
        :loading="historyLoading"
        :pagination="historyTablePagination"
        remote
      />
    </n-drawer-content></n-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { scheduledJobApi } from '@/api/scheduler'
import { executionRecordApi } from '@/api/ops'
import { usePermissionsStore } from '@/stores/permissions'
import type { ScheduledJob } from '@/types'
import MetaInfoLines from '@/components/MetaInfoLines.vue'
import ActiveFiltersBar from '@/components/ActiveFiltersBar.vue'
import { useFilterQuerySync, parseBooleanQuery, parseNumberQuery, toBooleanQuery } from '@/composables/useFilterQuerySync'
import { DataToolbar, DetailPanel, PageHeader, countActiveFilters } from '@/components/app'
import { NButton, NDataTable, NDrawer, NDrawerContent, NDropdown, NInput, NProgress, NSelect, NSpace, NTag, NTooltip, type DataTableColumns, useDialog, useMessage } from 'naive-ui'
import { CirclePause, Eye, History, MoreHorizontal, PauseCircle, Pencil, Play, Plus, RefreshCw, Search, Trash2 } from 'lucide-vue-next'

const dialog = useDialog()
const message = useMessage()
const router = useRouter()
const loading = ref(false)
const tasks = ref<ScheduledJob[]>([])
const permissionsStore = usePermissionsStore()
const historyVisible = ref(false)
const historyLoading = ref(false)
const historyRecords = ref<any[]>([])
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
  status: undefined as string | undefined,
  quick_range: '' as string | undefined,
  range: [] as string[],
  start_date: '' as string,
  end_date: '' as string
})
const currentHistoryJob = ref<ScheduledJob | null>(null)

const defaultSearchForm = () => ({
  name: '',
  plan_name: '',
  is_active: undefined as boolean | undefined,
  created_by: undefined as number | undefined,
  updated_by: undefined as number | undefined
})

// 搜索表单
const searchForm = reactive(defaultSearchForm())

// 可用用户列表（创建者）
const availableUsers = ref<Array<{id: number, username: string, name: string}>>([])

// 创建者搜索过滤结果
const filteredCreators = ref<Array<{id: number, username: string, name: string}>>([])

// 更新者搜索过滤结果
const filteredUpdaters = ref<Array<{id: number, username: string, name: string}>>([])

// 排序
const ordering = ref('')

// 分页配置
const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  showTotal: true,
  showPageSize: true,
  pageSizeOptions: ['10', '20', '50', '100']
})

const { initFromQuery, syncToQuery } = useFilterQuerySync({
  searchForm,
  pagination,
  ordering,
  fields: [
    { key: 'name' },
    { key: 'plan_name' },
    {
      key: 'is_active',
      toQuery: (value?: boolean) => toBooleanQuery(value, true),
      fromQuery: (value) => parseBooleanQuery(value)
    },
    {
      key: 'created_by',
      toQuery: (value?: number) => (value ? String(value) : undefined),
      fromQuery: (value) => parseNumberQuery(value)
    },
    {
      key: 'updated_by',
      toQuery: (value?: number) => (value ? String(value) : undefined),
      fromQuery: (value) => parseNumberQuery(value)
    }
  ]
})

const resolveUserName = (id?: number) => {
  if (!id) return ''
  return availableUsers.value.find(user => user.id === id)?.name || String(id)
}

const resolveStatusText = (value?: boolean) => {
  if (value === true) return '启用'
  if (value === false) return '禁用'
  return ''
}

const activeFilterItems = computed(() => [
  { key: 'name', label: '任务名称', display: searchForm.name },
  { key: 'plan_name', label: '执行方案', display: searchForm.plan_name },
  { key: 'is_active', label: '状态', display: resolveStatusText(searchForm.is_active) },
  { key: 'created_by', label: '创建者', display: resolveUserName(searchForm.created_by) },
  { key: 'updated_by', label: '更新者', display: resolveUserName(searchForm.updated_by) }
])

const scheduledTaskActiveFilterCount = computed(() => countActiveFilters(searchForm as unknown as Record<string, unknown>))

const handleClearFilter = (key: string) => {
  const defaults = defaultSearchForm()
  if (key in defaults) {
    ;(searchForm as any)[key] = (defaults as any)[key]
  }
  pagination.current = 1
  syncToQuery()
  fetchTasks()
}

// 表格列配置
const taskRowActions = (row: any) => {
  const actions: any[] = [
    { label: '编辑', key: 'edit', disabled: !canChangeTask(row.id), icon: () => h(Pencil, { size: 14 }) },
    { label: '历史', key: 'history', icon: () => h(History, { size: 14 }) },
  ]
  if (row.is_active) {
    actions.push({ label: '禁用', key: 'toggle', disabled: !canChangeTask(row.id), icon: () => h(PauseCircle, { size: 14 }) })
  } else {
    actions.push({ label: '启用', key: 'toggle', disabled: !canChangeTask(row.id), icon: () => h(Play, { size: 14 }) })
  }
  actions.push({ label: '删除', key: 'delete', disabled: !canDeleteTask(row.id), icon: () => h(Trash2, { size: 14 }), props: { class: 'danger' } })
  return actions
}

const onTaskRowAction = (key: string, row: any) => {
  if (key === 'edit') { if (canChangeTask(row.id)) handleEdit(row); else showNoPermissionMessage() }
  if (key === 'history') handleHistory(row)
  if (key === 'toggle') handleClickToggleStatus(row)
  if (key === 'delete') handleClickDeleteTask(row)
}

const columns: DataTableColumns<any> = [
  {
    title: '任务',
    key: 'task',
    width: 260,
    render: (row) =>
      h('div', { class: 'task-name-cell' }, [
        h(NButton, { text: true, size: 'small', class: 'task-name-link', onClick: () => handleView(row) }, { default: () => row.name }),
        h('div', { class: 'task-context-line' }, `方案：${row.plan_name || '-'}`),
        h('div', { class: 'task-context-line' }, `模板：${row.template_name || '-'}`),
      ]),
  },
  {
    title: '状态',
    key: 'status',
    width: 72,
    align: 'center',
    render: (row) => (row.is_active
      ? h(NTag, { type: 'success' }, { default: () => '启用' })
      : h(NTag, { type: 'error' }, { default: () => '禁用' })),
  },
  {
    title: 'Cron表达式',
    key: 'cron_expression',
    width: 128,
    render: (row) =>
      h(NTooltip, {}, {
        trigger: () => h('code', row.cron_expression),
        default: () => getCronDescription(row.cron_expression),
      }),
  },
  {
    title: '成功率',
    key: 'success_rate',
    width: 110,
    align: 'center',
    render: (row) =>
      h('span', { style: 'display: inline-flex; align-items: center' }, [
        h(NProgress, {
          type: 'line',
          percentage: row.success_rate,
          color: getProgressColor(row.success_rate),
          showIndicator: false,
          height: 6,
        }),
        h('span', { style: 'margin-left: 8px' }, `${row.success_rate}%`),
      ]),
  },
  {
    title: '执行统计',
    key: 'execution_stats',
    width: 108,
    align: 'center',
    render: (row) =>
      h('div', { class: 'stats-cell' }, [
        h('div', `总计: ${row.total_runs}`),
        h('div', [ '成功: ', h('span', { style: 'color: #16a34a' }, String(row.success_runs)) ]),
        h('div', [ '失败: ', h('span', { style: 'color: #dc2626' }, String(row.failed_runs)) ]),
      ]),
  },
  {
    title: '最近执行结果',
    key: 'last_execution',
    width: 150,
    render: (row) => {
      if (!row.last_execution_status && !row.last_execution_at) {
        return h('span', { style: 'color: var(--app-meta)' }, '暂无')
      }
      return h('div', {}, [
        row.last_execution_status
          ? h(NTag, { type: getExecutionStatusColor(row.last_execution_status) as any }, { default: () => getExecutionStatusText(row.last_execution_status) })
          : h('span', { style: 'color: var(--app-meta)' }, '状态未知'),
        row.last_execution_at ? h('div', { class: 'meta-line' }, formatDateTime(row.last_execution_at)) : null,
      ])
    },
  },
  {
    title: '创建信息',
    key: 'created_at',
    render: (row) =>
      h(MetaInfoLines, {
        createdText: `创建：${formatDateTime(row.created_at)} · ${row.created_by_name || '-'}`,
        updatedText: `更新：${row.updated_at ? formatDateTime(row.updated_at) : '-'} · ${row.updated_by_name || row.created_by_name || '-'}`,
      }),
  },
  {
    title: '操作',
    key: 'actions',
    width: 130,
    render: (row) =>
      h(NSpace, { class: 'table-row-actions', size: 2, wrap: false, wrapItem: false, align: 'center' }, {
        default: () => [
          h(NButton, { text: true, size: 'small', class: 'scheduled-primary-action', onClick: () => handleView(row) }, {
            icon: () => h(Eye, { size: 14 }),
            default: () => '查看',
          }),
          h(NDropdown, {
            trigger: 'click',
            options: taskRowActions(row),
            onSelect: (key: string) => onTaskRowAction(key, row),
          }, {
            default: () => h(NButton, { text: true, size: 'small', class: 'scheduled-more-action', 'aria-label': '更多操作' }, {
              icon: () => h(MoreHorizontal, { size: 16 }),
            }),
          }),
        ],
      }),
  },
]

const tablePagination = computed(() => ({
  page: pagination.current,
  pageSize: pagination.pageSize,
  itemCount: pagination.total,
  onChange: (page: number) => handlePageChange(page),
  onUpdatePageSize: (size: number) => handlePageSizeChange(size),
}))

// 获取可用用户列表（创建者）
const fetchAvailableUsers = async () => {
  try {
    // 从当前任务列表中提取唯一用户列表
    if (tasks.value.length > 0) {
      const userMap = new Map<number, { id: number; username: string; name: string }>()
      const appendUser = (id?: number, name?: string) => {
        if (!id || !name) return
        userMap.set(id, { id, username: name, name })
      }

      tasks.value.forEach(task => {
        appendUser(task.created_by, task.created_by_name)
        appendUser(task.updated_by, task.updated_by_name)
      })
      availableUsers.value = Array.from(userMap.values()).sort((a, b) => a.name.localeCompare(b.name))
      // 初始化过滤结果为全部用户
      filteredCreators.value = [...availableUsers.value]
      filteredUpdaters.value = [...availableUsers.value]
    }
  } catch (error) {
    console.error('获取用户列表失败:', error)
  }
}

const filterUsers = (searchValue: string) => {
  if (!searchValue.trim()) {
    return [...availableUsers.value]
  }

  const searchTerm = searchValue.toLowerCase().trim()
  return availableUsers.value.filter(user =>
    user.name.toLowerCase().includes(searchTerm) ||
    user.username.toLowerCase().includes(searchTerm)
  )
}

// 处理创建者搜索
const handleCreatorSearch = (searchValue: string) => {
  filteredCreators.value = filterUsers(searchValue)
}

// 处理更新者搜索
const handleUpdaterSearch = (searchValue: string) => {
  filteredUpdaters.value = filterUsers(searchValue)
}

// 获取执行方案定时任务列表
const fetchTasks = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.current,
      page_size: pagination.pageSize,
      ordering: ordering.value || undefined,
      name: searchForm.name || undefined,
      plan_name: searchForm.plan_name || undefined,
      is_active: searchForm.is_active === undefined ? undefined : searchForm.is_active,
      created_by: searchForm.created_by || undefined,
      updated_by: searchForm.updated_by || undefined,
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
    await fetchAvailableUsers()
  } catch (error) {
    message.error('获取执行方案定时任务列表失败')
    console.error('获取执行方案定时任务列表失败:', error)
  } finally {
    loading.value = false
  }
}

// 搜索
const handleSearch = (): void => {
  pagination.current = 1
  syncToQuery()
  fetchTasks()
}

// 重置搜索
const handleReset = (): void => {
  Object.assign(searchForm, defaultSearchForm())
  // 重置创建者/更新者过滤
  filteredCreators.value = [...availableUsers.value]
  filteredUpdaters.value = [...availableUsers.value]
  pagination.current = 1
  syncToQuery()
  fetchTasks()
}

// 刷新
const handleRefresh = (): void => {
  fetchTasks()
}

// 分页处理
const handlePageChange = (page: number): void => {
  pagination.current = page
  syncToQuery()
  fetchTasks()
}

const handlePageSizeChange = (pageSize: number): void => {
  pagination.pageSize = pageSize
  pagination.current = 1
  syncToQuery()
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

const formatDateTimeParam = (date: Date) => {
  const pad = (num: number) => String(num).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}

const applyHistoryRange = (start: Date, end: Date) => {
  const startStr = formatDateTimeParam(start)
  const endStr = formatDateTimeParam(end)
  historyFilters.range = [startStr, endStr]
  historyFilters.start_date = startStr
  historyFilters.end_date = endStr
}

const fetchHistory = async () => {
  if (!currentHistoryJob.value) return
  historyLoading.value = true
  try {
    const params: any = {
      page: historyPagination.current,
      page_size: historyPagination.pageSize,
      scheduled_job_id: currentHistoryJob.value.id
    }
    if (historyFilters.keyword) params.search = historyFilters.keyword
    if (historyFilters.status) params.status = historyFilters.status
    if (historyFilters.start_date) params.start_date = historyFilters.start_date
    if (historyFilters.end_date) params.end_date = historyFilters.end_date
    const res = await executionRecordApi.getRecords(params)
    historyRecords.value = res.results || []
    historyPagination.total = res.total || 0
  } catch (error) {
    console.error('获取执行历史失败:', error)
    message.error('获取执行历史失败')
  } finally {
    historyLoading.value = false
  }
}

const handleHistory = (record: ScheduledJob): void => {
  currentHistoryJob.value = record
  historyPagination.current = 1
  historyFilters.keyword = ''
  historyFilters.status = undefined
  historyFilters.quick_range = undefined
  historyFilters.range = []
  historyFilters.start_date = ''
  historyFilters.end_date = ''
  historyVisible.value = true
  fetchHistory()
}

const handleHistoryPageChange = (page: number) => {
  historyPagination.current = page
  fetchHistory()
}

const handleHistoryPageSizeChange = (size: number) => {
  historyPagination.pageSize = size
  historyPagination.current = 1
  fetchHistory()
}

const handleHistorySearch = () => {
  historyPagination.current = 1
  fetchHistory()
}

const handleQuickRangeChange = (value: string) => {
  if (!value) return
  const end = new Date()
  const start = new Date(end.getTime())
  if (value === '1h') {
    start.setHours(start.getHours() - 1)
  } else if (value === '24h') {
    start.setHours(start.getHours() - 24)
  } else if (value === '7d') {
    start.setDate(start.getDate() - 7)
  }
  applyHistoryRange(start, end)
  handleHistorySearch()
}

const handleQuickRangeClear = () => {
  historyFilters.quick_range = undefined
  historyFilters.range = []
  historyFilters.start_date = ''
  historyFilters.end_date = ''
  handleHistorySearch()
}

const handleRangeChange = (value: string[] | undefined) => {
  if (!value || value.length !== 2) {
    historyFilters.start_date = ''
    historyFilters.end_date = ''
    handleHistorySearch()
    return
  }
  historyFilters.quick_range = undefined
  historyFilters.start_date = value[0]
  historyFilters.end_date = value[1]
  handleHistorySearch()
}

// 编辑任务
const handleEdit = (record: ScheduledJob): void => {
  router.push(`/scheduled-tasks/${record.id}/edit`)
}

// 切换任务状态
const handleToggleStatus = async (record: ScheduledJob): Promise<void> => {
  try {
    const action = record.is_active ? '禁用' : '启用'
    dialog.warning({
      title: `确认${action}任务`,
      content: `确定要${action}任务"${record.name}"吗？`,
      onPositiveClick: async () => {
        await scheduledJobApi.toggleStatus(record.id, !record.is_active)
        message.success(`${action}成功`)
        await fetchTasks()
      }
    })
  } catch (error) {
    console.error('切换任务状态失败:', error)
    // 错误消息已由HTTP拦截器处理，这里不再重复显示
  }
}

const handleClickToggleStatus = (record: ScheduledJob): void => {
  if (!canChangeTask(record.id)) {
    showNoPermissionMessage()
    return
  }
  handleToggleStatus(record)
}

// 删除任务
const handleDelete = async (record: ScheduledJob): Promise<void> => {
  try {
    dialog.warning({
      title: '确认删除',
      content: `确定要删除任务"${record.name}"吗？此操作不可恢复。`,
      onPositiveClick: async () => {
        try {
          await scheduledJobApi.delete(record.id)
          message.success('删除成功')
          await fetchTasks()
        } catch (error: any) {
          const message = error?.response?.data?.message || '删除任务失败'
          message.error(message)
        }
      }
    })
  } catch (error) {
    console.error('删除任务失败:', error)
  }
}

const handleClickDeleteTask = (record: ScheduledJob): void => {
  if (!canDeleteTask(record.id)) {
    showNoPermissionMessage()
    return
  }
  handleDelete(record)
}

const showNoPermissionMessage = () => {
  message.warning('没有权限执行此操作，请联系管理员开放权限')
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
  if (percent >= 90) return '#16a34a'
  if (percent >= 70) return '#d97706'
  return '#dc2626'
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
    pending: 'default',
    running: 'info',
    success: 'success',
    failed: 'error',
    cancelled: 'warning',
    timeout: 'error',
    paused: 'warning',
    retrying: 'info'
  }
  return status ? (map[status] || 'gray') : 'gray'
}

const formatDuration = (seconds?: number): string => {
  if (!seconds) return '-'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = seconds % 60
  if (h > 0) return `${h}h ${m}m ${s}s`
  if (m > 0) return `${m}m ${s}s`
  return `${s}s`
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

const historyTableColumns: DataTableColumns<any> = [
  { title: '执行ID', key: 'execution_id', ellipsis: { tooltip: true }, render: (row) => row.execution_id },
  { title: '名称', key: 'name', ellipsis: { tooltip: true }, render: (row) => row.name },
  {
    title: '状态',
    key: 'status',
    width: 100,
    render: (row) => {
      if (row.status === 'SUCCESS') return h(NTag, { type: 'success' }, { default: () => '成功' })
      if (row.status === 'FAILED') return h(NTag, { type: 'error' }, { default: () => '失败' })
      if (row.status === 'RUNNING') return h(NTag, { type: 'info' }, { default: () => '运行中' })
      if (row.status === 'CANCELLED') return h(NTag, { type: 'warning' }, { default: () => '取消' })
      return h(NTag, {}, { default: () => row.status })
    },
  },
  { title: '开始时间', key: 'started_at', width: 160, render: (row) => row.started_at },
  { title: '结束时间', key: 'finished_at', width: 160, render: (row) => row.finished_at },
  { title: '耗时', key: 'duration', width: 100, render: (row) => (row.duration ? formatDuration(row.duration) : h('span', { style: 'color: var(--app-meta)' }, '-')) },
  {
    title: '操作',
    key: 'actions',
    width: 120,
    render: (row) =>
      h(NButton, { text: true, size: 'small', onClick: () => router.push(`/execution-records/${row.id}`) }, { default: () => '查看详情' }),
  }
]

const historyTablePagination = computed(() => ({
  page: historyPagination.current,
  pageSize: historyPagination.pageSize,
  itemCount: historyPagination.total,
  onChange: (page: number) => handleHistoryPageChange(page),
  onUpdatePageSize: (size: number) => handleHistoryPageSizeChange(size),
}))

// 生命周期
onMounted(() => {
  initFromQuery()
  fetchTasks()
})

// 机械转换生成的静态下拉选项
const selectOptions1 = [{ label: '成功', value: 'SUCCESS' }, { label: '失败', value: 'FAILED' }, { label: '运行中', value: 'RUNNING' }, { label: '已取消', value: 'CANCELLED' }]
const selectOptions2 = [{ label: '近1小时', value: '1h' }, { label: '近24小时', value: '24h' }, { label: '近7天', value: '7d' }]

</script>

<style scoped>
.scheduled-tasks-page {
  padding: 0;
}

.task-name-cell {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}

.task-name-link {
  min-width: 0;
  overflow: hidden;
  font-weight: 500;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-context-line {
  min-width: 0;
  overflow: hidden;
  color: var(--app-meta);
  font-size: 12px;
  line-height: 1.35;
  text-overflow: ellipsis;
  white-space: nowrap;
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

.meta-line {
  font-size: 12px;
  line-height: 1.4;
  color: var(--app-muted);
}

.disabled-option {
  opacity: 0.5;
  cursor: not-allowed;
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
  width: 100%;
  max-width: 100%;

  .arco-table-container,
  .arco-table-content,
  .arco-table-body,
  .arco-table-element {
    max-width: 100%;
    min-width: 0;
    overflow-x: hidden;
  }

  table {
    width: 100%;
    table-layout: fixed;
  }

  .arco-table-th {
    background-color: #fff;
  }

  .arco-table-td {
    padding: 12px 10px;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .arco-space-item {
    min-width: 0;
  }
}

:deep(.table-row-actions) {
  justify-content: center;
  max-width: 100%;
  overflow: hidden;
}

:deep(.scheduled-primary-action) {
  min-width: 46px;
  padding-inline: 6px;
}

:deep(.scheduled-more-action) {
  width: 28px;
  min-width: 28px;
  padding-inline: 0;
}
</style>
