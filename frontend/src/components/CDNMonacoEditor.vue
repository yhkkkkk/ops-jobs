<template>
  <MonacoEditor
    ref="editorRef"
    :model-value="modelValue"
    :language="language"
    :theme="theme"
    :height="height"
    :readonly="readonly"
    :options="options"
    @update:modelValue="(value) => emit('update:modelValue', value)"
    @change="(value) => emit('change', value)"
  />
</template>

<script setup lang="ts">
import { ref } from 'vue'
import MonacoEditor from './MonacoEditor.vue'

interface Props {
  modelValue: string
  language?: string
  theme?: string
  height?: number
  readonly?: boolean
  options?: any
}

interface Emits {
  (e: 'update:modelValue', value: string): void
  (e: 'change', value: string): void
}

withDefaults(defineProps<Props>(), {
  language: 'shell',
  theme: 'vs-dark',
  height: 400,
  readonly: false,
  options: () => ({}),
})

const emit = defineEmits<Emits>()

const editorRef = ref<any>(null)

defineExpose({
  setValue: (value: string) => editorRef.value?.setValue(value),
  getValue: () => editorRef.value?.getValue(),
  setLanguage: (language: string) => editorRef.value?.setLanguage(language),
  setTheme: (theme: string) => editorRef.value?.setTheme(theme),
  formatCode: () => editorRef.value?.formatCode(),
  getEditor: () => editorRef.value?.getEditor?.(),
})
</script>
