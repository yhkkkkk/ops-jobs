<template>
  <div :class="['flow-editor-shell', { 'flow-editor-shell--readonly': isReadonly }]">
    <header class="flow-editor-command">
      <div class="flow-editor-command__title">
        <a-button size="small" @click="router.push('/flows')">
          <template #icon><icon-left /></template>
        </a-button>
        <div>
          <h1>{{ workbenchTitle }}</h1>
          <p>{{ nodes.length }} 个节点 / {{ edges.length }} 条连线 / {{ form.is_active ? '启用' : '停用' }}</p>
        </div>
      </div>

      <a-form v-if="!isReadonly" :model="form" layout="inline" class="flow-editor-command__form">
        <a-form-item label="名称" required>
          <a-input v-model="form.name" placeholder="生产发布前置检查" />
        </a-form-item>
        <a-form-item label="说明">
          <a-input v-model="form.description" placeholder="用途、窗口、负责人" />
        </a-form-item>
        <a-form-item label="状态">
          <a-switch v-model="form.is_active" checked-text="启用" unchecked-text="停用" />
        </a-form-item>
      </a-form>
      <div v-else class="readonly-template-meta">
        <span>{{ form.description || '查看流程模板拓扑、全局变量和节点配置。' }}</span>
        <em>负责人 {{ currentTemplate?.created_by_name || '-' }} / 更新 {{ formatTime(currentTemplate?.updated_at || currentTemplate?.created_at) }}</em>
      </div>

      <a-space class="flow-editor-command__actions">
        <a-button @click="variablesDrawerVisible = true">
          <template #icon><icon-code /></template>
          全局变量
        </a-button>
        <a-button v-if="currentTemplate?.id" @click="scheduleDrawerVisible = true">
          <template #icon><icon-schedule /></template>
          定时调度
        </a-button>        <a-button v-if="isReadonly && currentTemplate?.id" @click="router.push(`/flows/${currentTemplate.id}/edit`)">
          <template #icon><icon-edit /></template>
          编辑
        </a-button>
        <a-button v-if="isReadonly" type="primary" :disabled="!form.is_active" @click="startVisible = true">
          <template #icon><icon-play-arrow /></template>
          启动
        </a-button>
        <a-button v-if="!isReadonly" @click="layoutNodes">
          <template #icon><icon-sort /></template>
          自动排布
        </a-button>
        <a-button v-if="!isReadonly" type="primary" :loading="saving" @click="saveTemplate">
          <template #icon><icon-save /></template>
          保存
        </a-button>
      </a-space>
    </header>

    <a-spin :loading="loading" class="flow-editor-spin">
      <section class="flow-editor-workbench">
        <aside class="flow-plugin-rail" :class="{ 'flow-plugin-rail--collapsed': pluginRailCollapsed }">
          <div class="flow-plugin-rail__toggle">
            <a-button size="mini" @click="pluginRailCollapsed = !pluginRailCollapsed">
              <template #icon><icon-menu-fold v-if="!pluginRailCollapsed" /><icon-menu-unfold v-else /></template>
            </a-button>
          </div>
          <FlowNodeLibraryPanel
            v-show="!pluginRailCollapsed"
            :plugins="libraryPlugins"
            :scenarios="scenarios"
            :readonly="isReadonly"
            @add-node="addNode"
            @apply-scenario="applyScenario"
          />
        </aside>

        <main class="flow-canvas-stage">
          <div class="flow-canvas-toolbar flow-canvas-toolbar--compact">
            <div>
              <h2>可视化编排</h2>
              <p>{{ isReadonly ? '只读查看模板 DAG 拓扑，点击节点打开配置抽屉。' : '拖拽标准插件，按 DAG 串并行、分支、子流程组织执行路径。' }}</p>
            </div>
            <a-space v-if="!isReadonly">
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

          <div class="flow-validation-strip">
            <div :class="{ ok: validation.missingRequired === 0 }"><strong>{{ validation.missingRequired }}</strong><span>缺失必填</span></div>
            <div :class="{ ok: validation.disconnected === 0 }"><strong>{{ validation.disconnected }}</strong><span>未连接</span></div>
            <div><strong>{{ validation.startNodes }}</strong><span>起点</span></div>
            <div :class="{ ok: validation.terminalNodes >= 1 || nodes.length <= 1 }"><strong>{{ validation.terminalNodes }}</strong><span>终点</span></div>
          </div>

          <div class="flow-canvas-frame" @dragover.prevent @drop.prevent="handleCanvasDrop">
            <VueFlow
              :nodes="flowNodes"
              :edges="flowEdges"
              :default-edge-options="defaultEdgeOptions"
              :nodes-draggable="!isReadonly"
              :nodes-connectable="!isReadonly"
              :edges-updatable="!isReadonly"
              :elements-selectable="true"
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
                <div :class="['ops-node-card', { 'ops-node-card--selected': data.selected }]">
                  <Handle type="target" :position="Position.Left" />
                  <div class="ops-node-card__top">
                    <span><component :is="data.icon" />{{ data.typeText }}</span>
                  </div>
                  <strong>{{ data.label }}</strong>
                  <em>{{ data.summary }}</em>
                  <Handle type="source" :position="Position.Right" />
                </div>
              </template>
            </VueFlow>

            <div v-if="nodes.length === 0" class="flow-canvas-empty">
              <icon-branch />
              <p>{{ isReadonly ? '当前模板暂无节点' : '从左侧插件库添加节点' }}</p>
            </div>
          </div>
        </main>
      </section>
    </a-spin>

    <a-drawer
      v-model:visible="propertyDrawerVisible"
      :width="propertyDrawerWidth"
      placement="right"
      :footer="false"
      class="flow-property-drawer"
      @cancel="closePropertyDrawer"
    >
      <template #title>节点配置</template>
      <div v-if="selectedNode" class="property-panel">
        <div class="property-panel-head">
          <div>
            <h2>{{ selectedNode.name }}</h2>
            <p>{{ flowNodeTypeText(selectedNode.node_type) }}</p>
          </div>
          <a-button v-if="!isReadonly" size="small" @click="duplicateSelectedNode">
            <template #icon><icon-copy /></template>
            复制节点
          </a-button>
        </div>

        <div v-if="isReadonly" class="readonly-config-rows">
          <div v-for="row in selectedNodeConfigRows" :key="row.label" class="readonly-config-row">
            <span>{{ row.label }}</span>
            <pre v-if="row.multiline">{{ row.value }}</pre>
            <strong v-else>{{ row.value }}</strong>
          </div>
          <section v-if="selectedNode.node_type === 'script'" class="node-config-section">
            <div class="node-config-section__head">
              <div>
                <h3>脚本内容</h3>
                <p>只读查看脚本节点配置。</p>
              </div>
            </div>
            <ScriptEditorWithValidation
              v-model="selectedNode.config.script_content"
              class="script-monaco-editor"
              :language="scriptEditorLanguage"
              theme="vs-dark"
              :height="360"
              :readonly="true"
              :auto-validate="false"
            />
          </section>
        </div>

        <a-form v-else :model="selectedNode" layout="vertical" class="node-form">
          <section class="node-config-section">
            <div class="node-config-section__head">
              <div>
                <h3>基础信息</h3>
                <p>节点名称、插件类型和失败处理策略。</p>
              </div>
            </div>
            <a-row :gutter="16">
              <a-col :span="12">
                <a-form-item label="节点名称" required>
                  <a-input v-model="selectedNode.name" />
                </a-form-item>
              </a-col>
              <a-col :span="12">
                <a-form-item label="节点类型">
                  <a-select v-model="selectedNode.node_type" @change="resetNodeConfig(selectedNode)">
                    <a-option v-for="plugin in libraryPlugins" :key="plugin.type" :value="plugin.type">{{ plugin.name }}</a-option>
                  </a-select>
                </a-form-item>
              </a-col>
            </a-row>
            <a-form-item label="失败策略">
              <a-radio-group v-model="selectedNode.config.failure_policy" type="button">
                <a-radio value="stop">失败终止</a-radio>
                <a-radio value="pause">暂停处理</a-radio>
                <a-radio value="ignore">忽略继续</a-radio>
              </a-radio-group>
            </a-form-item>
          </section>

          <template v-if="selectedNode.node_type === 'script'">
            <section class="node-config-section">
              <div class="node-config-section__head">
                <div>
                  <h3>脚本执行配置</h3>
                  <p>对齐作业模板步骤：脚本类型、目标主机变量、超时和脚本内容。</p>
                </div>
              </div>
              <a-row :gutter="16">
                <a-col :span="16">
                  <a-form-item label="脚本类型">
                    <a-radio-group v-model="selectedNode.config.script_type" @change="handleSelectedScriptTypeChange">
                      <a-radio value="shell">Shell</a-radio>
                      <a-radio value="python">Python</a-radio>
                      <a-radio value="powershell">PowerShell</a-radio>
                      <a-radio value="perl">Perl</a-radio>
                      <a-radio value="javascript">JavaScript</a-radio>
                      <a-radio value="go">Go</a-radio>
                    </a-radio-group>
                  </a-form-item>
                </a-col>
                <a-col :span="8">
                  <a-form-item label="超时秒数">
                    <a-input-number v-model="selectedNode.config.timeout" :min="1" />
                  </a-form-item>
                </a-col>
              </a-row>
              <a-form-item label="目标主机" required>
                <a-input-group compact class="variable-binding-input">
                  <a-input v-model="selectedNode.config.target_host_ids" placeholder="例如 ${CheckHost}" />
                  <a-dropdown trigger="click" @select="value => bindSelectedNodeHostVariable(String(value))">
                    <a-button>插入变量</a-button>
                    <template #content>
                      <a-doption v-for="option in hostVariableOptions" :key="option.key" :value="option.value">{{ option.label }}</a-doption>
                    </template>
                  </a-dropdown>
                </a-input-group>
              </a-form-item>
              <a-form-item label="脚本内容" required>
                <template #extra>
                  <a-button size="small" @click="insertSelectedScriptExample">
                    <template #icon><icon-code /></template>
                    插入示例
                  </a-button>
                </template>
                <ScriptEditorWithValidation
                  v-model="selectedNode.config.script_content"
                  class="script-monaco-editor"
                  :language="scriptEditorLanguage"
                  theme="vs-dark"
                  :height="560"
                  :readonly="isReadonly"
                  :auto-validate="true"
                />
              </a-form-item>
              <div class="node-config-hint">
                <icon-info-circle />
                <div>
                  <strong>变量绑定</strong>
                  <span>目标主机必须绑定 host_list 全局变量；脚本内容可插入 ${Key}。</span>
                </div>
              </div>
            </section>
          </template>

          <template v-else-if="selectedNode.node_type === 'file_transfer'">
            <section class="node-config-section">
              <div class="node-config-section__head">
                <div>
                  <h3>文件分发配置</h3>
                  <p>文件来源、远端路径、目标主机都通过变量引用串联。</p>
                </div>
              </div>
              <a-form-item label="目标主机" required>
                <a-input-group compact class="variable-binding-input">
                  <a-input v-model="selectedNode.config.target_host_ids" placeholder="例如 ${CheckHost}" />
                  <a-dropdown trigger="click" @select="value => bindSelectedNodeHostVariable(String(value))">
                    <a-button>插入变量</a-button>
                    <template #content>
                      <a-doption v-for="option in hostVariableOptions" :key="option.key" :value="option.value">{{ option.label }}</a-doption>
                    </template>
                  </a-dropdown>
                </a-input-group>
              </a-form-item>
              <a-row :gutter="16">
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
              <div class="file-source-list">
                <div v-for="(source, index) in selectedNode.config.file_sources" :key="index" class="file-source-row">
                  <a-input-group compact class="variable-binding-input">
                    <a-input v-model="source.download_url" placeholder="下载地址，支持 ${PackageUrl}" />
                    <a-dropdown trigger="click" @select="value => insertFileSourceVariable(source, 'download_url', String(value))">
                      <a-button>插入变量</a-button>
                      <template #content>
                        <a-doption v-for="option in allVariableOptions" :key="option.key" :value="option.value">{{ option.label }}</a-doption>
                      </template>
                    </a-dropdown>
                  </a-input-group>
                  <a-input-group compact class="variable-binding-input">
                    <a-input v-model="source.remote_path" placeholder="远端路径，支持 ${DeployPath}" />
                    <a-dropdown trigger="click" @select="value => insertFileSourceVariable(source, 'remote_path', String(value))">
                      <a-button>插入变量</a-button>
                      <template #content>
                        <a-doption v-for="option in allVariableOptions" :key="option.key" :value="option.value">{{ option.label }}</a-doption>
                      </template>
                    </a-dropdown>
                  </a-input-group>
                  <a-button size="small" status="danger" :disabled="selectedNode.config.file_sources.length <= 1" @click="removeFileSource(index)">
                    <template #icon><icon-delete /></template>
                  </a-button>
                </div>
                <a-button size="small" @click="addFileSource">
                  <template #icon><icon-plus /></template>
                  添加文件来源
                </a-button>
              </div>
            </section>
          </template>

          <template v-else-if="selectedNode.node_type === 'job_plan'">
            <section class="node-config-section">
              <div class="node-config-section__head">
                <div>
                  <h3>作业执行方案配置</h3>
                  <p>只选择执行方案，方案变量映射到流水线全局变量。</p>
                </div>
                <a-button size="small" :loading="executionPlanDetailLoading" @click="refreshSelectedExecutionPlan">
                  <template #icon><icon-refresh /></template>
                  刷新方案
                </a-button>
              </div>
              <a-form-item label="作业执行方案" required>
                <a-select v-model="selectedNode.config.execution_plan_id" allow-search placeholder="选择作业执行方案" @change="handleExecutionPlanChange">
                  <a-option v-for="plan in executionPlans" :key="plan.id" :value="plan.id">{{ plan.name }}</a-option>
                </a-select>
              </a-form-item>
              <div class="execution-parameter-block">
                <div class="execution-parameter-block__head">
                  <div>
                    <h4>方案变量映射</h4>
                    <p>映射值应为流水线全局变量引用，例如 ${DeployPath}。</p>
                  </div>
                </div>
                <div class="execution-parameter-list">
                  <div v-for="item in selectedExecutionPlanVariables" :key="item.key" class="execution-parameter-row">
                    <div class="execution-parameter-row__meta">
                      <strong>{{ item.key }}</strong>
                      <span>{{ item.description || item.defaultDisplay || '方案变量' }}</span>
                    </div>
                    <a-input-group compact class="variable-binding-input">
                      <a-input
                        :model-value="getExecutionParameterBinding(item.key)"
                        placeholder="例如 ${DeployPath}"
                        @input="value => setExecutionParameterBinding(item.key, value)"
                      />
                      <a-dropdown trigger="click" @select="value => insertExecutionParameterVariable(item.key, String(value))">
                        <a-button>插入变量</a-button>
                        <template #content>
                          <a-doption v-for="option in allVariableOptions" :key="option.key" :value="option.value">{{ option.label }}</a-doption>
                        </template>
                      </a-dropdown>
                    </a-input-group>
                  </div>
                  <a-empty v-if="selectedExecutionPlanVariables.length === 0" description="选择执行方案后加载变量" />
                </div>
              </div>
            </section>
          </template>

          <template v-else-if="selectedNode.node_type === 'sub_process'">
            <section class="node-config-section">
              <div class="node-config-section__head">
                <div>
                  <h3>子流程配置</h3>
                  <p>选择另一个流程模板作为子流程，输入由全局变量传递。</p>
                </div>
              </div>
              <a-form-item label="子流程模板" required>
                <a-select v-model="selectedNode.config.template_id" allow-search placeholder="选择子流程模板">
                  <a-option v-for="template in flowTemplates" :key="template.id" :value="template.id">{{ template.name }}</a-option>
                </a-select>
              </a-form-item>
              <a-form-item label="输入继承">
                <a-switch v-model="selectedNode.config.inherit_inputs" checked-text="继承" unchecked-text="独立" />
              </a-form-item>
            </section>
          </template>

          <template v-else>
            <section class="node-config-section">
              <div class="node-config-section__head">
                <div>
                  <h3>{{ flowNodeTypeText(selectedNode.node_type) }}</h3>
                  <p>网关、条件和人工确认节点只维护执行控制语义。</p>
                </div>
              </div>
              <a-form-item label="说明">
                <a-textarea v-model="selectedNode.config.description" :auto-size="{ minRows: 3, maxRows: 5 }" />
              </a-form-item>
              <a-form-item v-if="selectedNode.node_type === 'manual'" label="确认说明">
                <a-textarea v-model="selectedNode.config.instructions" :auto-size="{ minRows: 3, maxRows: 5 }" />
              </a-form-item>
            </section>
          </template>
        </a-form>
      </div>
      <a-empty v-else description="请选择画布节点" />
    </a-drawer>

    <a-drawer
      v-model:visible="variablesDrawerVisible"
      width="760px"
      placement="right"
      :footer="false"
      class="flow-variable-drawer"
    >
      <template #title>全局变量</template>
      <FlowVariableEditor v-if="!isReadonly" v-model="form.variables" />
      <FlowVariableReadOnlyPanel v-else :variables="form.variables" empty-text="暂无全局变量" />
    </a-drawer>

    <FlowScheduleDrawer
      v-model:visible="scheduleDrawerVisible"
      :template="currentTemplate"
      :readonly="isReadonly"
    />
    <FlowStartModal
      v-model:visible="startVisible"
      :template="currentTemplate"
      @started="run => router.push(`/flows/runs/${run.id}`)"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent, nextTick, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { MiniMap } from '@vue-flow/minimap'
import { Handle, MarkerType, Position, VueFlow } from '@vue-flow/core'
import type { Edge, Node } from '@vue-flow/core'
import { executionPlanApi, flowApi } from '@/api/ops'
import type { ExecutionPlan, FlowEdge, FlowNode, FlowNodePlugin, FlowNodeType, FlowTemplate } from '@/types'
import FlowNodeLibraryPanel, { type FlowNodePluginOption, type FlowScenarioOption } from './FlowNodeLibraryPanel.vue'
import FlowScheduleDrawer from './FlowScheduleDrawer.vue'
import FlowStartModal from './FlowStartModal.vue'
import FlowVariableEditor from './FlowVariableEditor.vue'
import FlowVariableReadOnlyPanel from './FlowVariableReadOnlyPanel.vue'
import {
  evaluateFlowGraph,
  flowNodeConfigDisplayRows,
  flowNodeTypeText,
  flowVariableSelectOptions,
  normalizeFlowVariables,
  normalizeFlowNode,
  resolveFlowTemplateTopology,
  serializeFlowNode,
  summarizeFlowNode,
  validateFlowNodeConfigJson,
  type SupportedFlowNodeType,
} from '../flowUtils'

const ScriptEditorWithValidation = defineAsyncComponent(() => import('@/components/ScriptEditorWithValidation.vue'))

const props = withDefaults(defineProps<{
  mode?: 'edit' | 'readonly'
}>(), {
  mode: 'edit',
})

const FLOW_PROPERTY_DRAWER_WIDTH = '760px'
const route = useRoute()
const router = useRouter()
const isReadonly = computed(() => props.mode === 'readonly')
const isEdit = computed(() => props.mode === 'edit' && route.name === 'FlowEdit')
const loading = ref(false)
const saving = ref(false)
const startVisible = ref(false)
const scheduleDrawerVisible = ref(false)
const propertyDrawerVisible = ref(false)
const variablesDrawerVisible = ref(false)
const pluginRailCollapsed = ref(false)
const propertyDrawerWidth = computed(() => window.innerWidth < 1180 ? '100vw' : FLOW_PROPERTY_DRAWER_WIDTH)
const selectedUuid = ref('')
const currentTemplate = ref<FlowTemplate | null>(null)
const executionPlans = ref<ExecutionPlan[]>([])
const flowTemplates = ref<FlowTemplate[]>([])
const plugins = ref<FlowNodePlugin[]>([])
const selectedExecutionPlanDetail = ref<ExecutionPlan | null>(null)
const executionPlanDetailLoading = ref(false)

const form = reactive({
  name: '',
  description: '',
  variables: {} as Record<string, any>,
  is_active: true,
})
const nodes = ref<FlowNode[]>([])
const edges = ref<FlowEdge[]>([])
const workbenchTitle = computed(() => {
  if (isReadonly.value) return form.name || '流水线详情'
  return isEdit.value ? '编辑流水线' : '新建流水线'
})

const fallbackPlugins: FlowNodePluginOption[] = [
  { type: 'script', name: '脚本执行', description: '快速执行脚本', category: '作业原子', risk: '中', icon: 'icon-code' },
  { type: 'file_transfer', name: '文件分发', description: '上传或下载文件', category: '作业原子', risk: '中', icon: 'icon-upload' },
  { type: 'job_plan', name: '作业执行方案', description: '调用作业方案', category: '作业编排', risk: '高', icon: 'icon-calendar' },
  { type: 'manual', name: '人工确认', description: '暂停等待确认', category: '控制节点', risk: '低', icon: 'icon-check-circle' },
  { type: 'condition', name: '条件分支', description: '按变量选择分支', category: '控制节点', risk: '低', icon: 'icon-branch' },
  { type: 'parallel', name: '并行网关', description: '并行启动下游', category: '控制节点', risk: '低', icon: 'icon-share-alt' },
  { type: 'join', name: '汇聚网关', description: '等待分支汇聚', category: '控制节点', risk: '低', icon: 'icon-relation' },
  { type: 'sub_process', name: '子流程', description: '嵌套执行模板', category: '流程编排', risk: '中', icon: 'icon-layers' },
]
const scenarios: FlowScenarioOption[] = [
  { key: 'release', name: '发布检查', description: '检查 -> 分发 -> 执行方案 -> 确认' },
  { key: 'dispatch', name: '文件分发', description: '准备变量 -> 文件分发 -> 人工确认' },
]

const libraryPlugins = computed<FlowNodePluginOption[]>(() => {
  if (!plugins.value.length) return fallbackPlugins
  return plugins.value.map(plugin => ({
    type: plugin.type as SupportedFlowNodeType,
    name: plugin.name,
    description: plugin.description || flowNodeTypeText(plugin.type),
    category: plugin.category || '标准插件',
    risk: plugin.type === 'job_plan' ? '高' : '中',
    icon: fallbackPlugins.find(item => item.type === plugin.type)?.icon || 'icon-apps',
  }))
})
const selectedNode = computed(() => nodes.value.find(item => item.uuid === selectedUuid.value) || null)
const selectedNodeConfigRows = computed(() => selectedNode.value ? flowNodeConfigDisplayRows(selectedNode.value) : [])
const validation = computed(() => evaluateFlowGraph(nodes.value, edges.value))
const normalizedVariableDefinitions = computed(() => normalizeFlowVariables(form.variables || {}))
const allVariableOptions = computed(() => flowVariableSelectOptions(normalizedVariableDefinitions.value))
const hostVariableOptions = computed(() => flowVariableSelectOptions(normalizedVariableDefinitions.value, 'host_list'))
const scriptEditorLanguage = computed(() => selectedNode.value?.config.script_type || 'shell')
const selectedExecutionPlanVariables = computed(() => {
  const params = selectedExecutionPlanDetail.value?.global_parameters_snapshot || selectedExecutionPlanDetail.value?.template_global_parameters || {}
  return Object.entries(params).map(([key, value]) => ({
    key,
    description: typeof value === 'object' && value ? String((value as any).description || (value as any).name || '') : '',
    defaultDisplay: typeof value === 'object' ? JSON.stringify((value as any).default ?? '') : String(value ?? ''),
  }))
})

const defaultEdgeOptions = {
  type: 'smoothstep',
  markerEnd: MarkerType.ArrowClosed,
}
const flowNodes = computed<Node[]>(() => nodes.value.map(node => ({
  id: node.uuid,
  type: 'ops',
  position: { x: node.position?.x || 0, y: node.position?.y || 0 },
  data: {
    label: node.name || '未知节点',
    typeText: flowNodeTypeText(node.node_type),
    summary: summarizeFlowNode(node),
    icon: libraryPlugins.value.find(plugin => plugin.type === node.node_type)?.icon || 'icon-apps',
    selected: selectedUuid.value === node.uuid,
  },
})))
const flowEdges = computed<Edge[]>(() => edges.value.filter(edge => edge.source_uuid && edge.target_uuid).map((edge, index) => ({
  id: `${edge.source_uuid}-${edge.target_uuid}-${index}`,
  source: edge.source_uuid!,
  target: edge.target_uuid!,
  type: 'smoothstep',
  markerEnd: MarkerType.ArrowClosed,
  label: edge.condition?.default ? '默认' : '',
})))

const normalizeList = <T,>(value: any): T[] => Array.isArray(value) ? value : value?.results || value?.data || []
const formatTime = (value?: string | null) => value ? new Date(value).toLocaleString('zh-CN') : '-'
const createUuid = (type: string) => `node-${type}-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`
const defaultConfig = (type: FlowNodeType) => {
  if (type === 'script') return { failure_policy: 'stop', script_type: 'shell', timeout: 300, target_host_ids: '', script_content: '' }
  if (type === 'file_transfer') return { failure_policy: 'stop', timeout: 600, bandwidth_limit: 0, target_host_ids: '', file_sources: [{ download_url: '', remote_path: '' }] }
  if (type === 'job_plan') return { failure_policy: 'pause', execution_plan_id: undefined, execution_parameter_bindings: {} }
  if (type === 'sub_process') return { failure_policy: 'stop', template_id: undefined, inherit_inputs: true, inputs_text: '{}' }
  if (type === 'manual') return { failure_policy: 'pause', instructions: '确认后继续执行。' }
  return { failure_policy: 'stop', description: '' }
}
const makeNode = (type: FlowNodeType, index = nodes.value.length): FlowNode => ({
  uuid: createUuid(type),
  name: flowNodeTypeText(type),
  node_type: type,
  config: defaultConfig(type),
  position: { x: 80 + index * 220, y: 120 + (index % 3) * 90 },
})

const resetNodeConfig = (node: FlowNode) => {
  node.config = defaultConfig(node.node_type)
}
const openPropertyDrawer = () => {
  propertyDrawerVisible.value = true
}
const closePropertyDrawer = () => {
  propertyDrawerVisible.value = false
}
const handleFlowNodeClick = ({ node }: { node: Node }) => {
  selectedUuid.value = node.id
  openPropertyDrawer()
}
const handleNodeDragStop = ({ node }: { node: Node }) => {
  if (isReadonly.value) return
  const current = nodes.value.find(item => item.uuid === node.id)
  if (current) current.position = { x: node.position.x, y: node.position.y }
}
const addNode = (type: SupportedFlowNodeType) => {
  if (isReadonly.value) return
  const node = makeNode(type)
  const previous = nodes.value[nodes.value.length - 1]
  nodes.value.push(node)
  if (previous) edges.value.push({ source_uuid: previous.uuid, target_uuid: node.uuid, condition: {} })
  selectedUuid.value = node.uuid
  openPropertyDrawer()
}
const applyScenario = (key: 'release' | 'dispatch') => {
  if (isReadonly.value) return
  const types: SupportedFlowNodeType[] = key === 'release'
    ? ['script', 'condition', 'file_transfer', 'job_plan', 'manual']
    : ['script', 'file_transfer', 'manual']
  nodes.value = types.map((type, index) => makeNode(type, index))
  edges.value = nodes.value.slice(1).map((node, index) => ({
    source_uuid: nodes.value[index].uuid,
    target_uuid: node.uuid,
    condition: {},
  }))
  selectedUuid.value = nodes.value[0]?.uuid || ''
  openPropertyDrawer()
}
const handleCanvasDrop = (event: DragEvent) => {
  if (isReadonly.value) return
  const type = event.dataTransfer?.getData('application/x-flow-node-type') as SupportedFlowNodeType
  if (type) addNode(type)
}
const handleConnect = (connection: any) => {
  if (isReadonly.value) return
  if (!connection.source || !connection.target || connection.source === connection.target) return
  const exists = edges.value.some(edge => edge.source_uuid === connection.source && edge.target_uuid === connection.target)
  if (!exists) edges.value.push({ source_uuid: connection.source, target_uuid: connection.target, condition: {} })
}
const removeSelectedNode = () => {
  if (isReadonly.value) return
  if (!selectedUuid.value) return
  const uuid = selectedUuid.value
  nodes.value = nodes.value.filter(node => node.uuid !== uuid)
  edges.value = edges.value.filter(edge => edge.source_uuid !== uuid && edge.target_uuid !== uuid)
  selectedUuid.value = ''
  closePropertyDrawer()
}
const duplicateSelectedNode = () => {
  if (isReadonly.value) return
  if (!selectedNode.value) return
  const copy: FlowNode = {
    ...structuredClone(selectedNode.value),
    uuid: createUuid(selectedNode.value.node_type),
    name: `${selectedNode.value.name} 副本`,
    position: { x: (selectedNode.value.position?.x || 0) + 220, y: selectedNode.value.position?.y || 0 },
  }
  nodes.value.push(copy)
  edges.value.push({ source_uuid: selectedNode.value.uuid, target_uuid: copy.uuid, condition: {} })
  selectedUuid.value = copy.uuid
}
const layoutNodes = () => {
  if (isReadonly.value) return
  nodes.value = nodes.value.map((node, index) => ({
    ...node,
    position: { x: 80 + index * 220, y: 120 + (index % 2) * 120 },
  }))
}
const selectFirstInvalidNode = () => {
  const issue = validation.value.issues.find(item => item.nodeUuid)
  if (issue?.nodeUuid) {
    selectedUuid.value = issue.nodeUuid
    openPropertyDrawer()
  } else {
    Message.info('当前没有需要定位的节点问题')
  }
}
const bindSelectedNodeHostVariable = (value: string) => {
  if (selectedNode.value) selectedNode.value.config.target_host_ids = value
}
const insertFileSourceVariable = (source: Record<string, any>, field: 'download_url' | 'remote_path', value: string) => {
  source[field] = `${source[field] || ''}${value}`
}
const addFileSource = () => {
  selectedNode.value?.config.file_sources.push({ download_url: '', remote_path: '' })
}
const removeFileSource = (index: number) => {
  selectedNode.value?.config.file_sources.splice(index, 1)
}
const handleSelectedScriptTypeChange = () => {
  // ScriptEditorWithValidation reacts to scriptEditorLanguage.
}
const insertSelectedScriptExample = () => {
  if (!selectedNode.value) return
  const language = selectedNode.value.config.script_type || 'shell'
  selectedNode.value.config.script_content = language === 'python'
    ? 'print("hello ${CheckHost}")'
    : 'echo "hello ${CheckHost}"'
}
const getExecutionParameterBinding = (key: string) => selectedNode.value?.config.execution_parameter_bindings?.[key] || ''
const setExecutionParameterBinding = (key: string, value: string) => {
  if (!selectedNode.value) return
  if (!selectedNode.value.config.execution_parameter_bindings) selectedNode.value.config.execution_parameter_bindings = {}
  selectedNode.value.config.execution_parameter_bindings[key] = value
}
const insertExecutionParameterVariable = (key: string, value: string) => {
  setExecutionParameterBinding(key, `${getExecutionParameterBinding(key)}${value}`)
}
const handleExecutionPlanChange = async (planId: number | string) => {
  if (!selectedNode.value) return
  selectedNode.value.config.execution_plan_id = Number(planId)
  if (!selectedNode.value.config.execution_parameter_bindings) selectedNode.value.config.execution_parameter_bindings = {}
  await refreshSelectedExecutionPlan()
}
const refreshSelectedExecutionPlan = async () => {
  const planId = selectedNode.value?.config.execution_plan_id
  if (!planId) {
    selectedExecutionPlanDetail.value = null
    return
  }
  executionPlanDetailLoading.value = true
  try {
    selectedExecutionPlanDetail.value = await executionPlanApi.getPlan(Number(planId))
  } catch (error) {
    console.error('加载执行方案变量失败:', error)
    selectedExecutionPlanDetail.value = null
    Message.warning('加载执行方案变量失败')
  } finally {
    executionPlanDetailLoading.value = false
  }
}
const validateVariableBindingsBeforeSave = () => {
  const hostKeys = new Set(hostVariableOptions.value.map(option => option.value))
  const badNode = nodes.value.find(node =>
    ['script', 'file_transfer'].includes(node.node_type) &&
    (!node.config.target_host_ids || !hostKeys.has(String(node.config.target_host_ids)))
  )
  if (badNode) {
    selectedUuid.value = badNode.uuid
    openPropertyDrawer()
    Message.warning(`${badNode.name} 的目标主机必须绑定 host_list 全局变量`)
    return false
  }
  return true
}
const loadData = async () => {
  loading.value = true
  try {
    const [planResult, templateListResult, pluginResult] = await Promise.allSettled([
      executionPlanApi.getPlans({ page_size: 200 }),
      flowApi.getTemplates(),
      flowApi.getNodePlugins(),
    ])
    executionPlans.value = planResult.status === 'fulfilled' ? normalizeList<ExecutionPlan>(planResult.value) : []
    flowTemplates.value = templateListResult.status === 'fulfilled' ? normalizeList<FlowTemplate>(templateListResult.value) : []
    plugins.value = pluginResult.status === 'fulfilled' ? normalizeList<FlowNodePlugin>(pluginResult.value) : []

    if (isEdit.value || isReadonly.value) {
      const templateId = Number(route.params.id)
      const [template, nodeResult, edgeResult] = await Promise.all([
        flowApi.getTemplate(templateId),
        flowApi.getNodes({ template: templateId }),
        flowApi.getEdges({ template: templateId }),
      ])
      const topology = resolveFlowTemplateTopology(
        template,
        normalizeList<FlowNode>(nodeResult),
        normalizeList<FlowEdge>(edgeResult),
      )
      form.name = template.name
      form.description = template.description || ''
      form.variables = template.variables || {}
      form.is_active = template.is_active
      nodes.value = topology.nodes.map(normalizeFlowNode)
      edges.value = topology.edges
      currentTemplate.value = {
        ...template,
        nodes: topology.nodes,
        edges: topology.edges,
      }
    } else {
      form.name = '新建运维流水线'
      form.description = ''
      form.variables = {}
      form.is_active = true
      nodes.value = []
      edges.value = []
      currentTemplate.value = null
    }
    if (isReadonly.value) {
      selectedUuid.value = nodes.value[0]?.uuid || ''
    } else {
      nextTick(layoutNodes)
    }
  } catch (error) {
    console.error('加载流水线编辑数据失败:', error)
    Message.error('加载流水线编辑数据失败')
  } finally {
    loading.value = false
  }
}
const saveTemplate = async () => {
  if (isReadonly.value) return
  if (!form.name.trim()) {
    Message.warning('请填写流水线名称')
    return
  }
  const blockingIssue = validation.value.issues.find(issue => issue.severity === 'error')
  if (blockingIssue) {
    selectFirstInvalidNode()
    Message.warning(blockingIssue.message)
    return
  }
  for (const node of nodes.value) {
    const jsonValidation = validateFlowNodeConfigJson(node)
    if (!jsonValidation.valid) {
      selectedUuid.value = node.uuid
      openPropertyDrawer()
      Message.warning(jsonValidation.message || '节点配置格式不正确')
      return
    }
  }
  if (!validateVariableBindingsBeforeSave()) return
  saving.value = true
  try {
    const payload = {
      ...form,
      nodes: nodes.value.map(serializeFlowNode),
      edges: edges.value,
    }
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
.flow-editor-shell {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  gap: 8px;
  width: 100%;
  max-width: 100%;
  height: calc(100vh - 88px);
  min-height: 640px;
  min-width: 0;
  padding: 0;
  overflow: hidden;
  background: #f5f7fb;
}
.flow-editor-command {
  display: grid;
  grid-template-columns: 230px minmax(0, 1fr) auto;
  gap: 10px;
  align-items: center;
  min-width: 0;
  min-height: 58px;
  padding: 9px 12px;
  background: #fff;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
}
.flow-editor-command__title {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}
.flow-editor-command__title h1 {
  margin: 0;
  color: var(--app-fg);
  font-size: 16px;
  line-height: 1.25;
}
.flow-editor-command__title p {
  margin: 3px 0 0;
  color: var(--app-muted);
  font-size: 12px;
}
.flow-editor-command__form {
  display: grid;
  grid-template-columns: minmax(180px, 260px) minmax(220px, 360px) auto;
  gap: 8px;
  align-items: center;
  min-width: 0;
}
.flow-editor-command__form :deep(.arco-form-item) {
  margin-bottom: 0;
}
.readonly-template-meta {
  display: grid;
  gap: 4px;
  min-width: 0;
}
.readonly-template-meta span,
.readonly-template-meta em {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.readonly-template-meta span {
  color: var(--app-fg);
  font-size: 13px;
}
.readonly-template-meta em {
  color: var(--app-muted);
  font-size: 12px;
  font-style: normal;
}
.flow-editor-command__actions {
  justify-content: flex-end;
}
.flow-editor-spin,
.flow-editor-spin :deep(.arco-spin-children) {
  height: 100%;
  min-height: 0;
  overflow: hidden;
}
.flow-editor-workbench {
  display: grid;
  grid-template-columns: 220px minmax(0, 1fr);
  gap: 8px;
  width: 100%;
  max-width: 100%;
  height: 100%;
  min-height: 0;
  min-width: 0;
  overflow: hidden;
}
.flow-plugin-rail {
  position: relative;
  min-width: 0;
  min-height: 0;
}
.flow-plugin-rail--collapsed {
  width: 42px;
}
.flow-plugin-rail__toggle {
  position: absolute;
  top: 8px;
  right: 8px;
  z-index: 4;
}
.flow-plugin-rail--collapsed .flow-plugin-rail__toggle {
  left: 7px;
  right: auto;
}
.flow-canvas-stage {
  display: grid;
  grid-template-rows: auto auto minmax(0, 1fr);
  gap: 8px;
  min-width: 0;
  min-height: 0;
  padding: 10px;
  overflow: hidden;
  background: #fff;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
}
.flow-canvas-toolbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  min-width: 0;
}
.flow-canvas-toolbar h2 {
  margin: 0;
  color: var(--app-fg);
  font-size: 15px;
}
.flow-canvas-toolbar p {
  margin: 4px 0 0;
  color: var(--app-muted);
  font-size: 12px;
}
.flow-validation-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 6px;
}
.flow-validation-strip div {
  display: flex;
  align-items: baseline;
  gap: 6px;
  min-width: 0;
  padding: 6px 8px;
  color: var(--app-warn);
  background: var(--app-warn-soft);
  border: 1px solid color-mix(in srgb, var(--app-warn) 20%, transparent);
  border-radius: var(--app-radius-sm);
}
.flow-validation-strip div.ok {
  color: var(--app-success);
  background: var(--app-success-soft);
  border-color: color-mix(in srgb, var(--app-success) 20%, transparent);
}
.flow-validation-strip strong {
  font-family: var(--app-mono);
  font-size: 14px;
}
.flow-validation-strip span {
  color: var(--app-muted);
  font-size: 12px;
}
.flow-canvas-frame {
  position: relative;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  background: #f7f9fc;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
}
.ops-flow {
  width: 100%;
  height: 100%;
  min-height: 520px;
}
.ops-node-card {
  display: grid;
  gap: 2px;
  width: 158px;
  min-height: 54px;
  padding: 6px 8px;
  background: #fff;
  border: 1px solid var(--app-border);
  border-left: 3px solid var(--app-accent);
  border-radius: var(--app-radius-sm);
  box-shadow: 0 4px 10px rgba(15, 23, 42, .06);
}
.ops-node-card--selected {
  border-color: var(--app-accent);
  box-shadow: 0 0 0 2px var(--app-accent-soft), 0 8px 18px rgba(15, 23, 42, .08);
}
.ops-node-card__top span {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
  overflow: hidden;
  color: var(--app-accent);
  font-size: 10px;
  font-weight: 700;
  line-height: 16px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ops-node-card strong,
.ops-node-card em {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ops-node-card strong {
  color: var(--app-fg);
  font-size: 12px;
  line-height: 1.25;
}
.ops-node-card em {
  color: var(--app-muted);
  font-size: 10px;
  font-style: normal;
}
.flow-canvas-empty {
  position: absolute;
  inset: 0;
  display: grid;
  place-content: center;
  gap: 10px;
  color: var(--app-muted);
  text-align: center;
  pointer-events: none;
}
.flow-canvas-empty svg {
  justify-self: center;
  color: var(--app-accent);
  font-size: 30px;
}
.flow-property-drawer :deep(.arco-drawer),
.flow-variable-drawer :deep(.arco-drawer) {
  max-width: 100vw;
}
.flow-property-drawer :deep(.arco-drawer-body),
.flow-variable-drawer :deep(.arco-drawer-body) {
  min-width: 0;
  padding: 12px;
  overflow-x: hidden;
}
.property-panel,
.node-form,
.node-config-section {
  display: grid;
  gap: 12px;
  min-width: 0;
}
.property-panel-head,
.node-config-section__head,
.execution-parameter-block__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  min-width: 0;
}
.property-panel-head h2,
.node-config-section__head h3,
.execution-parameter-block__head h4 {
  margin: 0;
  color: var(--app-fg);
  font-size: 14px;
}
.property-panel-head p,
.node-config-section__head p,
.execution-parameter-block__head p {
  margin: 4px 0 0;
  color: var(--app-muted);
  font-size: 12px;
}
.node-config-section {
  padding-bottom: 14px;
  border-bottom: 1px solid var(--app-border);
}
.readonly-config-rows {
  display: grid;
  gap: 8px;
  min-width: 0;
}
.readonly-config-row {
  display: grid;
  grid-template-columns: 110px minmax(0, 1fr);
  gap: 10px;
  align-items: start;
  min-width: 0;
  padding: 9px;
  background: var(--app-surface-soft);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
}
.readonly-config-row span {
  color: var(--app-muted);
  font-size: 12px;
}
.readonly-config-row strong,
.readonly-config-row pre {
  min-width: 0;
  margin: 0;
  overflow: auto;
  color: var(--app-fg);
  font-family: var(--app-mono);
  font-size: 12px;
  line-height: 1.45;
  white-space: pre-wrap;
  word-break: break-word;
}
.node-form :deep(.arco-form-item) {
  display: block;
  margin-bottom: 12px;
}
.node-form :deep(.arco-form-item-label-col),
.node-form :deep(.arco-form-item-wrapper-col) {
  display: block;
  width: 100%;
  max-width: 100%;
}
.variable-binding-input {
  display: flex;
  width: 100%;
  min-width: 0;
}
.variable-binding-input :deep(.arco-input-wrapper) {
  flex: 1 1 auto;
  min-width: 0;
}
.variable-binding-input :deep(.arco-btn) {
  flex: 0 0 auto;
  width: 86px;
  padding: 0 8px;
}
.script-monaco-editor {
  width: 100%;
  min-width: 0;
}
.node-config-hint {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  padding: 10px 12px;
  color: var(--app-muted);
  background: var(--app-surface-soft);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
  font-size: 12px;
}
.node-config-hint strong {
  display: block;
  margin-bottom: 2px;
  color: var(--app-fg);
}
.file-source-list,
.execution-parameter-list {
  display: grid;
  gap: 8px;
}
.file-source-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) auto;
  gap: 8px;
  align-items: center;
}
.execution-parameter-block {
  display: grid;
  gap: 10px;
  padding: 12px;
  background: var(--app-surface-soft);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
}
.execution-parameter-row {
  display: grid;
  grid-template-columns: minmax(180px, 260px) minmax(0, 1fr);
  gap: 10px;
  align-items: center;
  padding: 8px;
  background: #fff;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
}
.execution-parameter-row__meta {
  display: grid;
  gap: 3px;
  min-width: 0;
}
.execution-parameter-row__meta strong,
.execution-parameter-row__meta span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.execution-parameter-row__meta strong {
  color: var(--app-fg);
  font-family: var(--app-mono);
  font-size: 12px;
}
.execution-parameter-row__meta span {
  color: var(--app-muted);
  font-size: 12px;
}
@media (max-width: 1180px) {
  .flow-editor-shell {
    height: auto;
    min-height: 0;
  }
  .flow-editor-command {
    grid-template-columns: 1fr;
  }
  .flow-editor-command__form {
    grid-template-columns: 1fr 1fr auto;
  }
}
@media (max-width: 780px) {
  .flow-editor-workbench {
    grid-template-columns: 1fr;
  }
  .flow-editor-command__form,
  .file-source-row,
  .execution-parameter-row {
    grid-template-columns: 1fr;
  }
}
</style>
