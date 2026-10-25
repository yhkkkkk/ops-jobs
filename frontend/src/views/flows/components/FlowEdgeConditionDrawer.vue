<template>
  <n-drawer :show="visible" :width="420" placement="right" @update:show="emit('update:visible', $event)">
    <n-drawer-content title="分支条件" closable>
      <n-form v-if="draft" label-placement="top" size="small" :disabled="readonly">
        <n-alert type="info" :bordered="false" style="margin-bottom: 12px">
          来源 {{ sourceLabel }} → 目标 {{ targetLabel }}
        </n-alert>
        <n-form-item label="默认分支">
          <n-switch v-model:value="draft.default" @update:value="onDefaultChange" />
          <span class="hint">默认分支在其它条件都不匹配时走此边</span>
        </n-form-item>
        <template v-if="!draft.default">
          <n-form-item label="变量路径" required>
            <n-input
              v-model:value="draft.variable"
              placeholder="如 env / inputs.env / outputs.node_uuid.success"
            />
          </n-form-item>
          <n-form-item label="运算符">
            <n-select v-model:value="draft.operator" :options="operatorOptions" />
          </n-form-item>
          <n-form-item v-if="needsValue" label="比较值">
            <n-input v-model:value="draft.value" placeholder="比较值" />
          </n-form-item>
        </template>
        <n-space justify="end">
          <n-button v-if="!readonly" @click="emit('update:visible', false)">取消</n-button>
          <n-button v-if="!readonly" type="primary" @click="save">保存条件</n-button>
        </n-space>
      </n-form>
      <n-empty v-else description="未选中连线" />
    </n-drawer-content>
  </n-drawer>
</template>

<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import { FLOW_EDGE_CONDITION_OPERATORS } from '../flowUtils'
import {
  NAlert, NButton, NDrawer, NDrawerContent, NEmpty, NForm, NFormItem, NInput, NSelect, NSpace, NSwitch, useMessage,
} from 'naive-ui'

const props = defineProps<{
  visible: boolean
  readonly?: boolean
  sourceLabel?: string
  targetLabel?: string
  condition?: Record<string, any> | null
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  save: [condition: Record<string, any>]
}>()

const message = useMessage()
const draft = reactive({
  default: false,
  variable: '',
  operator: 'eq',
  value: '',
})

const operatorOptions = FLOW_EDGE_CONDITION_OPERATORS.map(item => ({ label: item.label, value: item.value }))
const needsValue = computed(() => !['truthy', 'falsy', 'empty', 'not_empty'].includes(draft.operator))

const syncDraft = () => {
  const condition = props.condition || {}
  draft.default = Boolean(condition.default)
  draft.variable = String(condition.variable || condition.left || condition.key || '')
  draft.operator = String(condition.operator || condition.op || 'eq')
  draft.value = condition.value === undefined || condition.value === null ? '' : String(condition.value)
}

watch(() => [props.visible, props.condition], () => {
  if (props.visible) syncDraft()
}, { immediate: true, deep: true })

const onDefaultChange = (value: boolean) => {
  if (value) {
    draft.variable = ''
    draft.operator = 'eq'
    draft.value = ''
  }
}

const save = () => {
  if (draft.default) {
    emit('save', { default: true })
    emit('update:visible', false)
    return
  }
  if (!draft.variable.trim()) {
    message.warning('请填写变量路径')
    return
  }
  const condition: Record<string, any> = {
    variable: draft.variable.trim(),
    operator: draft.operator,
  }
  if (needsValue.value) condition.value = draft.value
  emit('save', condition)
  emit('update:visible', false)
}
</script>

<style scoped>
.hint {
  margin-left: 8px;
  color: var(--app-muted);
  font-size: 12px;
}
</style>
