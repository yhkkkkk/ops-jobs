<template>
  <div class="uninstall-records-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-content">
        <div class="header-left">
          <h2>Agent 卸载记录</h2>
          <p class="header-desc">查看和管理 Agent 卸载历史记录</p>
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

    <!-- 卸载记录列表 -->
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
      title="卸载记录详情"
     
     
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
        <n-descriptions-item v-if="currentRecord.agent_id" label="Agent ID">
          {{ currentRecord.agent_id }}
        </n-descriptions-item>
        <n-descriptions-item label="Agent类型"><n-tag :type="currentRecord.agent_type === 'agent-server' ? 'purple' : 'blue' as any">
            {{ currentRecord.agent_type_display }}
          </n-tag>
        </n-descriptions-item>
        <n-descriptions-item v-if="currentRecord.package_version" label="版本">
          {{ currentRecord.package_version }}
        </n-descriptions-item>
        <n-descriptions-item v-if="currentRecord.package_os_type" label="操作系统">
          {{ currentRecord.package_os_type }}
        </n-descriptions-item>
        <n-descriptions-item v-if="currentRecord.package_arch" label="架构">
          {{ currentRecord.package_arch }}
        </n-descriptions-item>
        <n-descriptions-item label="卸载状态">
          <n-space><n-tag :type="getStatusColor(currentRecord.status) as any">
              {{ currentRecord.status_display }}
            </n-tag>
          </n-space>
        </n-descriptions-item>
        <n-descriptions-item label="卸载时间">
          {{ formatDateTime(currentRecord.uninstalled_at) }}
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
        <n-descriptions-item label="操作者">
          {{ currentRecord.uninstalled_by_name }}
        </n-descriptions-item>
        <n-descriptions-item v-if="currentRecord.message" label="消息">
          <div style="word-break: break-all; white-space: pre-wrap">{{ currentRecord.message }}</div>
        </n-descriptions-item>
        <n-descriptions-item v-if="currentRecord.error_message" label="错误信息">
          <div style="word-break: break-all; white-space: pre-wrap; color: #ff4d4f">{{ currentRecord.error_message }}</div>
        </n-descriptions-item>
        <n-descriptions-item v-if="currentRecord.error_detail" label="错误详情">
          <div style="word-break: break-all; white-space: pre-wrap; color: #ff4d4f">{{ currentRecord.error_detail }}</div>
        </n-descriptions-item>
      </n-descriptions>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, h, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { agentsApi } from '@/api/agents'
import { useFilterQuerySync } from '@/composables/useFilterQuerySync'
import { formatDateTime } from '@/utils/date'
import { NButton, NCard, NDataTable, NDescriptions, NDescriptionsItem, NForm, NFormItem, NInput, NModal, NSelect, NSpace, NTag, type DataTableColumns, useMessage } from 'naive-ui'
import { Eye, RefreshCw, Search } from 'lucide-vue-next'

// 搜索防抖定时器
let searchDebounceTimer: ReturnType<typeof setTimeout> | null = null

const message = useMessage()
const route = useRoute()

// 类型定义
interface UninstallRecord {
  id: number
  host_id: number
  host_name: string
  host_ip: string
  agent_id?: number
  agent_type?: string
  agent_type_display?: string
  status: 'pending' | 'success' | 'failed'
  status_display: string
  package_version?: string
  package_os_type?: string
  package_arch?: string
  message?: string
  error_message?: string
  error_detail?: string
  uninstalled_at: string
  uninstalled_by: number
  uninstalled_by_name: string
  uninstall_task_id: string
  task_total_hosts?: number
  task_success_count?: number
  task_failed_count?: number
}

// 响应式数据
const records = ref<UninstallRecord[]>([])
const loading = ref(false)
const currentRecord = ref<UninstallRecord | null>(null)
const detailVisible = ref(false)

// 搜索表单
const searchForm = reactive({
  search: '',
  status: undefined as string | undefined
})

// 分页配置
const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  showSizeChanger: true,
  showQuickJumper: true,
  pageSizeOptions: ['10', '20', '50', '100']
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
    title: '主机',
    key: 'host',
    width: 180,
    render: (row) =>
      h('div', {}, [
        h('div', { style: 'font-weight: 500' }, row.host_name),
        h('div', { style: 'color: var(--app-meta); font-size: 12px' }, row.host_ip),
      ]),
  },
  { title: 'Agent ID', key: 'agent_id', width: 100, render: (row) => row.agent_id },
  { title: 'Agent类型', key: 'agent_type_display', width: 120, render: (row) => row.agent_type_display },
  {
    title: '状态',
    key: 'status',
    width: 100,
    render: (row) => h(NTag, { type: getStatusColor(row.status) as any }, { default: () => row.status_display }),
  },
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
  { title: '卸载时间', key: 'uninstalled_at', width: 180, render: (row) => formatDateTime(row.uninstalled_at) },
  {
    title: '操作',
    key: 'actions',
    width: 120,
    render: (row) =>
      h(NSpace, { size: 4 }, {
        default: () =>
          h(NButton, { text: true, size: 'small', onClick: () => handleViewDetail(row) }, {
            icon: () => h(Eye, { size: 14 }),
            default: () => '查看详情',
          }),
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

// 获取状态颜色
const getStatusColor = (status: string) => {
  switch (status) {
    case 'success':
      return 'success'
    case 'failed':
      return 'error'
    case 'pending':
      return 'warning'
    default:
      return 'default'
  }
}

// 加载数据
const loadData = async () => {
  try {
    loading.value = true

    const params = {
      page: pagination.current,
      page_size: pagination.pageSize,
      ...searchForm
    }

    const response = await agentsApi.getUninstallRecords(params)
    records.value = response.results
    pagination.total = response.total
  } catch (error) {
    console.error('加载卸载记录失败:', error)
    message.error('加载卸载记录失败')
  } finally {
    loading.value = false
  }
}

watch(
  () => route.query,
  () => {
    initFromQuery()
    loadData()
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

// 重置搜索
const handleReset = () => {
  // 清除防抖定时器
  if (searchDebounceTimer) {
    clearTimeout(searchDebounceTimer)
    searchDebounceTimer = null
  }
  Object.assign(searchForm, {
    search: '',
    status: undefined
  })
  pagination.current = 1
  syncToQuery()
}

// 刷新
const handleRefresh = () => {
  loadData()
}

// 分页变化
const handlePageChange = (page: number) => {
  pagination.current = page
  syncToQuery()
}

const handlePageSizeChange = (pageSize: number) => {
  pagination.pageSize = pageSize
  pagination.current = 1
  syncToQuery()
}

// 查看详情
const handleViewDetail = (record: UninstallRecord) => {
  currentRecord.value = record
  detailVisible.value = true
}


// 机械转换生成的静态下拉选项
const selectOptions1 = [{ label: '卸载中', value: 'pending' }, { label: '成功', value: 'success' }, { label: '失败', value: 'failed' }]
</script>

<style scoped>
.uninstall-records-page {
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
