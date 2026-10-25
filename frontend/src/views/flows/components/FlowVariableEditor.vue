<template>
  <div class="flow-variable-editor">
    <div class="variable-workspace">
      <section class="variable-list-pane">
        <div class="variable-toolbar">
          <div>
            <strong>全局变量</strong>
            <span>节点与分支用 ${KEY} 引用；「执行时显示」的变量会出现在新建任务表单。</span>
          </div>
          <n-button size="small" type="primary" @click="addVariable">
            <template #icon><Plus /></template>
            新增变量
          </n-button>
        </div>

        <div class="variable-table">
          <div class="variable-table__head">
            <span>名称</span>
            <span>KEY</span>
            <span>类型</span>
            <span>来源</span>
            <span>显示</span>
            <span>操作</span>
          </div>
          <n-empty v-if="draft.length === 0" description="暂无自定义变量，点击上方新增" />
          <button
            v-for="(item, index) in draft"
            :key="item.id"
            type="button"
            :class="['variable-table__row', { 'variable-table__row--active': selectedId === item.id }]"
            @click="selectedId = item.id"
          >
            <span class="ellipsis">{{ item.name || '未命名' }}</span>
            <code class="ellipsis">{{ variableReference(item.key) }}</code>
            <span>{{ typeLabel(item.type) }}</span>
            <span>{{ sourceLabel(item.source_type) }}</span>
            <span>{{ item.show_on_start ? '显示' : '隐藏' }}</span>
            <span class="variable-row-actions" @click.stop>
              <n-button text size="tiny" @click="copyReference(item.key)">复制 KEY</n-button>
              <n-button text size="tiny" type="error" @click="removeVariable(index)">删除</n-button>
            </span>
          </button>
        </div>

        <div class="system-variable-block">
          <div class="system-variable-block__head">
            <strong>系统内置变量</strong>
            <span>任务启动自动注入，不可编辑</span>
          </div>
          <div
            v-for="hint in systemHints"
            :key="hint.key"
            class="system-variable-row"
          >
            <div>
              <strong>{{ hint.name }}</strong>
              <span>{{ hint.description }}</span>
            </div>
            <div class="variable-ref-cell">
              <code>{{ flowVariableReference(hint.key) }}</code>
              <n-button text size="tiny" @click="copyReference(hint.key)">复制</n-button>
            </div>
          </div>
        </div>
      </section>

      <section class="variable-edit-pane">
        <template v-if="selected">
          <h3>基础信息</h3>
          <n-form label-placement="left" label-width="88" size="small">
            <n-form-item label="名称" required>
              <n-input v-model:value="selected.name" placeholder="变量显示名称" @update:value="emitChange" />
            </n-form-item>
            <n-form-item label="Key" required>
              <n-input v-model:value="selected.key" placeholder="DeployPath" @update:value="emitChange" />
            </n-form-item>
            <n-form-item label="类型">
              <n-select
                v-model:value="selected.type"
                :options="typeOptions"
                @update:value="() => handleTypeChange(selected)"
              />
            </n-form-item>
            <n-form-item v-if="selected.type === 'text' || selected.type === 'number'" label="正则校验">
              <n-input v-model:value="selected.regex" placeholder="例如 ^.+$" @update:value="emitChange" />
            </n-form-item>
            <n-form-item label="执行时显示">
              <n-select
                :value="selected.show_on_start ? 'show' : 'hide'"
                :options="showTypeOptions"
                @update:value="value => { selected.show_on_start = value === 'show'; emitChange() }"
              />
            </n-form-item>
            <n-form-item label="必填">
              <n-checkbox v-model:checked="selected.required" @update:checked="emitChange">新建任务时必填</n-checkbox>
            </n-form-item>
            <n-form-item label="提示文本">
              <n-input
                type="textarea"
                v-model:value="selected.description"
                placeholder="请输入变量提示文本"
                :autosize="{ minRows: 2, maxRows: 4 }"
                @update:value="emitChange"
              />
            </n-form-item>
          </n-form>

          <h3>默认值</h3>
          <n-form label-placement="left" label-width="88" size="small">
            <n-form-item v-if="selected.type === 'select'" label="枚举选项">
              <n-input
                type="textarea"
                v-model:value="selected.optionsText"
                placeholder="每行一个选项"
                :autosize="{ minRows: 3, maxRows: 6 }"
                @update:value="emitChange"
              />
            </n-form-item>
            <n-form-item label="默认值">
              <n-input
                v-if="selected.type === 'secret'"
                type="password"
                show-password-on="click"
                v-model:value="selected.defaultText"
                :placeholder="selected.has_default ? '已配置；输入新值可替换' : '密文默认值（可选）'"
                @update:value="emitChange"
              />
              <FlowIpSelectorField
                v-else-if="selected.type === 'host_list'"
                v-model="selected.defaultText"
                placeholder="每行一个 IP 或主机名"
                @update:model-value="emitChange"
              />
              <n-input
                v-else-if="selected.widget === 'textarea'"
                type="textarea"
                v-model:value="selected.defaultText"
                placeholder="多行默认值"
                :autosize="{ minRows: 2, maxRows: 5 }"
                @update:value="emitChange"
              />
              <n-select
                v-else-if="selected.type === 'boolean'"
                v-model:value="selected.defaultText"
                :options="booleanOptions"
                clearable
                placeholder="默认布尔值"
                @update:value="emitChange"
              />
              <n-input
                v-else
                v-model:value="selected.defaultText"
                :placeholder="selected.type === 'number' ? '整数默认值' : '默认值'"
                @update:value="emitChange"
              />
            </n-form-item>
            <n-form-item v-if="selected.type === 'text'" label="表单控件">
              <n-select
                v-model:value="selected.widget"
                :options="textWidgetOptions"
                @update:value="emitChange"
              />
            </n-form-item>
          </n-form>
        </template>
        <n-empty v-else description="选中左侧变量进行编辑，或新增变量" />
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { NButton, NCheckbox, NEmpty, NForm, NFormItem, NInput, NSelect, useMessage } from 'naive-ui'
import {
  FLOW_SYSTEM_VARIABLE_HINTS,
  flowVariableReference,
  normalizeFlowVariables,
  serializeFlowVariables,
  type FlowVariableDefinition,
  type FlowVariableSourceType,
  type FlowVariableType,
  type FlowVariableWidget,
} from '../flowUtils'
import FlowIpSelectorField from './FlowIpSelectorField.vue'
import { Plus } from 'lucide-vue-next'

interface DraftVariable extends Omit<FlowVariableDefinition, 'default' | 'options'> {
  id: string
  defaultText: string
  optionsText: string
}

const props = defineProps<{
  modelValue: Record<string, any>
}>()

const emit = defineEmits<{
  'update:modelValue': [value: Record<string, any>]
}>()

const message = useMessage()
const draft = reactive<DraftVariable[]>([])
const selectedId = ref<string | null>(null)
const systemHints = FLOW_SYSTEM_VARIABLE_HINTS
let syncing = false
let draftSequence = 0
let pendingModelSignature: string | null = null

const typeOptions = [
  { label: '输入框', value: 'text' },
  { label: '整数', value: 'number' },
  { label: '布尔', value: 'boolean' },
  { label: '下拉框', value: 'select' },
  { label: '密码', value: 'secret' },
  { label: 'IP选择器', value: 'host_list' },
]
const textWidgetOptions = [
  { label: '输入框（单行）', value: 'input' },
  { label: '文本框（多行）', value: 'textarea' },
]
const showTypeOptions = [
  { label: '显示', value: 'show' },
  { label: '隐藏', value: 'hide' },
]
const booleanOptions = [
  { label: 'true', value: 'true' },
  { label: 'false', value: 'false' },
]

const selected = computed(() => draft.find(item => item.id === selectedId.value) || null)

const typeLabel = (type: FlowVariableType) =>
  typeOptions.find(item => item.value === type)?.label || type

const sourceLabel = (source?: FlowVariableSourceType) => {
  if (source === 'component_outputs') return '组件输出'
  if (source === 'component_inputs') return '组件输入'
  if (source === 'system') return '系统'
  return '自定义'
}

const stringifyDefault = (value: any) => {
  if (Array.isArray(value)) return value.some(item => typeof item === 'number') ? '' : value.join('\n')
  if (typeof value === 'boolean') return value ? 'true' : 'false'
  if (value === undefined || value === null) return ''
  return String(value)
}

const parseDefault = (item: DraftVariable) => {
  const raw = item.defaultText
  if (item.type === 'host_list') return raw.split(/[\s,]+/).map(value => value.trim()).filter(Boolean)
  if (item.type === 'number') return raw.trim() ? Number(raw) : undefined
  if (item.type === 'boolean') return raw === 'true'
  return raw
}

const parseOptions = (item: DraftVariable) =>
  item.optionsText.split(/\r?\n/).map(value => value.trim()).filter(Boolean)

const createDraftId = () => `flow-variable-${++draftSequence}`

const toDraft = (definition: FlowVariableDefinition): DraftVariable => ({
  ...definition,
  id: createDraftId(),
  defaultText: stringifyDefault(definition.default),
  optionsText: (definition.options || []).join('\n'),
})

const ensureSelection = () => {
  if (!draft.length) {
    selectedId.value = null
    return
  }
  if (!selectedId.value || !draft.some(item => item.id === selectedId.value)) {
    selectedId.value = draft[0].id
  }
}

const syncFromModel = () => {
  syncing = true
  draft.splice(0, draft.length, ...normalizeFlowVariables(props.modelValue).map(toDraft))
  ensureSelection()
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
    has_default: item.type === 'secret' && (item.has_default || Boolean(item.defaultText.trim())),
    required: item.required,
    regex: item.regex,
    options: item.type === 'select' ? parseOptions(item) : undefined,
    show_on_start: item.show_on_start,
    placeholder: item.placeholder,
    description: item.description,
    source_type: item.source_type || 'custom',
    source_tag: item.source_tag,
    source_info: item.source_info,
  }))
  const nextValue = serializeFlowVariables(definitions)
  pendingModelSignature = JSON.stringify(nextValue)
  emit('update:modelValue', nextValue)
}

const variableReference = (key: string) => (key?.trim() ? flowVariableReference(key.trim()) : '${KEY}')

const copyReference = async (key: string) => {
  const text = variableReference(key)
  try {
    await navigator.clipboard.writeText(text)
    message.success(`已复制 ${text}`)
  } catch {
    message.warning('复制失败，请手动选择引用文本')
  }
}

const addVariable = () => {
  const item: DraftVariable = {
    id: createDraftId(),
    key: '',
    name: '',
    type: 'text' as FlowVariableType,
    widget: 'input' as FlowVariableWidget,
    defaultText: '',
    optionsText: '',
    required: false,
    show_on_start: true,
    regex: '',
    placeholder: '',
    description: '',
    source_type: 'custom',
  }
  draft.push(item)
  selectedId.value = item.id
}

const removeVariable = (index: number) => {
  const removed = draft[index]
  draft.splice(index, 1)
  if (selectedId.value === removed?.id) selectedId.value = draft[0]?.id || null
  emitChange()
}

const handleTypeChange = (item: DraftVariable | null) => {
  if (!item) return
  if (item.type === 'host_list') item.widget = 'host_list'
  else if (item.type === 'secret') item.widget = 'password'
  else if (item.type === 'select') item.widget = 'select'
  else if (item.type === 'boolean') item.widget = 'switch'
  else if (item.widget !== 'textarea') item.widget = 'input'
  emitChange()
}

watch(() => props.modelValue, value => {
  const signature = JSON.stringify(value || {})
  if (signature === pendingModelSignature) {
    pendingModelSignature = null
    return
  }
  pendingModelSignature = null
  syncFromModel()
}, { immediate: true, deep: true })
</script>

<style scoped>
.flow-variable-editor {
  min-height: 0;
}
.variable-workspace {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(280px, 0.85fr);
  gap: 12px;
  min-height: 520px;
}
.variable-list-pane,
.variable-edit-pane {
  min-width: 0;
  padding: 12px;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
  background: #fff;
}
.variable-edit-pane {
  overflow: auto;
  background: var(--app-surface-soft, #f7f8fa);
}
.variable-edit-pane h3 {
  margin: 0 0 10px;
  color: var(--app-fg);
  font-size: 14px;
}
.variable-edit-pane h3 + .n-form + h3 {
  margin-top: 16px;
}
.variable-toolbar {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
  margin-bottom: 10px;
}
.variable-toolbar strong {
  display: block;
  color: var(--app-fg);
  font-size: 14px;
}
.variable-toolbar span {
  color: var(--app-muted);
  font-size: 12px;
  line-height: 1.45;
}
.variable-table {
  display: grid;
  gap: 0;
  margin-bottom: 14px;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
  overflow: hidden;
}
.variable-table__head,
.variable-table__row {
  display: grid;
  grid-template-columns: minmax(80px, 1fr) minmax(100px, 1.1fr) 64px 64px 44px 100px;
  gap: 6px;
  align-items: center;
  padding: 0 8px;
  min-height: 40px;
  text-align: left;
  font-size: 12px;
}
.variable-table__head {
  color: var(--app-muted);
  background: var(--app-surface-soft, #f7f8fa);
  border-bottom: 1px solid var(--app-border);
  font-size: 12px;
  font-weight: 600;
}
.variable-table__row {
  width: 100%;
  border: 0;
  border-bottom: 1px solid var(--app-border);
  background: #fff;
  color: var(--app-fg);
  cursor: pointer;
  font: inherit;
}
.variable-table__row:last-child {
  border-bottom: 0;
}
.variable-table__row:hover,
.variable-table__row--active {
  background: rgba(58, 132, 255, 0.08);
}
.variable-table__row code {
  color: var(--app-accent);
  font-family: var(--app-mono);
  font-size: 12px;
}
.variable-row-actions {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}
.ellipsis {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.system-variable-block {
  display: grid;
  gap: 8px;
}
.system-variable-block__head strong {
  display: block;
  color: var(--app-fg);
  font-size: 13px;
}
.system-variable-block__head span {
  color: var(--app-muted);
  font-size: 12px;
}
.system-variable-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 150px;
  gap: 10px;
  align-items: center;
  padding: 8px 10px;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
  background: #fff;
}
.system-variable-row strong {
  display: block;
  color: var(--app-fg);
  font-size: 13px;
}
.system-variable-row span {
  color: var(--app-muted);
  font-size: 12px;
}
.variable-ref-cell {
  display: grid;
  gap: 2px;
  min-width: 0;
}
.variable-ref-cell code {
  overflow: hidden;
  color: var(--app-accent);
  font-family: var(--app-mono);
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
@media (max-width: 960px) {
  .variable-workspace {
    grid-template-columns: 1fr;
    min-height: 0;
  }
}
</style>
