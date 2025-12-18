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
        <a-form-item label="安装模式">
          <a-select
            v-model="searchForm.install_mode"
            placeholder="请选择安装模式"
            allow-clear
            @change="handleSearch"
            @clear="handleSearch"
            style="width: 150px"
          >
            <a-option value="direct">直连模式</a-option>
            <a-option value="agent-server">Agent-Server 模式</a-option>
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
          <a-tag :color="record.install_mode === 'agent-server' ? 'blue' : 'green'">
            {{ record.install_mode === 'agent-server' ? 'Agent-Server' : '直连' }}
          </a-tag>
        </template>

        <template #error_message="{ record }">
          <div v-if="record.error_message" style="max-width: 300px">
            <a-tooltip :content="record.error_message">
              <span style="color: #f53f3f; cursor: pointer">
                {{ record.error_message.length > 50 ? record.error_message.substring(0, 50) + '...' : record.error_message }}
              </span>
            </a-tooltip>
          </div>
          <span v-else style="color: #86909c">-</span>
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
              v-if="record.status === 'pending'"
              type="text"
              status="warning"
              size="small"
              @click="handleRegenerateScript(record)"
            >
              <template #icon>
                <IconRefresh />
              </template>
              重新生成脚本
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
          <a-tag :color="currentRecord.install_mode === 'agent-server' ? 'blue' : 'green'">
            {{ currentRecord.install_mode === 'agent-server' ? 'Agent-Server 模式' : '直连模式' }}
          </a-tag>
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
        <a-descriptions-item v-if="currentRecord.agent_id" label="关联 Agent">
          <a-button type="text" size="small" @click="handleViewAgent(currentRecord)">
            查看 Agent #{{ currentRecord.agent_id }}
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

    <!-- 安装脚本抽屉 -->
    <a-drawer
      v-model:visible="scriptDrawerVisible"
      title="安装脚本"
      width="900px"
      :footer="false"
      placement="right"
    >
      <div class="install-step-scripts">
        <div class="install-script-tip">
          <p class="install-script-tip-title">
            <strong>重要提示：</strong>这只是生成安装脚本，Agent 尚未实际安装！
          </p>
          <p class="install-script-tip-text">
            您需要：
          </p>
          <ul class="install-script-tip-list">
            <li>将以下脚本复制到对应主机上手动执行，或</li>
            <li>使用「批量安装（SSH）」功能自动安装</li>
          </ul>
          <p class="install-script-tip-warning">
            <strong>注意：Token 仅显示一次，请妥善保存！</strong>
          </p>
        </div>
        <div v-if="installScripts">
          <div v-for="(scriptGroup, osType) in installScripts" :key="String(osType)">
            <h3 style="margin: 16px 0 8px 0;">{{ String(osType) === 'linux' ? 'Linux' : 'Windows' }} 安装脚本</h3>
            <div v-for="item in scriptGroup" :key="item.host_id" style="margin-bottom: 24px">
              <a-card :title="`${item.host_name} (${item.host_ip})`" size="small">
                <template #extra>
                  <a-button type="text" size="small" @click="copyScript(item.script)">
                    <template #icon>
                      <IconCopy />
                    </template>
                    复制脚本
                  </a-button>
                </template>
                <div class="install-script-token-row">
                  <span class="install-script-token-label"><strong>注册 Token:</strong></span>
                  <code class="install-script-token-value">{{ item.register_token }}</code>
                  <a-button type="text" size="mini" @click="copyText(item.register_token)" style="margin-left: 8px">
                    <template #icon>
                      <IconCopy />
                    </template>
                  </a-button>
                </div>
                <a-textarea
                  :model-value="item.script"
                  auto-size
                  readonly
                  :rows="24"
                  style="font-family: 'Courier New', monospace; font-size: 12px; margin-top: 8px;"
                />
              </a-card>
            </div>
          </div>
        </div>
        <div v-else style="text-align: center; padding: 40px; color: #86909c">
          正在生成脚本...
        </div>
      </div>
    </a-drawer>
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
  IconCopy,
} from '@arco-design/web-vue/es/icon'
import { agentsApi } from '@/api/agents'
import dayjs from 'dayjs'

const router = useRouter()

// 响应式数据
const loading = ref(false)
const records = ref<any[]>([])
const detailVisible = ref(false)
const currentRecord = ref<any>(null)
const scriptDrawerVisible = ref(false)
const installScripts = ref<any>(null)
const regeneratingScript = ref(false)

// 搜索表单
const searchForm = reactive({
  search: '',
  status: '',
  install_mode: '',
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
    title: '安装模式',
    dataIndex: 'install_mode',
    slotName: 'install_mode',
    width: 140,
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
    title: '安装时间',
    dataIndex: 'installed_at',
    slotName: 'installed_at',
    width: 180,
  },
  {
    title: '错误信息',
    dataIndex: 'error_message',
    slotName: 'error_message',
    width: 300,
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
    if (searchForm.install_mode) {
      params.install_mode = searchForm.install_mode
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

// 搜索
const handleSearch = () => {
  pagination.current = 1
  fetchRecords()
}

// 重置
const handleReset = () => {
  searchForm.search = ''
  searchForm.status = ''
  searchForm.install_mode = ''
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

// 查看详情
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

// 重新生成脚本
const handleRegenerateScript = async (record: any) => {
  regeneratingScript.value = true
  scriptDrawerVisible.value = true
  installScripts.value = null
  
  try {
    const response = await agentsApi.regenerateScriptFromRecord({
      install_record_id: record.id
    })
    
    installScripts.value = response.scripts
    
    if (response.notice) {
      Message.warning(response.notice)
    }
    Message.success('安装脚本重新生成成功')
  } catch (error: any) {
    console.error('重新生成脚本失败:', error)
    const errorMsg = error?.response?.data?.message || error?.message || '重新生成脚本失败'
    Message.error(errorMsg)
    scriptDrawerVisible.value = false
  } finally {
    regeneratingScript.value = false
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
            install_mode: record.install_mode || 'agent-server',
            agent_server_url: record.agent_server_url || '',
            agent_server_backup_url: record.agent_server_backup_url || '',
            package_version: record.package_version || '',
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

// 复制脚本
const copyScript = (script: string) => {
  navigator.clipboard.writeText(script).then(() => {
    Message.success('脚本已复制到剪贴板')
  }).catch(() => {
    Message.error('复制失败，请手动复制')
  })
}

// 复制文本
const copyText = (text: string) => {
  navigator.clipboard.writeText(text).then(() => {
    Message.success('已复制到剪贴板')
  }).catch(() => {
    Message.error('复制失败')
  })
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

.install-step-scripts {
  padding-bottom: 16px;
}

.install-script-tip {
  margin-bottom: 16px;
  padding: 12px 16px;
  border-radius: 4px;
  background-color: #f7f8fa;
  border: 1px solid #e5e6eb;
  font-size: 13px;
  color: #1d2129;
}

.install-script-tip-title {
  margin: 0 0 8px 0;
}

.install-script-tip-text {
  margin: 0 0 4px 0;
}

.install-script-tip-list {
  margin: 0;
  padding-left: 20px;
}

.install-script-tip-warning {
  margin: 8px 0 0 0;
  color: #f53f3f;
}

.install-script-token-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  font-size: 13px;
}

.install-script-token-label {
  color: #1d2129;
}

.install-script-token-value {
  font-family: 'Courier New', monospace;
  padding: 2px 6px;
  border-radius: 3px;
  background-color: #f2f3f5;
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
}
</style>

