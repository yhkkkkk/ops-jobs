<template>
  <div class="script-editor-with-validation">
    <!-- 验证结果面板 -->
    <div v-if="showValidationPanel && validationResults.length > 0" class="validation-panel">
      <div class="validation-header">
        <span class="validation-title">
          <icon-exclamation-circle />
          脚本验证结果
        </span>
        <a-button type="text" size="small" @click="showValidationPanel = false">
          <icon-close />
        </a-button>
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
              :class="`validation-icon-${result.severity}`"
            />
            <span class="message-text">{{ result.message }}</span>
          </div>
          <div v-if="result.suggestion" class="validation-suggestion">
            <icon-bulb />
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
        <a-badge 
          :count="validationResults.length" 
          :number-style="{ backgroundColor: getValidationColor() }"
        >
          <a-button 
            type="primary" 
            size="small" 
            @click="showValidationPanel = !showValidationPanel"
          >
            <icon-exclamation-circle />
            验证结果
          </a-button>
        </a-badge>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import MonacoEditor from './MonacoEditor.vue'
import { validateScript, type ScriptValidationResult } from '@/utils/scriptValidator'

interface Props {
  modelValue: string
  language?: 'shell' | 'python' | 'powershell'
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
const validationTimer = ref<NodeJS.Timeout | null>(null)

// 编辑器选项
const editorOptions = computed(() => ({
  minimap: { enabled: false },
  scrollBeyondLastLine: false,
  wordWrap: 'on',
  lineNumbers: 'on',
  folding: true,
  contextmenu: true,
  selectOnLineNumbers: true,
  accessibilitySupport: 'off',
  glyphMargin: true, // 启用装饰器边距
  lineDecorationsWidth: 20,
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
      return 'icon-close-circle'
    case 'warning':
      return 'icon-exclamation-circle'
    case 'info':
      return 'icon-info-circle'
    default:
      return 'icon-question-circle'
  }
}

// 获取验证颜色
const getValidationColor = () => {
  const hasErrors = validationResults.value.some(r => r.severity === 'error')
  const hasWarnings = validationResults.value.some(r => r.severity === 'warning')
  
  if (hasErrors) return '#ff4d4f'
  if (hasWarnings) return '#faad14'
  return '#52c41a'
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
  background: white;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  z-index: 1000;
  overflow: hidden;
}

.validation-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: #fafafa;
  border-bottom: 1px solid #d9d9d9;
}

.validation-title {
  font-weight: 500;
  color: #262626;
}

.validation-content {
  max-height: 250px;
  overflow-y: auto;
}

.validation-item {
  padding: 8px 12px;
  border-bottom: 1px solid #f0f0f0;
  cursor: pointer;
  transition: background-color 0.2s;
}

.validation-item:hover {
  background-color: #f5f5f5;
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
  color: #ff4d4f;
  margin-right: 6px;
  margin-top: 2px;
}

.validation-icon-warning {
  color: #faad14;
  margin-right: 6px;
  margin-top: 2px;
}

.validation-icon-info {
  color: #1890ff;
  margin-right: 6px;
  margin-top: 2px;
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
  background: #f6ffed;
  border: 1px solid #b7eb8f;
  border-radius: 4px;
  font-size: 12px;
  color: #52c41a;
}

.validation-suggestion .arco-icon {
  margin-right: 4px;
  margin-top: 1px;
}

.validation-location {
  font-size: 11px;
  color: #8c8c8c;
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
  border-left: 3px solid #ff4d4f;
}

.validation-warning {
  border-left: 3px solid #faad14;
}

.validation-info {
  border-left: 3px solid #1890ff;
}
</style>
