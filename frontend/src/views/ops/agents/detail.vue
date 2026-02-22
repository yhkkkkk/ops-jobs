<template>
  <div class="agent-detail">
    <div class="page-header">
      <a-breadcrumb>
        <a-breadcrumb-item @click="goBack">Agent 管理</a-breadcrumb-item>
        <a-breadcrumb-item>Agent 详情</a-breadcrumb-item>
      </a-breadcrumb>

      <div class="header-actions">
        <a-space>
          <a-button @click="goBack">
            <template #icon>
              <icon-arrow-left />
            </template>
            返回
          </a-button>
          <a-button v-if="agentDetail" @click="handleEditAgentServer">
            <template #icon>
              <icon-edit />
            </template>
            编辑
          </a-button>
          <a-button
            type="primary"
            @click="handleIssueToken"
          >
            <template #icon>
              <icon-key />
            </template>
            签发 Token
          </a-button>
          <a-button
            v-if="agentDetail && (agentDetail.computed_status || agentDetail.status) !== 'disabled'"
            status="warning"
            @click="handleDisable"
          >
            <template #icon>
              <icon-close-circle />
            </template>
            禁用
          </a-button>
          <a-button
            v-else-if="agentDetail"
            status="success"
            @click="handleEnable"
          >
            <template #icon>
              <icon-check-circle />
            </template>
            启用
          </a-button>
        </a-space>
      </div>
    </div>

    <div v-if="agentDetail" class="agent-detail-content">
      <!-- Agent 基本信息 -->
      <a-card class="mb-4">
        <template #title>Agent 基本信息</template>
        <div class="info-grid">
          <div class="info-item">
            <span class="label">状态：</span>
            <span class="value">
            <a-tag :color="getStatusColor(agentDetail.computed_status || agentDetail.status)">
                {{ agentDetail.computed_status_display || agentDetail.status_display }}
              </a-tag>
            </span>
          </div>
          <div class="info-item">
            <span class="label">版本：</span>
            <span class="value">
              <a-space>
                <span>{{ agentDetail.version || '-' }}</span>
                <a-tooltip
                  v-if="agentDetail.is_version_outdated && agentDetail.version"
                  :content="getVersionTooltip(agentDetail)"
                >
                  <a-tag color="red" size="small">
                    版本落后
                  </a-tag>
                </a-tooltip>
              </a-space>
            </span>
          </div>
          <div class="info-item">
            <span class="label">类型：</span>
            <span class="value">
              <a-tag color="purple">{{ agentDetail.agent_type_display || agentDetail.agent_type || '-' }}</a-tag>
            </span>
          </div>
          <div class="info-item">
            <span class="label">接入点：</span>
            <span class="value">{{ agentDetail.endpoint || '-' }}</span>
          </div>
          <div class="info-item">
            <span class="label">Agent-Server：</span>
            <span class="value">{{ agentServerLabel }}</span>
          </div>
          <div class="info-item">
            <span class="label">最后心跳：</span>
            <span class="value">
              {{ agentDetail.last_heartbeat_at ? formatTime(agentDetail.last_heartbeat_at) : '-' }}
            </span>
          </div>
          <div class="info-item">
            <span class="label">最近错误码：</span>
            <span class="value">
              <a-tag v-if="agentDetail.last_error_code" color="red" size="small">
                {{ agentDetail.last_error_code }}
              </a-tag>
              <span v-else>-</span>
            </span>
          </div>
          <div class="info-item">
            <span class="label">创建时间：</span>
            <span class="value">{{ formatTime(agentDetail.created_at) }}</span>
          </div>
          <div class="info-item">
            <span class="label">更新时间：</span>
            <span class="value">{{ formatTime(agentDetail.updated_at) }}</span>
          </div>
        </div>
      </a-card>

      <!-- 关联主机信息 -->
      <a-card class="mb-4">
        <template #title>关联主机信息</template>
        <div class="info-grid">
          <div class="info-item">
            <span class="label">主机名称：</span>
            <span class="value">{{ agentDetail.host.name }}</span>
          </div>
          <div class="info-item">
            <span class="label">IP地址：</span>
            <span class="value">{{ agentDetail.host.ip_address }}</span>
          </div>
          <div class="info-item">
            <span class="label">端口：</span>
            <span class="value">{{ agentDetail.host.port }}</span>
          </div>
          <div class="info-item">
            <span class="label">操作系统：</span>
            <span class="value">
              <a-tag color="blue">{{ agentDetail.host.os_type_display }}</a-tag>
            </span>
          </div>
          <div class="info-item" v-if="agentDetail.host.tags && agentDetail.host.tags.length">
            <span class="label">标签：</span>
            <span class="value">
              <a-space wrap>
                <a-tag
                  v-for="tag in agentDetail.host.tags"
                  :key="typeof tag === 'object' ? `${tag.key || ''}-${tag.value || ''}` : String(tag)"
                >
                  {{ tag.key ? (tag.value ? `${tag.key}=${tag.value}` : tag.key) : tag }}
                </a-tag>
              </a-space>
            </span>
          </div>
          <div class="info-item" v-if="agentDetail.host.service_role">
            <span class="label">服务角色：</span>
            <span class="value">{{ agentDetail.host.service_role }}</span>
          </div>
        </div>
      </a-card>

      <!-- Token 历史 -->
      <a-card class="mb-4">
        <template #title>Token 历史</template>
        <a-table
          :columns="tokenColumns"
          :data="agentDetail.tokens || []"
          :pagination="false"
        >
          <template #token_last4="{ record }">
            <span v-if="record.token_last4">****{{ record.token_last4 }}</span>
            <span v-else>-</span>
          </template>
          <template #status="{ record }">
            <a-tag
              :color="record.revoked_at ? 'red' : (record.expired_at && new Date(record.expired_at) < new Date() ? 'orange' : 'green')"
              size="small"
            >
              {{ record.revoked_at ? '已吊销' : (record.expired_at && new Date(record.expired_at) < new Date() ? '已过期' : '有效') }}
            </a-tag>
          </template>
          <template #actions="{ record }">
            <a-button
              v-if="!record.revoked_at && (!record.expired_at || new Date(record.expired_at) > new Date())"
              type="text"
              status="danger"
              size="small"
              @click="handleRevokeToken(record)"
            >
              <template #icon>
                <icon-close />
              </template>
              吊销
            </a-button>
          </template>
        </a-table>
      </a-card>

      <!-- 任务执行统计 -->
      <a-card v-if="agentDetail.task_stats" class="mb-4">
        <AgentTaskStatsCard :stats="agentDetail.task_stats" />
      </a-card>
      <a-card v-else class="mb-4">
        <a-empty description="暂无任务统计">
          <template #image>
            <icon-chart-pie />
          </template>
        </a-empty>
      </a-card>
    </div>

    <!-- 发 Token 弹窗 -->
    <a-modal
      v-model:visible="tokenModalVisible"
      title="签发 Agent Token"
      @ok="handleIssueTokenConfirm"
      @cancel="handleTokenModalCancel"
    >
      <a-form :model="tokenForm" ref="tokenFormRef">
        <a-form-item
          label="过期时间"
          field="expired_at"
        >
          <a-date-picker
            v-model="tokenForm.expired_at"
            show-time
            format="YYYY-MM-DD HH:mm:ss"
            style="width: 100%"
          />
        </a-form-item>
        <a-form-item
          label="备注"
          field="note"
        >
          <a-textarea
            v-model="tokenForm.note"
            placeholder="请输入备注"
            :max-length="255"
            :auto-size="{ minRows: 2, maxRows: 4 }"
          />
        </a-form-item>
        <a-form-item
          label="二次确认"
          field="confirmed"
        >
          <a-checkbox v-model="tokenForm.confirmed">
            我已确认此操作（高危操作）
          </a-checkbox>
        </a-form-item>
      </a-form>
      <template #footer>
        <a-space>
          <a-button @click="handleTokenModalCancel">取消</a-button>
          <a-button type="primary" @click="handleIssueTokenConfirm" :disabled="!tokenForm.confirmed">
            确认签发
          </a-button>
        </a-space>
      </template>
    </a-modal>

    <!-- 编辑 Agent 关联的 Agent-Server -->
    <a-modal
      v-model:visible="agentServerEditVisible"
      title="编辑 Agent"
      @ok="handleAgentServerEditConfirm"
      @cancel="handleAgentServerEditCancel"
    >
      <a-alert type="info" show-icon style="margin-bottom: 12px;">
        仅更新控制面记录，不会自动下发/重装
      </a-alert>
      <a-form :model="agentServerEditForm" layout="vertical">
        <a-form-item label="关联 Agent-Server">
          <a-select
            v-model="agentServerEditForm.agent_server_id"
            placeholder="请选择 Agent-Server"
            allow-clear
            allow-search
            :filter-option="filterAgentServerOption"
          >
            <a-option
              v-for="server in agentServers"
              :key="server.id"
              :value="server.id"
              :label="formatAgentServerLabel(server)"
            >
              {{ formatAgentServerLabel(server) }}
            </a-option>
          </a-select>
          <div class="form-help">留空表示解除绑定（仅控制面记录）</div>
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Message, Modal } from '@arco-design/web-vue'
import { agentsApi, agentServerApi, type AgentDetail, type AgentToken, type AgentServer } from '@/api/agents'
import AgentTaskStatsCard from './components/AgentTaskStatsCard.vue'
import dayjs from 'dayjs'

const router = useRouter()
const route = useRoute()

// 响应式数据
const loading = ref(false)
const agentDetail = ref<AgentDetail | null>(null)
const tokenModalVisible = ref(false)
const tokenFormRef = ref()

const agentServers = ref<AgentServer[]>([])
const agentServerEditVisible = ref(false)
const agentServerEditForm = reactive({
  agent_server_id: null as number | null
})

// Token 表单
const tokenForm = reactive({
  expired_at: null as string | null,
  note: '',
  confirmed: false
})

// Token 表格列
const tokenColumns = [
  {
    title: 'Token 标识',
    dataIndex: 'token_last4',
    slotName: 'token_last4',
    width: 120
  },
  {
    title: '签发人',
    dataIndex: 'issued_by_name',
    width: 120
  },
  {
    title: '签发时间',
    dataIndex: 'created_at',
    width: 180,
    render: ({ record }: any) => {
      return dayjs(record.created_at).format('YYYY-MM-DD HH:mm:ss')
    }
  },
  {
    title: '过期时间',
    dataIndex: 'expired_at',
    width: 180,
    render: ({ record }: any) => {
      return record.expired_at ? dayjs(record.expired_at).format('YYYY-MM-DD HH:mm:ss') : '-'
    }
  },
  {
    title: '状态',
    dataIndex: 'status',
    slotName: 'status',
    width: 100
  },
  {
    title: '备注',
    dataIndex: 'note',
    width: 150
  },
  {
    title: '操作',
    slotName: 'actions',
    width: 100,
    fixed: 'right'
  }
]

// 获取状态颜色
const getStatusColor = (status: string) => {
  const colorMap: Record<string, string> = {
    pending: 'orange',
    online: 'green',
    offline: 'red',
    disabled: 'gray'
  }
  return colorMap[status] || 'blue'
}

// 版本落后提示文案
const getVersionTooltip = (agent: AgentDetail & { expected_min_version?: string }) => {
  if (agent.expected_min_version) {
    return `当前版本 ${agent.version} 落后于期望版本 ${agent.expected_min_version}`
  }
  return `当前版本 ${agent.version} 落后于平台期望版本`
}

// 格式化时间
const formatTime = (time: string) => {
  return dayjs(time).format('YYYY-MM-DD HH:mm:ss')
}

const formatAgentServerLabel = (server: AgentServer) => {
  const suffix = server.shared_secret_last4 ? ` - 密钥尾号 ${server.shared_secret_last4}` : ''
  return `${server.name} (${server.base_url})${suffix}`
}

const filterAgentServerOption = (inputValue: string, option: any) => {
  const label = (option?.label || '').toString().toLowerCase()
  return label.includes(inputValue.toLowerCase())
}

const agentServerLabel = computed(() => {
  if (!agentDetail.value?.agent_server_id) return '-'
  const server = agentServers.value.find(s => s.id === agentDetail.value?.agent_server_id)
  return server ? formatAgentServerLabel(server) : `ID: ${agentDetail.value.agent_server_id}`
})

const fetchAgentServers = async () => {
  try {
    const response = await agentServerApi.getAgentServers({ page_size: 200 })
    agentServers.value = response.results || []
  } catch (error: any) {
    console.error('获取 Agent-Server 列表失败:', error)
    Message.error(error?.message || '获取 Agent-Server 列表失败')
    agentServers.value = []
  }
}

// 获取 Agent 详情
const fetchAgentDetail = async () => {
  const id = Number(route.params.id)
  if (!id) {
    Message.error('无效的 Agent ID')
    router.back()
    return
  }

  loading.value = true
  try {
    const result = await agentsApi.getAgent(id)
    agentDetail.value = result
  } catch (error: any) {
    console.error('获取 Agent 详情失败:', error)
    Message.error(error.message || '获取 Agent 详情失败')
    router.back()
  } finally {
    loading.value = false
  }
}

// 返回
const goBack = () => {
  router.push('/ops/agents')
}

// 发 Token
const handleIssueToken = () => {
  tokenForm.expired_at = null
  tokenForm.note = ''
  tokenForm.confirmed = false
  tokenModalVisible.value = true
}

// 确认发 Token
const handleIssueTokenConfirm = async () => {
  if (!tokenForm.confirmed) {
    Message.warning('请先确认此操作')
    return
  }
  if (!agentDetail.value) return

  try {
    const params: any = {
      confirmed: true
    }
    if (tokenForm.expired_at) {
      params.expired_at = dayjs(tokenForm.expired_at).format('YYYY-MM-DD HH:mm:ss')
    }
    if (tokenForm.note) {
      params.note = tokenForm.note
    }

    const result = await agentsApi.issueToken(agentDetail.value.id, params)
    Message.success('Token 签发成功')
    // 显示 Token（仅此一次）
    Modal.info({
      title: 'Token 签发成功',
      content: `Token: ${result.token}\n\n请妥善保管，此 Token 仅显示一次！`,
      okText: '我已保存'
    })
    tokenModalVisible.value = false
    fetchAgentDetail()
  } catch (error: any) {
    console.error('Token 签发失败:', error)
    Message.error(error.message || 'Token 签发失败')
  }
}

// 取消发 Token
const handleTokenModalCancel = () => {
  tokenModalVisible.value = false
  tokenForm.expired_at = null
  tokenForm.note = ''
  tokenForm.confirmed = false
}

const handleEditAgentServer = () => {
  if (!agentDetail.value) return
  agentServerEditForm.agent_server_id = agentDetail.value.agent_server_id ?? null
  agentServerEditVisible.value = true
}

const handleAgentServerEditCancel = () => {
  agentServerEditVisible.value = false
  agentServerEditForm.agent_server_id = null
}

const handleAgentServerEditConfirm = async () => {
  if (!agentDetail.value) return
  try {
    await agentsApi.updateAgentServer(agentDetail.value.id, {
      agent_server_id: agentServerEditForm.agent_server_id
    })
    Message.success('更新 Agent 成功')
    agentServerEditVisible.value = false
    fetchAgentDetail()
  } catch (error: any) {
    console.error('更新 Agent 失败:', error)
    const errorMsg = error?.response?.data?.message || error?.message || '更新 Agent 失败'
    Message.error(errorMsg)
  }
}

// 禁用 Agent
const handleDisable = () => {
  if (!agentDetail.value) return
  Modal.confirm({
    title: '确认禁用',
    content: `确定要禁用 Agent (${agentDetail.value.host.name}) 吗？`,
    okText: '确认禁用',
    cancelText: '取消',
    onOk: async () => {
      try {
        await agentsApi.disableAgent(agentDetail.value!.id, { confirmed: true })
        Message.success('禁用成功')
        fetchAgentDetail()
      } catch (error: any) {
        console.error('禁用失败:', error)
        const errorMsg = error?.response?.data?.message || error?.message || '禁用失败'
        Message.error(errorMsg)
      }
    }
  })
}

// 启用 Agent
const handleEnable = async () => {
  if (!agentDetail.value) return
  try {
    await agentsApi.enableAgent(agentDetail.value.id)
    Message.success('启用成功')
    fetchAgentDetail()
  } catch (error: any) {
    console.error('启用失败:', error)
    const errorMsg = error?.response?.data?.message || error?.message || '启用失败'
    Message.error(errorMsg)
  }
}

// 吊销 Token
const handleRevokeToken = (token: AgentToken) => {
  if (!agentDetail.value) return
  Modal.confirm({
    title: '确认吊销',
    content: '确定要吊销此 Token 吗？',
    okText: '确认吊销',
    cancelText: '取消',
    onOk: async () => {
      try {
        await agentsApi.revokeToken(agentDetail.value!.id, { confirmed: true })
        Message.success('吊销成功')
        fetchAgentDetail()
      } catch (error: any) {
        console.error('吊销失败:', error)
        const errorMsg = error?.response?.data?.message || error?.message || '吊销失败'
        Message.error(errorMsg)
      }
    }
  })
}

// 初始化
onMounted(() => {
  fetchAgentServers()
  fetchAgentDetail()
})
</script>

<style scoped>
.agent-detail .page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.mb-4 {
  margin-bottom: 16px;
}

.agent-detail .agent-detail-content .info-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.agent-detail .agent-detail-content .info-grid .info-item {
  display: flex;
}

.agent-detail .agent-detail-content .info-grid .info-item .label {
  font-weight: 500;
  color: #4e5969;
  margin-right: 8px;
  min-width: 100px;
}

.agent-detail .agent-detail-content .info-grid .info-item .value {
  color: #1d2129;
}

:deep(.arco-breadcrumb-item) {
  cursor: pointer;
}
</style>

