<template>
  <a-modal
    :visible="visible"
    title="启动流水线"
    width="940px"
    :confirm-loading="starting"
    ok-text="启动执行"
    @update:visible="emit('update:visible', $event)"
    @ok="startFlow"
  >
    <div class="start-workbench">
      <aside class="start-nodes">
        <div class="start-section-head">
          <strong>{{ template?.name || '-' }}</strong>
          <span>{{ isSelectedScope ? '选择本次要执行的节点，默认按画布连线顺序执行。' : '全量执行会运行所有节点，节点勾选仅在“只执行勾选节点”时生效。' }}</span>
        </div>
        <a-checkbox-group v-model="startForm.selectedNodeUuids" class="start-node-list" :disabled="!isSelectedScope">
          <label v-for="node in template?.nodes || []" :key="node.uuid" :class="['start-node-row', { 'start-node-row--disabled': !isSelectedScope }]">
            <a-checkbox :value="node.uuid" :disabled="!isSelectedScope" />
            <span>
              <strong>{{ node.name }}</strong>
              <em>{{ flowNodeTypeText(node.node_type) }} / {{ summarizeFlowNode(node) }}</em>
            </span>
          </label>
        </a-checkbox-group>
      </aside>

      <main class="start-config">
        <a-form :model="startForm" layout="vertical">
          <a-row :gutter="12">
            <a-col :span="8">
              <a-form-item label="调度 Agent Server" required>
                <a-input-number v-model="startForm.agent_server_id" :min="1" placeholder="Agent Server ID" />
              </a-form-item>
            </a-col>
            <a-col :span="16">
              <a-form-item label="执行范围">
                <a-radio-group v-model="startForm.scope" type="button">
                  <a-radio value="all">全量执行</a-radio>
                  <a-radio value="selected">只执行勾选节点</a-radio>
                </a-radio-group>
              </a-form-item>
            </a-col>
          </a-row>

          <section class="start-section">
            <div class="start-section-head">
              <strong>全局变量</strong>
              <span>启动时注入到 inputs，可覆盖模板变量。</span>
            </div>
            <div class="variable-row-list">
              <div v-for="(variable, index) in startForm.variables" :key="index" class="variable-row">
                <a-input v-model="variable.key" placeholder="变量名，如 env" />
                <a-input v-model="variable.value" placeholder="变量值，如 prod" />
                <a-button size="small" status="danger" :disabled="startForm.variables.length <= 1" @click="removeStartVariable(index)">
                  <template #icon><icon-delete /></template>
                </a-button>
              </div>
              <a-button size="small" @click="addStartVariable">
                <template #icon><icon-plus /></template>
                添加变量
              </a-button>
            </div>
          </section>

          <section class="start-section">
            <div class="start-section-head">
              <strong>节点参数覆盖</strong>
              <span>按需覆盖本次执行参数，不修改模板。</span>
            </div>
            <a-empty v-if="selectedStartNodes.length === 0" description="请至少选择一个执行节点" />
            <a-collapse v-else :bordered="false">
              <a-collapse-item v-for="node in selectedStartNodes" :key="node.uuid" :header="`${node.name} / ${flowNodeTypeText(node.node_type)}`">
                <a-textarea
                  v-model="startForm.nodeOverrides[node.uuid]"
                  :auto-size="{ minRows: 4, maxRows: 8 }"
                  placeholder='{"timeout":600}'
                />
              </a-collapse-item>
            </a-collapse>
          </section>
        </a-form>
      </main>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { Message } from '@arco-design/web-vue'
import { flowApi } from '@/api/ops'
import type { FlowRun, FlowTemplate } from '@/types'
import {
  buildStartInputs,
  canStartFlow,
  flowNodeTypeText,
  summarizeFlowNode,
  type PipelineScope,
  type StartVariable,
} from '../flowUtils'

const props = defineProps<{
  visible: boolean
  template: FlowTemplate | null
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  started: [run: FlowRun]
}>()

const startForm = reactive({
  agent_server_id: 1,
  scope: 'all' as PipelineScope,
  selectedNodeUuids: [] as string[],
  variables: [{ key: 'env', value: 'prod' }] as StartVariable[],
  nodeOverrides: {} as Record<string, string>,
})
const starting = ref(false)
const isSelectedScope = computed(() => startForm.scope === 'selected')

const selectedStartNodes = computed(() => {
  const templateNodes = props.template?.nodes || []
  return templateNodes.filter(node => startForm.selectedNodeUuids.includes(node.uuid))
})

const toStartVariables = (variables: Record<string, any>) => {
  const entries = Object.entries(variables || {})
  if (entries.length === 0) return [{ key: 'env', value: 'prod' }]
  return entries.map(([key, value]) => ({ key, value: typeof value === 'string' ? value : JSON.stringify(value) }))
}

const resetForm = () => {
  const nodes = props.template?.nodes || []
  startForm.agent_server_id = 1
  startForm.scope = 'all'
  startForm.selectedNodeUuids = nodes.map(node => node.uuid)
  startForm.variables = toStartVariables(props.template?.variables || {})
  startForm.nodeOverrides = Object.fromEntries(nodes.map(node => [node.uuid, '{}']))
}

const addStartVariable = () => {
  startForm.variables.push({ key: '', value: '' })
}

const removeStartVariable = (index: number) => {
  if (startForm.variables.length <= 1) return
  startForm.variables.splice(index, 1)
}

const startFlow = async () => {
  if (!props.template?.id) return
  if (!canStartFlow(startForm.scope, startForm.selectedNodeUuids)) {
    Message.warning('请至少选择一个执行节点')
    return
  }

  starting.value = true
  try {
    const inputs = buildStartInputs({
      scope: startForm.scope,
      selectedNodeUuids: startForm.selectedNodeUuids,
      variables: startForm.variables,
      nodes: props.template.nodes || [],
      nodeOverrides: startForm.nodeOverrides,
    })
    const run = await flowApi.startTemplate(props.template.id, {
      agent_server_id: startForm.agent_server_id,
      inputs,
    })
    Message.success('流水线已启动')
    emit('update:visible', false)
    emit('started', run)
  } catch (error) {
    console.error('启动流水线失败:', error)
    Message.error('启动流水线失败，请检查输入变量 JSON')
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
  grid-template-columns: 300px minmax(0, 1fr);
  gap: 14px;
  min-height: 520px;
}
.start-nodes,
.start-config {
  min-height: 0;
  padding: 12px;
  background: var(--app-surface-soft);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
}
.start-nodes { overflow: auto; }
.start-config { overflow: auto; background: #fff; }
.start-section-head {
  display: grid;
  gap: 3px;
  margin-bottom: 10px;
}
.start-section-head strong { color: var(--app-fg); font-size: 14px; line-height: 1.35; }
.start-section-head span { color: var(--app-muted); font-size: 12px; line-height: 1.45; }
.start-node-list { display: grid; gap: 8px; }
.start-node-row {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 8px;
  align-items: flex-start;
  padding: 9px;
  background: #fff;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
  cursor: pointer;
}
.start-node-row--disabled { cursor: default; opacity: .72; }
.start-node-row strong,
.start-node-row em {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.start-node-row strong { color: var(--app-fg); font-size: 13px; line-height: 1.35; }
.start-node-row em { margin-top: 3px; color: var(--app-muted); font-size: 12px; font-style: normal; line-height: 1.4; }
.start-section {
  display: grid;
  gap: 10px;
  padding-top: 12px;
  margin-top: 4px;
  border-top: 1px solid var(--app-border);
}
.variable-row-list { display: grid; gap: 8px; }
.variable-row {
  display: grid;
  grid-template-columns: minmax(120px, .6fr) minmax(180px, 1fr) auto;
  gap: 8px;
  align-items: center;
}
@media (max-width: 720px) {
  .start-workbench { grid-template-columns: 1fr; }
  .variable-row { grid-template-columns: 1fr; }
}
</style>
