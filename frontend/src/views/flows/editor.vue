<template>
  <div class="pipeline-editor">
    <header class="editor-command">
      <div class="editor-command__title">
        <a-button size="small" @click="router.push('/flows')">
          <template #icon><icon-left /></template>
        </a-button>
        <div>
          <h1>{{ isEdit ? '编辑流水线' : '新建流水线' }}</h1>
          <p>{{ nodes.length }} 个节点 / {{ edges.length }} 条连线 / {{ form.is_active ? '启用' : '停用' }}</p>
        </div>
      </div>

      <a-form :model="form" layout="inline" class="editor-command__form">
        <a-form-item class="editor-field-name" label="名称" required>
          <a-input v-model="form.name" placeholder="生产发布前置检查" />
        </a-form-item>
        <a-form-item class="editor-field-desc" label="说明">
          <a-input v-model="form.description" placeholder="用途、窗口、负责人" />
        </a-form-item>
        <a-form-item label="状态">
          <a-switch v-model="form.is_active" checked-text="启用" unchecked-text="停用" />
        </a-form-item>
      </a-form>

      <a-space class="editor-command__actions">
        <a-button @click="variablesVisible = true">
          <template #icon><icon-code /></template>
          变量
        </a-button>
        <a-button @click="fitCanvas">
          <template #icon><icon-fullscreen /></template>
          适配
        </a-button>
        <a-button type="primary" :loading="saving" @click="saveTemplate">
          <template #icon><icon-save /></template>
          保存
        </a-button>
      </a-space>
    </header>

    <a-spin :loading="loading" class="editor-spin">
    <section :class="['editor-workbench', { 'editor-workbench--no-selection': !selectedNode }]">
      <FlowNodeLibraryPanel :plugins="plugins" :scenarios="scenarios" @add-node="addNode" @apply-scenario="applyScenario" />

      <main class="canvas-panel">
        <div class="canvas-toolbar">
          <div>
            <h2>流水线画布</h2>
            <p>拖拽左侧插件到画布，节点连线表达执行顺序。</p>
          </div>
          <a-space>
            <a-radio-group v-model="previewMode" type="button" size="small">
              <a-radio v-for="option in previewModeOptions" :key="option.value" :value="option.value">{{ option.label }}</a-radio>
            </a-radio-group>
            <a-button size="small" @click="layoutNodes">
              <template #icon><icon-sort /></template>
              自动排布
            </a-button>
            <a-button size="small" @click="selectFirstInvalidNode">
              <template #icon><icon-search /></template>
              定位问题
            </a-button>
            <a-button size="small" status="danger" :disabled="!selectedNode" @click="removeSelectedNode">
              <template #icon><icon-delete /></template>
              删除节点
            </a-button>
          </a-space>
        </div>

        <div class="validation-strip">
          <div :class="{ ok: validation.missingRequired === 0 }">
            <strong>{{ validation.missingRequired }}</strong>
            <span>缺失必填</span>
          </div>
          <div :class="{ ok: validation.disconnected === 0 }">
            <strong>{{ validation.disconnected }}</strong>
            <span>未连接节点</span>
          </div>
          <div>
            <strong>{{ validation.startNodes }}</strong>
            <span>起始节点</span>
          </div>
          <div :class="{ ok: validation.terminalNodes >= 1 || nodes.length <= 1 }">
            <strong>{{ validation.terminalNodes }}</strong>
            <span>结束节点</span>
          </div>
          <div :class="{ ok: edges.length > 0 || nodes.length <= 1 }">
            <strong>{{ edges.length }}</strong>
            <span>有效连线</span>
          </div>
          <div :class="{ ok: validation.invalidEdges === 0 }">
            <strong>{{ validation.invalidEdges }}</strong>
            <span>异常连线</span>
          </div>
        </div>

        <div class="flow-canvas" @dragover.prevent="handleCanvasDragOver" @drop.prevent="handleCanvasDrop">
          <VueFlow
            :nodes="flowNodes"
            :edges="flowEdges"
            :default-edge-options="defaultEdgeOptions"
            :min-zoom="0.35"
            :max-zoom="1.6"
            fit-view-on-init
            elevate-edges-on-select
            class="ops-flow"
            @node-click="handleFlowNodeClick"
            @node-drag-stop="handleNodeDragStop"
            @connect="handleConnect"
          >
            <Background :gap="24" :size="1" pattern-color="#d8dee9" />
            <Controls position="bottom-left" />
            <MiniMap pannable zoomable node-color="#dbe7f6" mask-color="rgba(247, 248, 250, 0.76)" />

            <template #node-ops="{ data }">
              <div :class="['ops-node-card', `ops-node-card--${data.status}`, { 'ops-node-card--selected': data.selected }]">
                <Handle type="target" :position="Position.Left" />
                <div class="ops-node-card__top">
                  <span><component :is="data.icon" />{{ data.typeText }}</span>
                  <StatusBadge :status="data.status" :text="data.statusText" />
                </div>
                <strong>{{ data.label }}</strong>
                <em>{{ data.summary }}</em>
                <small>{{ data.roleText }} / {{ data.policyText }}</small>
                <Handle type="source" :position="Position.Right" />
              </div>
            </template>
          </VueFlow>

          <div v-if="nodes.length === 0" class="canvas-empty">
            <icon-branch />
            <p>拖拽左侧节点到画布，或点击节点快速添加</p>
          </div>
        </div>

        <div class="canvas-footer">
          <span>Vue Flow 画布 / 拖拽节点、连线、框选检查</span>
          <span>{{ nodes.length }} nodes / {{ edges.length }} edges / {{ previewModeText }}</span>
        </div>
      </main>

      <aside v-if="selectedNode" class="property-panel">
        <div class="workbench-panel-head">
          <div>
            <h2>节点配置</h2>
            <p>{{ `${selectedNode.name} / ${nodeTypeText(selectedNode.node_type)}` }}</p>
          </div>
          <StatusBadge :status="previewStatus(selectedNode)" :text="previewStatusText(previewStatus(selectedNode))" />
        </div>

        <a-alert v-if="!selectedNodeSupported" type="warning" class="unsupported-node-alert">
          当前前端只支持脚本执行、文件分发、作业执行方案、人工确认、条件分支、并行网关和汇聚网关节点；此节点会保持原配置，请后续补齐对应插件编辑器。
        </a-alert>

        <a-form v-else :model="selectedNode" layout="vertical" class="node-form">
          <div class="node-quick-actions">
            <a-button size="small" @click="duplicateSelectedNode">
              <template #icon><icon-copy /></template>
              复制节点
            </a-button>
            <a-radio-group v-model="selectedPreviewStatus" type="button" size="small">
              <a-radio v-for="option in previewStatusOptions" :key="option.value" :value="option.value">{{ option.label }}</a-radio>
            </a-radio-group>
          </div>
          <a-form-item label="节点名称" required>
            <a-input v-model="selectedNode.name" />
          </a-form-item>
          <a-form-item label="节点类型">
            <a-select v-model="selectedNode.node_type" @change="resetNodeConfig(selectedNode)">
              <a-option v-for="plugin in plugins" :key="plugin.type" :value="plugin.type">{{ plugin.name }}</a-option>
            </a-select>
          </a-form-item>
          <a-form-item label="失败策略">
            <a-radio-group v-model="selectedNode.config.failure_policy" type="button">
              <a-radio v-for="option in failurePolicyOptions" :key="option.value" :value="option.value">{{ option.label }}</a-radio>
            </a-radio-group>
          </a-form-item>

          <template v-if="selectedNode.node_type === 'script'">
            <a-row :gutter="10">
              <a-col :span="12">
                <a-form-item label="脚本类型">
                  <a-select v-model="selectedNode.config.script_type">
                    <a-option value="shell">Shell</a-option>
                    <a-option value="python">Python</a-option>
                    <a-option value="powershell">PowerShell</a-option>
                  </a-select>
                </a-form-item>
              </a-col>
              <a-col :span="12">
                <a-form-item label="超时秒数">
                  <a-input-number v-model="selectedNode.config.timeout" :min="1" />
                </a-form-item>
              </a-col>
            </a-row>
            <a-form-item label="目标主机">
              <a-select v-model="selectedNode.config.target_host_ids" multiple allow-search placeholder="选择目标主机">
                <a-option v-for="host in hosts" :key="host.id" :value="host.id">{{ host.name }} {{ host.ip_address || host.internal_ip || host.public_ip }}</a-option>
              </a-select>
            </a-form-item>
            <a-form-item label="脚本内容" required>
              <div class="field-hint">写入后端字段 script_content，按脚本类型高亮。</div>
              <SimpleMonacoEditor
                v-model="selectedNode.config.script_content"
                class="script-monaco-editor"
                :language="scriptEditorLanguage"
                theme="vs"
                :height="230"
              />
            </a-form-item>
          </template>

          <template v-else-if="selectedNode.node_type === 'file_transfer'">
            <a-form-item label="目标主机">
              <a-select v-model="selectedNode.config.target_host_ids" multiple allow-search placeholder="选择目标主机">
                <a-option v-for="host in hosts" :key="host.id" :value="host.id">{{ host.name }} {{ host.ip_address || host.internal_ip || host.public_ip }}</a-option>
              </a-select>
            </a-form-item>
            <a-row :gutter="10">
              <a-col :span="12">
                <a-form-item label="超时秒数">
                  <a-input-number v-model="selectedNode.config.timeout" :min="1" />
                </a-form-item>
              </a-col>
              <a-col :span="12">
                <a-form-item label="限速 MB/s">
                  <a-input-number v-model="selectedNode.config.bandwidth_limit" :min="0" />
                </a-form-item>
              </a-col>
            </a-row>
            <a-form-item label="文件来源" required>
              <div class="field-hint">每个来源会保存为 file_sources 数组项。</div>
              <div class="file-source-list">
                <div v-for="(source, index) in selectedNode.config.file_sources" :key="index" class="file-source-row">
                  <a-input v-model="source.download_url" placeholder="下载地址 download_url" />
                  <a-input v-model="source.remote_path" placeholder="远端路径 remote_path" />
                  <a-button size="small" status="danger" :disabled="selectedNode.config.file_sources.length <= 1" @click="removeFileSource(index)">
                    <template #icon><icon-delete /></template>
                  </a-button>
                </div>
                <a-button size="small" @click="addFileSource">
                  <template #icon><icon-plus /></template>
                  添加文件来源
                </a-button>
              </div>
            </a-form-item>
          </template>

          <template v-else-if="selectedNode.node_type === 'job_plan'">
            <a-form-item label="作业执行方案" required>
              <a-select v-model="selectedNode.config.execution_plan_id" allow-search placeholder="选择作业执行方案">
                <a-option v-for="plan in executionPlans" :key="plan.id" :value="plan.id">{{ plan.name }}</a-option>
              </a-select>
            </a-form-item>
            <a-form-item label="执行模式">
              <a-radio-group v-model="selectedNode.config.execution_mode" type="button">
                <a-radio v-for="option in executionModeOptions" :key="option.value" :value="option.value">{{ option.label }}</a-radio>
              </a-radio-group>
            </a-form-item>
            <a-row v-if="selectedNode.config.execution_mode === 'rolling'" :gutter="10">
              <a-col :span="12">
                <a-form-item label="滚动批次">
                  <a-input-number v-model="selectedNode.config.rolling_batch_size" :min="1" />
                </a-form-item>
              </a-col>
              <a-col :span="12">
                <a-form-item label="批次延迟秒">
                  <a-input-number v-model="selectedNode.config.rolling_batch_delay" :min="0" />
                </a-form-item>
              </a-col>
            </a-row>
            <a-form-item label="执行参数 JSON">
              <div class="field-hint">保存到 execution_parameters，用于覆盖执行方案变量。</div>
              <a-textarea v-model="selectedNode.config.execution_parameters_text" :auto-size="{ minRows: 9, maxRows: 16 }" />
            </a-form-item>
          </template>

          <template v-else-if="selectedNode.node_type === 'sub_process'">
            <a-form-item label="子流程模板" required>
              <a-select v-model="selectedNode.config.template_id" allow-search placeholder="选择要嵌套执行的流水线模板">
                <a-option v-for="template in availableSubProcessTemplates" :key="template.id" :value="template.id">{{ template.name }}</a-option>
              </a-select>
              <a-empty v-if="availableSubProcessTemplates.length === 0" class="inline-empty" description="暂无可用子流程模板" />
            </a-form-item>
            <a-row :gutter="10">
              <a-col :span="12">
                <a-form-item label="输入继承">
                  <a-switch v-model="selectedNode.config.inherit_inputs" checked-text="继承" unchecked-text="独立" />
                </a-form-item>
              </a-col>
              <a-col :span="12">
                <a-form-item label="超时秒数">
                  <a-input-number v-model="selectedNode.config.timeout" :min="1" />
                </a-form-item>
              </a-col>
            </a-row>
            <a-form-item label="子流程输入 JSON">
              <div class="field-hint">保存到 inputs；开启继承时会与父流程输入合并，显式字段优先。</div>
              <a-textarea v-model="selectedNode.config.inputs_text" :auto-size="{ minRows: 8, maxRows: 14 }" />
            </a-form-item>
            <div class="sub-process-hint">
              <strong>执行语义</strong>
              <span>该节点会创建子流程实例，等待子流程结束后把 child_flow_run_id 和子流程输出写回当前节点。</span>
            </div>
          </template>

          <template v-else-if="selectedNode.node_type === 'manual'">
            <a-form-item label="确认说明">
              <a-textarea
                v-model="selectedNode.config.instructions"
                :auto-size="{ minRows: 4, maxRows: 8 }"
                placeholder="例如：确认变更窗口、灰度检查或外部审批完成后继续"
              />
            </a-form-item>
          </template>

          <template v-else-if="selectedNode.node_type === 'condition'">
            <a-form-item label="分支说明">
              <a-textarea
                v-model="selectedNode.config.description"
                :auto-size="{ minRows: 3, maxRows: 6 }"
                placeholder="例如：按 env / region / success_count 选择后续分支"
              />
            </a-form-item>
          </template>

          <div class="node-summary">
            <span>配置摘要</span>
            <p>{{ nodeConfigSummary(selectedNode) }}</p>
          </div>
        </a-form>

        <div class="edge-list">
          <div class="edge-list__head">
            <h3>连线清单</h3>
            <span>{{ edges.length }} 条</span>
          </div>
          <a-empty v-if="edges.length === 0" description="拖拽节点连接点创建连线" />
          <div v-else class="edge-row-list">
            <div v-for="edge in edges" :key="`${edge.source_uuid}-${edge.target_uuid}`" class="edge-row">
              <span>{{ nodeName(edge.source_uuid) }}</span>
              <icon-arrow-right />
              <span>{{ nodeName(edge.target_uuid) }}</span>
              <a-button size="mini" type="text" status="danger" @click="removeEdge(edge)">
                <template #icon><icon-delete /></template>
              </a-button>
              <div v-if="isConditionSource(edge)" class="edge-condition">
                <a-checkbox v-model="edge.condition.default">默认分支</a-checkbox>
                <template v-if="!edge.condition.default">
                  <a-input v-model="edge.condition.variable" size="small" placeholder="变量，如 inputs.env" />
                  <a-select v-model="edge.condition.operator" size="small" placeholder="判断">
                    <a-option v-for="option in conditionOperatorOptions" :key="option.value" :value="option.value">{{ option.label }}</a-option>
                  </a-select>
                  <a-input v-model="edge.condition.value" size="small" placeholder="期望值" />
                </template>
                <span>{{ edgeConditionSummary(edge) }}</span>
              </div>
            </div>
          </div>
        </div>
      </aside>
    </section>
    </a-spin>

    <a-modal v-model:visible="variablesVisible" title="流水线变量 JSON" @ok="saveVariables">
      <a-textarea v-model="variablesText" :auto-size="{ minRows: 8, maxRows: 16 }" />
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import '@vue-flow/controls/dist/style.css'
import '@vue-flow/minimap/dist/style.css'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { MiniMap } from '@vue-flow/minimap'
import { Handle, Position, VueFlow, useVueFlow } from '@vue-flow/core'
import type { Edge, Node } from '@vue-flow/core'
import { executionPlanApi, flowApi, hostApi } from '@/api/ops'
import type { ExecutionPlan, FlowEdge, FlowNode, FlowNodePlugin, FlowNodeType, FlowTemplate, Host } from '@/types'
import { StatusBadge } from '@/components/app'
import SimpleMonacoEditor from '@/components/SimpleMonacoEditor.vue'
import FlowNodeLibraryPanel, { type FlowNodePluginOption, type FlowScenarioOption } from './components/FlowNodeLibraryPanel.vue'
import {
  createsCycle as createsFlowCycle,
  evaluateFlowGraph,
  flowNodeTypeText,
  isSupportedFlowNodeType,
  isNodeReady,
  normalizeFlowNode,
  parseFileSources,
  serializeFlowNode,
  summarizeEdgeCondition,
  summarizeFlowNode,
  type SupportedFlowNodeType,
} from './flowUtils'

type PreviewStatus = 'pending' | 'running' | 'success' | 'failed' | 'paused'
type EditorFlowEdge = FlowEdge & { condition: Record<string, any> }

const route = useRoute()
const router = useRouter()
const { fitView, project } = useVueFlow()
const saving = ref(false)
const loading = ref(false)
const variablesVisible = ref(false)
const variablesText = ref('{}')
const selectedUuid = ref('')
const previewMode = ref('template')
const previewOverrides = ref<Record<string, PreviewStatus>>({})
const hosts = ref<Host[]>([])
const executionPlans = ref<ExecutionPlan[]>([])
const flowTemplates = ref<FlowTemplate[]>([])
const nodes = ref<FlowNode[]>([])
const edges = ref<EditorFlowEdge[]>([])

const form = reactive({ name: '', description: '', variables: {} as Record<string, any>, is_active: true })
const fallbackPlugins: FlowNodePluginOption[] = [
  { type: 'script' as SupportedFlowNodeType, name: '脚本执行', description: '脚本类型、目标主机、超时和脚本内容', category: '主机原子', risk: '高频', icon: 'icon-code' },
  { type: 'file_transfer' as SupportedFlowNodeType, name: '文件分发', description: '下载地址、远端路径、目标主机和限速', category: '文件原子', risk: '变更', icon: 'icon-upload' },
  { type: 'job_plan' as SupportedFlowNodeType, name: '作业执行方案', description: '执行方案、参数覆盖、并行/串行/滚动', category: '作业平台', risk: '异步', icon: 'icon-calendar' },
  { type: 'manual' as SupportedFlowNodeType, name: '人工确认', description: '暂停流程，人工检查通过后继续', category: '控制节点', risk: '人工', icon: 'icon-check-circle' },
  { type: 'condition' as SupportedFlowNodeType, name: '条件分支', description: '按输入变量或节点输出选择后续分支', category: '控制节点', risk: '路由', icon: 'icon-branch' },
  { type: 'parallel' as SupportedFlowNodeType, name: '并行网关', description: '同时启动所有下游分支', category: '控制节点', risk: '并发', icon: 'icon-share-alt' },
  { type: 'join' as SupportedFlowNodeType, name: '汇聚网关', description: '等待所有活跃上游完成后继续', category: '控制节点', risk: '汇聚', icon: 'icon-merge-cells' },
  { type: 'sub_process' as SupportedFlowNodeType, name: '子流程', description: '嵌套执行另一个流水线模板并等待结果', category: '流程控制', risk: '嵌套', icon: 'icon-branch' },
]
const plugins = ref<FlowNodePluginOption[]>(fallbackPlugins)
const scenarios: FlowScenarioOption[] = [
  { key: 'release' as const, name: '发布前检查', description: '脚本检查 -> 文件分发 -> 作业方案' },
  { key: 'dispatch' as const, name: '批量文件分发', description: '文件分发 -> 作业方案验收' },
]
const previewModeOptions = [{ label: '模板', value: 'template' }, { label: '状态预览', value: 'preview' }]
const previewStatusOptions = [
  { label: '待执行', value: 'pending' },
  { label: '执行中', value: 'running' },
  { label: '成功', value: 'success' },
  { label: '失败', value: 'failed' },
  { label: '暂停', value: 'paused' },
]
const failurePolicyOptions = [{ label: '失败停止', value: 'stop' }, { label: '忽略继续', value: 'ignore' }, { label: '暂停处理', value: 'pause' }]
const executionModeOptions = [{ label: '并行', value: 'parallel' }, { label: '串行', value: 'serial' }, { label: '滚动', value: 'rolling' }]
const conditionOperatorOptions = [
  { label: '等于', value: 'eq' },
  { label: '不等于', value: 'ne' },
  { label: '大于', value: 'gt' },
  { label: '大于等于', value: 'gte' },
  { label: '小于', value: 'lt' },
  { label: '小于等于', value: 'lte' },
  { label: '包含', value: 'contains' },
  { label: '不包含', value: 'not_contains' },
  { label: '为真', value: 'truthy' },
  { label: '为假', value: 'falsy' },
  { label: '为空', value: 'empty' },
  { label: '不为空', value: 'not_empty' },
]
const defaultEdgeOptions = { type: 'smoothstep', animated: false, style: { stroke: 'var(--app-accent)', strokeWidth: 2 } }
const fallbackPluginMap = new Map(fallbackPlugins.map(plugin => [plugin.type, plugin]))

const mergeNodePlugins = (backendPlugins: FlowNodePlugin[] = []) => {
  const merged = [...fallbackPlugins]
  backendPlugins.forEach(plugin => {
    if (!isSupportedFlowNodeType(plugin.type)) return
    const fallback = fallbackPluginMap.get(plugin.type)
    const option: FlowNodePluginOption = {
      type: plugin.type,
      name: plugin.name || fallback?.name || plugin.type,
      description: plugin.description || fallback?.description || '',
      category: plugin.category || fallback?.category || '插件节点',
      risk: fallback?.risk || '插件',
      icon: fallback?.icon || 'icon-branch',
    }
    const index = merged.findIndex(item => item.type === plugin.type)
    if (index >= 0) merged[index] = option
    else merged.push(option)
  })
  return merged
}

const isEdit = computed(() => Boolean(route.params.id))
const currentTemplateId = computed(() => Number(route.params.id || 0))
const selectedNode = computed(() => nodes.value.find(item => item.uuid === selectedUuid.value) || null)
const selectedNodeSupported = computed(() => Boolean(selectedNode.value && isSupportedFlowNodeType(selectedNode.value.node_type)))
const availableSubProcessTemplates = computed(() =>
  flowTemplates.value.filter(template => template.id && template.id !== currentTemplateId.value && template.is_active !== false)
)
const scriptEditorLanguage = computed(() => {
  const type = selectedNode.value?.config.script_type
  if (type === 'python') return 'python'
  if (type === 'powershell') return 'powershell'
  return 'shell'
})
const selectedPreviewStatus = computed<PreviewStatus>({
  get: () => selectedNode.value ? previewStatus(selectedNode.value) : 'pending',
  set: value => {
    if (!selectedNode.value) return
    previewMode.value = 'preview'
    previewOverrides.value = { ...previewOverrides.value, [selectedNode.value.uuid]: value }
  },
})
const validation = computed(() => {
  return evaluateFlowGraph(nodes.value, edges.value)
})
const previewModeText = computed(() => previewMode.value === 'preview' ? '状态预览' : '模板编辑')

const flowNodes = computed<Node[]>(() => nodes.value.map((node, index) => {
  const status = previewStatus(node, index)
  return {
    id: node.uuid,
    type: 'ops',
    position: { x: Number(node.position?.x ?? 0), y: Number(node.position?.y ?? 0) },
    data: {
      label: node.name,
      icon: isSupportedFlowNodeType(node.node_type) ? pluginMeta(node.node_type)?.icon : 'icon-branch',
      typeText: nodeTypeText(node.node_type),
      summary: nodeConfigSummary(node),
      roleText: nodeRoleText(node.uuid),
      policyText: failurePolicyText(node.config?.failure_policy),
      selected: selectedUuid.value === node.uuid,
      status,
      statusText: previewStatusText(status),
    },
  }
}))

const flowEdges = computed<Edge[]>(() => edges.value.filter(edge => edge.source_uuid && edge.target_uuid).map(edge => ({
  id: `${edge.source_uuid}-${edge.target_uuid}`,
  source: edge.source_uuid!,
  target: edge.target_uuid!,
  type: 'smoothstep',
  markerEnd: 'arrowclosed',
  style: { stroke: 'var(--app-accent)', strokeWidth: 2 },
})))

const pluginMeta = (type: SupportedFlowNodeType) => plugins.value.find(item => item.type === type)
const nodeTypeText = (type: FlowNodeType) => flowNodeTypeText(type)
const failurePolicyText = (policy?: string) => ({ stop: '失败停止', ignore: '忽略继续', pause: '暂停处理' }[policy || 'stop'] || '失败停止')
const previewStatusText = (status: PreviewStatus) => ({ pending: '待执行', running: '执行中', success: '成功', failed: '失败', paused: '暂停' }[status])
const nodeRoleText = (uuid: string) => {
  const hasIncoming = edges.value.some(edge => edge.target_uuid === uuid)
  const hasOutgoing = edges.value.some(edge => edge.source_uuid === uuid)
  if (!hasIncoming && hasOutgoing) return '起始节点'
  if (hasIncoming && !hasOutgoing) return '结束节点'
  if (!hasIncoming && !hasOutgoing) return nodes.value.length <= 1 ? '单节点' : '孤立节点'
  return '中间节点'
}
const previewStatus = (node: FlowNode, index = nodes.value.findIndex(item => item.uuid === node.uuid)): PreviewStatus => {
  if (previewMode.value !== 'preview') return 'pending'
  if (previewOverrides.value[node.uuid]) return previewOverrides.value[node.uuid]
  if (index === 0) return 'success'
  if (node.node_type === 'job_plan' || node.node_type === 'manual' || node.node_type === 'condition') return 'running'
  return 'pending'
}

const nodeReady = (node: FlowNode) => isNodeReady(node)
const nodeConfigSummary = (node: FlowNode) => summarizeFlowNode(node)

const defaultConfig = (type: SupportedFlowNodeType) => {
  if (type === 'script') {
    return { script_type: 'shell', script_content: 'hostname && systemctl is-active ops-agent', target_host_ids: [], timeout: 300, failure_policy: 'stop' }
  }
  if (type === 'file_transfer') {
    const sources = [{ download_url: 'https://artifact.local/releases/app.tar.gz', remote_path: '/data/releases/current/app.tar.gz' }]
    return { target_host_ids: [], timeout: 600, bandwidth_limit: 200, file_sources: sources, failure_policy: 'stop' }
  }
  if (type === 'manual') {
    return { instructions: '确认检查项完成后继续执行', failure_policy: 'pause' }
  }
  if (type === 'condition') {
    return { description: '按输入变量选择后续分支', failure_policy: 'stop' }
  }
  if (type === 'parallel') {
    return { description: '并行启动所有下游分支', failure_policy: 'stop' }
  }
  if (type === 'join') {
    return { description: '等待所有活跃上游分支完成后继续', failure_policy: 'stop' }
  }
  if (type === 'sub_process') {
    return {
      template_id: availableSubProcessTemplates.value[0]?.id,
      inherit_inputs: true,
      inputs: {},
      inputs_text: '{}',
      timeout: 3600,
      failure_policy: 'pause',
    }
  }
  return {
    execution_plan_id: executionPlans.value[0]?.id,
    execution_parameters: { env: 'prod' },
    execution_parameters_text: JSON.stringify({ env: 'prod' }, null, 2),
    execution_mode: 'parallel',
    rolling_batch_size: 1,
    rolling_batch_delay: 30,
    failure_policy: 'pause',
  }
}

const normalizeNode = (node: FlowNode) => normalizeFlowNode(node)
const normalizeEdge = (edge: FlowEdge): EditorFlowEdge => ({ ...edge, condition: edge.condition || {} })

const addNode = (type: SupportedFlowNodeType, position?: { x: number; y: number }, autoConnect = true) => {
  const index = nodes.value.length
  const uuid = `node-${Date.now()}-${index}`
  const node: FlowNode = {
    uuid,
    name: pluginMeta(type)?.name || '新节点',
    node_type: type,
    config: defaultConfig(type),
    position: position || { x: 80 + index * 260, y: index % 2 ? 270 : 120 },
  }
  const previous = nodes.value[index - 1]
  nodes.value.push(node)
  if (autoConnect && previous) edges.value.push(normalizeEdge({ source_uuid: previous.uuid, target_uuid: uuid, condition: {} }))
  selectedUuid.value = uuid
  if (!position) nextTick(fitCanvas)
}

const createScenarioNode = (type: SupportedFlowNodeType, index: number, name: string, configPatch: Record<string, any> = {}): FlowNode => {
  const config = { ...defaultConfig(type), ...configPatch }
  return {
    uuid: `node-${Date.now()}-${type}-${index}`,
    name,
    node_type: type,
    config,
    position: { x: 80 + index * 280, y: index % 2 ? 260 : 110 },
  }
}

const applyScenario = (key: 'release' | 'dispatch') => {
  const scenarioNodes = key === 'release'
    ? [
        createScenarioNode('script', 0, '发布前主机检查', { script_content: 'hostname && df -h && systemctl is-active ops-agent' }),
        createScenarioNode('file_transfer', 1, '分发发布包', {}),
        createScenarioNode('job_plan', 2, '执行发布方案', { execution_mode: 'rolling', rolling_batch_size: 2, rolling_batch_delay: 60 }),
      ]
    : [
        createScenarioNode('file_transfer', 0, '批量分发配置包', { bandwidth_limit: 120 }),
        createScenarioNode('job_plan', 1, '远端校验文件', { execution_mode: 'parallel', failure_policy: 'stop' }),
      ]
  nodes.value = scenarioNodes
  edges.value = scenarioNodes.slice(1).map((node, index) => normalizeEdge({
    source_uuid: scenarioNodes[index].uuid,
    target_uuid: node.uuid,
    condition: {},
  }))
  selectedUuid.value = ''
  previewOverrides.value = {}
  nextTick(fitCanvas)
}

const resetNodeConfig = (node: FlowNode) => {
  if (!isSupportedFlowNodeType(node.node_type)) {
    Message.warning('当前节点类型暂不支持在前端编辑')
    return
  }
  node.config = defaultConfig(node.node_type)
}

const removeSelectedNode = () => {
  if (!selectedUuid.value) return
  nodes.value = nodes.value.filter(node => node.uuid !== selectedUuid.value)
  edges.value = edges.value.filter(edge => edge.source_uuid !== selectedUuid.value && edge.target_uuid !== selectedUuid.value)
  const nextOverrides = { ...previewOverrides.value }
  delete nextOverrides[selectedUuid.value]
  previewOverrides.value = nextOverrides
  selectedUuid.value = ''
}

const duplicateSelectedNode = () => {
  if (!selectedNode.value) return
  const base = selectedNode.value
  const uuid = `node-${Date.now()}-copy`
  const clone: FlowNode = {
    ...base,
    id: undefined,
    uuid,
    name: `${base.name} 副本`,
    config: JSON.parse(JSON.stringify(base.config || {})),
    position: { x: Number(base.position?.x || 0) + 260, y: Number(base.position?.y || 0) + 40 },
  }
  nodes.value.push(clone)
  edges.value.push(normalizeEdge({ source_uuid: base.uuid, target_uuid: uuid, condition: {} }))
  selectedUuid.value = uuid
  nextTick(fitCanvas)
}

const addFileSource = () => {
  if (!selectedNode.value || selectedNode.value.node_type !== 'file_transfer') return
  const sources = parseFileSources(selectedNode.value.config.file_sources_text, selectedNode.value.config.file_sources)
  selectedNode.value.config.file_sources = [...sources, { download_url: '', remote_path: '' }]
}

const removeFileSource = (index: number) => {
  if (!selectedNode.value || selectedNode.value.node_type !== 'file_transfer') return
  const sources = parseFileSources(selectedNode.value.config.file_sources_text, selectedNode.value.config.file_sources)
  if (sources.length <= 1) return
  selectedNode.value.config.file_sources = sources.filter((_, sourceIndex) => sourceIndex !== index)
}

const handleFlowNodeClick = ({ node }: { node: Node }) => {
  selectedUuid.value = node.id
}

const handleNodeDragStop = ({ node }: { node: Node }) => {
  const current = nodes.value.find(item => item.uuid === node.id)
  if (current) current.position = { x: node.position.x, y: node.position.y }
}

const handleCanvasDragOver = (event: DragEvent) => {
  if (event.dataTransfer) event.dataTransfer.dropEffect = 'copy'
}

const handleCanvasDrop = (event: DragEvent) => {
  const rawType = event.dataTransfer?.getData('application/x-flow-node-type') || event.dataTransfer?.getData('text/plain')
  if (!isSupportedFlowNodeType(rawType)) return

  const rect = (event.currentTarget as HTMLElement).getBoundingClientRect()
  const position = project({
    x: event.clientX - rect.left,
    y: event.clientY - rect.top,
  })
  addNode(rawType, { x: Math.max(0, position.x - 110), y: Math.max(0, position.y - 36) }, false)
}

const handleConnect = (connection: { source?: string | null; target?: string | null }) => {
  if (!connection.source || !connection.target || connection.source === connection.target) return
  const exists = edges.value.some(edge => edge.source_uuid === connection.source && edge.target_uuid === connection.target)
  if (exists) {
    Message.warning('这条连线已经存在')
    return
  }
  if (createsFlowCycle(edges.value, connection.source, connection.target)) {
    Message.warning('流水线不允许形成环路')
    return
  }
  edges.value.push(normalizeEdge({ source_uuid: connection.source, target_uuid: connection.target, condition: {} }))
}

const nodeName = (uuid?: string) => nodes.value.find(node => node.uuid === uuid)?.name || '-'
const isConditionSource = (edge: FlowEdge) => nodes.value.find(node => node.uuid === edge.source_uuid)?.node_type === 'condition'
const edgeConditionSummary = (edge: EditorFlowEdge) => summarizeEdgeCondition(edge.condition)

const removeEdge = (edge: FlowEdge) => {
  edges.value = edges.value.filter(item => !(item.source_uuid === edge.source_uuid && item.target_uuid === edge.target_uuid))
}

const layoutNodes = () => {
  nodes.value = nodes.value.map((node, index) => ({ ...node, position: { x: 80 + index * 260, y: index % 2 ? 270 : 120 } }))
  nextTick(fitCanvas)
}

const selectFirstInvalidNode = () => {
  const incoming = new Set(edges.value.map(edge => edge.target_uuid))
  const outgoing = new Set(edges.value.map(edge => edge.source_uuid))
  const invalid = nodes.value.find(node => !nodeReady(node))
    || nodes.value.find(node => nodes.value.length > 1 && !incoming.has(node.uuid) && !outgoing.has(node.uuid))
  if (invalid) {
    selectedUuid.value = invalid.uuid
    Message.warning(`已定位：${invalid.name}`)
    return
  }
  if (nodes.value.length > 1 && validation.value.startNodes !== 1) {
    Message.warning('请保留一个明确的起始节点')
    return
  }
  if (nodes.value.length > 1 && validation.value.terminalNodes < 1) {
    Message.warning('请至少保留一个结束节点')
    return
  }
  Message.success('当前拓扑和必填配置检查通过')
}

const fitCanvas = () => {
  nextTick(() => fitView({ padding: 0.18, duration: 220 }))
}

const saveVariables = () => {
  try {
    form.variables = JSON.parse(variablesText.value || '{}')
  } catch {
    Message.error('变量 JSON 格式不正确')
  }
}

const loadData = async () => {
  loading.value = true
  try {
    const [hostList, planList, templateList] = await Promise.all([
      hostApi.getHosts({ page_size: 200 }),
      executionPlanApi.getPlans({ page_size: 200 }),
      flowApi.getTemplates(),
    ])
    hosts.value = Array.isArray(hostList) ? hostList : hostList.results
    executionPlans.value = Array.isArray(planList) ? planList : planList.results
    flowTemplates.value = templateList
    try {
      plugins.value = mergeNodePlugins(await flowApi.getNodePlugins())
    } catch (pluginError) {
      console.warn('加载流水线节点插件失败，已使用内置插件元数据:', pluginError)
      plugins.value = fallbackPlugins
    }
    if (isEdit.value) {
      const template = await flowApi.getTemplate(Number(route.params.id))
      form.name = template.name
      form.description = template.description || ''
      form.variables = template.variables || {}
      form.is_active = template.is_active
      variablesText.value = JSON.stringify(form.variables, null, 2)
      nodes.value = template.nodes.map(normalizeNode)
      const nodeUuids = new Set(nodes.value.map(node => node.uuid))
      const validEdges = (template.edges || []).filter(edge =>
        Boolean(edge.source_uuid && edge.target_uuid && nodeUuids.has(edge.source_uuid) && nodeUuids.has(edge.target_uuid))
      )
      if (validEdges.length !== (template.edges || []).length) {
        Message.warning('已忽略指向不存在节点的异常连线')
      }
      edges.value = validEdges.map(normalizeEdge)
      previewOverrides.value = {}
      selectedUuid.value = ''
    } else if (nodes.value.length === 0) {
      form.name = '新建运维流水线'
      form.description = '串联脚本执行、文件分发和作业执行方案。'
    }
    nextTick(fitCanvas)
  } catch (error) {
    console.error('加载流水线编辑数据失败:', error)
    Message.error('加载流水线编辑数据失败')
  } finally {
    loading.value = false
  }
}

const saveTemplate = async () => {
  if (!form.name.trim()) {
    Message.warning('请填写流水线名称')
    return
  }
  if (validation.value.missingRequired > 0) {
    Message.warning('请先补齐节点必填配置')
    return
  }
  if (nodes.value.length > 1 && validation.value.startNodes !== 1) {
    Message.warning('请保留一个明确的起始节点')
    return
  }
  if (nodes.value.length > 1 && validation.value.terminalNodes < 1) {
    Message.warning('请至少保留一个结束节点')
    return
  }
  if (validation.value.invalidEdges > 0) {
    Message.warning('请先删除异常连线')
    return
  }
  saving.value = true
  try {
    const payload = { ...form, nodes: nodes.value.map(serializeFlowNode), edges: edges.value }
    const result = isEdit.value
      ? await flowApi.updateTemplate(Number(route.params.id), payload)
      : await flowApi.createTemplate(payload)
    Message.success('流水线已保存')
    if (!isEdit.value && result.id) router.replace(`/flows/${result.id}/edit`)
  } catch (error) {
    console.error('保存流水线失败:', error)
    Message.error('保存流水线失败')
  } finally {
    saving.value = false
  }
}

onMounted(loadData)
</script>

<style scoped>
.pipeline-editor {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  gap: 8px;
  height: calc(100vh - 88px);
  min-height: 720px;
  padding: 0;
  background: #f5f7fb;
}
.editor-spin {
  height: 100%;
  min-height: 0;
  overflow: hidden;
}
.editor-spin :deep(.arco-spin-children) {
  height: 100%;
  min-height: 0;
}
.editor-command {
  display: grid;
  grid-template-columns: minmax(180px, auto) minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
  min-height: 58px;
  padding: 9px 12px;
  background: #fff;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
}
.editor-command__title { display: flex; align-items: center; gap: 10px; min-width: 0; }
.editor-command__title h1 { margin: 0; color: var(--app-fg); font-size: 16px; line-height: 1.25; }
.editor-command__title p { margin: 3px 0 0; color: var(--app-muted); font-size: 12px; }
.editor-command__form {
  display: grid;
  grid-template-columns: minmax(180px, 240px) minmax(220px, 340px) auto;
  gap: 8px;
  align-items: center;
  min-width: 0;
}
.editor-command__form :deep(.arco-form-item) { margin-bottom: 0; }
.editor-command__form :deep(.arco-form-item-layout-inline) { margin-right: 0; }
.editor-command__form :deep(.arco-form-item-label) {
  align-items: center;
  height: 32px;
  padding-right: 6px;
  color: var(--app-muted);
  font-size: 12px;
  line-height: 32px;
  white-space: nowrap;
}
.editor-command__form :deep(.arco-form-item-label-required-symbol) {
  margin-right: 2px;
}
.editor-command__form :deep(.arco-input-wrapper) { width: 100%; min-width: 0; }
.editor-field-name { max-width: 240px; }
.editor-field-desc { max-width: 340px; }
.editor-command__actions { justify-content: flex-end; }
.editor-workbench {
  display: grid;
  grid-template-columns: 216px minmax(560px, 1fr) 336px;
  gap: 8px;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}
.editor-workbench--no-selection {
  grid-template-columns: 216px minmax(620px, 1fr);
}
.canvas-panel, .property-panel {
  min-height: 0;
  padding: 10px;
  background: #fff;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
}
.canvas-panel { overflow: hidden; }
.property-panel { display: flex; flex-direction: column; overflow: auto; }
.workbench-panel-head, .canvas-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 8px;
}
.workbench-panel-head h2, .canvas-toolbar h2 { margin: 0; color: var(--app-fg); font-size: 15px; line-height: 1.3; }
.workbench-panel-head p, .canvas-toolbar p { margin: 4px 0 0; color: var(--app-muted); font-size: 12px; line-height: 1.4; }
.canvas-panel { display: grid; grid-template-rows: auto auto minmax(0, 1fr) auto; }
.validation-strip {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 6px;
  margin-bottom: 8px;
}
.validation-strip div {
  display: flex;
  align-items: baseline;
  gap: 6px;
  padding: 6px 8px;
  color: var(--app-warn);
  background: var(--app-warn-soft);
  border: 1px solid color-mix(in srgb, var(--app-warn) 20%, transparent);
  border-radius: var(--app-radius-sm);
}
.validation-strip div.ok { color: var(--app-success); background: var(--app-success-soft); border-color: color-mix(in srgb, var(--app-success) 20%, transparent); }
.validation-strip strong { font-family: var(--app-mono); font-size: 16px; }
.validation-strip span { color: var(--app-muted); font-size: 12px; }
.flow-canvas { position: relative; min-height: 0; overflow: hidden; background: #f7f9fc; border: 1px solid var(--app-border); border-radius: var(--app-radius-sm); }
.flow-canvas::after {
  position: absolute;
  right: 10px;
  bottom: 9px;
  z-index: 2;
  color: var(--app-meta);
  font-family: var(--app-mono);
  font-size: 10px;
  content: 'DROP NODE';
  pointer-events: none;
}
.ops-flow { width: 100%; height: 100%; min-height: 540px; }
.ops-node-card {
  width: 214px;
  padding: 10px;
  background: #fff;
  border: 1px solid var(--app-border);
  border-top: 3px solid var(--app-muted);
  border-radius: var(--app-radius-sm);
  box-shadow: 0 6px 14px rgba(15, 23, 42, .07);
}
.ops-node-card--selected { border-color: var(--app-accent); box-shadow: 0 0 0 2px var(--app-accent-soft), 0 8px 18px rgba(15, 23, 42, .08); }
.ops-node-card--success { border-top-color: var(--app-success); }
.ops-node-card--running, .ops-node-card--paused { border-top-color: var(--app-warn); }
.ops-node-card--failed { border-top-color: var(--app-danger); }
.ops-node-card__top { display: flex; justify-content: space-between; align-items: center; gap: 8px; margin-bottom: 8px; }
.ops-node-card__top span:first-child { display: inline-flex; align-items: center; gap: 5px; color: var(--app-accent); font-size: 12px; font-weight: 700; }
.ops-node-card strong { display: block; overflow: hidden; color: var(--app-fg); font-size: 14px; line-height: 1.35; text-overflow: ellipsis; white-space: nowrap; }
.ops-node-card em { display: block; margin-top: 5px; overflow: hidden; color: var(--app-muted); font-size: 12px; font-style: normal; line-height: 1.45; text-overflow: ellipsis; white-space: nowrap; }
.ops-node-card small {
  display: block;
  margin-top: 7px;
  overflow: hidden;
  color: var(--app-meta);
  font-family: var(--app-mono);
  font-size: 11px;
  line-height: 1.3;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.canvas-empty {
  position: absolute;
  inset: 0;
  display: grid;
  place-content: center;
  gap: 10px;
  color: var(--app-muted);
  text-align: center;
  pointer-events: none;
}
.canvas-empty svg { justify-self: center; font-size: 30px; color: var(--app-accent); }
.canvas-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  min-height: 30px;
  padding: 0 10px;
  color: var(--app-muted);
  background: #fff;
  border: 1px solid var(--app-border);
  border-top: 0;
  border-radius: 0 0 var(--app-radius-sm) var(--app-radius-sm);
  font-family: var(--app-mono);
  font-size: 11px;
}
.canvas-footer span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.node-form { min-width: 0; }
.unsupported-node-alert { margin-bottom: 12px; }
.node-form :deep(.arco-form-item) { margin-bottom: 12px; }
.node-quick-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  padding: 8px;
  background: var(--app-surface-soft);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
}
.field-hint { margin: -2px 0 6px; color: var(--app-muted); font-size: 12px; line-height: 1.45; }
.script-monaco-editor {
  height: 230px;
  min-height: 230px;
  overflow: hidden;
  background: #fff;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
}
.script-monaco-editor :deep(.monaco-editor),
.script-monaco-editor :deep(.monaco-editor-background),
.script-monaco-editor :deep(.margin) {
  background: #fff;
}
.inline-empty {
  margin-top: 8px;
  padding: 8px 0;
  background: var(--app-surface-soft);
  border: 1px dashed var(--app-border);
  border-radius: var(--app-radius-sm);
}
.sub-process-hint {
  display: grid;
  gap: 4px;
  margin-bottom: 12px;
  padding: 10px;
  background: var(--app-surface-soft);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
}
.sub-process-hint strong { color: var(--app-fg); font-size: 12px; line-height: 1.35; }
.sub-process-hint span { color: var(--app-muted); font-size: 12px; line-height: 1.45; }
.file-source-list { display: grid; gap: 8px; }
.file-source-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) auto;
  gap: 8px;
  align-items: center;
}
.node-summary { display: grid; gap: 6px; margin-top: 6px; padding: 10px; background: var(--app-surface-soft); border: 1px solid var(--app-border); border-radius: var(--app-radius-sm); }
.node-summary span { color: var(--app-muted); font-size: 12px; }
.node-summary p { margin: 0; color: var(--app-fg); font-size: 13px; line-height: 1.45; }
.edge-list {
  display: grid;
  gap: 8px;
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid var(--app-border);
}
.edge-list__head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}
.edge-list__head h3 { margin: 0; color: var(--app-fg); font-size: 13px; }
.edge-list__head span { color: var(--app-muted); font-family: var(--app-mono); font-size: 12px; }
.edge-row-list { display: grid; gap: 6px; }
.edge-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr) auto;
  gap: 7px;
  align-items: center;
  padding: 7px 8px;
  background: #fff;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
  color: var(--app-muted);
  font-size: 12px;
}
.edge-row span {
  overflow: hidden;
  color: var(--app-fg);
  text-overflow: ellipsis;
  white-space: nowrap;
}
.edge-condition {
  display: grid;
  grid-column: 1 / -1;
  grid-template-columns: auto minmax(0, 1fr) 110px minmax(0, 1fr) minmax(88px, auto);
  gap: 6px;
  align-items: center;
  padding-top: 6px;
  border-top: 1px dashed var(--app-border);
}
.edge-condition > span {
  color: var(--app-muted);
  font-size: 12px;
}
@media (max-width: 1180px) {
  .pipeline-editor { height: auto; min-height: 0; }
  .editor-command { grid-template-columns: 1fr; align-items: stretch; }
  .editor-command__form { grid-template-columns: 1fr 1fr auto; }
  .editor-workbench { grid-template-columns: 200px minmax(460px, 1fr); }
  .editor-workbench--no-selection { grid-template-columns: 200px minmax(460px, 1fr); }
  .property-panel { grid-column: 1 / -1; max-height: none; }
}
@media (max-width: 780px) {
  .editor-command__form { grid-template-columns: 1fr; }
  .editor-workbench { grid-template-columns: 1fr; }
  .ops-flow { min-height: 420px; }
  .validation-strip { grid-template-columns: 1fr; }
  .canvas-footer { align-items: flex-start; flex-direction: column; padding: 8px 10px; }
  .node-quick-actions { align-items: stretch; flex-direction: column; }
  .file-source-row { grid-template-columns: 1fr; }
}
</style>
