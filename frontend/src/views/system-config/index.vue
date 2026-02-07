<template>
  <div class="system-config-page">
    <a-card title="系统配置" :bordered="false">
      <a-tabs v-model:active-key="activeTab" type="card">
        <!-- 任务执行配置 -->
        <a-tab-pane key="task" title="任务执行配置">
          <div class="tab-content">
            <a-form
              ref="taskFormRef"
              :model="taskConfig"
              :rules="taskRules"
              layout="vertical"
              class="config-form"
            >
            <a-form-item label="单个任务最大并发主机数" field="fabric_max_concurrent_hosts">
              <a-input-number
                v-model="taskConfig.fabric_max_concurrent_hosts"
                :min="1"
                :max="100"
                placeholder="请输入并发主机数"
              />
              <div class="form-help">单个任务执行时同时连接的最大主机数量（适用于并行执行模式）</div>
            </a-form-item>

            <a-form-item label="SSH连接超时时间（秒）" field="fabric_connection_timeout">
              <a-input-number
                v-model="taskConfig.fabric_connection_timeout"
                :min="5"
                :max="300"
                placeholder="请输入连接超时时间"
              />
              <div class="form-help">SSH连接建立的最大等待时间</div>
            </a-form-item>

            <a-form-item label="命令执行超时时间（秒）" field="fabric_command_timeout">
              <a-input-number
                v-model="taskConfig.fabric_command_timeout"
                :min="30"
                :max="3600"
                placeholder="请输入命令执行超时时间"
              />
              <div class="form-help">单个命令执行的最大等待时间</div>
            </a-form-item>

            <a-form-item label="启用SSH连接池" field="fabric_enable_connection_pool">
              <a-switch v-model="taskConfig.fabric_enable_connection_pool" />
              <div class="form-help">启用SSH连接池可减少连接开销，提升执行效率</div>
            </a-form-item>

            <a-form-item>
              <a-button type="primary" @click="handleSaveTaskConfig" :loading="taskLoading">
                保存配置
              </a-button>
            </a-form-item>
          </a-form>
          </div>
        </a-tab-pane>

        <!-- 通知配置 -->
        <a-tab-pane key="notification" title="通知配置">
          <div class="tab-content">
            <a-form
              ref="notificationFormRef"
              :model="notificationConfig"
              :rules="notificationRules"
              layout="vertical"
              class="config-form"
            >
            <!-- 钉钉配置 -->
            <a-card title="钉钉" size="small" class="notification-card">
              <a-form-item label="启用钉钉通知" field="dingtalk_enabled">
                <a-switch v-model="notificationConfig.dingtalk_enabled" />
                <div class="form-help">是否启用钉钉机器人通知</div>
              </a-form-item>

              <a-form-item label="Webhook地址" field="dingtalk_webhook">
                <a-input
                  v-model="notificationConfig.dingtalk_webhook"
                  placeholder="https://oapi.dingtalk.com/robot/send?access_token=xxx"
                />
                <div class="form-help">钉钉机器人Webhook地址</div>
              </a-form-item>

              <a-form-item label="关键词" field="dingtalk_keyword">
                <a-input
                  v-model="notificationConfig.dingtalk_keyword"
                  placeholder="请输入钉钉机器人设置的关键词"
                />
                <div class="form-help">钉钉机器人安全设置的关键词（可选）</div>
              </a-form-item>
            </a-card>

            <!-- 飞书配置 -->
            <a-card title="飞书" size="small" class="notification-card">
              <a-form-item label="启用飞书通知" field="feishu_enabled">
                <a-switch v-model="notificationConfig.feishu_enabled" />
                <div class="form-help">是否启用飞书机器人通知</div>
              </a-form-item>

              <a-form-item label="Webhook地址" field="feishu_webhook">
                <a-input
                  v-model="notificationConfig.feishu_webhook"
                  placeholder="https://open.feishu.cn/open-apis/bot/v2/hook/xxx"
                />
                <div class="form-help">飞书机器人Webhook地址</div>
              </a-form-item>

              <a-form-item label="关键词" field="feishu_keyword">
                <a-input
                  v-model="notificationConfig.feishu_keyword"
                  placeholder="请输入飞书机器人设置的关键词"
                />
                <div class="form-help">飞书机器人安全设置的关键词（可选）</div>
              </a-form-item>
            </a-card>

            <!-- 企业微信配置 -->
            <a-card title="企业微信" size="small" class="notification-card">
              <a-form-item label="启用企业微信通知" field="wechatwork_enabled">
                <a-switch v-model="notificationConfig.wechatwork_enabled" />
                <div class="form-help">是否启用企业微信机器人通知</div>
              </a-form-item>

              <a-form-item label="Webhook地址" field="wechatwork_webhook">
                <a-input
                  v-model="notificationConfig.wechatwork_webhook"
                  placeholder="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx"
                />
                <div class="form-help">企业微信机器人Webhook地址</div>
              </a-form-item>

              <a-form-item label="关键词" field="wechatwork_keyword">
                <a-input
                  v-model="notificationConfig.wechatwork_keyword"
                  placeholder="请输入企业微信机器人设置的关键词"
                />
                <div class="form-help">企业微信机器人安全设置的关键词（可选）</div>
              </a-form-item>
            </a-card>

            <!-- 通知级别 -->
            <a-card title="通知级别" size="small" class="notification-card">
              <a-form-item label="通知级别" field="levels">
                <a-checkbox-group v-model="notificationConfig.levels">
                  <a-checkbox value="info">信息</a-checkbox>
                  <a-checkbox value="warning">警告</a-checkbox>
                  <a-checkbox value="error">错误</a-checkbox>
                  <a-checkbox value="critical">严重</a-checkbox>
                </a-checkbox-group>
                <div class="form-help">选择需要发送通知的事件级别</div>
              </a-form-item>
            </a-card>

            <a-form-item>
              <a-button type="primary" @click="handleSaveNotificationConfig" :loading="notificationLoading">
                保存配置
              </a-button>
            </a-form-item>
          </a-form>
          </div>
        </a-tab-pane>

        <!-- Agent配置 -->
        <a-tab-pane key="agent" title="Agent配置">
          <div class="tab-content">
            <a-form
              ref="agentFormRef"
              :model="agentConfig"
              :rules="agentRules"
              layout="vertical"
              class="config-form"
            >
            <a-form-item label="默认离线判定阈值（秒）" field="offline_threshold_seconds">
              <a-input-number
                v-model="agentConfig.offline_threshold_seconds"
                :min="60"
                :max="3600"
                placeholder="请输入离线判定阈值"
              />
              <div class="form-help">Agent超过此时间未心跳则认为离线，默认600秒（10分钟）</div>
            </a-form-item>

            <a-form-item label="按环境配置离线阈值" field="offline_threshold_by_env">
              <a-textarea
                v-model="offlineThresholdEnvText"
                :rows="4"
                placeholder="请输入JSON格式，如: {&quot;prod&quot;: 300, &quot;test&quot;: 900}"
              />
              <div class="form-help">
                按环境覆盖默认阈值，格式为JSON对象。环境名称作为key，阈值秒数作为value
                <br />例如：prod环境300秒离线，test环境900秒离线
              </div>
            </a-form-item>

            <a-form-item>
              <a-button type="primary" @click="handleSaveAgentConfig" :loading="agentLoading">
                保存配置
              </a-button>
            </a-form-item>
          </a-form>
          </div>
        </a-tab-pane>

        <!-- 所有配置 -->
        <a-tab-pane key="all" title="所有配置">
          <div class="tab-content tab-wide">
            <div class="config-table">
            <div class="table-header">
              <a-space>
                <a-input
                  v-model="searchText"
                  placeholder="搜索配置项"
                  allow-clear
                  style="width: 300px"
                  @input="handleSearch"
                  @clear="handleSearch"
                >
                  <template #prefix>
                    <icon-search />
                  </template>
                </a-input>
                <a-select
                  v-model="categoryFilter"
                  placeholder="选择分类"
                  allow-clear
                  style="width: 150px"
                  @change="handleSearch"
                >
                  <a-option value="">全部</a-option>
                  <a-option value="task">任务执行配置</a-option>
                  <a-option value="notification">通知配置</a-option>
                  <a-option value="agent">Agent配置</a-option>
                  <a-option value="cloud">云厂商配置</a-option>
                  <a-option value="security">安全配置</a-option>
                  <a-option value="system">系统配置</a-option>
                </a-select>
                <a-button @click="fetchConfigs">
                  <template #icon>
                    <icon-refresh />
                  </template>
                  刷新
                </a-button>
              </a-space>
            </div>

            <a-table
              :columns="columns"
              :data="filteredConfigs"
              :loading="tableLoading"
              :pagination="pagination"
              @page-change="handlePageChange"
              @page-size-change="handlePageSizeChange"
            >
              <template #category="{ record }">
                <a-tag :color="getCategoryColor(record.category)">
                  {{ record.category_display }}
                </a-tag>
              </template>

              <template #value="{ record }">
                <div class="config-value">
                  <pre>{{ formatValue(record.value) }}</pre>
                </div>
              </template>

              <template #is_active="{ record }">
                <a-tag :color="record.is_active ? 'green' : 'red'">
                  {{ record.is_active ? '启用' : '禁用' }}
                </a-tag>
              </template>

              <template #updated_at="{ record }">
                <div>{{ formatDate(record.updated_at) }}</div>
                <div class="text-gray-400 text-xs">{{ record.updated_by_name }}</div>
              </template>

              <template #actions="{ record }">
                <a-space>
                  <a-button type="text" size="small" @click="handleEdit(record)">
                    <template #icon>
                      <icon-edit />
                    </template>
                    编辑
                  </a-button>
                </a-space>
              </template>
            </a-table>
          </div>
          </div>
        </a-tab-pane>
      </a-tabs>
    </a-card>

    <!-- 编辑配置对话框 -->
    <a-modal
      v-model:visible="editModalVisible"
      title="编辑配置"
      width="600px"
      @ok="handleSaveEdit"
      @cancel="handleCancelEdit"
    >
      <a-form
        ref="editFormRef"
        :model="editForm"
        :rules="editRules"
        layout="vertical"
      >
        <a-form-item label="配置键" field="key">
          <a-input v-model="editForm.key" readonly />
        </a-form-item>

        <a-form-item label="配置值" field="value">
          <a-textarea
            v-model="editForm.valueText"
            :rows="6"
            placeholder="字符串直接输入，对象/数组请输入json格式（如: {&quot;key&quot;: &quot;value&quot;} 或 [1, 2, 3]）"
          />
          <div class="form-help">
            提示：字符串直接输入即可，无需引号；对象或数组请输入有效的json格式
          </div>
        </a-form-item>

        <a-form-item label="描述" field="description">
          <a-textarea
            v-model="editForm.description"
            :rows="3"
            placeholder="请输入配置描述"
          />
        </a-form-item>

        <a-form-item label="状态" field="is_active">
          <a-switch v-model="editForm.is_active" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { Message } from '@arco-design/web-vue'
// @ts-ignore - IDE path alias resolution in this environment
import { systemConfigApi, type SystemConfig, type TaskConfig, type NotificationConfig, type AgentConfig } from '@/api/system'

// 响应式数据
const activeTab = ref('task')
const tableLoading = ref(false)
const taskLoading = ref(false)
const notificationLoading = ref(false)
const agentLoading = ref(false)
const agentFormRef = ref()
const configs = ref<SystemConfig[]>([])
const searchText = ref('')
const categoryFilter = ref('')

// 分页配置
const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  showSizeChanger: true,
  showTotal: true,
  showJumper: true,
})

// 任务配置
const taskConfig = ref<TaskConfig>({
  fabric_max_concurrent_hosts: 20,
  fabric_connection_timeout: 30,
  fabric_command_timeout: 300,
  fabric_enable_connection_pool: true
})

// 通知配置
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

// Agent配置
const agentConfig = ref<AgentConfig>({
  offline_threshold_seconds: 600,
  offline_threshold_by_env: {}
})

// 编辑对话框
const editModalVisible = ref(false)
const editForm = reactive({
  id: 0,
  key: '',
  value: null as any,
  valueText: '',
  description: '',
  is_active: true
})

// 表单验证规则
const taskRules = {
}

const notificationRules = {
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

// 表格列配置
const columns = [
  {
    title: '配置键',
    dataIndex: 'key',
    width: 250
  },
  {
    title: '分类',
    dataIndex: 'category',
    slotName: 'category',
    width: 140
  },
  {
    title: '配置值',
    dataIndex: 'value',
    slotName: 'value',
    width: 400
  },
  {
    title: '描述',
    dataIndex: 'description',
    width: 250
  },
  {
    title: '状态',
    dataIndex: 'is_active',
    slotName: 'is_active',
    width: 100
  },
  {
    title: '更新时间',
    dataIndex: 'updated_at',
    slotName: 'updated_at',
    width: 180
  },
  {
    title: '操作',
    slotName: 'actions',
    width: 120,
    fixed: 'right'
  }
]

// Agent配置文本编辑（JSON格式）
const offlineThresholdEnvText = computed({
  get: () => {
    if (!agentConfig.value.offline_threshold_by_env || Object.keys(agentConfig.value.offline_threshold_by_env).length === 0) {
      return ''
    }
    return JSON.stringify(agentConfig.value.offline_threshold_by_env, null, 2)
  },
  set: (val: string) => {
    if (!val.trim()) {
      agentConfig.value.offline_threshold_by_env = {}
      return
    }
    try {
      agentConfig.value.offline_threshold_by_env = JSON.parse(val)
    } catch (e) {
      // JSON解析失败时不更新，保持原值
    }
  }
})

// 计算属性
const filteredConfigs = computed(() => {
  return configs.value || []
})

// 方法
const fetchConfigs = async (opts: any = {}) => {
  try {
    tableLoading.value = true
    const params: any = {
      page: opts.page || pagination.current,
      page_size: opts.page_size || pagination.pageSize
    }
    if (categoryFilter.value) params.category = categoryFilter.value
    if (searchText.value) params.search = searchText.value
    const response = await systemConfigApi.getConfigs(params)
    configs.value = response.results || []
    pagination.total = response.total || (response.results ? response.results.length : 0)
    // 确保当前页在总页范围内
    const totalPages = Math.max(1, Math.ceil((pagination.total || 0) / pagination.pageSize))
    if (pagination.current > totalPages) {
      pagination.current = totalPages
    }
  } catch (error) {
    Message.error('获取配置列表失败')
  } finally {
    tableLoading.value = false
  }
}

const fetchTaskConfig = async () => {
  try {
    const response = await systemConfigApi.getTaskConfig()
    taskConfig.value = response
  } catch (error) {
    Message.error('获取任务配置失败')
  }
}

const fetchNotificationConfig = async () => {
  try {
    const response = await systemConfigApi.getNotificationConfig()
    notificationConfig.value = response
  } catch (error) {
    Message.error('获取通知配置失败')
  }
}

const fetchAgentConfig = async () => {
  try {
    const response = await systemConfigApi.getAgentConfig()
    agentConfig.value = response
  } catch (error) {
    Message.error('获取Agent配置失败')
  }
}

const handleSaveTaskConfig = async () => {
  try {
    taskLoading.value = true
    await systemConfigApi.updateTaskConfig(taskConfig.value)
    Message.success('任务配置保存成功')
  } catch (error) {
    Message.error('任务配置保存失败')
  } finally {
    taskLoading.value = false
  }
}

const handleSaveNotificationConfig = async () => {
  try {
    notificationLoading.value = true
    await systemConfigApi.updateNotificationConfig(notificationConfig.value)
    Message.success('通知配置保存成功')
  } catch (error) {
    Message.error('通知配置保存失败')
  } finally {
    notificationLoading.value = false
  }
}

const handleSaveAgentConfig = async () => {
  try {
    agentLoading.value = true
    await systemConfigApi.updateAgentConfig(agentConfig.value)
    Message.success('Agent配置保存成功')
  } catch (error) {
    Message.error('Agent配置保存失败')
  } finally {
    agentLoading.value = false
  }
}

const handleEdit = (record: SystemConfig) => {
  editForm.id = record.id
  editForm.key = record.key
  editForm.value = record.value
  // 智能格式化显示：字符串直接显示（不带引号），其他类型显示格式化的JSON
  if (typeof record.value === 'string') {
    editForm.valueText = record.value
  } else {
  editForm.valueText = JSON.stringify(record.value, null, 2)
  }
  editForm.description = record.description
  editForm.is_active = record.is_active
  editModalVisible.value = true
}

const handleSaveEdit = async () => {
  try {
    let value: any
    
    // 智能解析：先尝试解析JSON，如果失败且不是JSON格式，当作字符串处理
    const trimmedText = editForm.valueText.trim()
    
    // 如果以 { 或 [ 开头，尝试解析为JSON
    if (trimmedText.startsWith('{') || trimmedText.startsWith('[')) {
      try {
        value = JSON.parse(trimmedText)
      } catch (e) {
        Message.error('配置值格式错误，请输入有效的json')
        return
      }
    } else {
      // 尝试解析为JSON（可能是数字、布尔值、null等）
      try {
        value = JSON.parse(trimmedText)
      } catch (e) {
        // 解析失败，当作字符串处理
        value = editForm.valueText
      }
    }
    
    await systemConfigApi.updateConfig(editForm.id, {
      value,
      description: editForm.description,
      is_active: editForm.is_active
    })
    
    Message.success('配置更新成功')
    editModalVisible.value = false
    fetchConfigs()
  } catch (error: any) {
    if (error instanceof SyntaxError) {
      Message.error('配置值格式错误，请输入有效的json')
    } else {
      Message.error(error.message || '配置更新失败')
    }
  }
}

const handleCancelEdit = () => {
  editModalVisible.value = false
}

const handlePageChange = (page: number) => {
  pagination.current = page
  fetchConfigs({ page: pagination.current, page_size: pagination.pageSize })
}

const handlePageSizeChange = (pageSize: number) => {
  pagination.pageSize = pageSize
  pagination.current = 1
  fetchConfigs({ page: pagination.current, page_size: pagination.pageSize })
}

const handleSearch = () => {
  // 搜索和过滤逻辑由计算属性filteredConfigs自动处理
  // 这里可以添加额外的搜索逻辑，比如重置分页等
  pagination.current = 1
  fetchConfigs({ page: 1, page_size: pagination.pageSize })
}

// 工具函数
const getCategoryColor = (category: string) => {
  const colors: Record<string, string> = {
    task: 'blue',
    notification: 'green',
    cloud: 'cyan',
    cache: 'orange',
    security: 'red',
    system: 'purple'
  }
  return colors[category] || 'gray'
}

const formatValue = (value: any) => {
  if (typeof value === 'object') {
    return JSON.stringify(value, null, 2)
  }
  return String(value)
}

const formatDate = (dateString: string) => {
  return new Date(dateString).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

// 生命周期
onMounted(() => {
  fetchTaskConfig()
  fetchNotificationConfig()
  fetchAgentConfig()
  fetchConfigs()
})
</script>

<style scoped>
.system-config-page {
  padding: 0;
}

.tab-content {
  padding: 24px;
  max-width: 800px;
}

.config-form {
  max-width: 900px;
}

.form-help {
  font-size: 12px;
  color: #86909c;
  margin-top: 4px;
}

.config-table {
  background: #fff;
  border-radius: 6px;
  overflow-x: auto;
}

.table-header {
  margin-bottom: 16px;
}

.config-value {
  max-width: 400px;
  overflow: hidden;
}

.config-value pre {
  font-size: 12px;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 100px;
  overflow-y: auto;
}

.tab-wide {
  max-width: none;
}

.notification-card {
  margin-bottom: 16px;
}

.notification-card:last-child {
  margin-bottom: 0;
}
</style>
