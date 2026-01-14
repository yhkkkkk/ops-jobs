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
            <a-option value="pending">卸载中</a-option>
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

    <!-- 卸载记录列表 -->
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

        <template #uninstalled_at="{ record }">
          {{ formatDateTime(record.uninstalled_at) }}
        </template>

        <template #actions="{ record }">
          <a-space>
            <a-button type="text" size="small" @click="handleViewDetail(record)">
              <template #icon>
                <IconEye />
              </template>
              查看详情
            </a-button>
          </a-space>
        </template>
      </a-table>
    </div>

    <!-- 详情对话框 -->
    <a-modal
      v-model:visible="detailVisible"
      title="卸载记录详情"
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
        <a-descriptions-item v-if="currentRecord.agent_id" label="Agent ID">
          {{ currentRecord.agent_id }}
        </a-descriptions-item>
        <a-descriptions-item label="Agent类型">
          <a-tag :color="currentRecord.agent_type === 'agent-server' ? 'purple' : 'blue'">
            {{ currentRecord.agent_type_display }}
          </a-tag>
        </a-descriptions-item>
        <a-descriptions-item label="卸载状态">
          <a-space>
            <a-tag :color="getStatusColor(currentRecord.status)">
              {{ currentRecord.status_display }}
            </a-tag>
          </a-space>
        </a-descriptions-item>
        <a-descriptions-item label="卸载时间">
          {{ formatDateTime(currentRecord.uninstalled_at) }}
        </a-descriptions-item>
        <a-descriptions-item label="操作者">
          {{ currentRecord.uninstalled_by_name }}
        </a-descriptions-item>
        <a-descriptions-item v-if="currentRecord.message" label="消息">
          <div style="word-break: break-all; white-space: pre-wrap">{{ currentRecord.message }}</div>
        </a-descriptions-item>
        <a-descriptions-item v-if="currentRecord.error_message" label="错误信息">
          <div style="word-break: break-all; white-space: pre-wrap; color: #ff4d4f">{{ currentRecord.error_message }}</div>
        </a-descriptions-item>
        <a-descriptions-item v-if="currentRecord.error_detail" label="错误详情">
          <div style="word-break: break-all; white-space: pre-wrap; color: #ff4d4f">{{ currentRecord.error_detail }}</div>
        </a-descriptions-item>
      </a-descriptions>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { IconRefresh, IconSearch, IconEye } from '@/components/icons'
import { agentsApi } from '@/api/agents'
import { formatDateTime } from '@/utils/date'

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
  message?: string
  error_message?: string
  error_detail?: string
  uninstalled_at: string
  uninstalled_by: number
  uninstalled_by_name: string
  uninstall_task_id: string
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

// 表格列配置
const columns = [
  {
    title: '主机',
    key: 'host',
    slot: 'host',
    width: 200
  },
  {
    title: 'Agent ID',
    key: 'agent_id',
    dataIndex: 'agent_id',
    width: 100
  },
  {
    title: 'Agent类型',
    key: 'agent_type_display',
    dataIndex: 'agent_type_display',
    width: 120
  },
  {
    title: '状态',
    key: 'status',
    slot: 'status',
    width: 100
  },
  {
    title: '卸载时间',
    key: 'uninstalled_at',
    slot: 'uninstalled_at',
    width: 180
  },
  {
    title: '操作者',
    key: 'uninstalled_by_name',
    dataIndex: 'uninstalled_by_name',
    width: 120
    ellipsis: true
  },
  {
    title: '操作',
    key: 'actions',
    slot: 'actions',
    width: 120,
    fixed: 'right'
  }
]

// 获取状态颜色
const getStatusColor = (status: string) => {
  switch (status) {
    case 'success':
      return 'green'
    case 'failed':
      return 'red'
    case 'pending':
      return 'orange'
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

// 搜索
const handleSearch = () => {
  pagination.current = 1
  loadData()
}

// 重置搜索
const handleReset = () => {
  Object.assign(searchForm, {
    search: '',
    status: undefined
  })
  handleSearch()
}

// 刷新
const handleRefresh = () => {
  loadData()
}

// 分页变化
const handlePageChange = (page: number) => {
  pagination.current = page
  loadData()
}

const handlePageSizeChange = (pageSize: number) => {
  pagination.pageSize = pageSize
  pagination.current = 1
  loadData()
}

// 查看详情
const handleViewDetail = (record: UninstallRecord) => {
  currentRecord.value = record
  detailVisible.value = true
}

// 组件挂载时加载数据
onMounted(() => {
  loadData()
})
</script>

<style scoped>
.uninstall-records-page {
  padding: 24px;
}

.page-header {
  margin-bottom: 24px;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left h2 {
  margin: 0 0 8px 0;
  font-size: 20px;
  font-weight: 600;
  color: #1d2129;
}

.header-desc {
  margin: 0;
  color: #86909c;
  font-size: 14px;
}

.table-container {
  background: #ffffff;
  border-radius: 8px;
  overflow: hidden;
}

.mb-4 {
  margin-bottom: 16px;
}
</style>
