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
          <a-space>
            <a-button @click="handleRefresh">
              <template #icon>
                <IconRefresh />
              </template>
              刷新
            </a-button>
          </a-space>
        </div>
      </div>
    </div>

    <!-- 搜索栏 -->
    <a-card class="mb-4">
      <a-form :model="searchForm" layout="inline">
        <a-form-item label="搜索">
          <a-input
            v-model="searchForm.search"
            placeholder="主机名、IP"
            allow-clear
            @press-enter="handleSearch"
            @clear="handleSearch"
            style="width: 250px"
          />
        </a-form-item>
        <a-form-item label="状态">
          <a-select
            v-model="searchForm.status"
            placeholder="请选择状态"
            allow-clear
            @change="handleSearch"
            @clear="handleSearch"
            style="width: 120px"
          >
            <a-option value="pending">安装中</a-option>
            <a-option value="success">成功</a-option>
            <a-option value="failed">失败</a-option>
          </a-select>
        </a-form-item>
        <a-form-item>
          <a-button type="primary" @click="handleSearch">
            <template #icon>
              <IconSearch />
            </template>
            搜索
          </a-button>
          <a-button @click="handleReset" style="margin-left: 8px">
            <template #icon>
              <IconRefresh />
            </template>
            重置
          </a-button>
        </a-form-item>
      </a-form>
    </a-card>

    <!-- 安装记录列表 -->
    <div class="table-container">
      <a-table
        :columns="columns"
        :data="records"
        :loading="loading"
        :pagination="pagination"
        @page-change="handlePageChange"
        @page-size-change="handlePageSizeChange"
      >
        <template #host="{ record }">
          <div>
            <div style="font-weight: 500">{{ record.host_name }}</div>
            <div style="color: #86909c; font-size: 12px">{{ record.host_ip }}</div>
          </div>
        </template>

        <template #status="{ record }">
          <a-tag :color="getStatusColor(record.status)">
            {{ record.status_display }}
          </a-tag>
        </template>

        <template #install_mode="{ record }">
          <a-tag color="blue">Agent-Server</a-tag>
        </template>

        <template #task_stats="{ record }">
          <div class="task-stats">
            <div class="stat-item">
              <span class="stat-label">总数:</span>
              <span class="stat-value">{{ record.task_total_hosts || 1 }}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label stat-success">成功:</span>
              <span class="stat-value stat-success">{{ record.task_success_count || 0 }}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label stat-error">失败:</span>
              <span class="stat-value stat-error">{{ record.task_failed_count || 0 }}</span>
            </div>
          </div>
        </template>

        <template #installed_at="{ record }">
          {{ formatDateTime(record.installed_at) }}
        </template>

        <template #actions="{ record }">
          <a-space>
            <a-button type="text" size="small" @click="handleViewDetail(record)">
              <template #icon>
                <IconEye />
              </template>
              查看详情
            </a-button>
            <a-button
              v-if="record.agent_id"
              type="text"
              size="small"
              @click="handleViewAgent(record)"
            >
              <template #icon>
                <IconRight />
              </template>
              查看 Agent
            </a-button>
            <a-button
              v-if="canRetryFailedHosts(record)"
              type="text"
              size="small"
              status="warning"
              @click="handleRetryFailedHosts(record)"
            >
              <template #icon>
                <IconRefresh />
              </template>
              重试失败主机
            </a-button>
          </a-space>
        </template>
      </a-table>
    </div>

    <!-- 详情对话框 -->
    <a-modal
      v-model:visible="detailVisible"
      title="安装记录详情"
      width="800px"
      :footer="false"
    >
      <a-descriptions
        v-if="currentRecord"
        :column="1"
        bordered
        size="large"
      >
        <a-descriptions-item label="主机信息">
          <div>
            <div><strong>主机名：</strong>{{ currentRecord.host_name }}</div>
            <div><strong>IP 地址：</strong>{{ currentRecord.host_ip }}</div>
          </div>
        </a-descriptions-item>
        <a-descriptions-item label="安装模式">
          <a-tag color="blue">Agent-Server 模式
          </a-tag>
        </a-descriptions-item>
        <a-descriptions-item v-if="currentRecord.package_version_display" label="版本">
          {{ currentRecord.package_version_display }}
        </a-descriptions-item>
        <a-descriptions-item v-if="currentRecord.package_os_type" label="操作系统">
          {{ currentRecord.package_os_type }}
        </a-descriptions-item>
        <a-descriptions-item v-if="currentRecord.package_arch" label="架构">
          {{ currentRecord.package_arch }}
        </a-descriptions-item>
        <a-descriptions-item v-if="currentRecord && currentRecord.control_plane_url" label="控制面url">
          <div style="word-break: break-all">{{ currentRecord.control_plane_url }}</div>
        </a-descriptions-item>
        <a-descriptions-item label="安装状态">
          <a-space>
          <a-tag :color="getStatusColor(currentRecord.status)">
            {{ currentRecord.status_display }}
          </a-tag>
            <a-button
              v-if="currentRecord.status === 'failed'"
              type="primary"
              size="small"
              @click="handleRetryInstall(currentRecord)"
            >
              <template #icon>
                <IconRefresh />
              </template>
              重试安装
            </a-button>
          </a-space>
        </a-descriptions-item>
        <a-descriptions-item label="安装用户">
          {{ currentRecord.installed_by_name }}
        </a-descriptions-item>
        <a-descriptions-item label="安装时间">
          {{ formatDateTime(currentRecord.installed_at) }}
        </a-descriptions-item>
        <a-descriptions-item v-if="currentRecord.task_total_hosts" label="任务统计">
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
        </a-descriptions-item>
        <a-descriptions-item v-if="currentRecord.agent_id" label="关联 Agent">
          <a-button type="text" size="small" @click="handleViewAgent(currentRecord)">
            查看 Agent #{{ currentRecord.agent_id }}
          </a-button>
        </a-descriptions-item>
        <a-descriptions-item v-if="currentRecord.host_id" label="关联 主机">
          <a-button type="text" size="small" @click="handleViewHost(currentRecord)">
            查看 主机 #{{ currentRecord.host_id }}
          </a-button>
        </a-descriptions-item>
        <a-descriptions-item v-if="currentRecord.error_message" label="错误信息">
          <div style="color: #f53f3f; white-space: pre-wrap; word-break: break-all; max-height: 200px; overflow-y: auto; padding: 8px; background: #fff2f0; border-radius: 4px;">
            {{ currentRecord.error_message }}
          </div>
        </a-descriptions-item>
        <a-descriptions-item v-if="currentRecord.error_detail" label="错误详情">
          <div style="color: #f53f3f; white-space: pre-wrap; word-break: break-all; max-height: 300px; overflow-y: auto; padding: 8px; background: #fff2f0; border-radius: 4px; font-family: monospace; font-size: 12px;">
            {{ currentRecord.error_detail }}
          </div>
        </a-descriptions-item>
        <a-descriptions-item v-if="currentRecord.message" label="安装消息">
          <div style="white-space: pre-wrap; word-break: break-all; max-height: 200px; overflow-y: auto; padding: 8px; background: #f7f8fa; border-radius: 4px;">
            {{ currentRecord.message }}
          </div>
        </a-descriptions-item>
      </a-descriptions>
    </a-modal>

  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Message, Modal } from '@arco-design/web-vue'
import {
  IconSearch,
  IconRefresh,
  IconEye,
  IconRight,
} from '@arco-design/web-vue/es/icon'
import { agentsApi } from '@/api/agents'
import dayjs from 'dayjs'

// 搜索防抖定时器
let searchDebounceTimer: ReturnType<typeof setTimeout> | null = null

const router = useRouter()

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

// 表格列配置
const columns = [
  {
    title: '主机信息',
    dataIndex: 'host',
    slotName: 'host',
    width: 180,
  },
  {
    title: 'Agent ID',
    dataIndex: 'agent_id',
    width: 100,
  },
  {
    title: '状态',
    dataIndex: 'status',
    slotName: 'status',
    width: 100,
  },
  {
    title: '安装用户',
    dataIndex: 'installed_by_name',
    width: 120,
  },
  {
    title: '任务统计',
    dataIndex: 'task_stats',
    slotName: 'task_stats',
    width: 150,
  },
  {
    title: '安装时间',
    dataIndex: 'installed_at',
    slotName: 'installed_at',
    width: 180,
  },
  {
    title: '操作',
    key: 'actions',
    slotName: 'actions',
    width: 200,
    fixed: 'right',
  },
]

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
    Message.error(errorMsg)
    records.value = []
    pagination.total = 0
  } finally {
    loading.value = false
  }
}

// 搜索（带防抖）
const handleSearch = () => {
  // 清除之前的防抖定时器
  if (searchDebounceTimer) {
    clearTimeout(searchDebounceTimer)
  }
  // 设置新的防抖定时器（300ms）
  searchDebounceTimer = setTimeout(() => {
  pagination.current = 1
  fetchRecords()
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
  fetchRecords()
}

// 刷新
const handleRefresh = () => {
  fetchRecords()
}

// 分页变化
const handlePageChange = (page: number) => {
  pagination.current = page
  fetchRecords()
}

const handlePageSizeChange = (size: number) => {
  pagination.pageSize = size
  pagination.current = 1
  fetchRecords()
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
  Modal.confirm({
    title: '确认重试失败主机',
    content: `确定要重试该安装任务中的 ${record.task_failed_count} 个失败主机吗？`,
    okText: '确认重试',
    cancelText: '取消',
    onOk: async () => {
      try {
        const result = await agentsApi.retryInstallRecord({
          install_record_id: record.id,
          confirmed: true,
        })

        Message.success(`重试任务已启动，可通过安装记录查看进度`)
        // 可以选择刷新列表或跳转到新的安装任务进度
        fetchRecords()
      } catch (error: any) {
        console.error('重试失败主机失败:', error)
        Message.error(error?.message || '重试失败主机失败')
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
    Modal.confirm({
      title: '确认重试安装',
      content: `确定要重新安装 Agent 到主机 ${record.host_name} (${record.host_ip}) 吗？`,
      onOk: async () => {
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
          
          Message.success('重试安装任务已提交，请查看安装记录')
          
          // 关闭详情对话框
          detailVisible.value = false
          
          // 刷新列表
          await fetchRecords()
        } catch (error: any) {
          console.error('重试安装失败:', error)
          const errorMsg = error?.response?.data?.message || error?.message || '重试安装失败'
          Message.error(errorMsg)
        }
      },
    })
  } catch (error: any) {
    console.error('重试安装失败:', error)
  }
}

// 初始化
onMounted(() => {
  fetchRecords()
})
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
