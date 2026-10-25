<template>
  <div class="script-editor-with-validation">
    <!-- 验证结果面板 -->
    <div v-if="showValidationPanel && validationResults.length > 0" class="validation-panel">
      <div class="validation-header">
        <span class="validation-title">
          <AlertTriangle :size="14" />
          脚本验证结果
        </span>
        <n-button quaternary circle size="tiny" @click="showValidationPanel = false">
          <X :size="14" />
        </n-button>
      </div>
      <div class="validation-content">
        <div
          v-for="(result, index) in validationResults"
          :key="index"
          class="validation-item"
          :class="`validation-${result.severity}`"
          @click="goToLine(result.line)"
        >
          <div class="validation-message">
            <component
              :is="getSeverityIcon(result.severity)"
              :size="14"
              :class="`validation-icon-${result.severity}`"
            />
            <span class="message-text">{{ result.message }}</span>
          </div>
          <div v-if="result.suggestion" class="validation-suggestion">
            <Lightbulb :size="12" class="suggestion-icon" />
            {{ result.suggestion }}
          </div>
          <div class="validation-location">
            第 {{ result.line }} 行，第 {{ result.column }} 列
          </div>
        </div>
      </div>
    </div>

    <!-- Monaco编辑器 -->
    <div class="editor-container">
      <MonacoEditor
        ref="editorRef"
        v-model="scriptContent"
        :language="language"
        :theme="theme"
        :height="height"
        :readonly="readonly"
        :options="editorOptions"
        @change="(value: string) => scriptContent = value"
      />

      <!-- 验证状态指示器 -->
      <div v-if="validationResults.length > 0" class="validation-indicator">
        <n-badge :value="validationResults.length" :color="getValidationColor()">
          <n-button
            type="primary"
            size="small"
            @click="showValidationPanel = !showValidationPanel"
          >
            <template #icon>
              <AlertTriangle :size="14" />
            </template>
            验证结果
          </n-button>
        </n-badge>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import type * as monaco from 'monaco-editor'
import { NBadge, NButton } from 'naive-ui'
import { AlertTriangle, CircleHelp, CircleX, Info, Lightbulb, X } from 'lucide-vue-next'
import MonacoEditor from './MonacoEditor.vue'
import { validateScript, type ScriptValidationResult } from '@/utils/scriptValidator'

interface Props {
  modelValue: string
  language?: 'shell' | 'python' | 'powershell' | 'perl' | 'javascript' | 'go'
  theme?: string
  height?: number
  readonly?: boolean
  autoValidate?: boolean
  validationDelay?: number
}

interface Emits {
  (e: 'update:modelValue', value: string): void
  (e: 'change', value: string): void
  (e: 'validation-change', results: ScriptValidationResult[]): void
}

const props = withDefaults(defineProps<Props>(), {
  language: 'shell',
  theme: 'vs-dark',
  height: 400,
  readonly: false,
  autoValidate: true,
  validationDelay: 1000,
})

const emit = defineEmits<Emits>()

const editorRef = ref()
const scriptContent = ref(props.modelValue)
const validationResults = ref<ScriptValidationResult[]>([])
const showValidationPanel = ref(false)
const validationTimer = ref<ReturnType<typeof setTimeout> | null>(null)

// 编辑器选项
const editorOptions = computed<monaco.editor.IStandaloneEditorConstructionOptions>(() => ({
  minimap: { enabled: false },
  scrollBeyondLastLine: false,
  wordWrap: 'on',
  scrollbar: {
    horizontal: 'hidden',
    vertical: 'auto',
  },
  lineNumbers: 'on',
  folding: true,
  contextmenu: true,
  selectOnLineNumbers: true,
  accessibilitySupport: 'off',
  glyphMargin: false,
  lineDecorationsWidth: 10,
  lineNumbersMinChars: 3,
}))

// 监听内容变化
watch(() => props.modelValue, (newValue) => {
  scriptContent.value = newValue
})

watch(scriptContent, (newValue) => {
  emit('update:modelValue', newValue)
  emit('change', newValue)

  if (props.autoValidate) {
    validateScriptContent(newValue)
  }
})

// 验证脚本内容
const validateScriptContent = (content: string) => {
  // 清除之前的定时器
  if (validationTimer.value) {
    clearTimeout(validationTimer.value)
  }

  // 设置新的定时器，避免频繁验证
  validationTimer.value = setTimeout(() => {
    try {
      const results = validateScript(content, props.language)
      validationResults.value = results
      emit('validation-change', results)

      // 如果有错误，自动显示验证面板
      if (results.some(r => r.severity === 'error')) {
        showValidationPanel.value = true
      }
    } catch (error) {
      console.error('脚本验证失败:', error)
    }
  }, props.validationDelay)
}

// 跳转到指定行
const goToLine = (lineNumber: number) => {
  if (editorRef.value) {
    const editor = editorRef.value.getEditor()
    if (editor) {
      editor.revealLineInCenter(lineNumber)
      editor.setPosition({ lineNumber, column: 1 })
      editor.focus()
    }
  }
}

// 获取严重程度图标
const getSeverityIcon = (severity: string) => {
  switch (severity) {
    case 'error':
      return CircleX
    case 'warning':
      return AlertTriangle
    case 'info':
      return Info
    default:
      return CircleHelp
  }
}

// 获取验证颜色
const getValidationColor = () => {
  const hasErrors = validationResults.value.some(r => r.severity === 'error')
  const hasWarnings = validationResults.value.some(r => r.severity === 'warning')

  if (hasErrors) return '#dc2626'
  if (hasWarnings) return '#d97706'
  return '#16a34a'
}

// 手动触发验证
const triggerValidation = () => {
  validateScriptContent(scriptContent.value)
}

// 清除验证结果
const clearValidation = () => {
  validationResults.value = []
  showValidationPanel.value = false
}

// 暴露方法
defineExpose({
  triggerValidation,
  clearValidation,
  getValidationResults: () => validationResults.value,
  formatCode: () => editorRef.value?.formatCode(),
})

// 组件卸载时清理定时器
import { onUnmounted } from 'vue'
onUnmounted(() => {
  if (validationTimer.value) {
    clearTimeout(validationTimer.value)
  }
})
</script>

<style scoped>
.script-editor-with-validation {
  position: relative;
  width: 100%;
}

.validation-panel {
  position: absolute;
  top: 0;
  right: 0;
  width: 400px;
  max-height: 300px;
  background: var(--app-surface, #fff);
  border: 1px solid var(--app-border, #e5e7eb);
  border-radius: 6px;
  box-shadow: var(--app-shadow-md, 0 4px 12px rgba(0, 0, 0, 0.15));
  z-index: 1000;
  overflow: hidden;
}

.validation-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: var(--app-surface-soft, #fafafa);
  border-bottom: 1px solid var(--app-border, #d9d9d9);
}

.validation-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-weight: 500;
  color: var(--app-fg, #262626);
}

.validation-content {
  max-height: 250px;
  overflow-y: auto;
}

.validation-item {
  padding: 8px 12px;
  border-bottom: 1px solid var(--app-border-soft, #f0f0f0);
  cursor: pointer;
  transition: background-color 0.2s;
}

.validation-item:hover {
  background-color: var(--app-surface-soft, #f5f5f5);
}

.validation-item:last-child {
  border-bottom: none;
}

.validation-message {
  display: flex;
  align-items: flex-start;
  margin-bottom: 4px;
}

.validation-icon-error {
  color: #dc2626;
  margin-right: 6px;
  margin-top: 2px;
  flex: 0 0 auto;
}

.validation-icon-warning {
  color: #d97706;
  margin-right: 6px;
  margin-top: 2px;
  flex: 0 0 auto;
}

.validation-icon-info {
  color: #2f6feb;
  margin-right: 6px;
  margin-top: 2px;
  flex: 0 0 auto;
}

.message-text {
  flex: 1;
  font-size: 13px;
  line-height: 1.4;
}

.validation-suggestion {
  display: flex;
  align-items: flex-start;
  margin: 4px 0;
  padding: 6px 8px;
  background: var(--app-success-soft, #f6ffed);
  border: 1px solid #b7eb8f;
  border-radius: 4px;
  font-size: 12px;
  color: #16a34a;
}

.suggestion-icon {
  margin-right: 4px;
  margin-top: 1px;
  flex: 0 0 auto;
}

.validation-location {
  font-size: 11px;
  color: var(--app-meta, #8c8c8c);
  margin-top: 2px;
}

.editor-container {
  position: relative;
  width: 100%;
}

.validation-indicator {
  position: absolute;
  top: 8px;
  right: 8px;
  z-index: 100;
}

.validation-error {
  border-left: 3px solid #dc2626;
}

.validation-warning {
  border-left: 3px solid #d97706;
}

.validation-info {
  border-left: 3px solid #2f6feb;
}
</style>
