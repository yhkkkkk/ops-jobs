<template>
  <div class="flow-variable-editor">
    <div class="variable-editor-head">
      <div>
        <h3>流水线全局变量</h3>
        <p>节点配置通过 ${Key} 引用变量，启动时只填写允许显示的变量。</p>
      </div>
      <a-button size="small" type="primary" @click="addVariable">
        <template #icon><icon-plus /></template>
        新增变量
      </a-button>
    </div>

    <a-empty v-if="draft.length === 0" description="暂无变量定义" />
    <div v-else class="variable-row-list">
      <section v-for="(item, index) in draft" :key="item.id" class="variable-row">
        <div class="variable-row__main">
          <a-input v-model="item.key" placeholder="Key，例如 CheckHost" @input="emitChange" />
          <a-input v-model="item.name" placeholder="显示名称，例如 执行脚本机器" @input="emitChange" />
          <a-select v-model="item.type" placeholder="变量类型" @change="handleTypeChange(item)">
            <a-option value="text">文本</a-option>
            <a-option value="number">数字</a-option>
            <a-option value="boolean">布尔</a-option>
            <a-option value="secret">密文</a-option>
            <a-option value="host_list">主机列表</a-option>
          </a-select>
          <a-select v-model="item.widget" placeholder="控件" @change="emitChange">
            <a-option value="input">输入框</a-option>
            <a-option value="textarea">文本框</a-option>
            <a-option value="password">密码框</a-option>
            <a-option value="host_list">主机选择</a-option>
          </a-select>
          <a-button size="small" status="danger" @click="removeVariable(index)">
            <template #icon><icon-delete /></template>
          </a-button>
        </div>
        <div class="variable-row__meta">
          <a-input v-model="item.defaultText" placeholder="默认值；主机列表用逗号分隔 ID" @input="emitChange" />
          <a-input v-model="item.regex" placeholder="正则校验，例如 ^v\\d+" @input="emitChange" />
          <a-input v-model="item.placeholder" placeholder="提示文本" @input="emitChange" />
          <a-checkbox v-model="item.required" @change="emitChange">必填</a-checkbox>
          <a-checkbox v-model="item.show_on_start" @change="emitChange">执行时显示</a-checkbox>
        </div>
        <a-textarea
          v-model="item.description"
          :auto-size="{ minRows: 1, maxRows: 3 }"
          placeholder="描述（可选）"
          @input="emitChange"
        />
        <div class="variable-reference">引用：{{ variableReference(item.key) }}</div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, watch } from 'vue'
import {
  flowVariableReference,
  normalizeFlowVariables,
  serializeFlowVariables,
  type FlowVariableDefinition,
  type FlowVariableType,
  type FlowVariableWidget,
} from '../flowUtils'

interface DraftVariable extends Omit<FlowVariableDefinition, 'default'> {
  id: string
  defaultText: string
}

const props = defineProps<{
  modelValue: Record<string, any>
}>()

const emit = defineEmits<{
  'update:modelValue': [value: Record<string, any>]
}>()

const draft = reactive<DraftVariable[]>([])
let syncing = false

const stringifyDefault = (value: any) => {
  if (Array.isArray(value)) return value.join(',')
  if (value === undefined || value === null) return ''
  return String(value)
}

const parseDefault = (item: DraftVariable) => {
  const raw = item.defaultText
  if (item.type === 'host_list') {
    return raw.split(',').map(part => part.trim()).filter(Boolean).map(Number).filter(value => !Number.isNaN(value))
  }
  if (item.type === 'number') return raw.trim() ? Number(raw) : undefined
  if (item.type === 'boolean') return raw === 'true'
  return raw
}

const toDraft = (definition: FlowVariableDefinition): DraftVariable => ({
  ...definition,
  id: `${definition.key}-${Math.random().toString(16).slice(2)}`,
  defaultText: stringifyDefault(definition.default),
})

const syncFromModel = () => {
  syncing = true
  draft.splice(0, draft.length, ...normalizeFlowVariables(props.modelValue).map(toDraft))
  syncing = false
}

const emitChange = () => {
  if (syncing) return
  const definitions = draft.map(item => ({
    key: item.key,
    name: item.name,
    type: item.type,
    widget: item.widget,
    default: parseDefault(item),
    required: item.required,
    regex: item.regex,
    show_on_start: item.show_on_start,
    placeholder: item.placeholder,
    description: item.description,
  }))
  emit('update:modelValue', serializeFlowVariables(definitions))
}

const variableReference = (key: string) => key?.trim() ? flowVariableReference(key.trim()) : '${Key}'

const addVariable = () => {
  draft.push({
    id: `var-${Date.now()}`,
    key: '',
    name: '',
    type: 'text' as FlowVariableType,
    widget: 'input' as FlowVariableWidget,
    defaultText: '',
    required: false,
    show_on_start: true,
    regex: '',
    placeholder: '',
    description: '',
  })
  emitChange()
}

const removeVariable = (index: number) => {
  draft.splice(index, 1)
  emitChange()
}

const handleTypeChange = (item: DraftVariable) => {
  if (item.type === 'host_list') item.widget = 'host_list'
  else if (item.type === 'secret') item.widget = 'password'
  else if (item.widget === 'host_list' || item.widget === 'password') item.widget = 'input'
  emitChange()
}

watch(() => props.modelValue, syncFromModel, { immediate: true, deep: true })
</script>

<style scoped>
.flow-variable-editor {
  display: grid;
  gap: 12px;
}
.variable-editor-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}
.variable-editor-head h3 { margin: 0; color: var(--app-fg); font-size: 15px; }
.variable-editor-head p { margin: 4px 0 0; color: var(--app-muted); font-size: 12px; }
.variable-row-list { display: grid; gap: 10px; }
.variable-row {
  display: grid;
  gap: 8px;
  padding: 10px;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
  background: #fff;
}
.variable-row__main {
  display: grid;
  grid-template-columns: minmax(120px, 1fr) minmax(150px, 1fr) 110px 110px auto;
  gap: 8px;
  align-items: center;
}
.variable-row__meta {
  display: grid;
  grid-template-columns: minmax(150px, 1fr) minmax(150px, 1fr) minmax(150px, 1fr) auto auto;
  gap: 8px;
  align-items: center;
}
.variable-reference {
  color: var(--app-muted);
  font-family: var(--app-mono);
  font-size: 12px;
}
@media (max-width: 900px) {
  .variable-row__main,
  .variable-row__meta {
    grid-template-columns: 1fr;
  }
}
</style>
