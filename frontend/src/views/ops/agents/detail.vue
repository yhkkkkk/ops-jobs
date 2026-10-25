<template>
  <div class="agent-detail">
    <div class="page-header">
      <div class="header-actions">
        <n-space>
          <n-button @click="goBack">
            <template #icon>
              <ChevronLeft />
            </template>
            返回
          </n-button>
          <n-button v-if="agentDetail" @click="handleEditAgentServer">
            <template #icon>
              <Pencil  />
            </template>
            编辑
          </n-button>
          <n-button
            type="primary"
            @click="handleIssueToken"
          >
            <template #icon>
              <Key />
            </template>
            签发 Token
          </n-button>
          <n-button
            v-if="agentDetail && (agentDetail.computed_status || agentDetail.status) !== 'disabled'"
           type="warning"
            @click="handleDisable"
          >
            <template #icon>
              <CircleX  />
            </template>
            禁用
          </n-button>
          <n-button
            v-else-if="agentDetail"
           type="success"
            @click="handleEnable"
          >
            <template #icon>
              <CircleCheck  />
            </template>
            启用
          </n-button>
        </n-space>
      </div>
    </div>

    <div v-if="agentDetail" class="agent-detail-content">
      <!-- Agent 基本信息 -->
      <n-card class="mb-4">
        <template #header>Agent 基本信息</template>
        <div class="info-grid">
          <div class="info-item">
            <span class="label">状态：</span>
            <span class="value"><n-tag :type="getStatusColor(agentDetail.computed_status || agentDetail.status) as any">
                {{ agentDetail.computed_status_display || agentDetail.status_display }}
              </n-tag>
            </span>
          </div>
          <div class="info-item">
            <span class="label">版本：</span>
            <span class="value">
              <n-space>
                <span>{{ agentDetail.version || '-' }}</span>
                <n-tooltip
                  v-if="agentDetail.is_version_outdated && agentDetail.version"
                  :content="getVersionTooltip(agentDetail)"
                >
                  <n-tag type="error" size="small">
                    版本落后
                  </n-tag>
                </n-tooltip>
              </n-space>
            </span>
          </div>
          <div class="info-item">
            <span class="label">类型：</span>
            <span class="value">
              <n-tag type="info">{{ agentDetail.agent_type_display || agentDetail.agent_type || '-' }}</n-tag>
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
              <n-tag v-if="agentDetail.last_error_code" type="error" size="small">
                {{ agentDetail.last_error_code }}
              </n-tag>
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
      </n-card>

      <!-- 关联主机信息 -->
      <n-card class="mb-4">
        <template #header>关联主机信息</template>
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
              <n-tag type="info">{{ agentDetail.host.os_type_display }}</n-tag>
            </span>
          </div>
          <div class="info-item" v-if="agentDetail.host.tags && agentDetail.host.tags.length">
            <span class="label">标签：</span>
            <span class="value">
              <n-space wrap>
                <n-tag
                  v-for="tag in agentDetail.host.tags"
                  :key="typeof tag === 'object' ? `${tag.key || ''}-${tag.value || ''}` : String(tag)"
                >
                  {{ tag.key ? (tag.value ? `${tag.key}=${tag.value}` : tag.key) : tag }}
                </n-tag>
              </n-space>
            </span>
          </div>
          <div class="info-item" v-if="agentDetail.host.service_role">
            <span class="label">服务角色：</span>
            <span class="value">{{ agentDetail.host.service_role }}</span>
          </div>
        </div>
      </n-card>

      <!-- Token 历史 -->
      <n-card class="mb-4">
        <template #header>Token 历史</template>
        <n-data-table
          :columns="tokenColumns"
          :data="agentDetail.tokens || []"
          :pagination="false"
        />
      </n-card>

      <!-- 任务执行统计 -->
      <n-card v-if="agentDetail.task_stats" class="mb-4">
        <AgentTaskStatsCard :stats="agentDetail.task_stats" />
      </n-card>
      <n-card v-else class="mb-4">
        <n-empty description="暂无任务统计">
          <template #icon>
            <PieChart  />
          </template>
        </n-empty>
      </n-card>
    </div>

    <!-- 发 Token 弹窗 -->
    <n-modal
      preset="card"
      v-model:show="tokenModalVisible"
      title="签发 Agent Token"
      style="width: 480px"
    >
      <n-form :model="tokenForm" ref="tokenFormRef">
        <n-form-item
          label="过期时间"
          path="expired_at"
        >
          <n-date-picker
            v-model:value="tokenForm.expired_at"
            type="datetime"
            clearable
            style="width: 100%"
          />
        </n-form-item>
        <n-form-item
          label="备注"
          path="note"
        >
          <n-input type="textarea"
            v-model:value="tokenForm.note"
            placeholder="请输入备注"
            :max-length="255"
            :autosize="{ minRows: 2, maxRows: 4 }"
          />
        </n-form-item>
        <n-form-item
          label="二次确认"
          path="confirmed"
        >
          <n-checkbox v-model:checked="tokenForm.confirmed">
            我已确认此操作（高危操作）
          </n-checkbox>
        </n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button @click="handleTokenModalCancel">取消</n-button>
          <n-button type="primary" @click="handleIssueTokenConfirm" :disabled="!tokenForm.confirmed">
            确认签发
          </n-button>
        </n-space>
      </template>
    </n-modal>

    <!-- 编辑 Agent 关联的 Agent-Server -->
    <n-modal preset="card"
      v-model:show="agentServerEditVisible"
      title="编辑 Agent"
      @ok="handleAgentServerEditConfirm"
      @cancel="handleAgentServerEditCancel"
    >
      <n-alert type="info" show-icon style="margin-bottom: 12px;">
        仅更新控制面记录，不会自动下发/重装
      </n-alert>
      <n-form :model="agentServerEditForm" layout="vertical">
        <n-form-item label="关联 Agent-Server">
          <n-select
            v-model:value="agentServerEditForm.agent_server_id"
            placeholder="请选择 Agent-Server"
            clearable
            filterable
            :filter-option="filterAgentServerOption" :options="(agentServers || []).map((server: any) => ({ label: formatAgentServerLabel(server), value: String(server.id) }))" />
          <div class="form-help">留空表示解除绑定（仅控制面记录）</div>
        </n-form-item>
      </n-form>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { agentsApi, agentServerApi, type AgentDetail, type AgentToken, type AgentServer } from '@/api/agents'
import AgentTaskStatsCard from './components/AgentTaskStatsCard.vue'
import dayjs from 'dayjs'
import { NAlert, NButton, NCard, NCheckbox, NDataTable, NDatePicker, NEmpty, NForm, NFormItem, NInput, NModal, NSelect, NSpace, NTag, NTooltip, type DataTableColumns, useDialog, useMessage } from 'naive-ui'
import { ChevronLeft, CircleCheck, CircleX, Copy, Key, Pencil, PieChart, X } from 'lucide-vue-next'

const message = useMessage()
const dialog = useDialog()
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
const tokenColumns: DataTableColumns<any> = [
  {
    title: 'Token 标识',
    key: 'token_last4',
    width: 120,
    render: (row) => (row.token_last4 ? `****${row.token_last4}` : '-'),
  },
  { title: '签发人', key: 'issued_by_name', width: 120, render: (row) => row.issued_by_name },
  { title: '签发时间', key: 'created_at', width: 180, render: (row) => formatTime(row.created_at) },
  {
    title: '状态',
    key: 'status',
    width: 100,
    render: (row) => {
      const expired = row.expired_at && new Date(row.expired_at) < new Date()
      const type = row.revoked_at ? 'error' : expired ? 'warning' : 'success'
      const text = row.revoked_at ? '已吊销' : expired ? '已过期' : '有效'
      return h(NTag, { type, size: 'small' }, { default: () => text })
    },
  },
  {
    title: '操作',
    key: 'actions',
    width: 100,
    render: (row) => {
      const active = !row.revoked_at && (!row.expired_at || new Date(row.expired_at) > new Date())
      return active
        ? h(NButton, { text: true, type: 'error', size: 'small', onClick: () => handleRevokeToken(row) }, {
            icon: () => h(X, { size: 14 }),
            default: () => '吊销',
          })
        : h('span', '-')
    },
  },
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
    message.error(error?.message || '获取 Agent-Server 列表失败')
    agentServers.value = []
  }
}

// 获取 Agent 详情
const fetchAgentDetail = async () => {
  const id = Number(route.params.id)
  if (!id) {
    message.error('无效的 Agent ID')
    router.back()
    return
  }

  loading.value = true
  try {
    const result = await agentsApi.getAgent(id)
    agentDetail.value = result
  } catch (error: any) {
    console.error('获取 Agent 详情失败:', error)
    message.error(error.message || '获取 Agent 详情失败')
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
    message.warning('请先确认此操作')
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
    message.success('Token 签发成功')
    tokenModalVisible.value = false
    showIssuedTokenDialog(result?.token || '')
    fetchAgentDetail()
  } catch (error: any) {
    console.error('Token 签发失败:', error)
    message.error(error.message || 'Token 签发失败')
  }
}

const copyText = (text: string) => {
  navigator.clipboard.writeText(text).then(() => {
    message.success('已复制到剪贴板')
  }).catch(() => {
    message.error('复制失败')
  })
}

/** One-time token dialog with copy */
const showIssuedTokenDialog = (token: string) => {
  const tokenText = token || ''
  if (!tokenText) {
    message.warning('未返回 Token，请检查接口响应')
    return
  }
  dialog.create({
    title: 'Token 签发成功',
    content: () =>
      h('div', { style: 'display:flex;flex-direction:column;gap:12px;' }, [
        h(NAlert, { type: 'warning', bordered: false }, {
          default: () => '此 Token 仅显示一次，请立即复制并妥善保管。',
        }),
        h('div', { style: 'display:flex;gap:8px;align-items:flex-start;' }, [
          h(NInput, {
            value: tokenText,
            readonly: true,
            type: 'textarea',
            autosize: { minRows: 2, maxRows: 4 },
            style: 'flex:1;',
          }),
          h(
            NButton,
            {
              type: 'primary',
              onClick: () => copyText(tokenText),
            },
            {
              icon: () => h(Copy, { size: 14 }),
              default: () => '复制',
            },
          ),
        ]),
      ]),
    positiveText: '我已保存',
  })
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
    message.success('更新 Agent 成功')
    agentServerEditVisible.value = false
    fetchAgentDetail()
  } catch (error: any) {
    console.error('更新 Agent 失败:', error)
    const errorMsg = error?.response?.data?.message || error?.message || '更新 Agent 失败'
    message.error(errorMsg)
  }
}

// 禁用 Agent
const handleDisable = () => {
  if (!agentDetail.value) return
  dialog.warning({
    title: '确认禁用',
    content: `确定要禁用 Agent (${agentDetail.value.host.name}) 吗？`,
    positiveText: '确认禁用',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await agentsApi.disableAgent(agentDetail.value!.id, { confirmed: true })
        message.success('禁用成功')
        fetchAgentDetail()
      } catch (error: any) {
        console.error('禁用失败:', error)
        const errorMsg = error?.response?.data?.message || error?.message || '禁用失败'
        message.error(errorMsg)
      }
    }
  })
}

// 启用 Agent
const handleEnable = async () => {
  if (!agentDetail.value) return
  try {
    await agentsApi.enableAgent(agentDetail.value.id)
    message.success('启用成功')
    fetchAgentDetail()
  } catch (error: any) {
    console.error('启用失败:', error)
    const errorMsg = error?.response?.data?.message || error?.message || '启用失败'
    message.error(errorMsg)
  }
}

// 吊销 Token
const handleRevokeToken = (token: AgentToken) => {
  if (!agentDetail.value) return
  dialog.warning({
    title: '确认吊销',
    content: '确定要吊销此 Token 吗？',
    positiveText: '确认吊销',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await agentsApi.revokeToken(agentDetail.value!.id, { confirmed: true })
        message.success('吊销成功')
        fetchAgentDetail()
      } catch (error: any) {
        console.error('吊销失败:', error)
        const errorMsg = error?.response?.data?.message || error?.message || '吊销失败'
        message.error(errorMsg)
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
  justify-content: flex-end;
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

