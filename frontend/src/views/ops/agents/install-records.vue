<template>
  <div class="install-records-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-content">
        <div class="header-left">
          <h2>Agent 安装记录</h2>
          <p class="header-desc">查看和管理 Agent 安装历史记录</p>
        </div>
        <div class="header-right">
          <n-space>
            <n-button @click="handleRefresh">
              <template #icon>
                <RefreshCw />
              </template>
              刷新
            </n-button>
          </n-space>
        </div>
      </div>
    </div>

    <!-- 搜索栏 -->
    <n-card class="mb-4">
      <n-form :model="searchForm" layout="inline">
        <n-form-item label="搜索">
          <n-input
            v-model:value="searchForm.search"
            placeholder="主机名、IP"
            clearable
            @press-enter="handleSearch"
            @clear="handleSearch"
            style="width: 250px"
          />
        </n-form-item>
        <n-form-item label="状态">
                    <n-select
            v-model:value="searchForm.status"
            placeholder="请选择状态"
            clearable
            @change="handleSearch"
            @clear="handleSearch"
            style="width: 120px" :options="selectOptions1" />
        </n-form-item>
        <n-form-item>
          <n-button type="primary" @click="handleSearch">
            <template #icon>
              <Search />
            </template>
            搜索
          </n-button>
          <n-button @click="handleReset" style="margin-left: 8px">
            <template #icon>
              <RefreshCw />
            </template>
            重置
          </n-button>
        </n-form-item>
      </n-form>
    </n-card>

    <!-- 安装记录列表 -->
    <div class="table-container">
      <n-data-table
        :columns="columns"
        :data="records"
        :loading="loading"
        :pagination="tablePagination"
        remote
      />
    </div>

    <!-- 详情对话框 -->
    <n-modal preset="card" :style="{ width: '800px' }"
      v-model:show="detailVisible"
      title="安装记录详情"
     
     
    >
      <n-descriptions
        v-if="currentRecord"
        :column="1"
        bordered
        size="large"
      >
        <n-descriptions-item label="主机信息">
          <div>
            <div><strong>主机名：</strong>{{ currentRecord.host_name }}</div>
            <div><strong>IP 地址：</strong>{{ currentRecord.host_ip }}</div>
          </div>
        </n-descriptions-item>
        <n-descriptions-item label="安装模式">
          <n-tag type="info">Agent-Server 模式
          </n-tag>
        </n-descriptions-item>
        <n-descriptions-item v-if="currentRecord.package_version_display" label="版本">
          {{ currentRecord.package_version_display }}
        </n-descriptions-item>
        <n-descriptions-item v-if="currentRecord.package_os_type" label="操作系统">
          {{ currentRecord.package_os_type }}
        </n-descriptions-item>
        <n-descriptions-item v-if="currentRecord.package_arch" label="架构">
          {{ currentRecord.package_arch }}
        </n-descriptions-item>
        <n-descriptions-item v-if="currentRecord && currentRecord.control_plane_url" label="控制面url">
          <div style="word-break: break-all">{{ currentRecord.control_plane_url }}</div>
        </n-descriptions-item>
        <n-descriptions-item label="安装状态">
          <n-space><n-tag :type="getStatusColor(currentRecord.status) as any">
            {{ currentRecord.status_display }}
          </n-tag>
            <n-button
              v-if="currentRecord.status === 'failed'"
              type="primary"
              size="small"
              @click="handleRetryInstall(currentRecord)"
            >
              <template #icon>
                <RefreshCw />
              </template>
              重试安装
            </n-button>
          </n-space>
        </n-descriptions-item>
        <n-descriptions-item label="安装用户">
          {{ currentRecord.installed_by_name }}
        </n-descriptions-item>
        <n-descriptions-item label="安装时间">
          {{ formatDateTime(currentRecord.installed_at) }}
        </n-descriptions-item>
        <n-descriptions-item v-if="currentRecord.task_total_hosts" label="任务统计">
          <div class="task-stats-detail">
            <div class="stat-item">
              <span class="stat-label">总主机数:</span>
              <span class="stat-value">{{ currentRecord.task_total_hosts }}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label stat-success">成功:</span>
              <span class="stat-value stat-success">{{ currentRecord.task_success_count }}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label stat-error">失败:</span>
              <span class="stat-value stat-error">{{ currentRecord.task_failed_count }}</span>
            </div>
          </div>
        </n-descriptions-item>
        <n-descriptions-item v-if="currentRecord.agent_id" label="关联 Agent">
          <n-button text size="small" @click="handleViewAgent(currentRecord)">
            查看 Agent #{{ currentRecord.agent_id }}
          </n-button>
        </n-descriptions-item>
        <n-descriptions-item v-if="currentRecord.host_id" label="关联 主机">
          <n-button text size="small" @click="handleViewHost(currentRecord)">
            查看 主机 #{{ currentRecord.host_id }}
          </n-button>
        </n-descriptions-item>
        <n-descriptions-item v-if="currentRecord.error_message" label="错误信息">
          <div style="color: #f53f3f; white-space: pre-wrap; word-break: break-all; max-height: 200px; overflow-y: auto; padding: 8px; background: #fff2f0; border-radius: 4px;">
            {{ currentRecord.error_message }}
          </div>
        </n-descriptions-item>
        <n-descriptions-item v-if="currentRecord.error_detail" label="错误详情">
          <div style="color: #f53f3f; white-space: pre-wrap; word-break: break-all; max-height: 300px; overflow-y: auto; padding: 8px; background: #fff2f0; border-radius: 4px; font-family: monospace; font-size: 12px;">
            {{ currentRecord.error_detail }}
          </div>
        </n-descriptions-item>
        <n-descriptions-item v-if="currentRecord.message" label="安装消息">
          <div style="white-space: pre-wrap; word-break: break-all; max-height: 200px; overflow-y: auto; padding: 8px; background: #f7f8fa; border-radius: 4px;">
            {{ currentRecord.message }}
          </div>
        </n-descriptions-item>
      </n-descriptions>
    </n-modal>

  </div>
</template>

<script setup lang="ts">
import { computed, h, reactive, ref, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { agentsApi } from '@/api/agents'
import { useFilterQuerySync } from '@/composables/useFilterQuerySync'
import dayjs from 'dayjs'
import { NButton, NCard, NDataTable, NDescriptions, NDescriptionsItem, NForm, NFormItem, NInput, NModal, NSelect, NSpace, NTag, type DataTableColumns, useDialog, useMessage } from 'naive-ui'
import { ChevronRight, Eye, RefreshCw, Search } from 'lucide-vue-next'

// 搜索防抖定时器
let searchDebounceTimer: ReturnType<typeof setTimeout> | null = null

const dialog = useDialog()
const message = useMessage()
const router = useRouter()
const route = useRoute()

// 响应式数据
const loading = ref(false)
const records = ref<any[]>([])
const detailVisible = ref(false)
const currentRecord = ref<any>(null)

// 搜索表单
const searchForm = reactive({
  search: '',
  status: '',
})

// 分页配置
const pagination = reactive({
  current: 1,
  pageSize: 10,
  total: 0,
  showTotal: true,
  showJumper: true,
  showPageSize: true,
  pageSizeOptions: [10, 20, 50, 100],
})

const { initFromQuery, syncToQuery } = useFilterQuerySync({
  searchForm,
  pagination,
  fields: [
    { key: 'search' },
    { key: 'status' }
  ]
})

// 表格列配置
const columns: DataTableColumns<any> = [
  {
    title: '主机信息',
    key: 'host',
    width: 180,
    render: (row) =>
      h('div', {}, [
        h('div', { style: 'font-weight: 500' }, row.host_name),
        h('div', { style: 'color: var(--app-meta); font-size: 12px' }, row.host_ip),
      ]),
  },
  { title: 'Agent ID', key: 'agent_id', width: 100, render: (row) => row.agent_id },
  {
    title: '状态',
    key: 'status',
    width: 100,
    render: (row) => h(NTag, { type: getStatusColor(row.status) as any }, { default: () => row.status_display }),
  },
  { title: '安装用户', key: 'installed_by_name', width: 120, render: (row) => row.installed_by_name },
  {
    title: '任务统计',
    key: 'task_stats',
    width: 150,
    render: (row) =>
      h('div', { class: 'task-stats' }, [
        h('div', { class: 'stat-item' }, [h('span', { class: 'stat-label' }, '总数:'), h('span', { class: 'stat-value' }, String(row.task_total_hosts || 1))]),
        h('div', { class: 'stat-item' }, [h('span', { class: 'stat-label stat-success' }, '成功:'), h('span', { class: 'stat-value stat-success' }, String(row.task_success_count || 0))]),
        h('div', { class: 'stat-item' }, [h('span', { class: 'stat-label stat-error' }, '失败:'), h('span', { class: 'stat-value stat-error' }, String(row.task_failed_count || 0))]),
      ]),
  },
  { title: '安装时间', key: 'installed_at', width: 180, render: (row) => formatDateTime(row.installed_at) },
  {
    title: '操作',
    key: 'actions',
    width: 260,
    render: (row) =>
      h(NSpace, { size: 4, wrap: false, wrapItem: false, align: 'center' }, {
        default: () => [
          h(NButton, { text: true, size: 'small', onClick: () => handleViewDetail(row) }, {
            icon: () => h(Eye, { size: 14 }),
            default: () => '查看详情',
          }),
          row.agent_id
            ? h(NButton, { text: true, size: 'small', onClick: () => handleViewAgent(row) }, {
                icon: () => h(ChevronRight, { size: 14 }),
                default: () => '查看 Agent',
              })
            : null,
          canRetryFailedHosts(row)
            ? h(NButton, { size: 'small', type: 'warning', onClick: () => handleRetryFailedHosts(row) }, {
                icon: () => h(RefreshCw, { size: 14 }),
                default: () => '重试失败主机',
              })
            : null,
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

// 获取安装记录列表
const fetchRecords = async () => {
  loading.value = true
  try {
    const params: any = {
      page: pagination.current,
      page_size: pagination.pageSize,
    }

    // 添加筛选条件
    if (searchForm.status) {
      params.status = searchForm.status
    }
    if (searchForm.search) {
      params.search = searchForm.search
    }

    const response = await agentsApi.getInstallRecords(params)
    records.value = response.results || []
    pagination.total = response.total || 0
  } catch (error: any) {
    console.error('获取安装记录失败:', error)
    const errorMsg = error?.response?.data?.message || error?.message || '获取安装记录失败'
    message.error(errorMsg)
    records.value = []
    pagination.total = 0
  } finally {
    loading.value = false
  }
}

watch(
  () => route.query,
  () => {
    initFromQuery()
    fetchRecords()
  },
  { immediate: true }
)

// 搜索（带防抖）
const handleSearch = () => {
  // 清除之前的防抖定时器
  if (searchDebounceTimer) {
    clearTimeout(searchDebounceTimer)
  }
  // 设置新的防抖定时器（300ms）
  searchDebounceTimer = setTimeout(() => {
    pagination.current = 1
    syncToQuery()
  }, 300)
}

// 重置
const handleReset = () => {
  // 清除防抖定时器
  if (searchDebounceTimer) {
    clearTimeout(searchDebounceTimer)
    searchDebounceTimer = null
  }
  searchForm.search = ''
  searchForm.status = ''
  pagination.current = 1
  syncToQuery()
}

// 刷新
const handleRefresh = () => {
  fetchRecords()
}

// 分页变化
const handlePageChange = (page: number) => {
  pagination.current = page
  syncToQuery()
}

const handlePageSizeChange = (size: number) => {
  pagination.pageSize = size
  pagination.current = 1
  syncToQuery()
}

// 获取状态颜色
const getStatusColor = (status: string) => {
  const colorMap: Record<string, string> = {
    pending: 'orange',
    success: 'green',
    failed: 'red',
  }
  return colorMap[status] || 'gray'
}

// 格式化时间
const formatDateTime = (dateTime: string) => {
  if (!dateTime) return '-'
  return dayjs(dateTime).format('YYYY-MM-DD HH:mm:ss')
}

// 查看详情（使用列表数据，不再调用单条详情接口）
const handleViewDetail = (record: any) => {
  currentRecord.value = record
  detailVisible.value = true
}

// 查看 Agent
const handleViewAgent = (record: any) => {
  if (record.agent_id) {
    router.push({
      name: 'OpsAgentDetail',
      params: { id: record.agent_id },
    })
  }
}

// 检查是否可以重试失败主机
const canRetryFailedHosts = (record: any) => {
  // 如果该记录对应的任务有失败的记录，则可以重试
  return record.task_failed_count > 0 && record.status === 'failed'
}

// 重试失败主机
const handleRetryFailedHosts = async (record: any) => {
  dialog.warning({
    title: '确认重试失败主机',
    content: `确定要重试该安装任务中的 ${record.task_failed_count} 个失败主机吗？`,
    positiveText: '确认重试',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        const result = await agentsApi.retryInstallRecord({
          install_record_id: record.id,
          confirmed: true,
        })

        message.success(`重试任务已启动，可通过安装记录查看进度`)
        // 可以选择刷新列表或跳转到新的安装任务进度
        fetchRecords()
      } catch (error: any) {
        console.error('重试失败主机失败:', error)
        message.error(error?.message || '重试失败主机失败')
      }
    },
  })
}

const handleViewHost = (record: any) => {
  if (record.host_id) {
    router.push({
      name: 'OpsHostDetail',
      params: { id: record.host_id },
    })
  }
}

// 重试安装
const handleRetryInstall = async (record: any) => {
  try {
    dialog.warning({
      title: '确认重试安装',
      content: `确定要重新安装 Agent 到主机 ${record.host_name} (${record.host_ip}) 吗？`,
      onPositiveClick: async () => {
        try {
          // 调用批量安装 API，但只针对当前主机
          const response = await agentsApi.batchInstall({
            host_ids: [record.host_id],
            agent_server_url: record.agent_server_url || '',
            agent_server_backup_url: record.agent_server_backup_url || '',
            package_id: record.package_id || null,
            confirmed: true,
            allow_reinstall: true, // 允许重新安装
          })
          
          message.success('重试安装任务已提交，请查看安装记录')
          
          // 关闭详情对话框
          detailVisible.value = false
          
          // 刷新列表
          await fetchRecords()
        } catch (error: any) {
          console.error('重试安装失败:', error)
          const errorMsg = error?.response?.data?.message || error?.message || '重试安装失败'
          message.error(errorMsg)
        }
      },
    })
  } catch (error: any) {
    console.error('重试安装失败:', error)
  }
}


// 机械转换生成的静态下拉选项
const selectOptions1 = [{ label: '安装中', value: 'pending' }, { label: '成功', value: 'success' }, { label: '失败', value: 'failed' }]
</script>

<style scoped>
.install-records-page {
  padding: 0;
}

.page-header {
  background: white;
  border-radius: 6px;
  padding: 20px 24px;
  margin-bottom: 16px;
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.03), 0 1px 6px -1px rgba(0, 0, 0, 0.02), 0 2px 4px 0 rgba(0, 0, 0, 0.02);
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left h2 {
  margin: 0 0 4px 0;
  font-size: 20px;
  font-weight: 600;
  color: #1d2129;
}

.header-desc {
  margin: 0;
  font-size: 14px;
  color: #86909c;
}

.mb-4 {
  margin-bottom: 16px;
}

.table-container {
  background: white;
  border-radius: 6px;
  overflow: hidden;
}

/* 表格样式优化 */
:deep(.arco-table) {
  /* 普通表头背景色 */
  .arco-table-th {
    background-color: #fff !important;
  }

  /* 固定列样式 */
  .arco-table-col-fixed-right {
    background-color: transparent !important;
  }

  .arco-table-col-fixed-right .arco-table-td {
    background-color: inherit !important;
  }

  .arco-table-col-fixed-right .arco-table-cell {
    background-color: inherit !important;
  }

  .arco-table-col-fixed-right::before {
    background-color: transparent !important;
    box-shadow: none !important;
  }

  .task-stats {
    display: flex;
    flex-direction: column;
    gap: 2px;
    font-size: 12px;
  }

  .stat-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .stat-label {
    color: #86909c;
    font-weight: 500;
  }

  .stat-value {
    font-weight: 600;
  }

  .stat-success {
    color: #00b42a;
  }

  .stat-error {
    color: #f53f3f;
  }

  .task-stats-detail {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
}
</style>
