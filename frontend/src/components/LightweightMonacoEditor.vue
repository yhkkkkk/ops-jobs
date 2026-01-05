<template>
  <div ref="editorRef" class="monaco-editor" :style="{ height: height + 'px' }">
    <div v-if="loading" class="loading-overlay">
      <div class="loading-spinner"></div>
      <div class="loading-text">正在加载编辑器...</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { loadMonaco, createEditor, getMonacoLanguage, disposeMonaco } from '@/utils/monacoFactory'

interface Props {
  modelValue: string
  language?: string
  theme?: string
  height?: number
  readonly?: boolean
  options?: any
  useCDN?: boolean
}

interface Emits {
  (e: 'update:modelValue', value: string): void
  (e: 'change', value: string): void
  (e: 'ready'): void
}

const props = withDefaults(defineProps<Props>(), {
  language: 'shell',
  theme: 'vs-dark',
  height: 400,
  readonly: false,
  options: () => ({}),
  useCDN: false,
})

const emit = defineEmits<Emits>()

const editorRef = ref<HTMLElement>()
let editor: any = null
let monaco: any = null
const loading = ref(false)

// 初始化编辑器
const initEditor = async () => {
  if (!editorRef.value) return

  // 确保DOM元素已经渲染
  await nextTick()

  // 再次检查DOM元素
  if (!editorRef.value) {
    console.error('Monaco编辑器容器元素不存在')
    return
  }

  loading.value = true

  try {
    // 加载Monaco Editor
    monaco = await loadMonaco()

    const defaultOptions = {
      value: props.modelValue || '',
      language: getMonacoLanguage(props.language),
      theme: props.theme,
      readOnly: props.readonly,
      ...props.options,
    }

    // 销毁之前的编辑器实例
    if (editor) {
      editor.dispose()
      editor = null
    }

    // 创建编辑器实例
    editor = await createEditor(editorRef.value, defaultOptions)

    // 确保编辑器获得焦点
    setTimeout(() => {
      if (editor && !props.readonly) {
        editor.focus()
      }
    }, 100)

    // 监听内容变化
    if (editor) {
      editor.onDidChangeModelContent(() => {
        const value = editor?.getValue() || ''
        emit('update:modelValue', value)
        emit('change', value)
      })
    }

    loading.value = false
    emit('ready')
    console.log('Monaco编辑器初始化成功')
  } catch (error) {
    console.error('Monaco编辑器初始化失败:', error)
    loading.value = false
  }
}

// 销毁编辑器
const destroyEditor = () => {
  if (editor) {
    editor.dispose()
    editor = null
  }
}

// 设置编辑器值
const setValue = (value: string) => {
  if (editor && editor.getValue() !== value) {
    editor.setValue(value)
  }
}

// 获取编辑器值
const getValue = () => {
  return editor?.getValue() || ''
}

// 设置语言
const setLanguage = (language: string) => {
  if (editor && monaco) {
    const model = editor.getModel()
    if (model) {
      monaco.editor.setModelLanguage(model, getMonacoLanguage(language))
    }
  }
}

// 设置主题
const setTheme = (theme: string) => {
  if (editor && monaco) {
    monaco.editor.setTheme(theme)
  }
}

// 格式化代码
const formatCode = () => {
  if (editor) {
    editor.getAction('editor.action.formatDocument')?.run()
  }
}

// 监听属性变化
watch(() => props.modelValue, (newValue) => {
  if (editor && editor.getValue() !== newValue) {
    setValue(newValue)
  }
})

watch(() => props.language, (newLanguage) => {
  setLanguage(newLanguage)
})

watch(() => props.theme, (newTheme) => {
  setTheme(newTheme)
})

watch(() => props.readonly, (readonly) => {
  if (editor) {
    editor.updateOptions({ readOnly: readonly })
  }
})

// 暴露方法
defineExpose({
  setValue,
  getValue,
  setLanguage,
  setTheme,
  formatCode,
  getEditor: () => editor,
})

// 生命周期
onMounted(() => {
  // 延迟初始化，确保DOM完全渲染
  setTimeout(() => {
    initEditor()
  }, 100)
})

onUnmounted(() => {
  destroyEditor()
})
</script>

<style scoped>
.monaco-editor {
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  overflow: hidden;
  width: 100%;
  position: relative;
}

.monaco-editor:focus-within {
  border-color: #1890ff;
  box-shadow: 0 0 0 2px rgba(24, 144, 255, 0.2);
}

.loading-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(255, 255, 255, 0.9);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  z-index: 10;
}

.loading-spinner {
  width: 32px;
  height: 32px;
  border: 3px solid #f3f3f3;
  border-top: 3px solid #1890ff;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

.loading-text {
  margin-top: 12px;
  color: #666;
  font-size: 14px;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

/* 确保Monaco编辑器内部元素正确显示 */
:deep(.monaco-editor) {
  width: 100% !important;
  height: 100% !important;
}

:deep(.monaco-editor .overflow-guard) {
  width: 100% !important;
  height: 100% !important;
}
</style>
