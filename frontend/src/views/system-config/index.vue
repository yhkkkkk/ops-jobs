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
            <a-form-item label="最大并发任务数" field="max_concurrent_jobs">
              <a-input-number
                v-model="taskConfig.max_concurrent_jobs"
                :min="1"
                :max="100"
                placeholder="请输入最大并发任务数"
              />
              <div class="form-help">系统同时执行的最大任务数量</div>
            </a-form-item>

            <a-form-item label="任务超时时间（秒）" field="job_timeout">
              <a-input-number
                v-model="taskConfig.job_timeout"
                :min="60"
                :max="86400"
                placeholder="请输入任务超时时间"
              />
              <div class="form-help">单个任务的最大执行时间，超时将被强制终止</div>
            </a-form-item>

            <a-form-item label="重试次数" field="retry_attempts">
              <a-input-number
                v-model="taskConfig.retry_attempts"
                :min="0"
                :max="10"
                placeholder="请输入重试次数"
              />
              <div class="form-help">任务失败后的自动重试次数</div>
            </a-form-item>

            <a-form-item label="日志保留天数" field="cleanup_days">
              <a-input-number
                v-model="taskConfig.cleanup_days"
                :min="1"
                :max="365"
                placeholder="请输入日志保留天数"
              />
              <div class="form-help">任务执行日志的保留时间</div>
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
            <a-form-item label="邮件通知" field="email_enabled">
              <a-switch v-model="notificationConfig.email_enabled" />
              <div class="form-help">是否启用邮件通知功能</div>
            </a-form-item>

            <a-form-item label="Webhook通知" field="webhook_enabled">
              <a-switch v-model="notificationConfig.webhook_enabled" />
              <div class="form-help">是否启用Webhook通知功能</div>
            </a-form-item>

            <a-form-item label="通知级别" field="levels">
              <a-checkbox-group v-model="notificationConfig.levels">
                <a-checkbox value="info">信息</a-checkbox>
                <a-checkbox value="warning">警告</a-checkbox>
                <a-checkbox value="error">错误</a-checkbox>
                <a-checkbox value="critical">严重</a-checkbox>
              </a-checkbox-group>
              <div class="form-help">选择需要发送通知的事件级别</div>
            </a-form-item>

            <a-form-item label="默认邮件接收人" field="email_recipients">
              <a-select
                v-model="notificationConfig.email_recipients"
                multiple
                allow-create
                allow-clear
                placeholder="请输入邮箱地址"
              >
                <a-option
                  v-for="email in notificationConfig.email_recipients"
                  :key="email"
                  :value="email"
                >
                  {{ email }}
                </a-option>
              </a-select>
              <div class="form-help">默认的通知邮件接收人列表</div>
            </a-form-item>

            <a-form-item>
              <a-button type="primary" @click="handleSaveNotificationConfig" :loading="notificationLoading">
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
            placeholder="请输入JSON格式的配置值"
          />
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
import { systemConfigApi, type SystemConfig, type TaskConfig, type NotificationConfig } from '@/api/system'

// 响应式数据
const activeTab = ref('task')
const tableLoading = ref(false)
const taskLoading = ref(false)
const notificationLoading = ref(false)
const configs = ref<SystemConfig[]>([])
const searchText = ref('')
const categoryFilter = ref('')

// 分页配置
const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  showSizeChanger: true,
  showTotal: true
})

// 任务配置
const taskConfig = ref<TaskConfig>({
  max_concurrent_jobs: 10,
  job_timeout: 3600,
  retry_attempts: 3,
  cleanup_days: 30
})

// 通知配置
const notificationConfig = ref<NotificationConfig>({
  email_enabled: true,
  webhook_enabled: false,
  levels: ['error', 'warning'],
  email_recipients: []
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
  max_concurrent_jobs: [{ required: true, message: '请输入最大并发任务数' }],
  job_timeout: [{ required: true, message: '请输入任务超时时间' }],
  retry_attempts: [{ required: true, message: '请输入重试次数' }],
  cleanup_days: [{ required: true, message: '请输入日志保留天数' }]
}

const notificationRules = {
  levels: [{ required: true, message: '请选择通知级别' }]
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

// 计算属性
const filteredConfigs = computed(() => {
  let result = configs.value

  if (searchText.value) {
    result = result.filter(config =>
      config.key.toLowerCase().includes(searchText.value.toLowerCase()) ||
      config.description.toLowerCase().includes(searchText.value.toLowerCase())
    )
  }

  if (categoryFilter.value) {
    result = result.filter(config => config.category === categoryFilter.value)
  }

  // 更新分页总数
  pagination.total = result.length

  // 前端分页
  const start = (pagination.current - 1) * pagination.pageSize
  const end = start + pagination.pageSize

  return result.slice(start, end)
})

// 方法
const fetchConfigs = async () => {
  try {
    tableLoading.value = true
    // 获取所有配置，前端进行过滤和分页
    const response = await systemConfigApi.getConfigs()
    configs.value = response.results || []
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

const handleEdit = (record: SystemConfig) => {
  editForm.id = record.id
  editForm.key = record.key
  editForm.value = record.value
  editForm.valueText = JSON.stringify(record.value, null, 2)
  editForm.description = record.description
  editForm.is_active = record.is_active
  editModalVisible.value = true
}

const handleSaveEdit = async () => {
  try {
    // 验证JSON格式
    const value = JSON.parse(editForm.valueText)
    
    await systemConfigApi.updateConfig(editForm.id, {
      value,
      description: editForm.description,
      is_active: editForm.is_active
    })
    
    Message.success('配置更新成功')
    editModalVisible.value = false
    fetchConfigs()
  } catch (error) {
    if (error instanceof SyntaxError) {
      Message.error('配置值格式错误，请输入有效的JSON')
    } else {
      Message.error('配置更新失败')
    }
  }
}

const handleCancelEdit = () => {
  editModalVisible.value = false
}

const handlePageChange = (page: number) => {
  pagination.current = page
  // 前端分页，不需要重新请求数据
}

const handlePageSizeChange = (pageSize: number) => {
  pagination.pageSize = pageSize
  pagination.current = 1
  // 前端分页，不需要重新请求数据
}

const handleSearch = () => {
  // 搜索和过滤逻辑由计算属性filteredConfigs自动处理
  // 这里可以添加额外的搜索逻辑，比如重置分页等
  pagination.current = 1
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
  max-width: 600px;
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
</style>
