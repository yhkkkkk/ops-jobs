<template>
  <div ref="editorRef" class="monaco-editor" :style="{ height: height + 'px' }"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import * as monaco from 'monaco-editor'

interface Props {
  modelValue: string
  language?: string
  theme?: string
  height?: number
  readonly?: boolean
  options?: monaco.editor.IStandaloneEditorConstructionOptions
}

interface Emits {
  (e: 'update:modelValue', value: string): void
  (e: 'change', value: string): void
}

const props = withDefaults(defineProps<Props>(), {
  language: 'shell',
  theme: 'vs-dark',
  height: 400,
  readonly: false,
  options: () => ({}),
})

const emit = defineEmits<Emits>()

const editorRef = ref<HTMLElement>()
let editor: monaco.editor.IStandaloneCodeEditor | null = null

// 语言映射
const languageMap = {
  shell: 'shell',
  bash: 'shell',
  python: 'python',
  powershell: 'powershell',
  sql: 'sql',
  javascript: 'javascript',
  typescript: 'typescript',
  json: 'json',
  yaml: 'yaml',
  xml: 'xml',
}

// 获取Monaco语言
const getMonacoLanguage = (lang: string) => {
  return languageMap[lang] || 'plaintext'
}

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

  try {
    const defaultOptions: monaco.editor.IStandaloneEditorConstructionOptions = {
      value: props.modelValue || '',
      language: getMonacoLanguage(props.language),
      theme: props.theme,
      readOnly: props.readonly,
      automaticLayout: true,
      fontSize: 14,
      lineNumbers: 'on',
      minimap: { enabled: false },
      scrollBeyondLastLine: false,
      wordWrap: 'on',
      folding: true,
      lineDecorationsWidth: 10,
      lineNumbersMinChars: 3,
      glyphMargin: false,
      contextmenu: true,
      selectOnLineNumbers: true,
      roundedSelection: false,
      cursorStyle: 'line',
      accessibilitySupport: 'off',
      tabSize: 2,
      insertSpaces: true,
      detectIndentation: false,
      ...props.options,
    }

    // 销毁之前的编辑器实例
    if (editor) {
      editor.dispose()
      editor = null
    }

    editor = monaco.editor.create(editorRef.value, defaultOptions)

    // 确保编辑器获得焦点
    setTimeout(() => {
      if (editor && !props.readonly) {
        editor.focus()
      }
    }, 100)
  } catch (error) {
    console.error('Monaco编辑器初始化失败:', error)
  }

    // 监听内容变化
    if (editor) {
      editor.onDidChangeModelContent(() => {
        const value = editor?.getValue() || ''
        emit('update:modelValue', value)
        emit('change', value)
      })
    }

  // 设置Shell语言的语法高亮
  if (props.language === 'shell' || props.language === 'bash') {
    monaco.languages.setMonarchTokensProvider('shell', {
      tokenizer: {
        root: [
          [/#.*$/, 'comment'],
          [/\$\w+/, 'variable'],
          [/\$\{[^}]+\}/, 'variable'],
          [/".*?"/, 'string'],
          [/'.*?'/, 'string'],
          [/\b(if|then|else|elif|fi|for|while|do|done|case|esac|function|return|exit|break|continue)\b/, 'keyword'],
          [/\b(echo|printf|read|cd|ls|cp|mv|rm|mkdir|rmdir|chmod|chown|grep|sed|awk|sort|uniq|head|tail|cat|less|more)\b/, 'keyword.control'],
          [/[|&;()<>]/, 'delimiter'],
          [/\d+/, 'number'],
        ],
      },
    })
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
  if (editor) {
    const model = editor.getModel()
    if (model) {
      monaco.editor.setModelLanguage(model, getMonacoLanguage(language))
    }
  }
}

// 设置主题
const setTheme = (theme: string) => {
  if (editor) {
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
