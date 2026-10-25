<template>
  <n-modal
    preset="card"
    :style="{ width: '960px' }"
    :show="visible"
    title="新建任务"
    :mask-closable="false"
    @update:show="emit('update:visible', $event)"
  >
    <div class="start-workbench">
      <aside class="start-nodes">
        <div class="start-section-head">
          <strong>{{ template?.name || '-' }}</strong>
          <span>{{ isSelectedScope ? '选择本次要执行的节点。' : '全量执行会运行所有节点。' }}</span>
        </div>
        <n-checkbox-group v-model:value="startForm.selectedNodeUuids" class="start-node-list" :disabled="!isSelectedScope">
          <label v-for="node in template?.nodes || []" :key="node.uuid" :class="['start-node-row', { 'start-node-row--disabled': !isSelectedScope }]">
            <n-checkbox :value="node.uuid" :disabled="!isSelectedScope" />
            <span>
              <strong>{{ node.name }}</strong>
              <em>{{ flowNodeTypeText(node.node_type) }} / {{ summarizeFlowNode(node) }}</em>
            </span>
          </label>
        </n-checkbox-group>
      </aside>

      <main class="start-config">
        <n-steps :current="step" size="small" style="margin-bottom: 16px">
          <n-step title="任务信息" />
          <n-step title="全局变量" />
          <n-step title="确认执行" />
        </n-steps>

        <n-form v-show="step === 1" :model="startForm" label-placement="top">
          <n-form-item label="任务名称">
            <n-input v-model:value="startForm.name" :maxlength="200" placeholder="默认使用流水线名称" />
          </n-form-item>
          <n-form-item label="执行范围">
            <n-radio-group v-model:value="startForm.scope" name="flow-start-scope">
              <n-radio-button value="all">全量执行</n-radio-button>
              <n-radio-button value="selected">只执行勾选节点</n-radio-button>
            </n-radio-group>
          </n-form-item>
        </n-form>

        <section v-show="step === 2" class="start-section">
          <div class="start-section-head">
            <strong>全局变量</strong>
            <span>隐藏变量使用模板默认值；系统变量自动注入。</span>
          </div>
          <n-empty v-if="visibleVariables.length === 0" description="当前流水线没有执行时显示的变量" />
          <div v-else class="variable-form-list">
            <div v-for="variable in visibleVariables" :key="variable.key" class="variable-form-row">
              <div class="variable-form-row__label">
                <strong>{{ variable.name }}<em v-if="variable.required"> *</em></strong>
                <span>{{ flowVariableReference(variable.key) }}</span>
              </div>
              <n-input
                v-if="variable.widget === 'textarea'"
                type="textarea"
                v-model:value="startForm.variableValues[variable.key]"
                :placeholder="variable.placeholder || variable.description || variable.key"
                :autosize="{ minRows: 2, maxRows: 5 }"
              />
              <n-input
                v-else-if="variable.widget === 'password' || variable.type === 'secret'"
                type="password"
                show-password-on="click"
                v-model:value="startForm.variableValues[variable.key]"
                :placeholder="variable.placeholder || variable.description || variable.key"
              />
              <FlowIpSelectorField
                v-else-if="variable.widget === 'host_list' || variable.type === 'host_list'"
                v-model="startForm.variableValues[variable.key]"
                :placeholder="variable.placeholder || '选择或填写主机'"
              />
              <n-select
                v-else-if="variable.type === 'select' || variable.widget === 'select'"
                v-model:value="startForm.variableValues[variable.key]"
                :options="(variable.options || []).map(option => ({ label: option, value: option }))"
                :placeholder="variable.placeholder || '请选择'"
                clearable
              />
              <n-switch
                v-else-if="variable.type === 'boolean' || variable.widget === 'switch'"
                :value="Boolean(startForm.variableValues[variable.key])"
                @update:value="value => startForm.variableValues[variable.key] = value"
              />
              <n-input-number
                v-else-if="variable.type === 'number'"
                v-model:value="startForm.variableValues[variable.key]"
                style="width: 100%"
                :placeholder="variable.placeholder || variable.description || variable.key"
              />
              <n-input
                v-else
                v-model:value="startForm.variableValues[variable.key]"
                :placeholder="variable.placeholder || variable.description || variable.key"
              />
            </div>
          </div>
        </section>

        <section v-show="step === 3" class="start-section">
          <div class="start-section-head">
            <strong>确认执行</strong>
            <span>核对任务名称、范围与可见变量后启动。</span>
          </div>
          <n-descriptions label-placement="left" :column="1" size="small" bordered>
            <n-descriptions-item label="任务名称">{{ startForm.name || template?.name || '-' }}</n-descriptions-item>
            <n-descriptions-item label="执行范围">{{ startForm.scope === 'all' ? '全量执行' : `勾选 ${startForm.selectedNodeUuids.length} 个节点` }}</n-descriptions-item>
            <n-descriptions-item label="可见变量">{{ visibleVariables.length }} 个</n-descriptions-item>
          </n-descriptions>
        </section>
      </main>
    </div>
    <template #footer>
      <n-space justify="end">
        <n-button @click="emit('update:visible', false)">取消</n-button>
        <n-button v-if="step > 1" @click="step -= 1">上一步</n-button>
        <n-button v-if="step < 3" type="primary" @click="goNext">下一步</n-button>
        <n-button v-else type="primary" :loading="starting" @click="startFlow">启动执行</n-button>
      </n-space>
    </template>
  </n-modal>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { flowApi } from '@/api/ops'
import type { FlowRun, FlowTemplate } from '@/types'
import FlowIpSelectorField from './FlowIpSelectorField.vue'
import {
  useMessage, NButton, NCheckbox, NCheckboxGroup, NDescriptions, NDescriptionsItem, NEmpty, NForm, NFormItem,
  NInput, NInputNumber, NModal, NRadioButton, NRadioGroup, NSelect, NSpace, NStep, NSteps, NSwitch,
} from 'naive-ui'
import {
  buildStartInputs,
  canStartFlow,
  flowVariableReference,
  flowNodeTypeText,
  normalizeFlowVariables,
  summarizeFlowNode,
  type FlowVariableDefinition,
  type PipelineScope,
} from '../flowUtils'

const message = useMessage()
const props = defineProps<{
  visible: boolean
  template: FlowTemplate | null
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  started: [run: FlowRun]
}>()

const step = ref(1)
const startForm = reactive({
  name: '',
  scope: 'all' as PipelineScope,
  selectedNodeUuids: [] as string[],
  variableValues: {} as Record<string, any>,
})
const starting = ref(false)
const isSelectedScope = computed(() => startForm.scope === 'selected')
const variableDefinitions = computed<FlowVariableDefinition[]>(() => normalizeFlowVariables(props.template?.variables || {}))
const visibleVariables = computed(() => variableDefinitions.value.filter(variable => variable.show_on_start !== false))

const defaultVariableValues = () => Object.fromEntries(variableDefinitions.value.map(variable => {
  const value = variable.default
  if (variable.type === 'host_list') {
    if (Array.isArray(value)) return [variable.key, value.some(item => typeof item === 'number') ? '' : value.join('\n')]
    return [variable.key, value || '']
  }
  return [variable.key, value]
}))

const resetForm = () => {
  const nodes = props.template?.nodes || []
  step.value = 1
  startForm.name = props.template?.name || ''
  startForm.scope = 'all'
  startForm.selectedNodeUuids = nodes.map(node => node.uuid)
  startForm.variableValues = defaultVariableValues()
}

const goNext = () => {
  if (step.value === 1 && !canStartFlow(startForm.scope, startForm.selectedNodeUuids)) {
    message.warning('请至少选择一个执行节点')
    return
  }
  if (step.value === 2) {
    const missingRequired = visibleVariables.value.find(variable => {
      const value = startForm.variableValues[variable.key]
      if (!variable.required) return false
      if (variable.type === 'boolean') return value === undefined || value === null || value === ''
      if (Array.isArray(value)) return value.length === 0
      return value === undefined || value === null || String(value).trim() === ''
    })
    if (missingRequired) {
      message.warning(`请填写必填变量：${missingRequired.name || missingRequired.key}`)
      return
    }
  }
  step.value += 1
}

const startFlow = async () => {
  if (!props.template?.id) return
  if (!canStartFlow(startForm.scope, startForm.selectedNodeUuids)) {
    message.warning('请至少选择一个执行节点')
    return
  }
  starting.value = true
  try {
    const inputs = buildStartInputs({
      scope: startForm.scope,
      selectedNodeUuids: startForm.selectedNodeUuids,
      variableDefinitions: variableDefinitions.value,
      variableValues: startForm.variableValues,
    })
    const run = await flowApi.startTemplate(props.template.id, {
      name: startForm.name.trim(),
      inputs,
    })
    message.success('流水线已启动')
    emit('update:visible', false)
    emit('started', run)
  } catch (error) {
    console.error('启动流水线失败:', error)
    message.error('启动流水线失败，请检查输入变量')
  } finally {
    starting.value = false
  }
}

watch(
  () => [props.visible, props.template?.id],
  ([visible]) => {
    if (visible) resetForm()
  },
  { immediate: true },
)
</script>

<style scoped>
.start-workbench {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  gap: 16px;
  min-height: 420px;
}
.start-nodes,
.start-config {
  min-width: 0;
}
.start-section-head {
  display: grid;
  gap: 4px;
  margin-bottom: 10px;
}
.start-section-head strong { color: var(--app-fg); font-size: 14px; }
.start-section-head span { color: var(--app-muted); font-size: 12px; }
.start-node-list {
  display: grid;
  gap: 6px;
  max-height: 360px;
  overflow: auto;
}
.start-node-row {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 8px;
  align-items: start;
  padding: 8px;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
}
.start-node-row--disabled { opacity: 0.65; }
.start-node-row strong { display: block; font-size: 13px; }
.start-node-row em { color: var(--app-muted); font-size: 12px; font-style: normal; }
.variable-form-list { display: grid; gap: 12px; }
.variable-form-row { display: grid; gap: 6px; }
.variable-form-row__label strong { color: var(--app-fg); font-size: 13px; }
.variable-form-row__label strong em { color: var(--app-danger); font-style: normal; }
.variable-form-row__label span { color: var(--app-accent); font-family: var(--app-mono); font-size: 12px; }
</style>
