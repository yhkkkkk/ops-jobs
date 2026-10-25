<template>
  <div class="system-config-page">
    <n-card title="系统配置" :bordered="false">
      <n-tabs v-model:value="activeTab" type="line" animated>
        <n-tab-pane name="task" tab="任务执行配置">
          <div class="tab-content">
            <n-form
              ref="taskFormRef"
              :model="taskConfig"
              :rules="taskRules"
              label-placement="top"
              class="config-form"
            >
              <n-form-item label="单个任务最大并发主机数" path="fabric_max_concurrent_hosts">
                <n-input-number
                  v-model:value="taskConfig.fabric_max_concurrent_hosts"
                  :min="1"
                  :max="100"
                  placeholder="请输入并发主机数"
                  style="width: 100%"
                />
                <div class="form-help">单个任务执行时同时连接的最大主机数量（适用于并行执行模式）</div>
              </n-form-item>
              <n-form-item label="SSH连接超时时间（秒）" path="fabric_connection_timeout">
                <n-input-number
                  v-model:value="taskConfig.fabric_connection_timeout"
                  :min="5"
                  :max="300"
                  placeholder="请输入连接超时时间"
                  style="width: 100%"
                />
                <div class="form-help">SSH连接建立的最大等待时间</div>
              </n-form-item>
              <n-form-item label="命令执行超时时间（秒）" path="fabric_command_timeout">
                <n-input-number
                  v-model:value="taskConfig.fabric_command_timeout"
                  :min="30"
                  :max="3600"
                  placeholder="请输入命令执行超时时间"
                  style="width: 100%"
                />
                <div class="form-help">单个命令执行的最大等待时间</div>
              </n-form-item>
              <n-form-item label="启用SSH连接池" path="fabric_enable_connection_pool">
                <n-switch v-model:value="taskConfig.fabric_enable_connection_pool" />
                <div class="form-help">启用SSH连接池可减少连接开销，提升执行效率</div>
              </n-form-item>
              <n-form-item>
                <n-button type="primary" :loading="taskLoading" @click="handleSaveTaskConfig">
                  保存配置
                </n-button>
              </n-form-item>
            </n-form>
          </div>
        </n-tab-pane>

        <n-tab-pane name="notification" tab="通知配置">
          <div class="tab-content">
            <n-form
              ref="notificationFormRef"
              :model="notificationConfig"
              :rules="notificationRules"
              label-placement="top"
              class="config-form"
            >
              <n-card title="钉钉" size="small" class="notification-card">
                <n-form-item label="启用钉钉通知" path="dingtalk_enabled">
                  <n-switch v-model:value="notificationConfig.dingtalk_enabled" />
                  <div class="form-help">是否启用钉钉机器人通知</div>
                </n-form-item>
                <n-form-item label="Webhook地址" path="dingtalk_webhook">
                  <n-input
                    v-model:value="notificationConfig.dingtalk_webhook"
                    placeholder="https://oapi.dingtalk.com/robot/send?access_token=xxx"
                    clearable
                  />
                  <div class="form-help">钉钉机器人Webhook地址；已配置时服务端不回显，留空保存表示保持原值</div>
                </n-form-item>
                <n-form-item label="关键词" path="dingtalk_keyword">
                  <n-input
                    v-model:value="notificationConfig.dingtalk_keyword"
                    placeholder="请输入钉钉机器人设置的关键词"
                    clearable
                  />
                  <div class="form-help">钉钉机器人安全设置的关键词（可选）</div>
                </n-form-item>
              </n-card>
              <n-card title="飞书" size="small" class="notification-card">
                <n-form-item label="启用飞书通知" path="feishu_enabled">
                  <n-switch v-model:value="notificationConfig.feishu_enabled" />
                  <div class="form-help">是否启用飞书机器人通知</div>
                </n-form-item>
                <n-form-item label="Webhook地址" path="feishu_webhook">
                  <n-input
                    v-model:value="notificationConfig.feishu_webhook"
                    placeholder="https://open.feishu.cn/open-apis/bot/v2/hook/xxx"
                    clearable
                  />
                  <div class="form-help">飞书机器人Webhook地址；已配置时服务端不回显，留空保存表示保持原值</div>
                </n-form-item>
                <n-form-item label="关键词" path="feishu_keyword">
                  <n-input
                    v-model:value="notificationConfig.feishu_keyword"
                    placeholder="请输入飞书机器人设置的关键词"
                    clearable
                  />
                  <div class="form-help">飞书机器人安全设置的关键词（可选）</div>
                </n-form-item>
              </n-card>
              <n-card title="企业微信" size="small" class="notification-card">
                <n-form-item label="启用企业微信通知" path="wechatwork_enabled">
                  <n-switch v-model:value="notificationConfig.wechatwork_enabled" />
                  <div class="form-help">是否启用企业微信机器人通知</div>
                </n-form-item>
                <n-form-item label="Webhook地址" path="wechatwork_webhook">
                  <n-input
                    v-model:value="notificationConfig.wechatwork_webhook"
                    placeholder="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx"
                    clearable
                  />
                  <div class="form-help">企业微信机器人Webhook地址；已配置时服务端不回显，留空保存表示保持原值</div>
                </n-form-item>
                <n-form-item label="关键词" path="wechatwork_keyword">
                  <n-input
                    v-model:value="notificationConfig.wechatwork_keyword"
                    placeholder="请输入企业微信机器人设置的关键词"
                    clearable
                  />
                  <div class="form-help">企业微信机器人安全设置的关键词（可选）</div>
                </n-form-item>
              </n-card>
              <n-card title="通知级别" size="small" class="notification-card">
                <n-form-item label="通知级别" path="levels">
                  <n-checkbox-group v-model:value="notificationConfig.levels">
                    <n-space>
                      <n-checkbox value="info">信息</n-checkbox>
                      <n-checkbox value="warning">警告</n-checkbox>
                      <n-checkbox value="error">错误</n-checkbox>
                      <n-checkbox value="critical">严重</n-checkbox>
                    </n-space>
                  </n-checkbox-group>
                  <div class="form-help">选择需要发送通知的事件级别</div>
                </n-form-item>
              </n-card>
              <n-form-item>
                <n-button type="primary" :loading="notificationLoading" @click="handleSaveNotificationConfig">
                  保存配置
                </n-button>
              </n-form-item>
            </n-form>
          </div>
        </n-tab-pane>

        <n-tab-pane name="agent" tab="Agent配置">
          <div class="tab-content">
            <n-form
              ref="agentFormRef"
              :model="agentConfig"
              :rules="agentRules"
              label-placement="top"
              class="config-form"
            >
              <n-form-item label="默认离线判定阈值（秒）" path="offline_threshold_seconds">
                <n-input-number
                  v-model:value="agentConfig.offline_threshold_seconds"
                  :min="60"
                  :max="3600"
                  placeholder="请输入离线判定阈值"
                  style="width: 100%"
                />
                <div class="form-help">Agent超过此时间未心跳则认为离线，默认600秒（10分钟）</div>
              </n-form-item>
              <n-form-item label="按环境配置离线阈值" path="offline_threshold_by_env">
                <n-input
                  v-model:value="offlineThresholdEnvText"
                  type="textarea"
                  :rows="4"
                  placeholder="请输入JSON格式，如: {&quot;prod&quot;: 300, &quot;test&quot;: 900}"
                />
                <div class="form-help">按环境覆盖默认阈值，格式为JSON对象。环境名称作为key，阈值秒数作为value<br />例如：prod环境300秒离线，test环境900秒离线</div>
              </n-form-item>
              <n-form-item>
                <n-button type="primary" :loading="agentLoading" @click="handleSaveAgentConfig">
                  保存配置
                </n-button>
              </n-form-item>
            </n-form>
          </div>
        </n-tab-pane>

        <n-tab-pane name="all" tab="所有配置">
          <div class="tab-content tab-wide">
            <div class="config-table">
              <div class="table-header">
                <n-space>
                  <n-input
                    v-model:value="searchText"
                    placeholder="搜索配置项"
                    clearable
                    style="width: 300px"
                    @keyup.enter="handleSearch"
                    @clear="handleSearch"
                  >
                    <template #prefix><Search :size="16" /></template>
                  </n-input>
                  <n-select
                    v-model:value="categoryFilter"
                    placeholder="选择分类"
                    clearable
                    :options="categoryOptions"
                    style="width: 180px"
                    @update:value="handleSearch"
                  />
                  <n-button :loading="tableLoading" @click="() => fetchConfigs()">
                    <template #icon><RefreshCw :size="16" /></template>
                    刷新
                  </n-button>
                </n-space>
              </div>
              <n-data-table
                :columns="columns"
                :data="filteredConfigs"
                :loading="tableLoading"
                :pagination="tablePagination"
                :scroll-x="1450"
                :row-key="(row) => row.id"
              />
            </div>
          </div>
        </n-tab-pane>
      </n-tabs>
    </n-card>

    <n-modal
      v-model:show="editModalVisible"
      preset="card"
      title="编辑配置"
      style="width: 600px; max-width: calc(100vw - 32px)"
      :mask-closable="false"
    >
      <n-form
        ref="editFormRef"
        :model="editForm"
        :rules="editRules"
        label-placement="top"
      >
        <n-form-item label="配置键" path="key">
          <n-input v-model:value="editForm.key" readonly />
        </n-form-item>
        <n-form-item label="配置值" path="valueText">
          <n-input
            v-if="isSensitiveConfigKey(editForm.key)"
            v-model:value="editForm.valueText"
            type="password"
            show-password-on="click"
            clearable
            placeholder="留空表示保持当前 Secret"
          />
          <n-input
            v-else
            v-model:value="editForm.valueText"
            type="textarea"
            :rows="6"
            placeholder="字符串直接输入，对象/数组请输入json格式（如: {&quot;key&quot;: &quot;value&quot;} 或 [1, 2, 3]）"
          />
          <div class="form-help">
            <template v-if="isSensitiveConfigKey(editForm.key)">敏感值不会在列表或编辑框回显；留空保存表示保持原值。</template>
            <template v-else>提示：字符串直接输入即可，无需引号；对象或数组请输入有效的json格式</template>
          </div>
        </n-form-item>
        <n-form-item label="描述" path="description">
          <n-input
            v-model:value="editForm.description"
            type="textarea"
            :rows="3"
            placeholder="请输入配置描述"
          />
        </n-form-item>
        <n-form-item label="状态" path="is_active">
          <n-switch v-model:value="editForm.is_active" />
        </n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button @click="handleCancelEdit">取消</n-button>
          <n-button type="primary" :loading="editLoading" @click="handleSaveEdit">保存</n-button>
        </n-space>
      </template>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from 'vue'
import { NButton, NCard, NCheckbox, NCheckboxGroup, NDataTable, NForm, NFormItem, NInput, NInputNumber, NModal, NSelect, NSpace, NSwitch, NTabPane, NTabs, NTag, type DataTableColumns, type FormRules, useMessage } from 'naive-ui'
import { Edit3, RefreshCw, Search } from 'lucide-vue-next'
// @ts-ignore - IDE path alias resolution in this environment
import { systemConfigApi, isSensitiveConfigKey, SENSITIVE_CONFIG_VALUE, type SystemConfig, type TaskConfig, type NotificationConfig, type AgentConfig } from '@/api/system'

const message = useMessage()
const activeTab = ref('task')
const tableLoading = ref(false)
const taskLoading = ref(false)
const notificationLoading = ref(false)
const agentLoading = ref(false)
const editLoading = ref(false)
const taskFormRef = ref()
const notificationFormRef = ref()
const agentFormRef = ref()
const editFormRef = ref()
const configs = ref<SystemConfig[]>([])
const searchText = ref('')
const categoryFilter = ref<string | null>(null)

const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  pageSizeOptions: [10, 20, 50, 100]
})
const taskConfig = ref<TaskConfig>({
  fabric_max_concurrent_hosts: 20,
  fabric_connection_timeout: 30,
  fabric_command_timeout: 300,
  fabric_enable_connection_pool: true
})
const notificationConfig = ref<NotificationConfig>({
  dingtalk_enabled: false,
  dingtalk_webhook: '',
  dingtalk_keyword: '',
  feishu_enabled: false,
  feishu_webhook: '',
  feishu_keyword: '',
  wechatwork_enabled: false,
  wechatwork_webhook: '',
  wechatwork_keyword: '',
  levels: ['error', 'warning']
})
const agentConfig = ref<AgentConfig>({
  offline_threshold_seconds: 600,
  offline_threshold_by_env: {}
})
const editModalVisible = ref(false)
const editForm = reactive({
  id: 0,
  key: '',
  value: null as any,
  valueText: '',
  description: '',
  is_active: true
})

const taskRules = {}
const notificationRules: FormRules = {
  levels: [{ required: true, message: '请选择通知级别' }],
  dingtalk_webhook: [{ type: 'url', message: '请输入有效的钉钉Webhook地址' }],
  feishu_webhook: [{ type: 'url', message: '请输入有效的飞书Webhook地址' }],
  wechatwork_webhook: [{ type: 'url', message: '请输入有效的企业微信Webhook地址' }]
}
const agentRules = {
  offline_threshold_seconds: [{ required: true, message: '请输入默认离线判定阈值' }]
}
const editRules = {
  valueText: [{ required: true, message: '请输入配置值' }]
}
const categoryOptions = [
  { label: '任务执行配置', value: 'task' },
  { label: '通知配置', value: 'notification' },
  { label: 'Agent配置', value: 'agent' },
  { label: '云厂商配置', value: 'cloud' },
  { label: '安全配置', value: 'security' },
  { label: '系统配置', value: 'system' }
]

const offlineThresholdEnvText = computed({
  get: () => {
    const value = agentConfig.value.offline_threshold_by_env
    return value && Object.keys(value).length > 0 ? JSON.stringify(value, null, 2) : ''
  },
  set: (val: string) => {
    if (!val.trim()) {
      agentConfig.value.offline_threshold_by_env = {}
      return
    }
    try {
      agentConfig.value.offline_threshold_by_env = JSON.parse(val)
    } catch {
      // JSON解析失败时不更新，保持原值
    }
  }
})

const filteredConfigs = computed(() => configs.value || [])
const columns: DataTableColumns<SystemConfig> = [
  { title: '配置键', key: 'key', width: 250 },
  {
    title: '分类',
    key: 'category',
    width: 140,
    render: (record: SystemConfig) => h(
      NTag,
      { type: getCategoryTagType(record.category) },
      { default: () => record.category_display }
    )
  },
  {
    title: '配置值',
    key: 'value',
    width: 400,
    render: (record: SystemConfig) => h(
      'div',
      { class: 'config-value' },
      [h('pre', {}, formatConfigValue(record))]
    )
  },
  { title: '描述', key: 'description', width: 250, ellipsis: { tooltip: true } },
  {
    title: '状态',
    key: 'is_active',
    width: 100,
    render: (record: SystemConfig) => h(
      NTag,
      { type: record.is_active ? 'success' : 'error' },
      { default: () => record.is_active ? '启用' : '禁用' }
    )
  },
  {
    title: '更新时间',
    key: 'updated_at',
    width: 180,
    render: (record: SystemConfig) => h('div', {}, [
      h('div', {}, formatDate(record.updated_at)),
      h('div', { class: 'text-gray-400 text-xs' }, record.updated_by_name || '')
    ])
  },
  {
    title: '操作',
    key: 'actions',
    width: 120,
    fixed: 'right' as const,
    render: (record: SystemConfig) => h(NSpace, { size: 4 }, {
      default: () => [h(NButton, {
        text: true,
        size: 'small',
        onClick: () => handleEdit(record)
      }, {
        icon: () => h(Edit3, { size: 15 }),
        default: () => '编辑'
      })]
    })
  }
]

const tablePagination = computed(() => ({
  page: pagination.current,
  pageSize: pagination.pageSize,
  itemCount: pagination.total,
  showSizePicker: true,
  pageSizes: pagination.pageSizeOptions,
  showQuickJumper: true,
  onUpdatePage: handlePageChange,
  onUpdatePageSize: handlePageSizeChange
}))

const fetchConfigs = async (opts: { page?: number; page_size?: number } = {}) => {
  try {
    tableLoading.value = true
    const params: Record<string, string | number> = {
      page: opts.page || pagination.current,
      page_size: opts.page_size || pagination.pageSize
    }
    if (categoryFilter.value) params.category = categoryFilter.value
    if (searchText.value) params.search = searchText.value
    const response = await systemConfigApi.getConfigs(params)
    configs.value = response.results || []
    pagination.total = response.total || response.results?.length || 0
    const totalPages = Math.max(1, Math.ceil(pagination.total / pagination.pageSize))
    if (pagination.current > totalPages) pagination.current = totalPages
  } catch {
    message.error('获取配置列表失败')
  } finally {
    tableLoading.value = false
  }
}

const fetchTaskConfig = async () => {
  try {
    taskConfig.value = await systemConfigApi.getTaskConfig()
  } catch {
    message.error('获取任务配置失败')
  }
}

const fetchNotificationConfig = async () => {
  try {
    const response = await systemConfigApi.getNotificationConfig()
    notificationConfig.value = {
      ...response,
      dingtalk_webhook: response.dingtalk_webhook === SENSITIVE_CONFIG_VALUE ? '' : response.dingtalk_webhook,
      feishu_webhook: response.feishu_webhook === SENSITIVE_CONFIG_VALUE ? '' : response.feishu_webhook,
      wechatwork_webhook: response.wechatwork_webhook === SENSITIVE_CONFIG_VALUE ? '' : response.wechatwork_webhook
    }
  } catch {
    message.error('获取通知配置失败')
  }
}

const fetchAgentConfig = async () => {
  try {
    agentConfig.value = await systemConfigApi.getAgentConfig()
  } catch {
    message.error('获取Agent配置失败')
  }
}

const handleSaveTaskConfig = async () => {
  try {
    taskLoading.value = true
    await systemConfigApi.updateTaskConfig(taskConfig.value)
    message.success('任务配置保存成功')
  } catch {
    message.error('任务配置保存失败')
  } finally {
    taskLoading.value = false
  }
}

const handleSaveNotificationConfig = async () => {
  try {
    notificationLoading.value = true
    await systemConfigApi.updateNotificationConfig(notificationConfig.value)
    message.success('通知配置保存成功')
  } catch {
    message.error('通知配置保存失败')
  } finally {
    notificationLoading.value = false
  }
}

const handleSaveAgentConfig = async () => {
  try {
    agentLoading.value = true
    await systemConfigApi.updateAgentConfig(agentConfig.value)
    message.success('Agent配置保存成功')
  } catch {
    message.error('Agent配置保存失败')
  } finally {
    agentLoading.value = false
  }
}

const handleEdit = (record: SystemConfig) => {
  editForm.id = record.id
  editForm.key = record.key
  editForm.value = record.value
  editForm.valueText = isSensitiveConfigKey(record.key)
    ? ''
    : typeof record.value === 'string'
      ? record.value
      : JSON.stringify(record.value, null, 2)
  editForm.description = record.description
  editForm.is_active = record.is_active
  editModalVisible.value = true
}

const handleSaveEdit = async () => {
  try {
    editLoading.value = true
    const trimmedText = editForm.valueText.trim()
    const isSensitive = isSensitiveConfigKey(editForm.key)
    if (isSensitive && !trimmedText) {
      await systemConfigApi.updateConfig(editForm.id, {
        description: editForm.description,
        is_active: editForm.is_active
      })
      message.success('配置更新成功')
      editModalVisible.value = false
      await fetchConfigs()
      return
    }
    let value: any
    if (trimmedText.startsWith('{') || trimmedText.startsWith('[')) {
      try {
        value = JSON.parse(trimmedText)
      } catch {
        message.error('配置值格式错误，请输入有效的json')
        return
      }
    } else {
      try {
        value = JSON.parse(trimmedText)
      } catch {
        value = editForm.valueText
      }
    }
    await systemConfigApi.updateConfig(editForm.id, {
      value,
      description: editForm.description,
      is_active: editForm.is_active
    })
    message.success('配置更新成功')
    editModalVisible.value = false
    await fetchConfigs()
  } catch (error: any) {
    message.error(error?.message || '配置更新失败')
  } finally {
    editLoading.value = false
  }
}
const handleCancelEdit = () => {
  editModalVisible.value = false
}

const handlePageChange = (page: number) => {
  pagination.current = page
  fetchConfigs({ page, page_size: pagination.pageSize })
}

const handlePageSizeChange = (pageSize: number) => {
  pagination.pageSize = pageSize
  pagination.current = 1
  fetchConfigs({ page: 1, page_size: pageSize })
}

const handleSearch = () => {
  pagination.current = 1
  fetchConfigs({ page: 1, page_size: pagination.pageSize })
}

const getCategoryTagType = (category: string): 'default' | 'info' | 'success' | 'warning' | 'error' => {
  const types: Record<string, 'default' | 'info' | 'success' | 'warning' | 'error'> = {
    task: 'info',
    notification: 'success',
    cloud: 'info',
    cache: 'warning',
    security: 'error',
    system: 'warning'
  }
  return types[category] || 'default'
}
const formatValue = (value: any) => (
  typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value)
)

const formatConfigValue = (config: SystemConfig) => (
  isSensitiveConfigKey(config.key) ? SENSITIVE_CONFIG_VALUE : formatValue(config.value)
)

const formatDate = (dateString: string) => new Date(dateString).toLocaleString('zh-CN', {
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit'
})

onMounted(() => {
  fetchTaskConfig()
  fetchNotificationConfig()
  fetchAgentConfig()
  fetchConfigs()
})
</script>

<style scoped>
.system-config-page { padding: 0; }
.tab-content { max-width: 800px; padding: 24px; }
.config-form { max-width: 900px; }
.form-help { margin-top: 4px; color: #86909c; font-size: 12px; }
.config-table { overflow-x: auto; background: #fff; border-radius: 6px; }
.table-header { margin-bottom: 16px; }
.config-value { max-width: 400px; overflow: hidden; }
.config-value pre { max-height: 100px; margin: 0; overflow-y: auto; font-size: 12px; white-space: pre-wrap; word-break: break-all; }
.tab-wide { max-width: none; }
.notification-card { margin-bottom: 16px; }
.notification-card:last-child { margin-bottom: 0; }
</style>
