<template>
  <div class="app-page audit-logs-page">
    <PageHeader
      eyebrow="审计追踪"
      title="审计日志"
      description="集中查看用户操作、资源变更和系统安全事件，便于追踪责任链路。"
    >
      <template #actions>
        <a-space>
          <a-button type="primary" @click="exportLogs" :loading="exporting">
            <template #icon>
              <icon-download />
            </template>
            导出日志
          </a-button>
          <a-button @click="handleRefresh">
            <template #icon>
              <icon-refresh />
            </template>
            刷新
          </a-button>
        </a-space>
      </template>
    </PageHeader>

    <DataToolbar
      title="筛选审计记录"
      description="按用户、操作类型、状态和日期快速定位关键变更。"
      :active-count="auditActiveFilterCount"
    >
      <div class="audit-filter-grid">
        <label class="filter-field">
          <span>关键词</span>
          <a-input
            v-model="searchForm.search"
            placeholder="搜索描述、资源名称等"
            allow-clear
            @press-enter="handleSearch"
          />
        </label>
        <label class="filter-field">
          <span>用户</span>
          <a-select
            v-model="searchForm.user_id"
            placeholder="选择用户"
            allow-clear
            @change="handleSearch"
          >
            <a-option
              v-for="user in userOptions"
              :key="user.id"
              :value="user.id"
              :label="user.username"
            />
          </a-select>
        </label>
        <label class="filter-field">
          <span>操作类型</span>
          <a-select
            v-model="searchForm.action"
            placeholder="选择操作类型"
            allow-clear
            @change="handleSearch"
          >
            <a-option
              v-for="action in actionOptions"
              :key="action.value"
              :value="action.value"
              :label="action.label"
            />
          </a-select>
        </label>
        <label class="filter-field">
          <span>状态</span>
          <a-select
            v-model="searchForm.success"
            placeholder="选择状态"
            allow-clear
            @change="handleSearch"
          >
            <a-option :value="true" label="成功" />
            <a-option :value="false" label="失败" />
          </a-select>
        </label>
        <label class="filter-field">
          <span>开始日期</span>
          <a-date-picker
            v-model="searchForm.start_date"
            placeholder="开始日期"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
            @change="handleSearch"
          />
        </label>
        <label class="filter-field">
          <span>结束日期</span>
          <a-date-picker
            v-model="searchForm.end_date"
            placeholder="结束日期"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
            @change="handleSearch"
          />
        </label>
        <div class="filter-actions">
          <a-space>
            <a-button type="primary" @click="handleSearch">
              <template #icon><icon-search /></template>
              搜索
            </a-button>
            <a-button @click="resetSearch">
              <template #icon><icon-refresh /></template>
              重置
            </a-button>
          </a-space>
        </div>
      </div>
    </DataToolbar>

    <DetailPanel
      title="审计明细"
      :description="`共 ${pagination.total} 条记录，当前页 ${auditLogs.length} 条`"
    >
      <a-table
        :data="auditLogs"
        :loading="loading"
        :pagination="pagination"
        @page-change="handlePageChange"
        @page-size-change="handlePageSizeChange"
        row-key="id"
      >
        <template #columns>
          <a-table-column title="用户" data-index="user_name" :width="120">
            <template #cell="{ record }">
              <div class="user-info">
                <a-avatar :size="24" class="user-avatar">
                  {{ getUserInitial(record) }}
                </a-avatar>
                <span>{{ getUserName(record) }}</span>
              </div>
            </template>
          </a-table-column>

          <a-table-column title="操作类型" data-index="action_display" :width="120">
            <template #cell="{ record }">
              <a-tag :color="getActionColor(record.action)">
                {{ record.action_display }}
              </a-tag>
            </template>
          </a-table-column>

          <a-table-column title="资源" data-index="resource_name" :width="170">
            <template #cell="{ record }">
              <div v-if="record.resource_name">
                <div class="resource-info">
                  <span class="resource-name">{{ record.resource_name }}</span>
                  <span v-if="record.resource_type_name || record.resource_type" class="resource-type">
                    ({{ record.resource_type_name || record.resource_type }})
                  </span>
                </div>
              </div>
              <span v-else class="text-muted">-</span>
            </template>
          </a-table-column>

          <a-table-column title="描述" data-index="description" :min-width="240" :width="320">
            <template #cell="{ record }">
              <div class="description-cell">
                <a-tooltip :content="record.description" position="top">
                  <span class="description-text">{{ record.description }}</span>
                </a-tooltip>
              </div>
            </template>
          </a-table-column>

          <a-table-column title="IP地址" data-index="ip_address" :width="120" />

          <a-table-column title="状态" data-index="success" :width="80">
            <template #cell="{ record }">
              <StatusBadge
                :status="record.success ? 'success' : 'failed'"
                :text="record.success ? '成功' : '失败'"
              />
            </template>
          </a-table-column>

          <a-table-column title="时间" data-index="created_at" :width="240">
            <template #cell="{ record }">
              <span>{{ formatDateTime(record.created_at) }}</span>
            </template>
          </a-table-column>

          <a-table-column title="操作" :width="100">
            <template #cell="{ record }">
              <a-button
                type="text"
                size="small"
                @click="viewDetail(record)"
              >
                详情
              </a-button>
            </template>
          </a-table-column>
        </template>
      </a-table>
    </DetailPanel>

    <!-- 详情弹窗 -->
    <a-modal
      v-model:visible="detailVisible"
      title="审计日志详情"
      width="800px"
      :footer="false"
    >
      <div v-if="currentLog" class="detail-content">
        <a-descriptions :column="2" bordered>
          <a-descriptions-item label="用户">
            {{ currentLog.user_full_name || currentLog.user_name }}
          </a-descriptions-item>
          <a-descriptions-item label="操作类型">
            <a-tag :color="getActionColor(currentLog.action)">
              {{ currentLog.action_display }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="资源名称">
            {{ currentLog.resource_name || '-' }}
          </a-descriptions-item>
          <a-descriptions-item label="资源类型">
            {{ currentLog.resource_type_name || currentLog.resource_type || '-' }}
          </a-descriptions-item>
          <a-descriptions-item label="IP地址">
            {{ currentLog.ip_address }}
          </a-descriptions-item>
          <a-descriptions-item label="状态">
            <a-tag :color="currentLog.success ? 'green' : 'red'">
              {{ currentLog.success ? '成功' : '失败' }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="操作时间" :span="2">
            {{ formatDateTime(currentLog.created_at) }}
          </a-descriptions-item>
          <a-descriptions-item label="操作描述" :span="2">
            {{ currentLog.description }}
          </a-descriptions-item>
          <a-descriptions-item v-if="currentLog.error_message" label="错误信息" :span="2">
            <div class="error-message">{{ currentLog.error_message }}</div>
          </a-descriptions-item>
          <a-descriptions-item v-if="currentLog.extra_data && Object.keys(currentLog.extra_data).length > 0" label="额外数据" :span="2">
            <pre class="extra-data">{{ JSON.stringify(currentLog.extra_data, null, 2) }}</pre>
          </a-descriptions-item>
        </a-descriptions>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { Message } from '@arco-design/web-vue'
import { auditLogApi } from '@/api/ops'
import { authApi } from '@/api/auth'
import type { AuditLog, AuditLogQueryParams } from '@/types'
import { formatDateTime } from '@/utils/date'
import { useFilterQuerySync, parseNumberQuery, parseBooleanQuery } from '@/composables/useFilterQuerySync'
import { DataToolbar, DetailPanel, PageHeader, StatusBadge, countActiveFilters } from '@/components/app'

// 响应式数据
const loading = ref(false)
const exporting = ref(false)
const auditLogs = ref<AuditLog[]>([])
const detailVisible = ref(false)
const currentLog = ref<AuditLog | null>(null)
const lastApiStatus = ref<string>('未请求')

// 分页
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

// 搜索表单
const searchForm = reactive<AuditLogQueryParams>({
  search: '',
  user_id: undefined,
  action: '',
  success: undefined,
  start_date: '',
  end_date: '',
})

const auditActiveFilterCount = computed(() => countActiveFilters(searchForm as unknown as Record<string, unknown>))

const { initFromQuery, syncToQuery } = useFilterQuerySync({
  searchForm,
  pagination,
  fields: [
    { key: 'search' },
    { key: 'user_id', fromQuery: value => parseNumberQuery(value) },
    { key: 'action' },
    { key: 'success', fromQuery: value => parseBooleanQuery(value) },
    { key: 'start_date' },
    { key: 'end_date' },
  ]
})

// 用户选项（这里需要从用户API获取）
const userOptions = ref<Array<{ id: number; username: string }>>([])

// 操作类型选项
const actionOptions = computed(() => [
  { value: 'login', label: '登录' },
  { value: 'logout', label: '登出' },
  { value: 'create', label: '创建' },
  { value: 'update', label: '更新' },
  { value: 'delete', label: '删除' },
  { value: 'execute', label: '执行' },
  { value: 'execute_script', label: '执行脚本' },
  { value: 'transfer_file', label: '传输文件' },
  { value: 'retry_execution', label: '重做执行' },
  { value: 'cancel_execution', label: '取消执行' },
  { value: 'ignore_error', label: '忽略错误继续' },
  { value: 'retry_step', label: '步骤重试' },
  { value: 'retry_failed_hosts', label: '失败主机重试' },
  { value: 'create_job', label: '创建作业' },
  { value: 'execute_job', label: '执行作业' },
  { value: 'cancel_job', label: '取消作业' },
  { value: 'create_scheduled_job', label: '创建定时作业' },
  { value: 'update_scheduled_job', label: '更新定时作业' },
  { value: 'delete_scheduled_job', label: '删除定时作业' },
  { value: 'enable_scheduled_job', label: '启用定时作业' },
  { value: 'disable_scheduled_job', label: '停用定时作业' },
  { value: 'manage_host', label: '管理主机' },
  { value: 'manage_server_account', label: '管理服务器账号' },
  { value: 'test_connection', label: '测试连接' },
  { value: 'enable_agent', label: '启用Agent' },
  { value: 'disable_agent', label: '禁用Agent' },
  { value: 'manage_template', label: '管理模板' },
  { value: 'create_template', label: '创建模板' },
  { value: 'update_template', label: '更新模板' },
  { value: 'delete_template', label: '删除模板' },
  { value: 'system_config', label: '系统配置' },
  { value: 'user_management', label: '用户管理' },
  { value: 'collect_system_info', label: '收集系统信息' },
  { value: 'sync_cloud_hosts', label: '同步云主机' },
])

// 获取操作类型颜色
const getActionColor = (action: string) => {
  const colorMap: Record<string, string> = {
    login: 'blue',
    logout: 'gray',
    create: 'green',
    update: 'orange',
    delete: 'red',
    execute: 'purple',
    execute_script: 'cyan',
    transfer_file: 'purple',
    retry_execution: 'orange',
    cancel_execution: 'red',
    ignore_error: 'orange',
    retry_step: 'orange',
    retry_failed_hosts: 'orange',
    create_job: 'green',
    execute_job: 'blue',
    cancel_job: 'red',
    create_scheduled_job: 'green',
    update_scheduled_job: 'orange',
    delete_scheduled_job: 'red',
    enable_scheduled_job: 'cyan',
    disable_scheduled_job: 'gray',
    manage_host: 'orange',
    manage_server_account: 'orange',
    test_connection: 'cyan',
    enable_agent: 'green',
    disable_agent: 'red',
    manage_template: 'purple',
    create_template: 'green',
    update_template: 'orange',
    delete_template: 'red',
    grant_permission: 'green',
    revoke_permission: 'red',
    system_config: 'orange',
    user_management: 'purple',
    collect_system_info: 'magenta',
    sync_cloud_hosts: 'cyan',
  }
  return colorMap[action] || 'default'
}

const getUserName = (record: AuditLog) => {
  return record.user_full_name || record.user_name || '未知用户'
}

const getUserInitial = (record: AuditLog) => {
  return getUserName(record).charAt(0).toUpperCase()
}

// 获取审计日志列表
const fetchAuditLogs = async () => {
  try {
    loading.value = true
    const params = {
      page: pagination.current,
      page_size: pagination.pageSize,
      ...searchForm,
    }

    const response = await auditLogApi.getAuditLogs(params)
    
    // 处理响应数据
     auditLogs.value = response.results || []
     pagination.total = response.total || 0
     pagination.current = response.page || 1
     pagination.pageSize = response.page_size || 20
     lastApiStatus.value = `成功 - 获取到 ${auditLogs.value.length} 条记录`
  } catch (error: any) {
    console.error('获取审计日志失败:', error)
    const msg = error?.message || '获取审计日志失败'
    Message.error(msg)
    auditLogs.value = []
    pagination.total = 0
    lastApiStatus.value = `失败 - ${msg}`
  } finally {
    loading.value = false
  }
}

// 获取用户列表
const fetchUsers = async () => {
  try {
    const response = await authApi.getUsers()
    userOptions.value = response.results || response
  } catch (error: any) {
    console.warn('获取用户列表失败:', error.message)
  }
}

// 刷新数据
const handleRefresh = () => {
  fetchAuditLogs()
}

// 搜索
const handleSearch = () => {
  pagination.current = 1
  syncToQuery()
  fetchAuditLogs()
}

// 重置搜索
const resetSearch = () => {
  Object.assign(searchForm, {
    search: '',
    user_id: undefined,
    action: '',
    success: undefined,
    start_date: '',
    end_date: '',
  })
  pagination.current = 1
  syncToQuery()
  fetchAuditLogs()
}

// 分页变化
const handlePageChange = (page: number) => {
  pagination.current = page
  syncToQuery()
  fetchAuditLogs()
}

// 页面大小变化
const handlePageSizeChange = (pageSize: number) => {
  pagination.pageSize = pageSize
  pagination.current = 1
  syncToQuery()
  fetchAuditLogs()
}

// 查看详情
const viewDetail = (record: AuditLog) => {
  currentLog.value = record
  detailVisible.value = true
}

// 导出日志
const exportLogs = async () => {
  try {
    exporting.value = true
    const params = { ...searchForm }
    
    const blob = await auditLogApi.exportAuditLogs(params)
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `audit-logs-${new Date().toISOString().split('T')[0]}.xlsx`
    link.click()
    window.URL.revokeObjectURL(url)
    
    Message.success('导出成功')
  } catch (error: any) {
    Message.error(`导出失败: ${error.message}`)
  } finally {
    exporting.value = false
  }
}

// 初始化
onMounted(() => {
  initFromQuery()
  fetchAuditLogs()
  fetchUsers()
})
</script>

<style scoped>
.audit-logs-page {
  padding: 0;
}

.audit-filter-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 14px;
  align-items: end;
}

.filter-field {
  display: grid;
  gap: 6px;
  min-width: 0;
}

.filter-field > span {
  color: var(--app-muted);
  font-size: 12px;
  line-height: 1.4;
}

.filter-field :deep(.arco-picker),
.filter-field :deep(.arco-select),
.filter-field :deep(.arco-input-wrapper) {
  width: 100%;
}

.filter-actions {
  display: flex;
  justify-content: flex-end;
  min-width: 0;
}

/* 表格样式优化 */
:deep(.arco-table) {
  .arco-table-th {
    background-color: var(--app-surface);
  }
}

.user-info {
  display: flex;
  align-items: center;
}

.user-avatar {
  margin-right: 8px;
}

.resource-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.resource-name {
  font-weight: 500;
}

.resource-type {
  font-size: 12px;
  color: var(--app-muted);
}

.description-cell {
  max-width: 260px;
}

.description-text {
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.text-muted {
  color: var(--app-muted);
}

.detail-content {
  max-height: 600px;
  overflow-y: auto;
}

.error-message {
  color: var(--app-danger);
  background: var(--app-danger-soft);
  padding: 8px;
  border-radius: 4px;
  border: 1px solid var(--app-border);
}

.extra-data {
  background: var(--app-surface-soft);
  padding: 12px;
  border-radius: 4px;
  border: 1px solid var(--app-border);
  font-size: 12px;
  max-height: 200px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
