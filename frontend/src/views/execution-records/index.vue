<template>
  <div 
    class="app-page execution-records-page"
    v-page-permissions="{ 
      resourceType: 'executionrecord', 
      permissions: ['view'],
      resourceIds: tableData.map(r => r.id)
    }"
  >
    <PageHeader
      eyebrow="执行审计"
      title="执行记录"
      description="按执行类型、状态、发起人和时间窗口追踪平台内所有任务执行。"
    >
      <template #actions>
        <n-button @click="handleRefresh">
          <template #icon>
            <RefreshCw  />
          </template>
          刷新
        </n-button>
      </template>
    </PageHeader>

    <DataToolbar
      title="筛选执行记录"
      description="默认展示最近执行，时间快捷项会同步到地址栏，方便复盘和共享。"
      :active-count="executionActiveFilterCount"
    >
      <div class="form-grid-row">
        <div class="form-grid-col" style="grid-column: span 4">
          <n-input
            v-model:value="searchForm.name"
            placeholder="请输入执行名称"
            clearable
            @press-enter="handleSearch"
          />
        </div>
        <div class="form-grid-col" style="grid-column: span 4">
                    <n-select
            v-model:value="searchForm.execution_type"
            placeholder="请选择执行类型"
            clearable
            @change="handleSearch" :options="selectOptions1" />
        </div>
        <div class="form-grid-col" style="grid-column: span 4">
                    <n-select
            v-model:value="searchForm.status"
            placeholder="状态"
            clearable
            @change="handleSearch" :options="selectOptions2" />
        </div>
        <div class="form-grid-col" style="grid-column: span 4">
          <n-select
            v-model:value="searchForm.executed_by"
            placeholder="执行用户"
            clearable
            filterable
            :filter-option="false"
            :options="executedByOptions"
            @search="handleExecutedBySearch"
            @change="handleSearch"
          />
        </div>
      </div>
      
      <div class="form-grid-row filter-row">
        <div class="form-grid-col" style="grid-column: span 6">
          <n-date-picker
            v-model="searchForm.start_date"
            placeholder="开始时间"
            format="YYYY-MM-DD HH:mm:ss"
            value-format="YYYY-MM-DD HH:mm:ss"
            show-time
            style="width: 100%"
            @change="handleSearch"
          />
        </div>
        <div class="form-grid-col" style="grid-column: span 6">
          <n-date-picker
            v-model="searchForm.end_date"
            placeholder="结束时间"
            format="YYYY-MM-DD HH:mm:ss"
            value-format="YYYY-MM-DD HH:mm:ss"
            show-time
            style="width: 100%"
            @change="handleSearch"
          />
        </div>
        <div class="form-grid-col" style="grid-column: span 12">
          <div class="time-actions">
            <n-space :size="4" class="time-shortcuts">
              <n-button size="tiny" @click="applyDateShortcut('last1h')">近1h</n-button>
              <n-button size="tiny" @click="applyDateShortcut('last12h')">近12h</n-button>
              <n-button size="tiny" @click="applyDateShortcut('today')">今天</n-button>
              <n-button size="tiny" @click="applyDateShortcut('yesterday')">昨天</n-button>
              <n-button size="tiny" @click="applyDateShortcut('last7')">近7天</n-button>
              <n-button size="tiny" @click="applyDateShortcut('last30')">近30天</n-button>
              <n-button size="tiny" @click="applyDateShortcut('thisMonth')">本月</n-button>
            </n-space>
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
      </div>
    </DataToolbar>

    <DetailPanel
      title="执行明细"
      :description="`共 ${pagination.total} 条记录，当前页 ${tableData.length} 条`"
    >
      <n-data-table
        :columns="columns"
        :data="tableData"
        :loading="loading"
        :pagination="tablePagination"
        remote
        :row-key="(row: any) => row.id"
      />
    </DetailPanel>

    <!-- 重试历史弹窗 -->
    <n-modal preset="card" :style="{ width: '800px' }"
      v-model:show="retryHistoryVisible"
      title="重试历史"
     
     
    >
      <div v-if="retryHistoryLoading" class="text-center py-8">
        <n-spin size="large" />
        <div class="mt-2">加载重试历史中...</div>
      </div>

      <n-timeline v-else-if="retryHistory.length > 0" class="retry-history-timeline">
        <n-timeline-item
          v-for="(retry, index) in retryHistory"
          :key="retry.id"
          :color="getTimelineColor(retry.status)"
        >
          <template #icon>
            <component :is="getStatusIcon(retry.status)" />
          </template>

          <div class="retry-item">
            <div class="retry-header">
              <div class="retry-title">
                <span class="retry-index">第 {{ retryHistory.length - index }} 次执行</span>
                <n-tag v-if="retry.is_latest" type="success" size="small">当前</n-tag>
                <n-tag v-else-if="index === retryHistory.length - 1" type="info" size="small">原始</n-tag>
              </div>
              <div class="retry-time">{{ formatDateTime(retry.created_at) }}</div>
            </div>

            <div class="retry-status"><n-tag :type="getStatusColor(retry.status) as any">
                {{ getStatusText(retry.status) }}
              </n-tag>
              <span class="retry-duration" v-if="retry.duration">
                耗时: {{ Math.round(retry.duration) }}秒
              </span>
            </div>

            <div class="retry-reason" v-if="retry.retry_reason">
              <strong>重试原因:</strong> {{ retry.retry_reason }}
            </div>

            <div class="retry-result" v-if="retry.error_message">
              <strong>错误信息:</strong>
              <div class="error-message">{{ retry.error_message }}</div>
            </div>

            <div class="retry-stats">
            </div>

            <div class="retry-actions mt-2">
              <n-button size="small" @click="handleView(retry)">查看详情</n-button>
            </div>
          </div>
        </n-timeline-item>
      </n-timeline>

      <n-empty v-else description="暂无重试历史" />
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, h, onMounted, reactive, ref, resolveDirective, type VNode, withDirectives } from 'vue'
import { useFilterQuerySync } from '@/composables/useFilterQuerySync'
import dayjs from 'dayjs'
import { useRouter } from 'vue-router'
import { executionRecordApi } from '@/api/ops'
import { usePermissionsStore } from '@/stores/permissions'
import { DataToolbar, DetailPanel, PageHeader, StatusBadge, countActiveFilters } from '@/components/app'
import { NButton, NDataTable, NDatePicker, NDropdown, NEmpty, NInput, NModal, NSelect, NSpace, NSpin, NTag, NText, NTimeline, NTimelineItem, NTooltip, type DataTableColumns, useDialog, useMessage } from 'naive-ui'
import { Check, CircleAlert, Eye, History, Loader2, MoreHorizontal, Pause, RefreshCw, Search, X } from 'lucide-vue-next'

type ExecutionRecordRow = {
  id: number
  execution_id?: string
  name?: string
  execution_type?: string
  status?: string
  total_retry_count?: number
  has_retries?: boolean
  executed_by_name?: string
  started_at?: string
  finished_at?: string
  created_at?: string
  [k: string]: any
}

type RetryHistoryItem = {
  id: number
  status: string
  created_at?: string
  duration?: number
  retry_reason?: string
  error_message?: string
  is_latest?: boolean
  [k: string]: any
}

type SearchForm = {
  execution_type: string
  status: string
  name: string
  executed_by: string
  start_date: string | null
  end_date: string | null
}

const dialog = useDialog()
const message = useMessage()
const router = useRouter()
const permissionsStore = usePermissionsStore()

// 响应式数据
const loading = ref(false)
const tableData = ref<ExecutionRecordRow[]>([])

// 重试历史相关
const retryHistoryVisible = ref(false)
const retryHistoryLoading = ref(false)
const retryHistory = ref<RetryHistoryItem[]>([])
const currentRecord = ref<ExecutionRecordRow | null>(null)
const executedByKeyword = ref('')
const executedByOptions = computed(() => {
  const options = Array.from(
    new Set(
      tableData.value
        .map(item => item.executed_by_name)
        .filter((name): name is string => !!name)
    )
  ).map(name => ({ label: name, value: name }))

  const keyword = executedByKeyword.value.trim().toLowerCase()
  if (!keyword) return options

  return options.filter(option => option.label.toLowerCase().includes(keyword))
})

// 搜索表单
const searchForm = reactive<SearchForm>({
  execution_type: '',
  status: '',
  name: '',
  executed_by: '',
  start_date: null,
  end_date: null
})

const executionActiveFilterCount = computed(() => countActiveFilters(searchForm as unknown as Record<string, unknown>))

// 分页配置
const pagination = reactive({
  current: 1,
  pageSize: 10,
  total: 0,
  showTotal: true,
  showJumper: true,
  showPageSize: true,
  showQuickJumper: true,
  pageSizeOptions: [10, 20, 50, 100],
  // size: 'default',
  hideOnSinglePage: false,
  showLessItems: false,
})

const { initFromQuery, syncToQuery } = useFilterQuerySync({
  searchForm,
  pagination,
  fields: [
    { key: 'name' },
    { key: 'execution_type' },
    { key: 'status' },
    { key: 'executed_by' },
    { key: 'start_date' },
    { key: 'end_date' }
  ]
})

// 表格列配置
const recordRowActions = (row: any) => {
  const actions: any[] = []
  if (row.status === 'running') {
    actions.push({ label: '取消', key: 'cancel', icon: () => h(X, { size: 14 }), props: { class: 'danger' } })
  } else if (row.status === 'failed') {
    actions.push({ label: '重试', key: 'retry', disabled: !canExecute(row.id), icon: () => h(RefreshCw, { size: 14 }) })
  } else if (row.status === 'pending') {
    actions.push({ label: '取消', key: 'cancel', disabled: !canExecute(row.id), icon: () => h(X, { size: 14 }), props: { class: 'danger' } })
  } else if (row.status === 'success' || row.status === 'cancelled') {
    actions.push({ label: '重做', key: 'retry', disabled: !canExecute(row.id), icon: () => h(RefreshCw, { size: 14 }) })
  }
  if (row.has_retries) {
    actions.push({ label: '重试历史', key: 'history', disabled: !canView(row.id), icon: () => h(History, { size: 14 }) })
  }
  return actions
}

const onRecordRowAction = (key: string, row: any) => {
  if (key === 'cancel' && row.status === 'running') handleCancel(row)
  if (key === 'cancel') handleClickCancel(row)
  if (key === 'retry') handleClickRetry(row)
  if (key === 'history') handleClickShowRetryHistory(row)
}

const columns: DataTableColumns<any> = [
  {
    title: '执行ID',
    key: 'execution_id',
    width: 180,
    ellipsis: { tooltip: true },
    render: (row) =>
      h(NText, { copyable: true, style: 'font-family: monospace; font-size: 12px;' }, { default: () => row.execution_id || '-' }),
  },
  {
    title: '执行名称',
    key: 'name',
    width: 200,
    ellipsis: { tooltip: true },
    render: (row) =>
      h('div', { style: 'max-width: 200px;' }, [
        h(NTooltip, {}, {
          trigger: () => h('div', { style: 'overflow: hidden; text-overflow: ellipsis; white-space: nowrap;' }, row.name || '-'),
          default: () => row.name,
        }),
      ]),
  },
  {
    title: '执行类型',
    key: 'execution_type',
    width: 150,
    render: (row) =>
      h(NTag, { type: getExecutionTypeColor(row.execution_type) as any }, { default: () => getExecutionTypeText(row.execution_type) }),
  },
  {
    title: '状态',
    key: 'status',
    width: 100,
    render: (row) =>
      h(NSpace, { size: 4, wrap: false, wrapItem: false, align: 'center' }, {
        default: () => [
          h(StatusBadge, { status: row.status, text: getStatusText(row.status) }),
          row.total_retry_count > 0
            ? h(NTag, { type: 'warning', size: 'small' }, {
                icon: () => h(RefreshCw, { size: 12 }),
                default: () => `重试 ${row.total_retry_count} 次`,
              })
            : null,
        ],
      }),
  },
  {
    title: '执行时长',
    key: 'duration',
    width: 120,
    render: (row) => {
      if (row.started_at && row.finished_at) return formatDuration(row.started_at, row.finished_at)
      if (row.started_at) return formatDuration(row.started_at, new Date())
      return '-'
    },
  },
  { title: '执行用户', key: 'executed_by_name', width: 120, render: (row) => row.executed_by_name },
  {
    title: '创建信息',
    key: 'created_at',
    width: 160,
    render: (row) =>
      h('div', {}, [
        h('div', formatDateTime(row.created_at)),
        h('div', { class: 'table-meta' }, row.executed_by_name || '-'),
      ]),
  },
  {
    title: '操作',
    key: 'actions',
    width: 124,
    render: (row) =>
      h(NSpace, { class: 'table-row-actions', wrap: false, wrapItem: false, align: 'center' }, {
        default: () => [
          withPerm(
            h(NButton, { text: true, size: 'small', onClick: () => handleView(row) }, {
              icon: () => h(Eye, { size: 14 }),
              default: () => '查看',
            }),
            { resourceType: 'executionrecord', permission: 'view', resourceId: row.id },
          ),
          h(NDropdown, {
            trigger: 'click',
            options: recordRowActions(row),
            onSelect: (key: string) => onRecordRowAction(key, row),
          }, {
            default: () => h(NButton, { text: true, size: 'small', 'aria-label': '更多操作' }, {
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

const withPerm = (vnode: VNode, value: unknown) => {
  const perm = resolveDirective('permission')
  return perm ? withDirectives(vnode, [[perm, value]]) : vnode
}

// 获取执行记录列表
const fetchRecords = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.current,
      page_size: pagination.pageSize,
      ...searchForm
    }

    // 过滤空值
    Object.keys(params).forEach(key => {
      if (params[key] === '' || params[key] === null || params[key] === undefined) {
        delete params[key]
      }
    })

    const response = await executionRecordApi.getRecords(params)
    tableData.value = response.results ?? []
    pagination.total = response.total ?? tableData.value.length
  } catch (error) {
    console.error('获取执行记录失败:', error)
  } finally {
    loading.value = false
  }
}

// 搜索
const handleSearch = () => {
  pagination.current = 1
  syncToQuery()
  fetchRecords()
}

const applyDateShortcut = (type: string) => {
  const now = dayjs()
  const fmt = (value: dayjs.Dayjs) => value.format('YYYY-MM-DD HH:mm:ss')

  let start = now
  let end = now

  switch (type) {
    case 'last1h':
      start = now.subtract(1, 'hour')
      end = now
      break
    case 'last12h':
      start = now.subtract(12, 'hour')
      end = now
      break
    case 'yesterday':
      start = now.subtract(1, 'day').startOf('day')
      end = now.subtract(1, 'day').endOf('day')
      break
    case 'last7':
      start = now.subtract(6, 'day').startOf('day')
      end = now
      break
    case 'last30':
      start = now.subtract(29, 'day').startOf('day')
      end = now
      break
    case 'thisMonth':
      start = now.startOf('month')
      end = now
      break
    case 'today':
    default:
      start = now.startOf('day')
      end = now
      break
  }

  searchForm.start_date = fmt(start)
  searchForm.end_date = fmt(end)
  handleSearch()
}

// 重置
const handleReset = () => {
  Object.keys(searchForm).forEach(key => {
    if (key === 'start_date' || key === 'end_date') {
      searchForm[key] = null
    } else {
      searchForm[key] = ''
    }
  })
  executedByKeyword.value = ''
  pagination.current = 1
  syncToQuery()
  fetchRecords()
}

// 刷新
const handleRefresh = () => {
  fetchRecords()
}

// 分页处理
const handlePageChange = (page: number | string) => {
  pagination.current = Number(page)
  syncToQuery()
  fetchRecords()
}

const handlePageSizeChange = (pageSize: number | string) => {
  pagination.pageSize = Number(pageSize)
  pagination.current = 1
  syncToQuery()
  fetchRecords()
}

const handleExecutedBySearch = (value: string) => {
  executedByKeyword.value = value
}

// 查看详情
const handleView = (record) => {
  router.push(`/execution-records/${record.id}`)
}

// 重试执行
const handleRetry = async (record) => {
  const isRetry = record.status === 'failed'
  const title = isRetry ? '确认重试' : '确认重做'
  const content = isRetry
    ? `确定要重试执行"${record.name}"吗？`
    : `确定要重做"${record.name}"吗？`
  const successMessage = isRetry ? '重试成功' : '重做成功'

  try {
    await dialog.warning({
      title,
      content,
      onPositiveClick: async () => {
        try {
          console.log('开始调用重做API, 执行记录ID:', record.id)
          const result = await executionRecordApi.retryExecution(record.id)
          console.log('重做API返回结果:', result)

          message.success(successMessage)

          // 如果返回了新的执行记录ID，跳转到新的执行记录详情页面
          // 注意：由于响应拦截器会自动提取content字段，result就是content的内容
          if (result && result.execution_record_id) {
            console.log('跳转到新的执行记录:', result.execution_record_id)
            await router.push(`/execution-records/${result.execution_record_id}`)
          } else {
            console.log('没有返回execution_record_id，刷新列表')
            console.log('result结构:', result)
            // 如果没有返回新的执行记录ID，刷新列表
            fetchRecords()
          }
        } catch (error) {
          console.error('重做操作失败:', error)
          message.error('重做操作失败')
        }
      }
    })
  } catch (error) {
    console.error('重试失败:', error)
  }
}

// 取消执行
const handleCancel = async (record) => {
  try {
    await dialog.warning({
      title: '确认取消',
      content: `确定要取消执行"${record.name}"吗？`,
      onPositiveClick: async () => {
        await executionRecordApi.cancelExecution(record.id)
        message.success('取消成功')
        fetchRecords()
      }
    })
  } catch (error) {
    console.error('取消失败:', error)
  }
}

// 显示重试历史
const handleShowRetryHistory = async (record) => {
  currentRecord.value = record
  retryHistoryVisible.value = true
  retryHistoryLoading.value = true

  try {
    const response = await executionRecordApi.getRetryHistory(record.id)
    retryHistory.value = response.content ?? []
  } catch (error) {
    console.error('获取重试历史失败:', error)
    message.error('获取重试历史失败')
    retryHistory.value = []
  } finally {
    retryHistoryLoading.value = false
  }
}

// 权限检查函数
const canExecute = (recordId) => {
  if (permissionsStore.isSuperUser) return true
  return (
    permissionsStore.hasPermission('executionrecord', 'execute', recordId) ||
    permissionsStore.hasPermission('executionrecord', 'execute')
  )
}

const canView = (recordId) => {
  if (permissionsStore.isSuperUser) return true
  return (
    permissionsStore.hasPermission('executionrecord', 'view', recordId) ||
    permissionsStore.hasPermission('executionrecord', 'view')
  )
}

// 显示无权限提示
const showNoPermissionMessage = () => {
  message.warning('没有权限执行此操作，请联系管理员开放权限')
}

// 点击处理函数（带权限检查）
const handleClickRetry = (record) => {
  if (!canExecute(record.id)) {
    showNoPermissionMessage()
    return
  }
  handleRetry(record)
}

const handleClickCancel = (record) => {
  if (!canExecute(record.id)) {
    showNoPermissionMessage()
    return
  }
  handleCancel(record)
}

// 批量选择变化
const handleClickShowRetryHistory = (record) => {
  if (!canView(record.id)) {
    showNoPermissionMessage()
    return
  }
  handleShowRetryHistory(record)
}

// 获取时间线颜色
const getTimelineColor = (status) => {
  const colorMap = {
    'success': 'green',
    'failed': 'red',
    'running': 'blue',
    'pending': 'orange',
    'cancelled': 'gray',
    'timeout': 'purple'
  }
  return colorMap[status] || 'gray'
}

// 工具函数
const getExecutionTypeText = (type) => {
  const typeMap = {
    'quick_script': '快速脚本执行',
    'quick_file_transfer': '快速文件传输',
    'job_workflow': 'Job工作流',
    'scheduled_job': '定时作业'
  }
  return typeMap[type] || type
}

const getExecutionTypeColor = (type) => {
  const colorMap = {
    'quick_script': 'blue',
    'quick_file_transfer': 'green',
    'job_workflow': 'purple',
    'scheduled_job': 'orange'
  }
  return colorMap[type] || 'gray'
}

const getStatusText = (status) => {
  const statusMap = {
    'pending': '等待中',
    'running': '执行中',
    'success': '成功',
    'failed': '失败',
    'cancelled': '已取消'
  }
  return statusMap[status] || status
}

const getStatusColor = (status) => {
  const colorMap = {
    'pending': 'gray',
    'running': 'blue',
    'success': 'green',
    'failed': 'red',
    'cancelled': 'orange'
  }
  return colorMap[status] || 'gray'
}

const getStatusIcon = (status: string) => {
  const iconMap: Record<string, any> = {
    pending: Pause,
    running: Loader2,
    success: Check,
    failed: CircleAlert,
    cancelled: X,
  }
  return iconMap[status] || Pause
}

const formatDuration = (startTime: any, endTime: any) => {
  const start = new Date(startTime as any).getTime()
  const end = new Date(endTime as any).getTime()
  const duration = (end - start) / 1000

  if (duration < 60) {
    return `${duration.toFixed(1)}秒`
  } else if (duration < 3600) {
    const minutes = Math.floor(duration / 60)
    const seconds = (duration % 60).toFixed(1)
    return `${minutes}分${seconds}秒`
  } else {
    const hours = Math.floor(duration / 3600)
    const minutes = Math.floor((duration % 3600) / 60)
    const seconds = (duration % 60).toFixed(1)
    return `${hours}时${minutes}分${seconds}秒`
  }
}

const formatDateTime = (dateTime) => {
  if (!dateTime) return '-'
  return new Date(dateTime).toLocaleString('zh-CN')
}

// 初始化
onMounted(() => {
  initFromQuery()
  fetchRecords()
})

// 机械转换生成的静态下拉选项
const selectOptions1 = [{ label: '快速脚本执行', value: 'quick_script' }, { label: '快速文件传输', value: 'quick_file_transfer' }, { label: 'Job工作流执行', value: 'job_workflow' }, { label: '定时作业执行', value: 'scheduled_job' }]
const selectOptions2 = [{ label: '等待中', value: 'pending' }, { label: '执行中', value: 'running' }, { label: '成功', value: 'success' }, { label: '失败', value: 'failed' }, { label: '已取消', value: 'cancelled' }]
</script>

<style scoped>
.execution-records-page {
  padding: 0;
}

.filter-row {
  margin-top: 16px;
}

.table-meta {
  color: var(--app-meta);
  font-size: 12px;
}

.time-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.time-shortcuts :deep(.arco-btn) {
  padding: 0 8px;
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

/* 重试历史样式 */
.retry-history-timeline {
  margin-top: 16px;
}

.retry-item {
  padding: 12px 0;
}

.retry-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.retry-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.retry-index {
  font-weight: 600;
  font-size: 14px;
}

.retry-time {
  color: #86909c;
  font-size: 12px;
}

.retry-status {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.retry-duration {
  color: #86909c;
  font-size: 12px;
}

.retry-reason {
  margin-bottom: 8px;
  padding: 8px 12px;
  background-color: #f7f8fa;
  border-radius: 4px;
  font-size: 13px;
}

.retry-result {
  margin-bottom: 8px;
}

.error-message {
  margin-top: 4px;
  padding: 8px 12px;
  background-color: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 4px;
  color: #dc2626;
  font-size: 12px;
  font-family: monospace;
  white-space: pre-wrap;
  word-break: break-all;
}

.retry-stats {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  font-size: 12px;
  color: #86909c;
}

.retry-actions {
  display: flex;
  gap: 8px;
}

.ml-4 {
  margin-left: 16px;
}

.disabled-option {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
