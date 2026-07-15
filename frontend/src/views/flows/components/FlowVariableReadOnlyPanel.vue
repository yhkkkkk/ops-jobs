<template>
  <div class="flow-variable-readonly">
    <a-tabs size="small">
      <a-tab-pane key="form" title="只读表单">
        <a-empty v-if="displayRows.length === 0" :description="emptyText" />
        <div v-else class="variable-readonly-table">
          <div class="variable-readonly-table__head">
            <span>变量</span>
            <span>{{ mode === 'value' ? '值' : '类型/控件' }}</span>
            <span>{{ mode === 'value' ? '引用' : '默认/校验' }}</span>
            <span>{{ mode === 'value' ? '说明' : '执行设置' }}</span>
          </div>
          <div v-for="row in displayRows" :key="row.key" class="variable-readonly-table__row">
            <div class="variable-name-cell">
              <strong>{{ row.name }}</strong>
              <code>{{ row.reference }}</code>
              <p v-if="row.description">{{ row.description }}</p>
            </div>
            <span>{{ row.primary }}</span>
            <span>{{ row.secondary }}</span>
            <span>{{ row.flags }}</span>
          </div>
        </div>
      </a-tab-pane>
      <a-tab-pane key="json" title="JSON">
        <pre class="variable-json-block">{{ formattedJson }}</pre>
      </a-tab-pane>
    </a-tabs>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { flowVariableReference, normalizeFlowVariables } from '../flowUtils'

const props = withDefaults(defineProps<{
  variables?: Record<string, any>
  values?: Record<string, any>
  mode?: 'definition' | 'value'
  emptyText?: string
}>(), {
  variables: () => ({}),
  values: () => ({}),
  mode: 'definition',
  emptyText: '暂无变量',
})

const variableDefinitionByKey = computed(() => new Map(
  normalizeFlowVariables(props.variables).map(variable => [variable.key, variable]),
))

const formatValue = (value: any, key = '') => {
  if (value === undefined || value === null || value === '') return '-'
  if (variableDefinitionByKey.value.get(key)?.type === 'host_list') {
    if (Array.isArray(value)) return value.length ? `已解析 ${value.length} 台主机` : '-'
    return '已填写主机变量'
  }
  if (Array.isArray(value)) return value.length ? `已填写 ${value.length} 项` : '-'
  if (typeof value === 'object') return JSON.stringify(value)
  if (typeof value === 'boolean') return value ? '是' : '否'
  return String(value)
}

const definitionRows = computed(() => normalizeFlowVariables(props.variables).map(variable => ({
  key: variable.key,
  name: variable.name || variable.key,
  reference: flowVariableReference(variable.key),
  description: variable.description || '',
  primary: `${variable.type} / ${variable.widget}`,
  secondary: `默认 ${variable.type === 'secret' && variable.has_default ? '已配置' : formatValue(variable.default, variable.key)}${variable.regex ? ` / ${variable.regex}` : ''}`,
  flags: `${variable.required ? '必填' : '选填'} / ${variable.show_on_start !== false ? '执行时显示' : '执行时隐藏'}${variable.placeholder ? ` / ${variable.placeholder}` : ''}`,
})))

const valueRows = computed(() => Object.entries(props.values || {}).filter(([key]) => !key.startsWith('__')).map(([key, value]) => ({
  key,
  name: key,
  reference: flowVariableReference(key),
  description: '',
  primary: formatValue(value, key),
  secondary: flowVariableReference(key),
  flags: '-',
})))

const displayRows = computed(() => props.mode === 'value' ? valueRows.value : definitionRows.value)
const jsonSource = computed(() => props.mode === 'value'
  ? Object.fromEntries(Object.entries(props.values || {})
      .filter(([key]) => !key.startsWith('__'))
      .map(([key, value]) => [key, formatValue(value, key)]))
  : props.variables)
const formattedJson = computed(() => JSON.stringify(jsonSource.value || {}, null, 2))
</script>

<style scoped>
.flow-variable-readonly { min-width: 0; }
.variable-readonly-table {
  display: grid;
  max-height: 520px;
  overflow: auto;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
  background: #fff;
}
.variable-readonly-table__head,
.variable-readonly-table__row {
  display: grid;
  grid-template-columns: minmax(180px, 1.1fr) minmax(120px, .8fr) minmax(160px, 1fr) minmax(160px, 1fr);
  gap: 10px;
  align-items: start;
  min-width: 720px;
  padding: 8px 10px;
}
.variable-readonly-table__head {
  position: sticky;
  top: 0;
  z-index: 1;
  color: var(--app-muted);
  background: var(--app-surface-soft);
  border-bottom: 1px solid var(--app-border);
  font-size: 12px;
}
.variable-readonly-table__row {
  border-bottom: 1px solid var(--app-border);
}
.variable-readonly-table__row:last-child {
  border-bottom: 0;
}
.variable-readonly-table__row > span {
  min-width: 0;
  overflow-wrap: anywhere;
  color: var(--app-fg);
  font-size: 12px;
  line-height: 1.45;
}
.variable-name-cell {
  display: grid;
  gap: 3px;
  min-width: 0;
}
.variable-name-cell strong,
.variable-name-cell code,
.variable-name-cell p {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
}
.variable-name-cell strong {
  color: var(--app-fg);
  font-size: 13px;
  line-height: 1.35;
  white-space: nowrap;
}
.variable-name-cell code {
  color: var(--app-accent);
  font-family: var(--app-mono);
  font-size: 12px;
  white-space: nowrap;
}
.variable-name-cell p {
  margin: 0;
  color: var(--app-muted);
  font-size: 12px;
  line-height: 1.45;
  white-space: nowrap;
}
.variable-json-block {
  min-height: 260px;
  max-height: 520px;
  margin: 0;
  overflow: auto;
  padding: 12px;
  color: var(--app-fg);
  background: var(--app-surface-soft);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
  font-family: var(--app-mono);
  font-size: 12px;
  line-height: 1.55;
}
@media (max-width: 720px) {
  .variable-readonly-table__head,
  .variable-readonly-table__row {
    min-width: 640px;
  }
}
</style>
