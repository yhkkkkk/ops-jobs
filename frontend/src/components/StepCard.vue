<template>
  <div class="step-card" :class="{ 'is-selected': selected }">
    <div class="step-card-header">
      <slot name="prefix"></slot>
      <div class="step-number">{{ index + 1 }}</div>
      <div class="step-info">
        <div class="step-title-row">
          <span class="step-name">{{ stepName }}</span>
          <n-tag size="small" :type="stepTypeTagType">{{ stepTypeName }}</n-tag>
          <span v-if="timeout !== undefined" class="step-meta">超时: {{ timeout }}秒</span>
          <n-tag v-if="ignoreError" size="small" type="warning">忽略错误</n-tag>
          <span v-if="hasCondition" class="step-meta">有执行条件</span>
        </div>
        <div class="step-desc">{{ stepDescription }}</div>
      </div>
      <div class="step-actions">
        <n-button
          v-if="collapsible"
          text
          size="small"
          @click.stop="toggleExpanded"
        >
          <template #icon>
            <ChevronDown v-if="!isExpanded" />
            <ChevronUp v-else />
          </template>
          {{ isExpanded ? '收起' : '查看详情' }}
        </n-button>
        <slot name="actions"></slot>
      </div>
    </div>

    <div v-if="isExpanded" class="step-card-body">
      <div v-if="stepType === 'script'" class="script-content">
        <div class="script-info">
          <div class="script-meta">
            <n-space :size="8" align="center">
              <n-tag size="small" type="info">{{ scriptTypeName }}</n-tag>
              <span v-if="accountDisplay">执行账号: {{ accountDisplay }}</span>
              <span class="script-lines">{{ scriptLineCount }} 行</span>
            </n-space>
          </div>
          <div class="script-actions">
            <n-space :size="8">
              <n-button text size="small" @click="copyScriptContent(scriptContent)">
                <template #icon>
                  <Copy :size="14" />
                </template>
                复制脚本
              </n-button>
              <n-button text size="small" @click="toggleScriptExpand">
                <template #icon>
                  <ChevronDown v-if="!scriptExpanded" />
                  <ChevronUp v-else />
                </template>
                {{ scriptExpanded ? '收起' : '展开' }}
              </n-button>
            </n-space>
          </div>
        </div>

        <div v-if="!scriptExpanded" class="script-preview">
          <div class="script-preview-content">
            {{ scriptPreview }}
          </div>
          <div class="script-preview-fade"></div>
        </div>

        <div v-else class="script-code">
          <simple-monaco-editor
            :model-value="scriptContent || '# 无脚本内容'"
            :language="scriptLanguage"
            :height="editorHeight"
            :readonly="true"
            theme="vs-dark"
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

        <div v-if="positionalArgs.length > 0" class="positional-args-section">
          <h4>位置参数</h4>
          <div class="positional-args">
            <div
              v-for="(arg, argIndex) in positionalArgs"
              :key="argIndex"
              class="positional-arg-item"
            >
              <span class="arg-index">{{ Number(argIndex) + 1 }}</span>
              <span class="arg-value">{{ arg }}</span>
            </div>
          </div>
        </div>
      </div>

      <div v-else-if="stepType === 'file_transfer'" class="file-transfer-content">
        <n-descriptions :column="2" size="small" label-placement="left">
          <n-descriptions-item label="覆盖策略">
            {{ overwritePolicyName }}
          </n-descriptions-item>
          <n-descriptions-item label="执行账号">
            {{ accountDisplay || '-' }}
          </n-descriptions-item>
          <n-descriptions-item v-if="fileSources.length > 0" label="文件来源">
            <div class="file-sources">
              <div v-for="(src, si) in fileSources" :key="si" class="file-source-row">
                <n-tag size="small" :type="getFileSourceTagType(src)">
                  {{ getFileSourceLabel(src) }}
                </n-tag>
                <div class="file-source-main">
                  <div class="file-source-title">
                    {{ getFileSourceTitle(src) }}
                  </div>
                  <div class="file-source-meta">
                    <span v-if="src.account_name">账号: {{ src.account_name }} · </span>
                    目标路径: {{ src.remote_path || '-' }}
                    <span v-if="src.size"> · {{ formatSize(src.size) }}</span>
                    <span v-if="src.checksum || src.sha256"> · sha256: {{ String(src.checksum || src.sha256).substr(0, 12) }}...</span>
                  </div>
                </div>
                <n-space :size="8">
                  <n-button
                    v-if="src.download_url"
                    text
                    size="small"
                    @click="openExternal(src.download_url)"
                  >下载</n-button>
                  <n-button
                    v-if="src.download_url"
                    text
                    size="small"
                    @click="copyToClipboard(src.download_url)"
                  >复制链接</n-button>
                </n-space>
              </div>
            </div>
          </n-descriptions-item>
          <n-descriptions-item v-else label="文件来源">
            <n-empty description="未配置文件来源" size="small" />
          </n-descriptions-item>
        </n-descriptions>
      </div>

      <div v-if="hasTargets" class="step-targets">
        <div v-if="targetHosts.length" class="target-group">
          <div class="target-label">目标主机</div>
          <n-space wrap :size="8">
            <n-tag
              v-for="host in targetHosts"
              :key="getItemKey(host)"
              type="info"
              size="small"
            >
              {{ formatHostLabel(host) }}
            </n-tag>
          </n-space>
        </div>
        <div v-if="targetGroups.length" class="target-group">
          <div class="target-label">目标分组</div>
          <n-space wrap :size="8">
            <n-tag
              v-for="group in targetGroups"
              :key="getItemKey(group)"
              type="primary"
              size="small"
            >
              {{ formatGroupLabel(group) }}
            </n-tag>
          </n-space>
        </div>
      </div>

      <div v-if="overrideParameterEntries.length > 0" class="override-params">
        <h4>覆盖参数</h4>
        <div class="parameters">
          <div
            v-for="([key, value]) in overrideParameterEntries"
            :key="key"
            class="parameter-item override"
          >
            <span class="param-key">{{ key }}:</span>
            <span class="param-value">{{ value }}</span>
          </div>
        </div>
      </div>
    </div>

    <div v-if="$slots.footer" class="step-card-footer">
      <slot name="footer"></slot>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { NButton, NDescriptions, NDescriptionsItem, NEmpty, NSpace, NTag, useMessage } from 'naive-ui'
import { ChevronDown, ChevronUp, Copy } from 'lucide-vue-next'
import SimpleMonacoEditor from '@/components/SimpleMonacoEditor.vue'

const message = useMessage()

const props = defineProps({
  step: {
    type: Object,
    required: true,
  },
  index: {
    type: Number,
    default: 0,
  },
  selected: {
    type: Boolean,
    default: false,
  },
  showDetail: {
    type: Boolean,
    default: true,
  },
  defaultExpanded: {
    type: Boolean,
    default: false,
  },
  collapsible: {
    type: Boolean,
    default: false,
  }
})

const scriptExpanded = ref(props.defaultExpanded)
const expanded = ref(props.defaultExpanded)

const isExpanded = computed(() => {
  if (props.collapsible) {
    return expanded.value
  }
  return props.showDetail
})

const stepType = computed(() => props.step.step_type || '')
const stepName = computed(() => props.step.name || props.step.step_name || '未命名步骤')
const stepDescription = computed(() => props.step.description || props.step.step_description || '无描述')
const timeout = computed(() => {
  const value = props.step.timeout ?? props.step.step_timeout ?? props.step.effective_timeout
  return typeof value === 'number' ? value : undefined
})
const ignoreError = computed(() => props.step.ignore_error ?? props.step.step_ignore_error ?? false)
const hasCondition = computed(() => !!props.step.condition)

const stepTypeName = computed(() => {
  const typeMap: Record<string, string> = {
    script: '脚本执行',
    file_transfer: '文件传输'
  }
  return typeMap[stepType.value] || stepType.value || '未知类型'
})

const stepTypeTagType = computed<'default' | 'info' | 'success'>(() => {
  const colorMap: Record<string, 'default' | 'info' | 'success'> = {
    script: 'info',
    file_transfer: 'success'
  }
  return colorMap[stepType.value] || 'default'
})

const scriptType = computed(() => props.step.script_type || props.step.step_script_type || 'shell')
const scriptContent = computed(() => props.step.script_content || props.step.step_script_content || '')
const scriptLineCount = computed(() => {
  const content = scriptContent.value || ''
  return content ? content.split('\n').length : 0
})

const scriptTypeName = computed(() => {
  const typeMap: Record<string, string> = {
    shell: 'Shell脚本',
    bash: 'Bash脚本',
    python: 'Python脚本',
    perl: 'Perl脚本',
    powershell: 'PowerShell脚本',
    javascript: 'JavaScript脚本',
    go: 'Go脚本'
  }
  return typeMap[scriptType.value] || scriptType.value || 'Shell脚本'
})

const scriptLanguage = computed(() => {
  const languageMap: Record<string, string> = {
    shell: 'shell',
    bash: 'shell',
    python: 'python',
    perl: 'perl',
    powershell: 'powershell',
    bat: 'bat',
    javascript: 'javascript',
    js: 'javascript',
    node: 'javascript',
    go: 'go'
  }
  return languageMap[scriptType.value] || 'shell'
})

const accountDisplay = computed(() => {
  const name = props.step.account_name || props.step.step_account_name
  const id = props.step.account_id || props.step.step_account_id
  if (name) return name
  if (id !== undefined && id !== null) return `ID: ${id}`
  return ''
})

const positionalArgs = computed(() => {
  if (Array.isArray(props.step.effective_parameters)) {
    return props.step.effective_parameters.filter((arg: string) => String(arg).trim() !== '')
  }
  if (Array.isArray(props.step.step_parameters)) {
    return props.step.step_parameters.filter((arg: string) => String(arg).trim() !== '')
  }
  return []
})

const targetHosts = computed(() => (Array.isArray(props.step.target_hosts) ? props.step.target_hosts : []))
const targetGroups = computed(() => (Array.isArray(props.step.target_groups) ? props.step.target_groups : []))
const fileSources = computed(() => (Array.isArray(props.step.file_sources) ? props.step.file_sources : (Array.isArray(props.step.step_file_sources) ? props.step.step_file_sources : [])))

const hasTargets = computed(() => targetHosts.value.length > 0 || targetGroups.value.length > 0)

const overwritePolicyName = computed(() => {
  const policy = props.step.overwrite_policy || props.step.step_overwrite_policy || 'overwrite'
  const policyMap: Record<string, string> = {
    overwrite: '覆盖',
    skip: '跳过',
    backup: '备份'
  }
  return policyMap[policy] || policy
})

const overrideParameterEntries = computed(() => {
  if (!props.step.override_parameters || typeof props.step.override_parameters !== 'object') {
    return [] as Array<[string, any]>
  }
  return Object.entries(props.step.override_parameters)
})

const editorHeight = computed(() => {
  const lines = scriptLineCount.value || 1
  return Math.min(800, Math.max(240, lines * 20 + 40))
})

const scriptPreview = computed(() => {
  if (!scriptContent.value) return '# 无脚本内容'
  const lines = scriptContent.value.split('\n')
  const previewLines = lines.slice(0, 4)
  let preview = previewLines.join('\n')
  if (lines.length > 4) {
    preview += '\n...'
  }
  return preview
})

const toggleScriptExpand = () => {
  scriptExpanded.value = !scriptExpanded.value
}

const toggleExpanded = () => {
  if (!props.collapsible) return
  expanded.value = !expanded.value
}

const copyScriptContent = async (content?: string) => {
  if (!content) {
    message.warning('无脚本内容可复制')
    return
  }
  try {
    await navigator.clipboard.writeText(content)
    message.success('脚本内容已复制到剪贴板')
  } catch (error) {
    message.error('复制失败，请手动选择复制')
  }
}

const getItemKey = (item: any) => {
  if (item && typeof item === 'object') {
    return item.id ?? item.name ?? JSON.stringify(item)
  }
  return String(item)
}

const formatHostLabel = (host: any) => {
  if (host && typeof host === 'object') {
    const ip = host.ip_address || host.ip || host.ipAddress || ''
    const name = host.name || host.hostname || ''
    if (name && ip) return `${name} (${ip})`
    if (ip) return ip
    if (name) return name
    return '未知主机'
  }
  return `ID: ${host}`
}

const formatGroupLabel = (group: any) => {
  if (group && typeof group === 'object') {
    const count = group.host_count ?? group.count
    if (count !== undefined && count !== null) {
      return `${group.name} (${count}台主机)`
    }
    return group.name || '未知分组'
  }
  return `ID: ${group}`
}

const getFileSourceTagType = (src: any) => {
  if (src.type === 'server') return 'warning'
  if (src.type === 'local') return 'info'
  return 'default'
}

const getFileSourceLabel = (src: any) => {
  if (src.type === 'server') return '服务器'
  if (src.type === 'local') return '本地'
  return '制品库'
}

const getFileSourceTitle = (src: any) => {
  if (src.type === 'server') {
    return `${src.server_name || src.server || (src.server_id ? `ID:${String(src.server_id)}` : '-')}`
      + ` · ${src.source_path || src.path || '-'}`
  }
  return src.filename || src.name || src.storage_path || src.download_url || '-'
}

const openExternal = (url?: string) => {
  if (url) {
    window.open(url, '_blank')
  }
}

const copyToClipboard = async (text?: string) => {
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
    message.success('已复制链接到剪贴板')
  } catch (error) {
    message.error('复制失败')
  }
}

const formatSize = (bytes?: number) => {
  if (!bytes && bytes !== 0) return '-'
  const kb = 1024
  if (bytes < kb) return bytes + ' B'
  const mb = kb * kb
  if (bytes < mb) return (bytes / kb).toFixed(2) + ' KB'
  return (bytes / mb).toFixed(2) + ' MB'
}
</script>

<style scoped>
.step-card {
  border: 1px solid var(--app-border);
  border-radius: 6px;
  background: var(--app-surface);
  overflow: hidden;
}

.step-card.is-selected {
  border-color: var(--app-accent);
  box-shadow: 0 0 0 1px var(--app-accent-soft);
}

.step-card-header {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px 16px;
  background: var(--app-surface);
  border-bottom: 1px solid var(--app-border);
}

.step-number {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--app-accent-soft);
  color: var(--app-accent);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 12px;
  flex-shrink: 0;
}

.step-info {
  flex: 1;
  min-width: 0;
}

.step-title-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.step-name {
  font-size: 16px;
  font-weight: 600;
  color: var(--app-fg);
}

.step-meta {
  font-size: 12px;
  color: var(--app-muted);
}

.step-desc {
  margin-top: 6px;
  color: var(--app-fg-secondary);
  font-size: 13px;
  word-break: break-word;
}

.step-targets {
  margin-bottom: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.target-label {
  font-size: 12px;
  color: var(--app-muted);
  margin-bottom: 4px;
}

.step-actions {
  flex-shrink: 0;
}

.step-card-body {
  padding: 16px;
}

.script-info {
  margin-bottom: 12px;
  padding: 12px 16px;
  background: var(--app-bg);
  border-radius: 6px;
  border: 1px solid var(--app-border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.script-meta {
  flex: 1;
}

.script-lines {
  color: var(--app-muted);
  font-size: 12px;
}

.script-preview {
  position: relative;
  margin-bottom: 12px;
  border: 1px solid #1f2329;
  border-radius: 6px;
  background: #1f2329;
  overflow: hidden;
}

.script-preview-content {
  padding: 12px 16px;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 13px;
  line-height: 1.5;
  color: #c9d1d9;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 100px;
  overflow: hidden;
}

.script-preview-fade {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 20px;
  background: linear-gradient(transparent, #1f2329);
  pointer-events: none;
}

.script-code {
  border: 1px solid #2b3138;
  border-radius: 6px;
  overflow: hidden;
  background: #1f2329;
}

.file-transfer-content {
  background: var(--app-bg);
  border-radius: 4px;
  padding: 12px;
}

.file-sources {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.file-source-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.file-source-main {
  flex: 1;
  min-width: 0;
}

.file-source-title {
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.file-source-meta {
  font-size: 12px;
  color: var(--app-muted);
}

.positional-args-section {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--app-border);
}

.positional-args-section h4 {
  margin: 0 0 12px 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--app-fg);
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
  background: var(--app-bg);
  border-radius: 4px;
  border: 1px solid var(--app-border);
}

.arg-index {
  font-weight: 600;
  color: var(--app-accent);
  margin-right: 12px;
  min-width: 40px;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 13px;
  background: var(--app-accent-soft);
  padding: 2px 6px;
  border-radius: 3px;
}

.arg-value {
  color: var(--app-fg);
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 13px;
  flex: 1;
  word-break: break-all;
}

.override-params {
  margin-top: 16px;
}

.override-params h4 {
  margin: 0 0 8px 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--app-fg);
}

.parameters {
  display: flex;
  flex-direction: column;
  gap: 8px;
  background: var(--app-bg);
  padding: 12px;
  border-radius: 4px;
  border: 1px solid var(--app-border);
}

.parameter-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}

.param-key {
  font-weight: 600;
  color: var(--app-fg-secondary);
  min-width: 120px;
}

.param-value {
  color: var(--app-fg);
  background: var(--app-surface);
  padding: 2px 6px;
  border-radius: 3px;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
}

.parameter-item.override .param-key {
  color: #d97706;
}

.parameter-item.override .param-value {
  background: var(--app-warn-soft);
  border: 1px solid #ffd8a8;
}

.step-card-footer {
  padding: 12px 16px;
  border-top: 1px solid var(--app-border);
  background: var(--app-surface);
}
</style>
