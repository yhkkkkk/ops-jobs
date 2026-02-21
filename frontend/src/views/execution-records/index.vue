<template>
  <div 
    class="execution-records-page"
    v-page-permissions="{ 
      resourceType: 'executionrecord', 
      permissions: ['view'],
      resourceIds: tableData.map(r => r.id)
    }"
  >
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-content">
        <div class="header-left">
          <h2>执行记录</h2>
          <p class="header-desc">查看和管理所有的任务执行记录</p>
        </div>
        <div class="header-right">
          <a-space>
            <a-button @click="handleRefresh">
              <template #icon>
                <icon-refresh />
              </template>
              刷新
            </a-button>
          </a-space>
        </div>
      </div>
    </div>

    <!-- 搜索区域 -->
    <a-card class="mb-4">
      <a-row :gutter="16">
        <a-col :span="4">
          <a-input
            v-model="searchForm.name"
            placeholder="请输入执行名称"
            allow-clear
            @press-enter="handleSearch"
          />
        </a-col>
        <a-col :span="4">
          <a-select
            v-model="searchForm.execution_type"
            placeholder="请选择执行类型"
            allow-clear
            @change="handleSearch"
          >
            <a-option value="quick_script">快速脚本执行</a-option>
            <a-option value="quick_file_transfer">快速文件传输</a-option>
            <a-option value="job_workflow">Job工作流执行</a-option>
            <a-option value="scheduled_job">定时作业执行</a-option>
          </a-select>
        </a-col>
        <a-col :span="4">
          <a-select
            v-model="searchForm.status"
            placeholder="状态"
            allow-clear
            @change="handleSearch"
          >
            <a-option value="pending">等待中</a-option>
            <a-option value="running">执行中</a-option>
            <a-option value="success">成功</a-option>
            <a-option value="failed">失败</a-option>
            <a-option value="cancelled">已取消</a-option>
          </a-select>
        </a-col>
        <a-col :span="4">
          <a-select
            v-model="searchForm.executed_by"
            placeholder="执行用户"
            allow-clear
            allow-search
            filter-option="false"
            :options="executedByOptions"
            @search="handleExecutedBySearch"
            @change="handleSearch"
          />
        </a-col>
      </a-row>
      
      <!-- 第二行：时间范围搜索 -->
      <a-row :gutter="16" style="margin-top: 16px;">
        <a-col :span="6">
          <a-date-picker
            v-model="searchForm.start_date"
            placeholder="开始时间"
            format="YYYY-MM-DD HH:mm:ss"
            value-format="YYYY-MM-DD HH:mm:ss"
            show-time
            style="width: 100%"
            @change="handleSearch"
          />
        </a-col>
        <a-col :span="6">
          <a-date-picker
            v-model="searchForm.end_date"
            placeholder="结束时间"
            format="YYYY-MM-DD HH:mm:ss"
            value-format="YYYY-MM-DD HH:mm:ss"
            show-time
            style="width: 100%"
            @change="handleSearch"
          />
        </a-col>
        <a-col :span="12">
          <div class="time-actions">
            <a-space size="mini" class="time-shortcuts">
              <a-button size="mini" @click="applyDateShortcut('last1h')">近1h</a-button>
              <a-button size="mini" @click="applyDateShortcut('last12h')">近12h</a-button>
              <a-button size="mini" @click="applyDateShortcut('today')">今天</a-button>
              <a-button size="mini" @click="applyDateShortcut('yesterday')">昨天</a-button>
              <a-button size="mini" @click="applyDateShortcut('last7')">近7天</a-button>
              <a-button size="mini" @click="applyDateShortcut('last30')">近30天</a-button>
              <a-button size="mini" @click="applyDateShortcut('thisMonth')">本月</a-button>
            </a-space>
            <a-space>
              <a-button type="primary" @click="handleSearch">
                <template #icon><icon-search /></template>
                搜索
              </a-button>
              <a-button @click="handleReset">
                <template #icon><icon-refresh /></template>
                重置
              </a-button>
            </a-space>
          </div>
        </a-col>
      </a-row>
    </a-card>

    <!-- 表格区域 -->
    <a-card>
      <a-table
        :columns="columns"
        :data="tableData"
        :loading="loading"
        :pagination="pagination"
        :scroll="{ x: 1300 }"
        @page-change="handlePageChange"
        @page-size-change="handlePageSizeChange"
        row-key="id"
      >
        <template #execution_id="{ record }">
          <a-typography-text copyable style="font-family: monospace; font-size: 12px;">
            {{ record.execution_id || '-' }}
          </a-typography-text>
        </template>

        <template #name="{ record }">
          <div style="max-width: 200px;">
            <a-tooltip :content="record.name">
              <div style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                {{ record.name || '-' }}
              </div>
            </a-tooltip>
          </div>
        </template>

        <template #execution_type="{ record }">
          <a-tag :color="getExecutionTypeColor(record.execution_type)">
            {{ getExecutionTypeText(record.execution_type) }}
          </a-tag>
        </template>

        <template #status="{ record }">
          <a-space>
            <a-tag :color="getStatusColor(record.status)">
              <template #icon>
                <component :is="getStatusIcon(record.status)" />
              </template>
              {{ getStatusText(record.status) }}
            </a-tag>
            <!-- 重试次数徽章 -->
            <a-tag v-if="record.total_retry_count > 0" color="orange" size="small">
              <template #icon>
                <icon-refresh />
              </template>
              重试 {{ record.total_retry_count }} 次
            </a-tag>
          </a-space>
        </template>

        <template #duration="{ record }">
          <span v-if="record.started_at && record.finished_at">
            {{ formatDuration(record.started_at, record.finished_at) }}
          </span>
          <span v-else-if="record.started_at">
            {{ formatDuration(record.started_at, new Date()) }}
          </span>
          <span v-else>-</span>
        </template>

        <template #created_at="{ record }">
          <div>
            <div>{{ formatDateTime(record.created_at) }}</div>
            <div style="color: #86909c; font-size: 12px">
              {{ record.executed_by_name || '-' }}
            </div>
          </div>
        </template>

        <template #actions="{ record }">
          <a-space>
            <a-button 
              type="text" 
              size="small" 
              v-permission="{ resourceType: 'executionrecord', permission: 'view', resourceId: record.id }"
              @click="handleView(record)"
            >
              <template #icon>
                <icon-eye />
              </template>
              查看
            </a-button>
            <template v-if="record.status === 'running'">
              <a-button
                type="text"
                size="small"
                status="danger"
                v-permission="{ resourceType: 'executionrecord', permission: 'execute', resourceId: record.id }"
                @click="handleCancel(record)"
              >
                <template #icon>
                  <icon-close />
                </template>
                取消
              </a-button>
            </template>
            <template v-else>
              <a-button
                v-if="record.status === 'failed'"
                type="text"
                size="small"
                :class="{ 'disabled-option': !canExecute(record.id) }"
                @click="handleClickRetry(record)"
              >
                <template #icon>
                  <icon-refresh />
                </template>
                重试
              </a-button>
              <a-button
                v-else-if="record.status === 'pending'"
                type="text"
                size="small"
                status="danger"
                :class="{ 'disabled-option': !canExecute(record.id) }"
                @click="handleClickCancel(record)"
              >
                <template #icon>
                  <icon-close />
                </template>
                取消
              </a-button>
              <a-button
                v-else-if="record.status === 'success' || record.status === 'cancelled'"
                type="text"
                size="small"
                :class="{ 'disabled-option': !canExecute(record.id) }"
                @click="handleClickRetry(record)"
              >
                <template #icon>
                  <icon-refresh />
                </template>
                重做
              </a-button>
              <a-button
                v-if="record.has_retries"
                type="text"
                size="small"
                :class="{ 'disabled-option': !canView(record.id) }"
                @click="handleClickShowRetryHistory(record)"
              >
                <template #icon>
                  <icon-history />
                </template>
                重试历史 ({{ record.total_retry_count }})
              </a-button>
            </template>
          </a-space>
        </template>
      </a-table>
    </a-card>

    <!-- 重试历史弹窗 -->
    <a-modal
      v-model:visible="retryHistoryVisible"
      title="重试历史"
      width="800px"
      :footer="false"
    >
      <div v-if="retryHistoryLoading" class="text-center py-8">
        <a-spin size="large" />
        <div class="mt-2">加载重试历史中...</div>
      </div>

      <a-timeline v-else-if="retryHistory.length > 0" class="retry-history-timeline">
        <a-timeline-item
          v-for="(retry, index) in retryHistory"
          :key="retry.id"
          :color="getTimelineColor(retry.status)"
        >
          <template #dot>
            <component :is="getStatusIcon(retry.status)" />
          </template>

          <div class="retry-item">
            <div class="retry-header">
              <div class="retry-title">
                <span class="retry-index">第 {{ retryHistory.length - index }} 次执行</span>
                <a-tag v-if="retry.is_latest" color="green" size="small">当前</a-tag>
                <a-tag v-else-if="index === retryHistory.length - 1" color="blue" size="small">原始</a-tag>
              </div>
              <div class="retry-time">{{ formatDateTime(retry.created_at) }}</div>
            </div>

            <div class="retry-status">
              <a-tag :color="getStatusColor(retry.status)">
                {{ getStatusText(retry.status) }}
              </a-tag>
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
              <a-button size="small" @click="handleView(retry)">查看详情</a-button>
            </div>
          </div>
        </a-timeline-item>
      </a-timeline>

      <a-empty v-else description="暂无重试历史" />
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useFilterQuerySync } from '@/composables/useFilterQuerySync'
import dayjs from 'dayjs'
import { useRouter } from 'vue-router'
import { Message, Modal } from '@arco-design/web-vue'
import {
  IconSearch,
  IconRefresh,
  IconHistory,
  IconEye,
  IconClose
} from '@arco-design/web-vue/es/icon'
import { executionRecordApi } from '@/api/ops'
import { usePermissionsStore } from '@/stores/permissions'

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
const columns = [
  {
    title: '执行ID',
    dataIndex: 'execution_id',
    slotName: 'execution_id',
    width: 180,
    ellipsis: true,
    tooltip: true
  },
  {
    title: '执行名称',
    dataIndex: 'name',
    slotName: 'name',
    width: 200,
    ellipsis: true,
    tooltip: true
  },
  {
    title: '执行类型',
    dataIndex: 'execution_type',
    slotName: 'execution_type',
    width: 150
  },
  {
    title: '状态',
    dataIndex: 'status',
    slotName: 'status',
    width: 100
  },
  {
    title: '执行时长',
    dataIndex: 'duration',
    slotName: 'duration',
    width: 120
  },
  {
    title: '执行用户',
    dataIndex: 'executed_by_name',
    width: 120
  },
  {
    title: '创建信息',
    dataIndex: 'created_at',
    slotName: 'created_at',
    width: 160
  },
  {
    title: '操作',
    key: 'actions',
    slotName: 'actions',
    width: 200,
    fixed: 'right'
  }
]

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
    await Modal.confirm({
      title,
      content,
      onOk: async () => {
        try {
          console.log('开始调用重做API, 执行记录ID:', record.id)
          const result = await executionRecordApi.retryExecution(record.id)
          console.log('重做API返回结果:', result)

          Message.success(successMessage)

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
          Message.error('重做操作失败')
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
    await Modal.confirm({
      title: '确认取消',
      content: `确定要取消执行"${record.name}"吗？`,
      onOk: async () => {
        await executionRecordApi.cancelExecution(record.id)
        Message.success('取消成功')
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
    Message.error('获取重试历史失败')
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
  Message.warning('没有权限执行此操作，请联系管理员开放权限')
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

const getStatusIcon = (status) => {
  const iconMap = {
    'pending': 'icon-pause',
    'running': 'icon-loading',
    'success': 'icon-check',
    'failed': 'icon-exclamation',
    'cancelled': 'icon-close'
  }
  return iconMap[status] || 'icon-pause'
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
</script>

<style scoped>
.execution-records-page {
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
