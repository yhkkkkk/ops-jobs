<template>
  <a-drawer
    v-model:visible="modalVisible"
    :title="isEdit ? '编辑步骤' : '添加步骤'"
    width="1050px"
    unmount-on-close
    @cancel="handleCancel"
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
            <a-radio value="javascript">JavaScript</a-radio>
            <a-radio value="go">Go</a-radio>
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
            :language="scriptType as any"
            :theme="editorTheme"
            :height="700"
            :auto-validate="true"
            @validation-change="handleValidationChange"
            :readonly="false"
          />
        </a-form-item>

        <!-- 变量使用指引 -->
        <div class="var-hint">
          <icon-info-circle class="var-hint-icon" />
          <div class="var-hint-body">
            <div class="var-hint-title">变量使用指引</div>
            <div class="var-hint-text">
              • 全局变量：在脚本/参数/文件路径中使用 <code v-pre>{{ GLOBAL.变量名 }}</code><br />
              • 系统变量：如 <code v-pre>{{ SYS.JOB_ID }}</code>、<code v-pre>{{ SYS.STEP_ID }}</code>、<code v-pre>{{ SYS.EXECUTOR }}</code><br />
              • 支持任意脚本类型与文件传输路径，未填写的必填变量会在执行前校验
            </div>
          </div>
        </div>

        <!-- 位置参数 -->
        <a-form-item label="位置参数">
          <div class="parameter-section">
            <!-- 参数输入模式切换 -->
            <div class="parameter-mode-selector">
              <a-radio-group v-model="parameterInputMode" @change="handleParameterModeChange">
                <a-radio value="individual">逐个输入</a-radio>
                <a-radio value="bulk">批量输入</a-radio>
              </a-radio-group>
            </div>

            <!-- 逐个输入模式 -->
            <div v-if="parameterInputMode === 'individual'" class="parameter-individual-mode">
              <div class="parameter-header">
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
                  <div class="parameter-item-row">
                    <span class="parameter-index">${{ index + 1 }}</span>
                    <a-input
                      v-model="positionalArgs[index]"
                      :type="parameterVisibility[index] ? 'text' : 'password'"
                      :placeholder="`参数 ${index + 1}`"
                      class="parameter-input"
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
                    <a-button
                      type="text"
                      status="danger"
                      @click="removePositionalArg(index)"
                      class="remove-btn"
                    >
                      <template #icon>
                        <icon-delete />
                      </template>
                    </a-button>
                  </div>
                </div>
              </div>
            </div>

            <!-- 批量输入模式 -->
            <div v-else class="parameter-bulk-mode">
              <div class="parameter-header">
                <span>位置参数（支持空格分隔或引号包含空格参数）</span>
              </div>
              <a-textarea
                v-model="bulkParameters"
                placeholder="例如：param1 param2 'param with spaces' --flag=value"
                :rows="4"
                @input="handleBulkParametersChange"
              />
              <div class="bulk-parameter-preview" v-if="bulkParameters.trim()">
                <div class="preview-header">参数预览：</div>
                <div class="preview-list">
                  <span
                    v-for="(param, index) in parsedBulkParameters"
                    :key="index"
                    class="preview-param"
                  >
                    ${{ index + 1 }}: {{ param }}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </a-form-item>
        <div class="form-tip parameter-tip">
          <icon-info-circle />
          位置参数将按顺序传递给脚本，在脚本中可以使用 $1, $2, $3... 访问
        </div>
      </div>

      <!-- 文件传输配置（仅本地上传） -->
      <div v-if="form.step_type === 'file_transfer'">
        <a-row :gutter="16">
          <a-col :span="24">
            <a-form-item label="文件来源" required>
              <FileSourcesPanel :artifacts="fileArtifacts" @update:artifacts="(v)=>{ fileArtifacts = v }" />
            </a-form-item>
          </a-col>
        </a-row>
        <a-row :gutter="16" style="margin-top:8px;">
          <a-col :span="24">
        <a-form-item label="远程路径" required>
          <a-input
            v-model="remotePath"
            placeholder="请输入远程文件路径，支持 [date]、[hostname] 等变量"
          />
          <div class="var-hint compact">
            <icon-info-circle class="var-hint-icon" />
            <div class="var-hint-body">
              路径可使用变量：<code v-pre>{{ GLOBAL.xxx }}</code>、<code v-pre>{{ SYS.JOB_ID }}</code>，以及内置 <code>[date]</code>、<code>[hostname]</code> 等占位符
            </div>
          </div>
          <!-- 路径变量预览 -->
          <div v-if="remotePath && hasVariables(remotePath)" class="path-preview">
            <div class="path-preview-header">
              <icon-eye />
              <span>变量预览</span>
                </div>
                <div class="path-preview-content">{{ previewPath(remotePath) }}</div>
              </div>
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

        <a-form-item label="最大匹配数">
          <a-input-number
            v-model="maxTargetMatches"
            :min="1"
            :max="1000"
            placeholder="目标路径最多匹配的文件/目录数量"
            style="width: 100%"
          />
          <div class="form-tip">
            <icon-info-circle />
            限制通配符匹配结果的数量，默认100，避免过度匹配
          </div>
        </a-form-item>
      </div>

      <!-- 目标主机选择 -->
      <a-divider>目标主机</a-divider>

      <!-- 使用全局变量切换 -->
      <a-form-item>
        <div class="target-source-selector">
          <a-radio-group v-model="targetSource" @change="handleTargetSourceChange">
            <a-radio value="manual">
              <template #radio="{ checked }">
                <a-space align="center">
                  <icon-computer :style="{ color: checked ? '#165DFF' : '#86909C' }" />
                  <span>手动选择</span>
                </a-space>
              </template>
            </a-radio>
            <a-radio value="global">
              <template #radio="{ checked }">
                <a-space align="center">
                  <icon-apps :style="{ color: checked ? '#165DFF' : '#86909C' }" />
                  <span>使用全局变量</span>
                </a-space>
              </template>
            </a-radio>
          </a-radio-group>
        </div>
      </a-form-item>

      <!-- 手动选择模式 -->
      <template v-if="targetSource === 'manual'">
        <a-form-item>
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
                          <div
                            v-if="host.agent_info"
                            class="host-agent"
                            :class="`agent-${host.agent_info.status}`"
                          >
                            <span class="agent-dot" :class="`agent-dot-${host.agent_info.status}`"></span>
                            {{ host.agent_info.status_display }}
                          </div>
                          <div v-else class="host-agent agent-none">
                            Agent未安装
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
                          <div
                            v-if="host.agent_info"
                            class="host-agent"
                            :class="`agent-${host.agent_info.status}`"
                          >
                            <span class="agent-dot" :class="`agent-dot-${host.agent_info.status}`"></span>
                            {{ host.agent_info.status_display }}
                          </div>
                          <div v-else class="host-agent agent-none">
                            Agent未安装
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
      </template>

      <!-- 全局变量模式 -->
      <template v-else>
        <a-form-item label="选择全局变量" :rules="[{ required: true, message: '请选择全局变量' }]">
          <a-select
            v-model="selectedGlobalVariable"
            placeholder="请选择IP列表类型的全局变量"
            style="width: 100%"
          >
            <a-option
              v-for="variable in hostListGlobalVariables"
              :key="variable.key"
              :value="variable.key"
            >
              <a-space>
                <span>{{ variable.key }}</span>
                <a-tag size="small" color="blue">IP列表</a-tag>
              </a-space>
            </a-option>
          </a-select>
          <div class="form-tip">
            <icon-info-circle />
            选择一个全局变量来作为目标主机来源，变量值应为逗号或换行符分隔的IP列表
          </div>

          <!-- 已选变量预览 -->
          <div v-if="selectedGlobalVariable && getGlobalVariablePreview" class="global-variable-preview">
            <div class="preview-header">
              <icon-eye />
              <span>变量预览</span>
            </div>
            <div class="preview-content">{{ getGlobalVariablePreview }}</div>
            <div class="preview-count">
              共 {{ getGlobalVariableHostCount }} 个IP
            </div>
          </div>
        </a-form-item>
      </template>

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
    <template #footer>
      <a-space>
        <a-button @click="handleCancel">取消</a-button>
        <a-button
          type="primary"
          :loading="loading"
          :disabled="form.step_type === 'script' && hasValidationErrors"
          @click="handleSubmit"
        >
          保存
        </a-button>
      </a-space>
    </template>
  </a-drawer>

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
    :selected-hosts="selectedHosts as any"
    :selected-groups="selectedGroups as any"
    :host-pagination="hostPagination"
    :enable-host-pagination="true"
    @confirm="handleHostSelection"
    @host-page-change="handleHostPageChange"
    @host-page-size-change="handleHostPageSizeChange"
  />
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted, nextTick, h } from 'vue'
import { Message, Modal } from '@arco-design/web-vue'
import { IconComputer, IconFolder, IconEye, IconEyeInvisible, IconDelete, IconPlus, IconInfoCircle, IconApps, IconEye as IconEyeIcon } from '@arco-design/web-vue/es/icon'
import { hostApi, hostGroupApi, scriptTemplateApi } from '@/api/ops'
import request from '@/utils/request'
import { accountApi, type ServerAccount } from '@/api/account'
import type { JobStep, Host, HostGroup, ScriptTemplate } from '@/types'
import ScriptEditorWithValidation from '@/components/ScriptEditorWithValidation.vue'
import HostSelector from '@/components/HostSelector.vue'
import { getScriptExample, getScriptTypeText, getScriptTypeColor } from '@/components/ScriptExamples'
import type { ScriptValidationResult } from '@/utils/scriptValidator'
import FileSourcesPanel from '@/components/FileSourcesPanel.vue'


interface Props {
  visible: boolean
  step?: Partial<JobStep>
  isEdit?: boolean
  globalParameters?: Record<string, any>  // 全局变量配置
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

// 主机分页状态
const hostPagination = ref({
  current: 1,
  pageSize: 50,
  total: 0,
  pageSizeOptions: ['20', '50', '100', '200']
})

// 目标主机来源选择
const targetSource = ref<'manual' | 'global'>('manual')
const selectedGlobalVariable = ref<string>('')

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
  // 文件传输相关字段（仅本地上传到模板存储）
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
const parameterInputMode = ref<'individual' | 'bulk'>('individual') // 参数输入模式
const bulkParameters = ref('') // 批量参数输入

// 文件传输相关（仅本地上传）
const remotePath = ref('')
const overwritePolicy = ref('overwrite')
const maxTargetMatches = ref(100) // 最大匹配数
const stepFileList = ref<any[]>([]) // 步骤文件列表
const fileArtifacts = ref<any[]>([]) // 已上传到制品库的 artifact metadata

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

// 获取IP列表类型的全局变量
const hostListGlobalVariables = computed(() => {
  const globalParams = props.globalParameters || {}
  if (!globalParams || Object.keys(globalParams).length === 0) return []

  return Object.entries(globalParams)
    .filter(([key, value]) => {
      // 检查是否是IP列表类型的变量
      if (typeof value === 'object' && value !== null) {
        return value.type === 'host_list' || value.type === 'array'
      }
      // 如果是字符串，尝试解析
      if (typeof value === 'string') {
        try {
          const parsed = JSON.parse(value)
          return parsed.type === 'host_list' || parsed.type === 'array'
        } catch {
          return false
        }
      }
      return false
    })
    .map(([key, value]) => {
      let displayValue = ''
      if (typeof value === 'object') {
        displayValue = value.value || ''
      } else if (typeof value === 'string') {
        try {
          const parsed = JSON.parse(value)
          displayValue = parsed.value || ''
        } catch {
          displayValue = value
        }
      }
      return {
        key,
        value: displayValue,
        type: typeof value === 'object' ? value.type : 'text'
      }
    })
})

// 获取已选全局变量的预览
const getGlobalVariablePreview = computed(() => {
  if (!selectedGlobalVariable.value || !props.globalParameters) return ''

  const value = props.globalParameters[selectedGlobalVariable.value]
  if (!value) return ''

  if (typeof value === 'object' && value.value) {
    return value.value
  }
  if (typeof value === 'string') {
    // 尝试解析JSON
    try {
      const parsed = JSON.parse(value)
      return parsed.value || value
    } catch {
      return value
    }
  }
  return String(value)
})

// 获取已选全局变量的IP数量
const getGlobalVariableHostCount = computed(() => {
  const preview = getGlobalVariablePreview.value
  if (!preview) return 0

  // 解析IP列表
  const ips = preview
    .split(/[,，\n\r\s]+/)
    .map(ip => ip.trim())
    .filter(ip => ip.length > 0)

  return ips.length
})

// 主机配置警告
const hostWarnings = computed(() => {
  const warnings = []

  // 检查是否没有选择主机（手动模式）
  if (targetSource.value === 'manual') {
    if ((!selectedHosts.value || selectedHosts.value.length === 0) &&
      (!selectedGroups.value || selectedGroups.value.length === 0)) {
      warnings.push({
        type: 'warning',
        message: '未选择目标主机，执行时将无法运行此步骤'
      })
    }
  } else if (targetSource.value === 'global') {
    // 全局变量模式下，检查是否选择了变量
    if (!selectedGlobalVariable.value) {
      warnings.push({
        type: 'warning',
        message: '请选择全局变量作为目标主机来源'
      })
    }
  }

  return warnings
})

// 处理目标主机来源变化
const handleTargetSourceChange = () => {
  if (targetSource.value === 'global') {
    // 切换到全局变量模式时，清空手动选择
    selectedHosts.value = []
    selectedGroups.value = []
  } else {
    // 切换到手动选择模式时，清空全局变量选择
    selectedGlobalVariable.value = ''
  }
}

// 批量参数解析
const parsedBulkParameters = computed(() => {
  if (!bulkParameters.value.trim()) return []

  // 简单的参数解析：支持空格分隔和引号包含空格
  const params: string[] = []
  let current = ''
  let inQuotes = false
  let quoteChar = ''

  for (let i = 0; i < bulkParameters.value.length; i++) {
    const char = bulkParameters.value[i]

    if (!inQuotes && (char === '"' || char === "'")) {
      inQuotes = true
      quoteChar = char
    } else if (inQuotes && char === quoteChar) {
      inQuotes = false
      quoteChar = ''
    } else if (!inQuotes && char === ' ') {
      if (current.trim()) {
        params.push(current.trim())
        current = ''
      }
    } else {
      current += char
    }
  }

  if (current.trim()) {
    params.push(current.trim())
  }

  return params
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

// 获取主机列表（支持分页）
const fetchHosts = async () => {
  try {
    hostLoading.value = true
    const response = await hostApi.getHosts({
      page: hostPagination.value.current,
      page_size: hostPagination.value.pageSize
    })
    hosts.value = response.results || []
    hostPagination.value.total = response.total || 0
  } catch (error) {
    console.error('获取主机列表失败:', error)
  } finally {
    hostLoading.value = false
  }
}

// 处理主机分页变化
const handleHostPageChange = (page: number, pageSize: number) => {
  hostPagination.value.current = page
  hostPagination.value.pageSize = pageSize
  fetchHosts()
}

// 处理主机每页数量变化
const handleHostPageSizeChange = (pageSize: number) => {
  hostPagination.value.pageSize = pageSize
  hostPagination.value.current = 1
  fetchHosts()
}

// 获取主机分组列表
const fetchHostGroups = async () => {
  try {
    groupLoading.value = true
    const response = await hostGroupApi.getGroups({ page_size: 500 })
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
        selectedHosts.value = form.target_hosts as number[]
      }

      // 处理目标分组数据 - 如果是对象数组，提取ID
      if (step.target_groups && Array.isArray(step.target_groups)) {
        form.target_groups = step.target_groups.map(group =>
          typeof group === 'object' && group ? (group as any).id : group
        )
        selectedGroups.value = form.target_groups as number[]
      }

      // 处理全局变量目标主机配置
      if (step.use_global_variable) {
        targetSource.value = 'global'
        selectedGlobalVariable.value = step.target_global_variable || ''
      } else {
        targetSource.value = 'manual'
        selectedGlobalVariable.value = ''
      }

      // 解析脚本和文件传输配置
      if (step.step_type === 'script') {
        scriptType.value = step.script_type || 'shell'
        scriptContent.value = step.script_content || ''
        selectedAccountId.value = step.account_id
      } else if (step.step_type === 'file_transfer') {
      // 解析文件传输配置（支持模板中保存的 file_sources，包括制品与服务器来源）
      remotePath.value = step.remote_path || (step.file_sources && step.file_sources[0]?.remote_path) || ''
      overwritePolicy.value = step.overwrite_policy || 'overwrite'
      maxTargetMatches.value = step.max_target_matches || 100
      selectedAccountId.value = step.account_id
        // populate fileArtifacts for UI display/editing
        fileArtifacts.value = []
        if (step.file_sources && Array.isArray(step.file_sources)) {
          for (const src of step.file_sources) {
            if (src.type === 'server') {
              fileArtifacts.value.push({
                type: 'server',
                server: src.server || src.server_name || '',
                server_id: src.server_id || null,
                source_path: src.source_path || src.download_url || src.storage_path || '',
                account: src.account || src.account_id || '',
                filename: src.filename || src.source_path?.split?.('/')?.pop?.() || '',
                remote_path: src.remote_path || ''
              })
            } else {
              // local / artifact
              fileArtifacts.value.push({
                type: 'local',
                storage_path: src.storage_path,
                download_url: src.download_url,
                checksum: src.checksum || src.sha256,
                size: src.size,
                name: src.filename || src.name,
                remote_path: src.remote_path || ''
              })
            }
          }
        }
      }

      // 解析位置参数 (现在 step_parameters 直接是数组)
      if (step.step_parameters && Array.isArray(step.step_parameters)) {
        const params = step.step_parameters.length > 0 ? step.step_parameters : ['']

        // 如果参数数量超过5个，自动切换到批量模式
        if (params.length > 5) {
          parameterInputMode.value = 'bulk'
          bulkParameters.value = params
            .map(param => param.includes(' ') ? `"${param}"` : param)
            .join(' ')
          positionalArgs.value = [''] // 清空逐个输入
        } else {
          parameterInputMode.value = 'individual'
          positionalArgs.value = params
          bulkParameters.value = '' // 清空批量输入
        }

        // 初始化参数可见性
        parameterVisibility.value = {}
        positionalArgs.value.forEach((_, index) => {
          parameterVisibility.value[index] = true // 默认可见
        })
      } else {
        positionalArgs.value = ['']
        bulkParameters.value = ''
        parameterInputMode.value = 'individual'
        parameterVisibility.value = {}
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
  remotePath.value = ''
  selectedAccountId.value = undefined
  // 清空脚本参数 & 文件相关
  stepFileList.value = []
  fileArtifacts.value = []
  positionalArgs.value = ['']

  // 重置默认值
  if (form.step_type === 'script') {
    scriptType.value = 'shell'
    // 使用 nextTick 确保 DOM 更新后再插入示例代码
    nextTick(() => {
      insertScriptExample()
    })
  } else if (form.step_type === 'file_transfer') {
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

// 处理参数输入模式切换
const handleParameterModeChange = () => {
  if (parameterInputMode.value === 'bulk') {
    // 从逐个输入切换到批量输入时，将现有参数合并到批量输入
    if (positionalArgs.value.some(arg => arg.trim())) {
      bulkParameters.value = positionalArgs.value
        .map(arg => arg.trim() ? (arg.includes(' ') ? `"${arg}"` : arg) : '')
        .filter(arg => arg)
        .join(' ')
    }
  } else {
    // 从批量输入切换到逐个输入时，清空逐个输入的参数
    positionalArgs.value = ['']
    parameterVisibility.value = {}
  }
}

// 处理批量参数输入变化
const handleBulkParametersChange = () => {
  // 当批量参数变化时，同步更新逐个输入模式（如果需要的话）
  // 这里暂时不自动同步，避免混乱
}

// 检查路径是否包含变量
const hasVariables = (path: string) => {
  return path && path.includes('[')
}

// 路径变量预览功能
const previewPath = (path: string) => {
  if (!path) return ''

  const now = new Date()
  const variables = {
    '[date]': now.toISOString().split('T')[0],
    '[time]': now.toTimeString().split(' ')[0].replace(/:/g, '-'),
    '[datetime]': `${now.toISOString().split('T')[0]}_${now.toTimeString().split(' ')[0].replace(/:/g, '-')}`,
    '[timestamp]': Math.floor(now.getTime() / 1000).toString(),
    '[year]': now.getFullYear().toString(),
    '[month]': (now.getMonth() + 1).toString().padStart(2, '0'),
    '[day]': now.getDate().toString().padStart(2, '0'),
    '[hostname]': 'example-host',
  }

  let result = path

  // 处理日期偏移 [date-1], [date+7]
  const offsetPattern = /\[date([+-]\d+)\]/g
  result = result.replace(offsetPattern, (match, offset) => {
    const targetDate = new Date(now)
    targetDate.setDate(targetDate.getDate() + parseInt(offset))
    return targetDate.toISOString().split('T')[0]
  })

  // 替换基础变量
  for (const [variable, value] of Object.entries(variables)) {
    result = result.replace(new RegExp(variable.replace(/[[\]]/g, '\\$&'), 'g'), value)
  }

  return result
}

// 文件大小格式化函数
const formatStepFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 B'

  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))

  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

// 步骤文件操作方法：上传到制品库并维护 artifact 元数据
const handleStepFileChange = async (files: any[]) => {
  // 更新 UI 列表
  stepFileList.value = files

  for (const f of files) {
    const exists = fileArtifacts.value.find(a => a.uid === f.uid || a.name === f.name)
    if (exists) continue
    // placeholder
    fileArtifacts.value.push({ uid: f.uid, name: f.name, uploading: true })
    try {
      const formData = new FormData()
      formData.append('file', f.file || f)
      const resp = await request.post('/agents/artifacts/upload/', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      const data = resp.data || resp
      const idx = fileArtifacts.value.findIndex(x => x.uid === f.uid || x.name === f.name)
      const meta = {
        uid: f.uid,
        name: f.name,
        storage_path: data.content?.storage_path || data.storage_path || data.content?.storage_path,
        download_url: data.content?.download_url || data.download_url || data.content?.download_url,
        checksum: data.content?.checksum || data.checksum || data.content?.checksum,
        size: data.content?.size || data.size || (f.file && f.file.size) || 0,
      }
      if (idx > -1) {
        fileArtifacts.value[idx] = meta
      } else {
        fileArtifacts.value.push(meta)
      }
    } catch (e) {
      console.error('上传制品失败', e)
      Message.error(`文件 ${f.name} 上传制品库失败`)
      fileArtifacts.value = fileArtifacts.value.filter(x => x.uid !== f.uid && x.name !== f.name)
    }
  }
}

const handleStepFileRemove = (fileItem: any) => {
  const remainingFiles = stepFileList.value.filter(f => f.uid !== fileItem.uid)
  stepFileList.value = remainingFiles
  fileArtifacts.value = fileArtifacts.value.filter(a => a.uid !== fileItem.uid && a.name !== fileItem.name)
}

// Read file as base64 string
const readFileAsBase64 = (file: File): Promise<string> => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const result = reader.result as string
      // remove data:*/*;base64, prefix if present
      const idx = result.indexOf('base64,')
      if (idx !== -1) {
        resolve(result.substring(idx + 7))
      } else {
        resolve(result)
      }
    }
    reader.onerror = (e) => reject(e)
    reader.readAsDataURL(file)
  })
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
    let validPositionalArgs: string[] = []
    if (parameterInputMode.value === 'individual') {
      validPositionalArgs = positionalArgs.value.filter(arg => arg.trim() !== '')
    } else {
      // 批量模式：使用解析后的参数
      validPositionalArgs = parsedBulkParameters.value
    }

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
      // 根据目标来源设置
      use_global_variable: targetSource.value === 'global',
      target_global_variable: targetSource.value === 'global' ? selectedGlobalVariable.value : undefined,
      // 手动选择模式下的目标
      target_hosts: targetSource.value === 'manual' ? (selectedHosts.value || []) : [],
      target_groups: targetSource.value === 'manual' ? (selectedGroups.value || []) : []
    }

    // 验证：如果使用全局变量，必须选择变量
    if (targetSource.value === 'global' && !selectedGlobalVariable.value) {
      Message.error('请选择全局变量作为目标主机来源')
      return
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
      if (!remotePath.value.trim()) {
        Message.error('请输入远程路径')
        return
      }
      stepData.remote_path = remotePath.value
      stepData.overwrite_policy = overwritePolicy.value
      stepData.max_target_matches = maxTargetMatches.value
      stepData.account_id = selectedAccountId.value

      // 检查源服务器和目标服务器的agent状态
      const agentStatusWarnings = checkFileTransferAgentStatus(fileArtifacts.value, allTargetHosts.value)
      if (agentStatusWarnings.length > 0) {
        const warningMessages = agentStatusWarnings.map(w => w.message).join('\n')
        const shouldContinue = await Modal.confirm({
          title: 'Agent状态警告',
          content: `发现以下服务器的Agent不在线：\n\n${warningMessages}\n\n是否继续执行？`,
          okText: '继续执行',
          cancelText: '取消',
          okButtonProps: { type: 'primary' },
          cancelButtonProps: { type: 'primary' },
        })
        if (!shouldContinue) {
          return
        }
      }

      // 构建 file_sources：支持本地制品与服务器来源
      const file_sources: any[] = []
      if (!fileArtifacts.value || fileArtifacts.value.length === 0) {
        Message.error('请至少添加一个文件来源（本地或服务器）')
        return
      }
      for (const a of fileArtifacts.value) {
        if (a.type === 'server') {
          if (!a.server && !a.server_id) {
            Message.error(`服务器来源未选择主机或主机无效`)
            return
          }
          if (!a.source_path) {
            Message.error(`服务器来源 ${a.server || a.filename || ''} 缺少源路径`)
            return
          }
          file_sources.push({
            type: 'server',
            server: a.server || undefined,
            server_id: a.server_id || undefined,
            source_path: a.source_path,
            account: a.account || undefined,
            filename: a.filename || a.source_path.split('/').pop(),
            remote_path: a.remote_path || remotePath.value
          })
        } else {
          // artifact / local
          if (!a.storage_path && !a.download_url) {
            Message.error(`文件 ${a.name || a.filename} 尚未上传完成，请稍后`)
            return
          }
          file_sources.push({
            type: 'local',
            storage_path: a.storage_path,
            download_url: a.download_url,
            checksum: a.checksum,
            size: a.size,
            filename: a.name || a.filename,
            remote_path: a.remote_path || remotePath.value
          })
        }
      }
      stepData.file_sources = file_sources
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

// 检查文件传输中源服务器和目标服务器的agent状态
const checkFileTransferAgentStatus = (fileArtifacts: any[], targetHosts: any[]) => {
  const warnings = []

  // 检查源服务器的agent状态
  const sourceServers = fileArtifacts.filter(a => a.type === 'server')
  sourceServers.forEach(source => {
    if (source.server_id) {
      const sourceHost = hosts.value.find(h => h.id === source.server_id)
      if (sourceHost && sourceHost.agent_info && sourceHost.agent_info.status !== 'online') {
        warnings.push({
          type: 'source',
          server: sourceHost.name || sourceHost.ip_address,
          status: sourceHost.agent_info.status_display || sourceHost.agent_info.status,
          message: `源服务器 ${sourceHost.name || sourceHost.ip_address}: Agent ${sourceHost.agent_info.status_display || sourceHost.agent_info.status}`
        })
      }
    }
  })

  // 检查目标服务器的agent状态
  targetHosts.forEach(targetHost => {
    if (targetHost.agent_info && targetHost.agent_info.status !== 'online') {
      warnings.push({
        type: 'target',
        server: targetHost.name || targetHost.ip_address,
        status: targetHost.agent_info.status_display || targetHost.agent_info.status,
        message: `目标服务器 ${targetHost.name || targetHost.ip_address}: Agent ${targetHost.agent_info.status_display || targetHost.agent_info.status}`
      })
    }
  })

  return warnings
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

.parameter-tip {
  display: block;
  width: 100%;
  margin-top: 12px;
  color: var(--color-text-3);
}

/* 参数输入样式 */
.parameter-section {
  border: 1px solid var(--color-border-2);
  border-radius: 6px;
  padding: 16px;
  background: var(--color-bg-1);
}

/* 更宽的参数表单，让输入区域占用更多横向空间 */
.parameter-section {
  width: calc(100% + 20px);
  margin-left: -10px;
  margin-right: -10px;
  box-sizing: border-box;
  max-width: calc(100% + 20px);
}

.parameter-mode-selector {
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--color-border-2);
}

.parameter-individual-mode,
.parameter-bulk-mode {
  margin-top: 16px;
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

.parameter-item-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.parameter-index {
  min-width: 40px;
  text-align: center;
  font-weight: 500;
  color: var(--color-text-2);
  font-family: 'Courier New', monospace;
}

.parameter-input {
  flex: 1;
}

.visibility-toggle,
.remove-btn {
  flex-shrink: 0;
}

.bulk-parameter-preview {
  margin-top: 12px;
  padding: 12px;
  background-color: var(--color-fill-1);
  border: 1px solid var(--color-border-2);
  border-radius: 4px;
}

.preview-header {
  font-size: 12px;
  font-weight: 500;
  color: var(--color-text-2);
  margin-bottom: 8px;
}

.preview-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.preview-param {
  font-size: 12px;
  font-family: 'Courier New', monospace;
  color: var(--color-text-1);
  background-color: var(--color-fill-2);
  padding: 4px 8px;
  border-radius: 4px;
  border: 1px solid var(--color-border-2);
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

/* 目标来源选择器样式 */
.target-source-selector {
  display: flex;
  align-items: center;
  gap: 24px;
  padding: 12px 16px;
  background: var(--color-fill-1);
  border-radius: 6px;
  margin-bottom: 12px;
}

/* 全局变量预览样式 */
.global-variable-preview {
  margin-top: 12px;
  padding: 12px 16px;
  background: var(--color-fill-1);
  border: 1px solid var(--color-border-2);
  border-radius: 6px;
}

.global-variable-preview .preview-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--color-primary);
  margin-bottom: 8px;
}

.global-variable-preview .preview-content {
  font-family: 'Courier New', monospace;
  font-size: 12px;
  color: var(--color-text-1);
  background: #fff;
  padding: 8px 12px;
  border-radius: 4px;
  border: 1px solid var(--color-border-2);
  word-break: break-all;
  max-height: 100px;
  overflow-y: auto;
}

.global-variable-preview .preview-count {
  margin-top: 8px;
  font-size: 12px;
  color: var(--color-text-3);
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

.var-hint {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin: 12px 0;
  padding: 10px 12px;
  border: 1px solid var(--color-border-2);
  border-radius: 6px;
  background: var(--color-fill-1);
  font-size: 13px;
  color: var(--color-text-2);
}
.var-hint.compact {
  margin-top: 8px;
}
.var-hint-icon {
  color: var(--color-primary);
  margin-top: 2px;
}
.var-hint-title {
  font-weight: 600;
  margin-bottom: 4px;
}
.var-hint-body code {
  background: var(--color-fill-3);
  padding: 1px 4px;
  border-radius: 3px;
  font-family: 'Courier New', monospace;
  font-size: 12px;
}

/* 路径变量预览样式 */
.path-preview {
  margin-top: 12px;
  padding: 12px 16px;
  background-color: var(--color-fill-1);
  border: 1px solid var(--color-primary-light-2);
  border-radius: 6px;
}

.path-preview-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--color-primary);
  margin-bottom: 8px;
}

.path-preview-content {
  display: block;
  font-family: 'Courier New', 'Fira Code', monospace;
  font-size: 13px;
  color: var(--color-text-1);
  background-color: #fff;
  padding: 8px 12px;
  border-radius: 4px;
  border: 1px solid var(--color-border-2);
  word-break: break-all;
  line-height: 1.6;
}

/* Agent状态样式 */
.host-agent {
  display: flex;
  align-items: center;
  gap: 3px;
  font-size: 10px;
  padding: 1px 4px;
  border-radius: 2px;
  font-weight: 500;
}

.agent-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  flex-shrink: 0;
}

.agent-dot-online {
  background-color: #52c41a;
  box-shadow: 0 0 0 2px rgba(82, 196, 26, 0.2);
}

.agent-dot-offline {
  background-color: #ff4d4f;
  box-shadow: 0 0 0 2px rgba(255, 77, 79, 0.2);
}

.agent-dot-pending {
  background-color: #ff9800;
  box-shadow: 0 0 0 2px rgba(255, 152, 0, 0.2);
}

.agent-dot-disabled {
  background-color: #d9d9d9;
  box-shadow: 0 0 0 2px rgba(217, 217, 217, 0.2);
}

.agent-online {
  background-color: var(--color-success-light-1);
  color: var(--color-success);
}

.agent-offline {
  background-color: var(--color-danger-light-1);
  color: var(--color-danger);
}

.agent-pending {
  background-color: var(--color-warning-light-1);
  color: var(--color-warning);
}

.agent-disabled {
  background-color: var(--color-fill-3);
  color: var(--color-text-3);
}

.agent-none {
  background-color: var(--color-fill-2);
  color: var(--color-text-3);
  font-size: 10px;
}
</style>
