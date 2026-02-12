<template>
  <div ref="editorContainer" class="simple-monaco-editor"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as monaco from 'monaco-editor'
import { setupMonacoWorkers } from '@/utils/monacoWorkers'
import { ensureMonacoLanguage, getMonacoLanguage } from '@/utils/monacoFactory'

interface Props {
  modelValue: string
  language?: string
  theme?: string
  height?: number
  readonly?: boolean
}

interface Emits {
  (e: 'update:modelValue', value: string): void
}

const props = withDefaults(defineProps<Props>(), {
  language: 'shell',
  theme: 'vs-dark',
  height: 400,
  readonly: false,
})

const emit = defineEmits<Emits>()

const editorContainer = ref<HTMLElement>()
let editor: monaco.editor.IStandaloneCodeEditor | null = null
const resolveLanguage = (lang?: string) => getMonacoLanguage((lang || '').toLowerCase())

const initEditor = async () => {
  if (!editorContainer.value) return

  try {
    // 创建编辑器
    setupMonacoWorkers()
    const resolvedLanguage = resolveLanguage(props.language)
    await ensureMonacoLanguage(monaco, resolvedLanguage)
    editor = monaco.editor.create(editorContainer.value, {
      value: props.modelValue,
      language: resolvedLanguage,
      theme: props.theme,
      readOnly: props.readonly,
      automaticLayout: true,
      fontSize: 14,
      minimap: { enabled: false },
      scrollBeyondLastLine: false,
      wordWrap: 'on',
      lineNumbers: 'on',
      folding: true,
      contextmenu: true,
      selectOnLineNumbers: true,
      accessibilitySupport: 'off',
    })

    // 监听内容变化
    editor.onDidChangeModelContent(() => {
      if (editor) {
        const value = editor.getValue()
        emit('update:modelValue', value)
      }
    })

    console.log('Monaco编辑器初始化成功')
  } catch (error) {
    console.error('Monaco编辑器初始化失败:', error)
  }
}

const destroyEditor = () => {
  if (editor) {
    editor.dispose()
    editor = null
  }
}

// 监听值变化
watch(() => props.modelValue, (newValue) => {
  if (editor && editor.getValue() !== newValue) {
    editor.setValue(newValue || '')
  }
}, { immediate: true })

// 监听语言变化
watch(() => props.language, (newLanguage) => {
  if (editor) {
    const model = editor.getModel()
    if (model) {
      const resolved = resolveLanguage(newLanguage)
      void ensureMonacoLanguage(monaco, resolved)
      monaco.editor.setModelLanguage(model, resolved)
    }
  }
})

// 监听主题变化
watch(() => props.theme, (newTheme) => {
  if (editor) {
    monaco.editor.setTheme(newTheme)
  }
})

onMounted(() => {
  setTimeout(() => {
    void initEditor()
  }, 200)
})

onUnmounted(() => {
  destroyEditor()
})
</script>

<style scoped>
.simple-monaco-editor {
  width: 100%;
  height: v-bind(height + 'px');
  border: 1px solid #d9d9d9;
  border-radius: 6px;
}
</style>
