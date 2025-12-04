<template>
  <a-modal
    v-model:visible="modalVisible"
    :title="isEdit ? '编辑步骤' : '添加步骤'"
    width="800px"
    @cancel="handleCancel"
    @ok="handleSubmit"
    :confirm-loading="loading"
    :ok-button-props="{ disabled: form.step_type === 'script' && hasValidationErrors }"
  >
    <a-form :model="form" layout="vertical">
      <!-- 基本信息 -->
      <a-row :gutter="16">
        <a-col :span="12">
          <a-form-item label="步骤名称" required>
            <a-input
              v-model="form.name"
              placeholder="请输入步骤名称"
              :max-length="200"
            />
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item label="步骤类型" required>
            <a-select
              v-model="form.step_type"
              placeholder="选择步骤类型"
              @change="handleStepTypeChange"
            >
              <a-option value="script">脚本执行</a-option>
              <a-option value="file_transfer">文件传输</a-option>
            </a-select>
          </a-form-item>
        </a-col>
      </a-row>

      <a-form-item label="步骤描述">
        <a-textarea
          v-model="form.description"
          placeholder="请输入步骤描述"
          :rows="2"
          :max-length="500"
        />
      </a-form-item>

      <!-- 脚本执行配置 -->
      <div v-if="form.step_type === 'script'">
        <a-form-item label="脚本类型">
          <a-radio-group v-model="scriptType" @change="handleScriptTypeChange">
            <a-radio value="shell">Shell</a-radio>
            <a-radio value="python">Python</a-radio>
            <a-radio value="powershell">PowerShell</a-radio>
          </a-radio-group>
        </a-form-item>

        <a-form-item label="脚本内容" required>
          <template #extra>
            <a-space size="small">
              <a-button size="small" @click="handleLoadTemplate">
                <template #icon>
                  <icon-file />
                </template>
                加载模板
              </a-button>
              <a-button size="small" @click="insertScriptExample">
                <template #icon>
                  <icon-code />
                </template>
                插入示例
              </a-button>
            </a-space>
          </template>

          <script-editor-with-validation
            ref="editorRef"
            v-model="scriptContent"
            :language="scriptType"
            :theme="editorTheme"
            :height="500"
            :auto-validate="true"
            @validation-change="handleValidationChange"
            :readonly="false"
          />
        </a-form-item>

        <!-- 位置参数 -->
        <a-form-item label="位置参数">
          <div class="parameter-section">
            <div class="parameter-header">
              <span>位置参数（在脚本中使用 $1, $2, $3... 访问）</span>
              <a-button type="text" size="small" @click="addPositionalArg">
                <template #icon>
                  <icon-plus />
                </template>
                添加参数
              </a-button>
            </div>
            <div class="parameter-list">
              <div
                v-for="(_, index) in positionalArgs"
                :key="index"
                class="parameter-item"
              >
                <span style="width: 60px; text-align: center">${{ index + 1 }}</span>
                <div class="parameter-input-wrapper">
                  <a-input
                    v-model="positionalArgs[index]"
                    :type="parameterVisibility[index] ? 'text' : 'password'"
                    :placeholder="`参数 ${index + 1}`"
                    style="flex: 1"
                  />
                  <a-button
                    type="text"
                    size="small"
                    @click="toggleParameterVisibility(index)"
                    class="visibility-toggle"
                  >
                    <template #icon>
                      <icon-eye v-if="parameterVisibility[index]" />
                      <icon-eye-invisible v-else />
                    </template>
                  </a-button>
                </div>
                <a-button
                  type="text"
                  status="danger"
                  @click="removePositionalArg(index)"
                  style="margin-left: 8px"
                >
                  <template #icon>
                    <icon-delete />
                  </template>
                </a-button>
              </div>
            </div>
          </div>
        </a-form-item>
      </div>

      <!-- 文件传输配置 -->
      <div v-if="form.step_type === 'file_transfer'">
        <a-form-item label="传输类型">
          <a-radio-group v-model="transferType">
            <a-radio value="upload">上传到服务器</a-radio>
            <a-radio value="download">从服务器下载</a-radio>
          </a-radio-group>
        </a-form-item>

        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="本地路径" required>
              <!-- 上传模式：使用 a-upload -->
              <div v-if="transferType === 'upload'" class="upload-section">
                <a-upload
                  :file-list="stepFileList"
                  :auto-upload="false"
                  multiple
                  :show-upload-button="true"
                  :show-file-list="false"
                  :show-cancel-button="false"
                  :show-retry-button="false"
                  :show-upload-list-button="false"
                  @change="handleStepFileChange"
                  @remove="handleStepFileRemove"
                  class="step-file-upload"
                >
                  <template #upload-button>
                    <div class="step-upload-btn">
                      <icon-plus />
                      <div class="upload-text">选择文件</div>
                    </div>
                  </template>
                </a-upload>

                <!-- 自定义步骤文件列表 -->
                <div v-if="stepFileList.length > 0" class="custom-step-file-list">
                  <div
                    v-for="(fileItem, index) in stepFileList"
                    :key="fileItem.uid || index"
                    class="custom-step-upload-list-item"
                  >
                    <div class="step-file-info">
                      <icon-file class="step-file-icon" />
                      <div class="step-file-details">
                        <div class="step-file-name">{{ fileItem.name }}</div>
                        <div class="step-file-size">{{ formatStepFileSize(fileItem.file?.size || 0) }}</div>
                      </div>
                    </div>
                    <div class="step-file-actions">
                      <a-button
                        type="text"
                        size="small"
                        @click="handleStepFileRemove(fileItem)"
                        class="step-remove-btn"
                      >
                        <template #icon>
                          <icon-delete />
                        </template>
                      </a-button>
                    </div>
                  </div>
                </div>
                <a-input
                  v-model="localPath"
                  placeholder="也可以手动输入文件路径"
                  class="manual-path-input"
                />
              </div>

              <!-- 下载模式：普通输入框 -->
              <a-input
                v-else
                v-model="localPath"
                placeholder="请输入本地文件路径"
                allow-clear
              />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="远程路径" required>
              <a-input
                v-model="remotePath"
                placeholder="请输入远程文件路径"
              />
            </a-form-item>
          </a-col>
        </a-row>

        <a-form-item label="覆盖策略">
          <a-select v-model="overwritePolicy" placeholder="选择覆盖策略">
            <a-option value="overwrite">覆盖</a-option>
            <a-option value="skip">跳过</a-option>
            <a-option value="backup">备份后覆盖</a-option>
            <a-option value="fail">失败</a-option>
          </a-select>
        </a-form-item>
      </div>

      <!-- 目标主机选择 -->
      <a-divider>目标主机</a-divider>

      <a-form-item label="目标主机">
        <template #extra>
          <a-button type="primary" size="small" @click="showHostSelector = true">
            <template #icon>
              <icon-computer />
            </template>
            选择主机
          </a-button>
        </template>

        <!-- 选择摘要 -->
        <div class="host-selection-summary">
          <div v-if="selectedGroups.length === 0 && selectedHosts.length === 0" class="empty-selection">
            <div class="empty-icon">
              <icon-computer />
            </div>
            <div class="empty-text">请选择执行主机</div>
            <div class="empty-desc">点击上方"选择主机"按钮选择目标主机或主机分组</div>
          </div>
          
          <div v-else class="selection-content">
            <!-- 所有目标主机（包含分组展开的主机和直接选择的主机） -->
            <div class="selection-section">
              <div class="section-title">
                <icon-computer />
                目标主机 ({{ allTargetHosts.length }})
                <div class="section-actions">
                  <a-button type="text" size="mini" @click="copyAllIPs">
                    复制所有IP
                  </a-button>
                  <a-button type="text" size="mini" @click="copyOfflineIPs">
                    复制异常IP
                  </a-button>
                  <a-button type="text" size="mini" @click="clearAllSelections">
                    <template #icon>
                      <icon-close />
                    </template>
                    清空
                  </a-button>
                  <a-button type="text" size="mini" @click="removeOfflineHosts">
                    <template #icon>
                      <icon-exclamation-circle />
                    </template>
                    清除异常
                  </a-button>
                </div>
              </div>

              <!-- 分组来源的主机 -->
              <div v-if="groupHosts.length > 0" class="host-group-section">
                <div class="group-header">
                  <icon-folder />
                  来自分组 ({{ groupHosts.length }} 台)
                </div>
                <div class="host-list">
                  <div
                    v-for="host in groupHosts"
                    :key="`group-${host.id}`"
                    class="host-item"
                    :class="{ 'host-offline': host.status === 'offline' }"
                  >
                    <div class="host-info">
                      <div class="host-name">{{ host.name }}</div>
                      <div class="host-ip">{{ host.ip_address }}:{{ host.port }}</div>
                      <div class="host-meta">
                        <div class="host-os" :class="`os-${host.os_type}`">
                          {{ getOSText(host.os_type) }}
                        </div>
                        <div class="host-status" :class="`status-${host.status}`">
                          {{ getStatusText(host.status) }}
                        </div>
                      </div>
                      <div class="host-source">来自: {{ getHostGroupNames(host.id) }}</div>
                    </div>
                    <a-button
                      type="text"
                      size="mini"
                      @click="removeHostFromGroup(host.id)"
                      class="remove-host-btn"
                    >
                      <template #icon>
                        <icon-close />
                      </template>
                    </a-button>
                  </div>
                </div>
              </div>

              <!-- 直接选择的主机 -->
              <div v-if="directHosts.length > 0" class="host-group-section">
                <div class="group-header">
                  <icon-computer />
                  直接选择 ({{ directHosts.length }} 台)
                </div>
                <div class="host-list">
                  <div
                    v-for="host in directHosts"
                    :key="`direct-${host.id}`"
                    class="host-item"
                    :class="{ 'host-offline': host.status === 'offline' }"
                  >
                    <div class="host-info">
                      <div class="host-name">{{ host.name }}</div>
                      <div class="host-ip">{{ host.ip_address }}:{{ host.port }}</div>
                      <div class="host-meta">
                        <div class="host-os" :class="`os-${host.os_type}`">
                          {{ getOSText(host.os_type) }}
                        </div>
                        <div class="host-status" :class="`status-${host.status}`">
                          {{ getStatusText(host.status) }}
                        </div>
                      </div>
                    </div>
                    <a-button
                      type="text"
                      size="mini"
                      @click="removeDirectHost(host.id)"
                      class="remove-host-btn"
                    >
                      <template #icon>
                        <icon-close />
                      </template>
                    </a-button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </a-form-item>

      <!-- 主机配置提示 -->
      <div v-if="hostWarnings.length > 0" class="host-warnings">
        <a-alert
          v-for="warning in hostWarnings"
          :key="warning.message"
          :type="warning.type"
          :show-icon="true"
        >
          {{ warning.message }}
        </a-alert>
      </div>

      <!-- 执行配置 -->
      <a-divider>执行配置</a-divider>

      <a-form-item label="执行账号">
        <a-select
          v-model="selectedAccountId"
          placeholder="选择服务器账号（可选）"
          allow-clear
          :loading="accountLoading"
          style="width: 100%"
        >
          <a-option
            v-for="account in serverAccounts"
            :key="account.id"
            :value="account.id"
          >
            {{ account.name }} ({{ account.username }})
          </a-option>
        </a-select>
        <div class="form-tip">
          <icon-info-circle />
          不选择时将使用主机配置的默认用户
        </div>
      </a-form-item>
      
      <a-row :gutter="16">
        <a-col :span="8">
          <a-form-item label="超时时间(秒)">
            <a-input-number
              v-model="form.timeout"
              :min="1"
              :max="3600"
              style="width: 100%"
            />
          </a-form-item>
        </a-col>
        <a-col :span="8">
          <a-form-item label="忽略错误">
            <a-switch v-model="form.ignore_error" />
          </a-form-item>
        </a-col>
      </a-row>
    </a-form>
  </a-modal>

  <!-- 脚本模板选择弹窗 -->
  <a-modal
    v-model:visible="templateModalVisible"
    title="选择脚本模板"
    :width="800"
    @ok="handleTemplateSelect"
    @cancel="templateModalVisible = false"
  >
    <a-table
      :columns="templateColumns"
      :data="scriptTemplates"
      :loading="templateLoading"
      :pagination="false"
      row-key="id"
      :row-selection="{
        type: 'radio',
        selectedRowKeys: selectedTemplateKeys,
        onSelectionChange: (keys) => { selectedTemplateKeys = keys }
      }"
      @row-click="handleTemplateRowClick"
    >
      <template #script_type="{ record }">
        <a-tag :color="getScriptTypeColor(record.script_type)">
          {{ getScriptTypeText(record.script_type) }}
        </a-tag>
      </template>
      <template #created_at="{ record }">
        {{ new Date(record.created_at).toLocaleString() }}
      </template>
    </a-table>
  </a-modal>

  <!-- 主机选择器弹窗 -->
  <HostSelector
    v-model:visible="showHostSelector"
    :hosts="hosts"
    :groups="hostGroups"
    :selected-hosts="selectedHosts"
    :selected-groups="selectedGroups"
    @confirm="handleHostSelection"
  />
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted, nextTick } from 'vue'
import { Message } from '@arco-design/web-vue'
import { IconComputer, IconFolder, IconEye, IconEyeInvisible, IconDelete, IconPlus } from '@arco-design/web-vue/es/icon'
import { hostApi, hostGroupApi, scriptTemplateApi } from '@/api/ops'
import { accountApi, type ServerAccount } from '@/api/account'
import type { JobStep, Host, HostGroup, ScriptTemplate } from '@/types'
import ScriptEditorWithValidation from '@/components/ScriptEditorWithValidation.vue'
import HostSelector from '@/components/HostSelector.vue'
import { getScriptExample, getScriptTypeText, getScriptTypeColor } from '@/components/ScriptExamples'
import type { ScriptValidationResult } from '@/utils/scriptValidator'


interface Props {
  visible: boolean
  step?: Partial<JobStep>
  isEdit?: boolean
}

interface Emits {
  (e: 'update:visible', visible: boolean): void
  (e: 'save', step: JobStep): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

// 响应式数据
const loading = ref(false)
const hostLoading = ref(false)
const groupLoading = ref(false)
const accountLoading = ref(false)
const editorRef = ref()
const editorTheme = ref('vs-dark')


// 数据列表
const hosts = ref<Host[]>([])
const hostGroups = ref<HostGroup[]>([])
const serverAccounts = ref<ServerAccount[]>([])
const selectedAccountId = ref<number | undefined>()

// HostSelector相关
const showHostSelector = ref(false)
const selectedHosts = ref<number[]>([])
const selectedGroups = ref<number[]>([])

// 表单数据
const form = reactive<Partial<JobStep>>({
  name: '',
  description: '',
  step_type: 'script',
  order: 1,
  step_parameters: [],  // 位置参数数组
  timeout: 300,
  ignore_error: false,
  target_hosts: [],
  target_groups: [],
  // 脚本相关字段
  script_type: 'shell',
  script_content: '',
  account_id: undefined,
  // 文件传输相关字段
  transfer_type: 'upload',
  local_path: '',
  remote_path: '',
  overwrite_policy: 'overwrite'
})

// 脚本相关
const scriptType = ref('shell')
const scriptContent = ref('')

// 脚本验证状态
const validationResults = ref<ScriptValidationResult[]>([])
const hasValidationErrors = computed(() => {
  return validationResults.value.some(result => result.severity === 'error')
})

// 脚本模板相关
const templateModalVisible = ref(false)
const templateLoading = ref(false)
const scriptTemplates = ref<ScriptTemplate[]>([])
const selectedTemplateKeys = ref<number[]>([])

// 参数相关
const positionalArgs = ref<string[]>([''])
const parameterVisibility = ref<Record<number, boolean>>({})

// 文件传输相关
const transferType = ref('upload')
const localPath = ref('')
const remotePath = ref('')
const overwritePolicy = ref('overwrite')
const stepFileList = ref<any[]>([]) // 步骤文件列表

// 模板表格列
const templateColumns = [
  { title: '模板名称', dataIndex: 'name', key: 'name' },
  { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
  { title: '脚本类型', dataIndex: 'script_type', key: 'script_type', slotName: 'script_type' },
  { title: '创建时间', dataIndex: 'created_at', key: 'created_at', slotName: 'created_at' }
]

// 计算属性
const modalVisible = computed({
  get: () => props.visible,
  set: (value) => emit('update:visible', value)
})

// 主机配置警告
const hostWarnings = computed(() => {
  const warnings = []

  // 检查是否没有选择主机
  if ((!selectedHosts.value || selectedHosts.value.length === 0) &&
      (!selectedGroups.value || selectedGroups.value.length === 0)) {
    warnings.push({
      type: 'warning',
      message: '未选择目标主机，执行时将无法运行此步骤'
    })
  }

  return warnings
})

// 主机选择相关计算属性
const totalSelectedTargets = computed(() => {
  return allTargetHosts.value.length
})

// 获取分组中的主机
const groupHosts = computed(() => {
  const groupHostIds = new Set<number>()
  const result: any[] = []

  selectedGroups.value.forEach(groupId => {
    hosts.value.forEach(host => {
      if (host.groups_info && host.groups_info.some(g => g.id === groupId)) {
        if (!groupHostIds.has(host.id)) {
          groupHostIds.add(host.id)
          result.push(host)
        }
      }
    })
  })

  return result
})

// 获取直接选择的主机（排除已在分组中的主机）
const directHosts = computed(() => {
  const groupHostIds = new Set(groupHosts.value.map(h => h.id))
  return hosts.value.filter(host =>
    selectedHosts.value.includes(host.id) && !groupHostIds.has(host.id)
  )
})

// 获取所有目标主机（去重）
const allTargetHosts = computed(() => {
  const allHosts = [...groupHosts.value, ...directHosts.value]
  const uniqueHosts = new Map()

  allHosts.forEach(host => {
    uniqueHosts.set(host.id, host)
  })

  return Array.from(uniqueHosts.values())
})

const getGroupName = (groupId: number) => {
  const group = hostGroups.value.find(g => g.id === groupId)
  return group?.name || `分组${groupId}`
}

const getHostName = (hostId: number) => {
  const host = hosts.value.find(h => h.id === hostId)
  return host?.name || `主机${hostId}`
}

const getHostIP = (hostId: number) => {
  const host = hosts.value.find(h => h.id === hostId)
  return host ? `${host.ip_address}:${host.port}` : '未知IP'
}

const getHostStatus = (hostId: number) => {
  const host = hosts.value.find(h => h.id === hostId)
  return host?.status || 'unknown'
}

const getHostStatusText = (hostId: number) => {
  const status = getHostStatus(hostId)
  return getStatusText(status)
}

const getStatusText = (status: string) => {
  const statusMap = {
    'online': '在线',
    'offline': '离线',
    'unknown': '未知'
  }
  return statusMap[status as keyof typeof statusMap] || '未知'
}

const getOSText = (osType: string) => {
  const osMap = {
    'linux': 'Linux',
    'windows': 'Windows',
    'aix': 'AIX',
    'solaris': 'Solaris'
  }
  return osMap[osType as keyof typeof osMap] || osType
}

const getHostGroupNames = (hostId: number) => {
  const host = hosts.value.find(h => h.id === hostId)
  if (!host || !host.groups_info) return ''

  const selectedGroupNames = host.groups_info
    .filter(g => selectedGroups.value.includes(g.id))
    .map(g => g.name)

  return selectedGroupNames.join(', ')
}

// 获取主机列表
const fetchHosts = async () => {
  try {
    hostLoading.value = true
    const response = await hostApi.getHosts({ page_size: 20 })
    hosts.value = response.results || []
  } catch (error) {
    console.error('获取主机列表失败:', error)
  } finally {
    hostLoading.value = false
  }
}

// 获取主机分组列表
const fetchHostGroups = async () => {
  try {
    groupLoading.value = true
    const response = await hostGroupApi.getGroups({ page_size: 20 })
    hostGroups.value = response.results || []
  } catch (error) {
    console.error('获取主机分组失败:', error)
  } finally {
    groupLoading.value = false
  }
}

// 获取服务器账号列表
const fetchServerAccounts = async () => {
  try {
    accountLoading.value = true
    const response = await accountApi.getAccounts({ page_size: 20 })
    serverAccounts.value = response.results || []
  } catch (error) {
    console.error('获取服务器账号列表失败:', error)
  } finally {
    accountLoading.value = false
  }
}

// 监听步骤数据变化
watch(
  () => props.step,
  (step) => {
    if (step) {
      Object.assign(form, step)

      // 处理目标主机数据 - 如果是对象数组，提取ID
      if (step.target_hosts && Array.isArray(step.target_hosts)) {
        form.target_hosts = step.target_hosts.map(host =>
          typeof host === 'object' && host ? (host as any).id : host
        )
        selectedHosts.value = form.target_hosts
      }

      // 处理目标分组数据 - 如果是对象数组，提取ID
      if (step.target_groups && Array.isArray(step.target_groups)) {
        form.target_groups = step.target_groups.map(group =>
          typeof group === 'object' && group ? (group as any).id : group
        )
        selectedGroups.value = form.target_groups
      }

      // 解析脚本和文件传输配置
      if (step.step_type === 'script') {
        scriptType.value = step.script_type || 'shell'
        scriptContent.value = step.script_content || ''
        selectedAccountId.value = step.account_id
      } else if (step.step_type === 'file_transfer') {
        transferType.value = step.transfer_type || 'upload'
        localPath.value = step.local_path || ''
        remotePath.value = step.remote_path || ''
        overwritePolicy.value = step.overwrite_policy || 'overwrite'
        selectedAccountId.value = step.account_id
      }

      // 解析位置参数 (现在 step_parameters 直接是数组)
      if (step.step_parameters && Array.isArray(step.step_parameters)) {
        positionalArgs.value = step.step_parameters.length > 0
          ? step.step_parameters
          : ['']
      } else {
        positionalArgs.value = ['']
      }

      // 如果是新建步骤且脚本内容为空，插入示例代码
      if (!props.isEdit && step.step_type === 'script' && !scriptContent.value.trim()) {
        insertScriptExample()
      }
    }
  },
  { immediate: true, deep: true }
)

// 步骤类型变化处理
const handleStepTypeChange = () => {
  // 清空参数
  form.step_parameters = []  // 位置参数数组
  scriptContent.value = ''
  localPath.value = ''
  remotePath.value = ''
  selectedAccountId.value = undefined

  // 清空脚本参数
  positionalArgs.value = ['']

  // 重置默认值
  if (form.step_type === 'script') {
    scriptType.value = 'shell'
    // 使用 nextTick 确保 DOM 更新后再插入示例代码
    nextTick(() => {
      insertScriptExample()
    })
  } else if (form.step_type === 'file_transfer') {
    transferType.value = 'upload'
    overwritePolicy.value = 'overwrite'
  }
}

// 脚本类型变化处理
const handleScriptTypeChange = () => {
  // 切换脚本类型时，如果当前内容是示例代码或为空，则替换为新类型的示例
  const currentContent = scriptContent.value.trim()
  const shouldReplace = !currentContent || isExampleContent(currentContent)

  if (shouldReplace) {
    // 使用 nextTick 确保 DOM 更新后再插入示例代码
    nextTick(() => {
      insertScriptExample()
    })
  } else {
    // 如果有自定义内容，询问用户是否要替换
    Message.info('脚本类型已切换，如需示例代码请点击"插入示例"按钮')
  }
}

// 插入脚本示例
const insertScriptExample = () => {
  scriptContent.value = getScriptExample(scriptType.value)
}

// 脚本模板操作
const handleLoadTemplate = async () => {
  try {
    await fetchScriptTemplates()
    templateModalVisible.value = true
  } catch (error) {
    console.error('加载模板失败:', error)
  }
}

// 获取脚本模板列表（用于导入，只显示启用的模板）
const fetchScriptTemplates = async () => {
  templateLoading.value = true
  try {
    const response = await scriptTemplateApi.getTemplatesForImport({ page_size: 50 })
    scriptTemplates.value = response.results
  } catch (error) {
    console.error('获取脚本模板失败:', error)
    Message.error('获取脚本模板失败')
  } finally {
    templateLoading.value = false
  }
}

// 处理模板行选择
const handleTemplateRowClick = (record: ScriptTemplate) => {
  selectedTemplateKeys.value = [record.id]
}

// 确认选择模板
const handleTemplateSelect = () => {
  if (selectedTemplateKeys.value.length > 0) {
    const template = scriptTemplates.value.find(t => t.id === selectedTemplateKeys.value[0])
    if (template) {
      scriptContent.value = template.script_content || template.content || ''
      scriptType.value = template.script_type
      Message.success(`已加载模板: ${template.name}`)
      templateModalVisible.value = false
      selectedTemplateKeys.value = []
    }
  } else {
    Message.warning('请选择一个模板')
    return
  }
}

// 位置参数操作
const addPositionalArg = () => {
  positionalArgs.value.push('')
}

const removePositionalArg = (index: number) => {
  if (positionalArgs.value.length > 1) {
    positionalArgs.value.splice(index, 1)
    // 重新整理可见性映射
    const newVisibility: Record<number, boolean> = {}
    Object.keys(parameterVisibility.value).forEach(key => {
      const keyIndex = parseInt(key)
      if (keyIndex < index) {
        newVisibility[keyIndex] = parameterVisibility.value[keyIndex]
      } else if (keyIndex > index) {
        newVisibility[keyIndex - 1] = parameterVisibility.value[keyIndex]
      }
    })
    parameterVisibility.value = newVisibility
  } else {
    positionalArgs.value[0] = ''
    parameterVisibility.value[0] = false
  }
}

// 切换参数可见性
const toggleParameterVisibility = (index: number) => {
  parameterVisibility.value[index] = !parameterVisibility.value[index]
}

// 文件大小格式化函数
const formatStepFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 B'

  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))

  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

// 步骤文件操作方法
const handleStepFileChange = (files: any[]) => {
  stepFileList.value = files

  // 更新localPath
  if (files.length === 0) {
    localPath.value = ''
  } else if (files.length === 1) {
    localPath.value = files[0].name
  } else {
    localPath.value = files.map((f: any) => f.name).join(';')
  }
}

const handleStepFileRemove = (fileItem: any) => {
  // 手动更新步骤文件列表（因为我们使用自定义文件列表）
  const remainingFiles = stepFileList.value.filter(f => f.uid !== fileItem.uid)
  stepFileList.value = remainingFiles

  // 更新localPath
  if (remainingFiles.length === 0) {
    localPath.value = ''
  } else if (remainingFiles.length === 1) {
    localPath.value = remainingFiles[0].name
  } else {
    localPath.value = remainingFiles.map((f: any) => f.name).join(';')
  }
}

// 检查是否是示例内容
const isExampleContent = (content: string) => {
  // 检查内容是否包含示例代码的特征
  const exampleMarkers = [
    'job_start',
    'job_success',
    'job_fail',
    '作业平台中执行脚本成功和失败的标准',
    '可在此处开始编写您的脚本逻辑代码'
  ]

  return exampleMarkers.some(marker => content.includes(marker))
}

// 处理脚本验证结果变化
const handleValidationChange = (results: ScriptValidationResult[]) => {
  validationResults.value = results
  const errorCount = results.filter(r => r.severity === 'error').length
  const warningCount = results.filter(r => r.severity === 'warning').length
  
  if (errorCount > 0) {
    Message.warning(`脚本中发现 ${errorCount} 个错误，${warningCount} 个警告`)
  } else if (warningCount > 0) {
    Message.info(`脚本中发现 ${warningCount} 个警告`)
  }
}

// 提交表单
const handleSubmit = async () => {
  try {
    // 验证表单
    if (!form.name?.trim()) {
      Message.error('请输入步骤名称')
      return
    }

    // 获取位置参数
    const validPositionalArgs = positionalArgs.value.filter(arg => arg.trim() !== '')

    const stepData: JobStep = {
      id: form.id || 0,
      name: form.name!,
      description: form.description || '',
      step_type: form.step_type!,
      step_type_display: form.step_type === 'script' ? '脚本执行' : '文件传输',
      order: form.order || 1,
      step_parameters: validPositionalArgs,  // 位置参数数组
      timeout: form.timeout || 300,
      ignore_error: form.ignore_error || false,
      target_hosts: selectedHosts.value || [],
      target_groups: selectedGroups.value || []
    }

    // 添加脚本或文件传输的专门字段
    if (form.step_type === 'script') {
      if (!scriptContent.value.trim()) {
        Message.error('请输入脚本内容')
        return
      }
      
      // 检查脚本验证错误
      if (hasValidationErrors.value) {
        Message.error('脚本存在错误，请修复后再保存')
        return
      }
      
      stepData.script_type = scriptType.value
      stepData.script_content = scriptContent.value
      stepData.account_id = selectedAccountId.value
    } else if (form.step_type === 'file_transfer') {
      if (!localPath.value.trim() || !remotePath.value.trim()) {
        Message.error('请输入本地路径和远程路径')
        return
      }
      stepData.transfer_type = transferType.value
      stepData.local_path = localPath.value
      stepData.remote_path = remotePath.value
      stepData.overwrite_policy = overwritePolicy.value
      stepData.account_id = selectedAccountId.value
    }

    emit('save', stepData)
  } catch (error) {
    console.error('保存步骤失败:', error)
    Message.error('保存步骤失败')
  }
}

// 取消操作
const handleCancel = () => {
  modalVisible.value = false
}

// 主机选择处理方法
const handleHostSelection = (selection: { selectedHosts: number[], selectedGroups: number[] }) => {
  selectedHosts.value = selection.selectedHosts
  selectedGroups.value = selection.selectedGroups
  console.log('主机选择完成:', selection)
}

// 主机管理方法
const clearAllSelections = () => {
  selectedHosts.value = []
  selectedGroups.value = []
  Message.success('已清空所有选择')
}

const removeHostFromGroup = (hostId: number) => {
  const host = hosts.value.find(h => h.id === hostId)
  if (!host || !host.groups_info) return

  // 找到该主机所属的已选择分组
  const hostSelectedGroups = host.groups_info
    .filter(g => selectedGroups.value.includes(g.id))
    .map(g => g.id)

  // 从选择的分组中移除这些分组
  hostSelectedGroups.forEach(groupId => {
    const index = selectedGroups.value.indexOf(groupId)
    if (index > -1) {
      selectedGroups.value.splice(index, 1)
    }
  })

  Message.success(`已从分组中移除主机: ${host.name}`)
}

const removeDirectHost = (hostId: number) => {
  const index = selectedHosts.value.indexOf(hostId)
  if (index > -1) {
    selectedHosts.value.splice(index, 1)
    const hostName = getHostName(hostId)
    Message.success(`已移除主机: ${hostName}`)
  }
}

const removeOfflineHosts = () => {
  const offlineHosts = allTargetHosts.value.filter(host => host.status === 'offline')
  if (offlineHosts.length === 0) {
    Message.info('没有找到离线主机')
    return
  }

  // 移除离线的直接选择主机
  selectedHosts.value = selectedHosts.value.filter(hostId => {
    const host = hosts.value.find(h => h.id === hostId)
    return host?.status !== 'offline'
  })

  // 移除包含离线主机的分组
  selectedGroups.value = selectedGroups.value.filter(groupId => {
    const groupHosts = hosts.value.filter(host =>
      host.groups_info && host.groups_info.some(g => g.id === groupId)
    )
    return !groupHosts.some(host => host.status === 'offline')
  })

  Message.success(`已移除 ${offlineHosts.length} 台离线主机`)
}

// 复制所有目标主机 IP
const copyAllIPs = async () => {
  const hosts = allTargetHosts.value
  if (!hosts.length) {
    Message.warning('当前没有目标主机可复制')
    return
  }

  const ips = hosts.map(host => host.ip_address).join('\n')

  try {
    await navigator.clipboard.writeText(ips)
    Message.success(`已复制 ${hosts.length} 个主机 IP 到剪贴板`)
  } catch (error) {
    console.error('复制IP失败:', error)
    Message.error('复制失败，请检查浏览器权限或手动复制')
  }
}

// 复制异常（离线）主机 IP
const copyOfflineIPs = async () => {
  const offlineHosts = allTargetHosts.value.filter(host => host.status === 'offline')
  if (!offlineHosts.length) {
    Message.info('当前没有异常（离线）主机')
    return
  }

  const ips = offlineHosts.map(host => host.ip_address).join('\n')

  try {
    await navigator.clipboard.writeText(ips)
    Message.success(`已复制 ${offlineHosts.length} 个异常主机 IP 到剪贴板`)
  } catch (error) {
    console.error('复制异常IP失败:', error)
    Message.error('复制失败，请检查浏览器权限或手动复制')
  }
}

// 工具函数已移至公共组件

// 生命周期
onMounted(() => {
  fetchHosts()
  fetchHostGroups()
  fetchServerAccounts()
})
</script>

<style scoped>
.form-tip {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 4px;
}

/* 主机警告样式 */
.host-warnings {
  margin-top: 8px;
  margin-bottom: 16px;
}

/* 参数配置样式 */
.parameter-section {
  border: 1px solid var(--color-border-2);
  border-radius: 6px;
  padding: 12px;
  background: var(--color-bg-1);
}

.parameter-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  font-size: 13px;
  color: var(--color-text-2);
}

.parameter-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.parameter-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* 主机选择摘要样式 */
.host-selection-summary {
  min-height: 120px;
}

.empty-selection {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 32px 16px;
  text-align: center;
}

.empty-icon {
  font-size: 32px;
  color: #c9cdd4;
  margin-bottom: 12px;
}

.empty-text {
  font-size: 14px;
  color: #4e5969;
  font-weight: 500;
  margin-bottom: 4px;
}

.empty-desc {
  font-size: 12px;
  color: #86909c;
  line-height: 1.4;
}

.selection-content {
  padding: 16px 0;
}

.selection-section {
  margin-bottom: 16px;
}

.selection-section:last-child {
  margin-bottom: 0;
}

.section-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  font-size: 13px;
  font-weight: 500;
  color: #4e5969;
  margin-bottom: 8px;
}

.section-actions {
  display: flex;
  gap: 4px;
}

.selection-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 6px;
}

.selection-stats {
  font-size: 12px;
  color: #86909c;
}

.selection-total {
  padding-top: 12px;
  border-top: 1px solid #e5e6eb;
  text-align: center;
}

/* 步骤文件上传样式 */
.upload-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.step-file-upload {
  width: 100%;
}

/* 自定义步骤文件列表容器 */
.custom-step-file-list {
  margin-top: 12px;
}

/* 自定义步骤文件列表样式 */
.custom-step-upload-list-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  border: 1px solid var(--color-border-2);
  border-radius: 6px;
  background-color: var(--color-fill-1);
  margin-bottom: 8px;
}

.step-file-info {
  display: flex;
  align-items: center;
  flex: 1;
}

.step-file-icon {
  font-size: 16px;
  color: var(--color-text-3);
  margin-right: 8px;
}

.step-file-details {
  flex: 1;
}

.step-file-name {
  font-size: 14px;
  color: var(--color-text-1);
  font-weight: 500;
  margin-bottom: 2px;
}

.step-file-size {
  font-size: 12px;
  color: var(--color-text-3);
}

.step-file-actions {
  display: flex;
  align-items: center;
}

.step-remove-btn {
  color: var(--color-text-3);
  transition: color 0.3s;
}

.step-remove-btn:hover {
  color: var(--color-danger-6);
}



.step-upload-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 16px;
  border: 2px dashed var(--color-border-2);
  border-radius: 6px;
  background-color: var(--color-fill-1);
  cursor: pointer;
  transition: all 0.3s;
}

.step-upload-btn:hover {
  border-color: var(--color-primary-light-4);
  background-color: var(--color-primary-light-1);
}

.upload-text {
  margin-top: 6px;
  font-size: 12px;
  color: var(--color-text-2);
}

.manual-path-input {
  margin-top: 8px;
}

/* 主机列表样式 */
.host-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 200px;
  overflow-y: auto;
}

.host-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background-color: var(--color-fill-1);
  border: 1px solid var(--color-border-2);
  border-radius: 4px;
  transition: all 0.2s;
}

.host-item:hover {
  background-color: var(--color-fill-2);
  border-color: var(--color-border-3);
}

.host-item.host-offline {
  background-color: var(--color-danger-light-1);
  border-color: var(--color-danger-light-3);
}

.host-info {
  flex: 1;
  min-width: 0;
}

.host-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-1);
  margin-bottom: 2px;
}

.host-ip {
  font-size: 11px;
  color: var(--color-text-3);
  font-family: 'Courier New', monospace;
  margin-bottom: 4px;
}

.host-meta {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 2px;
}

.host-os {
  font-size: 10px;
  padding: 1px 4px;
  border-radius: 2px;
  font-weight: 500;
  background-color: var(--color-fill-3);
  color: var(--color-text-2);
}

.os-linux {
  background-color: var(--color-blue-light-1);
  color: var(--color-blue);
}

.os-windows {
  background-color: var(--color-cyan-light-1);
  color: var(--color-cyan);
}

.os-aix {
  background-color: var(--color-purple-light-1);
  color: var(--color-purple);
}

.os-solaris {
  background-color: var(--color-orange-light-1);
  color: var(--color-orange);
}

.host-status {
  font-size: 10px;
  padding: 1px 4px;
  border-radius: 2px;
  font-weight: 500;
}

.status-online {
  background-color: var(--color-success-light-1);
  color: var(--color-success);
}

.status-offline {
  background-color: var(--color-danger-light-1);
  color: var(--color-danger);
}

.status-unknown {
  background-color: var(--color-warning-light-1);
  color: var(--color-warning);
}

.remove-host-btn {
  color: var(--color-text-3);
  flex-shrink: 0;
}

.remove-host-btn:hover {
  color: var(--color-danger);
}

/* 主机分组样式 */
.host-group-section {
  margin-bottom: 16px;
}

.host-group-section:last-child {
  margin-bottom: 0;
}

.group-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 500;
  color: var(--color-text-2);
  margin-bottom: 8px;
  padding: 4px 8px;
  background-color: var(--color-fill-2);
  border-radius: 4px;
}

.host-source {
  font-size: 10px;
  color: var(--color-text-4);
  font-style: italic;
}

/* 参数输入样式 */
.parameter-input-wrapper {
  position: relative;
  flex: 1;
  margin-left: 8px;
}

.parameter-input-wrapper .visibility-toggle {
  position: absolute;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
  z-index: 1;
  background: var(--color-bg-1);
  border: none;
  padding: 4px;
}
</style>
