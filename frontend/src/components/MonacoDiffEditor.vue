<template>
  <div ref="editorContainer" class="monaco-diff-editor"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as monaco from 'monaco-editor'
import { setupMonacoWorkers } from '@/utils/monacoWorkers'
import { ensureMonacoLanguage, getMonacoLanguage } from '@/utils/monacoFactory'

interface Props {
  original: string
  modified: string
  language?: string
  theme?: string
  height?: number
  readonly?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  language: 'shell',
  theme: 'vs-dark',
  height: 400,
  readonly: true,
})

const editorContainer = ref<HTMLElement>()
let diffEditor: monaco.editor.IStandaloneDiffEditor | null = null
let originalModel: monaco.editor.ITextModel | null = null
let modifiedModel: monaco.editor.ITextModel | null = null

const resolveLanguage = (lang?: string) => getMonacoLanguage((lang || '').toLowerCase())

const initEditor = async () => {
  if (!editorContainer.value) return

  try {
    setupMonacoWorkers()
    const resolvedLanguage = resolveLanguage(props.language)
    await ensureMonacoLanguage(monaco, resolvedLanguage)

    diffEditor = monaco.editor.createDiffEditor(editorContainer.value, {
      readOnly: props.readonly,
      automaticLayout: true,
      fontSize: 14,
      renderSideBySide: true,
      minimap: { enabled: false },
      scrollBeyondLastLine: false,
      wordWrap: 'on',
      folding: true,
      contextmenu: true,
      accessibilitySupport: 'off',
    })

    originalModel = monaco.editor.createModel(props.original || '', resolvedLanguage)
    modifiedModel = monaco.editor.createModel(props.modified || '', resolvedLanguage)
    diffEditor.setModel({ original: originalModel, modified: modifiedModel })
    monaco.editor.setTheme(props.theme)
  } catch (error) {
    console.error('Monaco diff 编辑器初始化失败:', error)
  }
}

const destroyEditor = () => {
  if (diffEditor) {
    diffEditor.dispose()
    diffEditor = null
  }
  if (originalModel) {
    originalModel.dispose()
    originalModel = null
  }
  if (modifiedModel) {
    modifiedModel.dispose()
    modifiedModel = null
  }
}

watch(() => props.original, (newValue) => {
  if (originalModel && originalModel.getValue() !== newValue) {
    originalModel.setValue(newValue || '')
  }
})

watch(() => props.modified, (newValue) => {
  if (modifiedModel && modifiedModel.getValue() !== newValue) {
    modifiedModel.setValue(newValue || '')
  }
})

watch(() => props.language, (newLanguage) => {
  if (originalModel && modifiedModel) {
    const resolved = resolveLanguage(newLanguage)
    void ensureMonacoLanguage(monaco, resolved)
    monaco.editor.setModelLanguage(originalModel, resolved)
    monaco.editor.setModelLanguage(modifiedModel, resolved)
  }
})

watch(() => props.theme, (newTheme) => {
  monaco.editor.setTheme(newTheme)
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
.monaco-diff-editor {
  width: 100%;
  height: v-bind(height + 'px');
  border: 1px solid #d9d9d9;
  border-radius: 6px;
}
</style>
