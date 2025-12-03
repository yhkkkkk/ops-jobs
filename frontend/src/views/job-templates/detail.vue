<template>
  <div class="template-detail">
    <a-page-header
      :title="template?.name || '模板详情'"
      @back="handleBack"
    >
      <template #subtitle>
        <a-space>
          <a-tag v-if="template?.category" color="blue">{{ template.category }}</a-tag>
          <span class="text-gray-500">创建于 {{ formatDate(template?.created_at) }}</span>
        </a-space>
      </template>

      <template #extra>
        <a-space>
          <a-button type="outline" @click="handleRefresh">
            <template #icon>
              <icon-refresh />
            </template>
            刷新
          </a-button>
          <a-button type="outline" @click="handleEdit">
            <template #icon>
              <icon-edit />
            </template>
            编辑
          </a-button>
          <a-button type="outline" @click="handleCopy">
            <template #icon>
              <icon-copy />
            </template>
            复制
          </a-button>
          <a-button type="primary" @click="handleDebugExecute">
            <template #icon>
              <icon-play-arrow />
            </template>
            调试执行
          </a-button>
        </a-space>
      </template>
    </a-page-header>

    <div class="detail-content" v-if="template">
      <a-row :gutter="24">
        <!-- 基本信息 -->
        <a-col :span="8">
          <a-card title="基本信息" class="mb-4">
            <a-descriptions :column="1" bordered>
              <a-descriptions-item label="模板名称">
                {{ template.name }}
              </a-descriptions-item>
              <a-descriptions-item label="分类">
                {{ template.category || '未分类' }}
              </a-descriptions-item>
              <a-descriptions-item label="标签">
                <a-space v-if="template.tag_list && template.tag_list.length > 0">
                  <a-tag
                    v-for="tag in template.tag_list"
                    :key="`${tag.key}-${tag.value}`"
                    size="small"
                  >
                    <strong>{{ tag.key }}:</strong> {{ tag.value }}
                  </a-tag>
                </a-space>
                <span v-else class="text-gray-400">无标签</span>
              </a-descriptions-item>
              <a-descriptions-item label="创建人">
                {{ template.created_by_name }}
              </a-descriptions-item>
              <a-descriptions-item label="创建时间">
                {{ formatDate(template.created_at) }}
              </a-descriptions-item>
              <a-descriptions-item label="更新时间">
                {{ formatDate(template.updated_at) }}
              </a-descriptions-item>
              <a-descriptions-item label="步骤数量">
                {{ template.step_count }}
              </a-descriptions-item>
              <a-descriptions-item label="执行方案数量">
                {{ template.plan_count }}
              </a-descriptions-item>
            </a-descriptions>

            <div v-if="template.description" class="mt-4">
              <h4 class="description-title">描述</h4>
              <p class="description-text">{{ template.description }}</p>
            </div>

            <!-- 全局变量 -->
            <div v-if="template.global_parameters && Object.keys(template.global_parameters).length > 0" class="global-variables-section">
              <h4 class="section-title">全局变量</h4>
              <div class="global-variables-container">
                <div
                  v-for="(value, key) in template.global_parameters"
                  :key="key"
                  class="variable-item"
                >
                  <div class="variable-key">{{ key }}</div>
                  <div class="variable-value">{{ formatGlobalParameterValue(value) }}</div>
                </div>
              </div>
            </div>
          </a-card>
        </a-col>

        <!-- 作业步骤 -->
        <a-col :span="16">
          <a-card title="作业步骤">
            <div v-if="template.steps && template.steps.length > 0">
              <div
                v-for="(step, index) in template.steps"
                :key="step.id || index"
                class="step-item"
              >
                <div class="step-header">
                  <div class="step-number">{{ index + 1 }}</div>
                  <div class="step-info">
                    <h4>{{ step.name }}</h4>
                    <a-space>
                      <a-tag :color="getStepTypeColor(step.step_type)">
                        {{ getStepTypeName(step.step_type) }}
                      </a-tag>
                      <span class="text-gray-500">超时: {{ step.timeout || 300 }}秒</span>
                      <a-tag v-if="step.ignore_error" color="orange">忽略错误</a-tag>
                    </a-space>
                    <!-- 目标主机信息 -->
                    <div v-if="step.target_hosts && step.target_hosts.length > 0" class="target-hosts">
                      <div class="target-hosts-label">目标主机:</div>
                      <a-space wrap>
                        <a-tag
                          v-for="host in step.target_hosts"
                          :key="host.id"
                          color="cyan"
                          size="small"
                        >
                          {{ host.name }} ({{ host.ip_address }})
                        </a-tag>
                      </a-space>
                    </div>
                    <!-- 目标分组信息 -->
                    <div v-if="step.target_groups && step.target_groups.length > 0" class="target-hosts">
                      <div class="target-hosts-label">目标分组:</div>
                      <a-space wrap>
                        <a-tag
                          v-for="group in step.target_groups"
                          :key="group.id"
                          color="blue"
                          size="small"
                        >
                          {{ group.name }} ({{ group.host_count }}台主机)
                        </a-tag>
                      </a-space>
                    </div>
                  </div>
                </div>

                <div class="step-content">
                  <!-- 脚本步骤 -->
                  <div v-if="step.step_type === 'script'" class="script-content">
                    <div class="script-info">
                      <div class="script-meta">
                        <a-space>
                          <a-tag color="blue">{{ getScriptTypeName(step.script_type) }}</a-tag>
                          <span v-if="step.account_id">
                            执行账号: {{ step.account_name || `ID: ${step.account_id}` }}
                          </span>
                          <span class="script-lines">
                            {{ (step.script_content?.split('\n').length || 0) }} 行
                          </span>
                        </a-space>
                      </div>
                      <div class="script-actions">
                        <a-space>
                          <a-button
                            type="text"
                            size="small"
                            @click="copyScriptContent(step.script_content)"
                          >
                            <template #icon>
                              <icon-copy />
                            </template>
                            复制脚本
                          </a-button>
                          <a-button
                            type="text"
                            size="small"
                            @click="toggleScriptExpand(index)"
                          >
                            <template #icon>
                              <icon-down v-if="!expandedScripts.has(index)" />
                              <icon-up v-else />
                            </template>
                            {{ expandedScripts.has(index) ? '收起' : '展开' }}
                          </a-button>
                        </a-space>
                      </div>
                    </div>

                    <!-- 脚本预览（收起状态） -->
                    <div v-if="!expandedScripts.has(index)" class="script-preview">
                      <div class="script-preview-content">
                        {{ getScriptPreview(step.script_content) }}
                      </div>
                      <div class="script-preview-fade"></div>
                    </div>

                    <!-- 完整脚本（展开状态） -->
                    <div v-else class="script-code">
                      <simple-monaco-editor
                        :model-value="step.script_content || '# 无脚本内容'"
                        :language="getMonacoLanguage(step.script_type)"
                        :height="Math.min(500, Math.max(200, (step.script_content?.split('\n').length || 1) * 20 + 40))"
                        :readonly="true"
                        theme="vs"
                        :options="{
                          minimap: { enabled: false },
                          scrollBeyondLastLine: false,
                          wordWrap: 'on',
                          lineNumbers: 'on',
                          folding: true,
                          selectOnLineNumbers: true,
                          automaticLayout: true
                        }"
                      />
                    </div>

                    <!-- 位置参数 -->
                    <div v-if="getPositionalArgs(step).length > 0" class="positional-args-section">
                      <h4>位置参数</h4>
                      <div class="positional-args">
                        <div
                          v-for="(arg, argIndex) in getPositionalArgs(step)"
                          :key="argIndex"
                          class="positional-arg-item"
                        >
                          <span class="arg-index">${{ argIndex + 1 }}</span>
                          <span class="arg-value">{{ arg }}</span>
                        </div>
                      </div>
                    </div>
                  </div>

                  <!-- 文件传输步骤 -->
                  <div v-else-if="step.step_type === 'file_transfer'" class="file-transfer-content">
                    <a-descriptions :column="2" size="small">
                      <a-descriptions-item label="传输类型">
                        {{ step.transfer_type === 'upload' ? '上传' : '下载' }}
                      </a-descriptions-item>
                      <a-descriptions-item label="本地路径">
                        {{ step.local_path || '-' }}
                      </a-descriptions-item>
                      <a-descriptions-item label="远程路径">
                        {{ step.remote_path || '-' }}
                      </a-descriptions-item>
                      <a-descriptions-item label="覆盖策略">
                        {{ getOverwritePolicyName(step.overwrite_policy) }}
                      </a-descriptions-item>
                    </a-descriptions>
                  </div>
                </div>
              </div>
            </div>
            <a-empty v-else description="暂无步骤" />
          </a-card>
        </a-col>
      </a-row>
    </div>

    <div v-else class="loading-container">
      <a-spin size="large" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import { IconEdit, IconCopy, IconPlayArrow, IconDown, IconUp, IconRefresh } from '@arco-design/web-vue/es/icon'
import { jobTemplateApi } from '@/api/ops'
import type { JobTemplate } from '@/types'
import SimpleMonacoEditor from '@/components/SimpleMonacoEditor.vue'

const router = useRouter()
const route = useRoute()

// 响应式数据
const template = ref<JobTemplate | null>(null)
const loading = ref(false)
const expandedScripts = ref(new Set<number>())

// 获取模板详情
const fetchTemplate = async () => {
  try {
    loading.value = true
    const id = Number(route.params.id)
    const response = await jobTemplateApi.getTemplate(id)
    template.value = response
  } catch (error) {
    console.error('获取模板详情失败:', error)
    Message.error('获取模板详情失败')
  } finally {
    loading.value = false
  }
}

// 格式化日期
const formatDate = (dateString?: string) => {
  if (!dateString) return '-'
  return new Date(dateString).toLocaleString('zh-CN')
}

// 获取步骤类型名称
const getStepTypeName = (type: string) => {
  const typeMap: Record<string, string> = {
    script: '脚本执行',
    file_transfer: '文件传输'
  }
  return typeMap[type] || type
}

// 获取步骤类型颜色
const getStepTypeColor = (type: string) => {
  const colorMap: Record<string, string> = {
    script: 'blue',
    file_transfer: 'green'
  }
  return colorMap[type] || 'gray'
}

// 获取覆盖策略名称
const getOverwritePolicyName = (policy?: string) => {
  const policyMap: Record<string, string> = {
    overwrite: '覆盖',
    skip: '跳过',
    backup: '备份'
  }
  return policyMap[policy || 'overwrite'] || policy || '覆盖'
}

// 获取脚本类型名称
const getScriptTypeName = (type?: string) => {
  const typeMap: Record<string, string> = {
    shell: 'Shell脚本',
    bash: 'Bash脚本',
    python: 'Python脚本',
    powershell: 'PowerShell脚本',
    bat: 'Batch脚本'
  }
  return typeMap[type || 'shell'] || type || 'Shell脚本'
}

// 获取位置参数
const getPositionalArgs = (step: any) => {
  if (step.step_parameters && Array.isArray(step.step_parameters)) {
    return step.step_parameters.filter((arg: string) => arg.trim() !== '')
  }
  return []
}

// 获取Monaco编辑器语言
const getMonacoLanguage = (type?: string) => {
  const languageMap: Record<string, string> = {
    shell: 'shell',
    bash: 'shell',
    python: 'python',
    powershell: 'powershell',
    bat: 'bat'
  }
  return languageMap[type || 'shell'] || 'shell'
}

// 复制脚本内容
const copyScriptContent = async (content?: string) => {
  if (!content) {
    Message.warning('无脚本内容可复制')
    return
  }

  try {
    await navigator.clipboard.writeText(content)
    Message.success('脚本内容已复制到剪贴板')
  } catch (error) {
    console.error('复制失败:', error)
    Message.error('复制失败，请手动选择复制')
  }
}

// 切换脚本展开状态
const toggleScriptExpand = (stepIndex: number) => {
  if (expandedScripts.value.has(stepIndex)) {
    expandedScripts.value.delete(stepIndex)
  } else {
    expandedScripts.value.add(stepIndex)
  }
}

// 获取脚本预览内容
const getScriptPreview = (content?: string) => {
  if (!content) return '# 无脚本内容'

  const lines = content.split('\n')
  const previewLines = lines.slice(0, 3) // 显示前3行
  let preview = previewLines.join('\n')

  if (lines.length > 3) {
    preview += '\n...'
  }

  return preview
}

// 全局变量展示：对密文参数做掩码处理
const formatGlobalParameterValue = (rawValue: any) => {
  // 兼容老格式：直接是字符串
  if (rawValue === null || rawValue === undefined) return ''
  if (typeof rawValue === 'string' || typeof rawValue === 'number' || typeof rawValue === 'boolean') {
    return String(rawValue)
  }

  // 新格式：{ value, type, description }
  const value = rawValue?.value
  const type = rawValue?.type

  if (type === 'secret') {
    // 密文统一显示为掩码
    return '******'
  }

  return value !== undefined ? String(value) : ''
}

// 操作方法
// 无论从哪里进入详情，都统一返回到作业模板列表
const handleBack = () => {
  router.push('/job-templates')
}

const handleEdit = () => {
  router.push(`/job-templates/${template.value?.id}/edit`)
}

const handleCopy = () => {
  if (!template.value) return

  // 创建复制的模板数据
  const copiedTemplate = {
    name: `${template.value.name}_副本`,
    description: template.value.description,
    category: template.value.category,
    tags: template.value.tag_list || [],
    steps: template.value.steps || []
  }

  // 将复制数据存储到sessionStorage
  sessionStorage.setItem('copyTemplateData', JSON.stringify(copiedTemplate))

  // 跳转到编辑器页面
  router.push('/job-templates/create?action=copy')
  Message.success('模板数据已复制，请修改模板名称后保存')
}

const handleDebugExecute = async () => {
  if (!template.value) return

  try {
    Message.loading('正在启动调试执行...', { duration: 0, id: 'debug-loading' })

    const result = await jobTemplateApi.debugTemplate(template.value.id, {
      execution_parameters: {},
      execution_mode: 'parallel',
      rolling_batch_size: 1,
      rolling_batch_delay: 0
    })

    Message.clear('debug-loading')
    Message.success('调试执行已启动！')

    // 跳转到执行记录页面查看结果
    router.push(`/execution-records/${result.execution_id}`)

  } catch (error: any) {
    Message.clear('debug-loading')
    console.error('调试执行失败:', error)
    Message.error(error.response?.data?.message || '调试执行失败')
  }
}

// 刷新模板详情
const handleRefresh = () => {
  fetchTemplate()
}

// 生命周期
onMounted(() => {
  fetchTemplate()
})
</script>

<style scoped>
.template-detail {
  padding: 0;
}

.detail-content {
  padding: 0 24px 24px;
}

.loading-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 400px;
}

.step-item {
  border: 1px solid #e5e6eb;
  border-radius: 6px;
  margin-bottom: 16px;
  overflow: hidden;
}

.step-header {
  display: flex;
  align-items: flex-start;
  padding: 16px;
  background: #f7f8fa;
  border-bottom: 1px solid #e5e6eb;
}

.step-number {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: #165dff;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  margin-right: 12px;
  flex-shrink: 0;
}

.step-info {
  flex: 1;
}

.step-info h4 {
  margin: 0 0 8px 0;
  font-size: 16px;
  font-weight: 600;
}

.step-content {
  padding: 16px;
}

.script-info {
  margin-bottom: 12px;
  padding: 12px 16px;
  background: #f7f8fa;
  border-radius: 6px;
  border: 1px solid #e5e6eb;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.script-meta {
  flex: 1;
}

.script-lines {
  color: #86909c;
  font-size: 12px;
}

.script-actions {
  flex-shrink: 0;
}

.script-preview {
  position: relative;
  margin-bottom: 12px;
  border: 1px solid #e5e6eb;
  border-radius: 6px;
  background: #fafbfc;
  overflow: hidden;
}

.script-preview-content {
  padding: 12px 16px;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 13px;
  line-height: 1.5;
  color: #4e5969;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 80px;
  overflow: hidden;
}

.script-preview-fade {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 20px;
  background: linear-gradient(transparent, #fafbfc);
  pointer-events: none;
}

.script-code {
  border: 1px solid #e5e6eb;
  border-radius: 6px;
  overflow: hidden;
  background: white;
}

.file-transfer-content {
  background: #f7f8fa;
  border-radius: 4px;
  padding: 12px;
}

/* 全局变量样式 */
.global-variables-section {
  margin-top: 24px;
}

.mt-4 {
  margin-top: 16px;
}

.section-title {
  margin: 0 0 12px 0;
  font-size: 14px;
  font-weight: 600;
  color: #1d2129;
}

.global-variables-container {
  display: flex;
  flex-direction: column;
  gap: 8px;
  background: #f7f8fa;
  border: 1px solid #e5e6eb;
  border-radius: 6px;
  padding: 12px;
}

.variable-item {
  display: flex;
  align-items: center;
  padding: 8px 12px;
  background: white;
  border-radius: 4px;
  border: 1px solid #e5e6eb;
  transition: all 0.2s ease;
}

.variable-item:hover {
  border-color: #165dff;
  box-shadow: 0 2px 4px rgba(22, 93, 255, 0.1);
}

.variable-key {
  font-weight: 500;
  color: #1d2129;
  margin-right: 12px;
  min-width: 100px;
  font-size: 13px;
}

.variable-key::after {
  content: ':';
  margin-left: 2px;
  color: #86909c;
}

.variable-value {
  color: #4e5969;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 13px;
  background: #f2f3f5;
  padding: 4px 8px;
  border-radius: 3px;
  flex: 1;
  word-break: break-all;
}

/* 位置参数样式 */
.positional-args-section {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #e5e6eb;
}

.positional-args-section h4 {
  margin: 0 0 12px 0;
  font-size: 14px;
  font-weight: 600;
  color: #1d2129;
}

.positional-args {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.positional-arg-item {
  display: flex;
  align-items: center;
  padding: 8px 12px;
  background: #f7f8fa;
  border-radius: 4px;
  border: 1px solid #e5e6eb;
  transition: all 0.2s ease;
}

.positional-arg-item:hover {
  border-color: #165dff;
  background: #f2f3ff;
}

.arg-index {
  font-weight: 600;
  color: #165dff;
  margin-right: 12px;
  min-width: 40px;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 13px;
  background: #e8f3ff;
  padding: 2px 6px;
  border-radius: 3px;
}

.arg-value {
  color: #1d2129;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 13px;
  flex: 1;
  word-break: break-all;
}

/* 目标主机样式 */
.target-hosts {
  margin-top: 8px;
  padding: 8px 0;
}

.target-hosts-label {
  font-size: 12px;
  color: #86909c;
  margin-bottom: 4px;
}

.description-title {
  margin-bottom: 8px; /* 增加标题和描述文本之间的间距 */
}

.description-text {
  color: #4e5969; /* 设置一个柔和的灰色 */
  line-height: 1.6; /* 增加行高以提高可读性 */
}
</style>
