<template>
  <div :class="['flow-editor-shell', { 'flow-editor-shell--readonly': isReadonly }]">
    <header class="flow-editor-command">
      <div class="flow-editor-command__title">
        <n-button size="tiny" quaternary @click="router.push('/flows')">
          <template #icon><ChevronLeft :size="16" /></template>
        </n-button>
        <h1>{{ workbenchTitle }}</h1>
        <n-input
          v-if="!isReadonly"
          v-model:value="form.name"
          size="small"
          placeholder="流水线名称"
          style="width: 220px"
        />
        <span class="flow-editor-command__meta">{{ nodes.length }} 节点 · {{ edges.length }} 连线</span>
      </div>

      <n-space class="flow-editor-command__actions" :size="6">
        <n-button size="small" @click="openSettingTab('variables')">全局变量</n-button>
        <n-button size="small" @click="openSettingTab('base')">基础信息</n-button>
        <n-button v-if="!isReadonly" size="small" @click="openSettingTab('notify')">通知</n-button>
        <n-button v-if="currentTemplate?.id" size="small" @click="scheduleDrawerVisible = true">定时调度</n-button>
        <n-button v-if="isReadonly && currentTemplate?.id" size="small" @click="router.push(`/flows/${currentTemplate.id}/edit`)">编辑</n-button>
        <n-button v-if="isReadonly" size="small" type="primary" :disabled="!form.is_active" @click="startVisible = true">启动</n-button>
        <n-button v-if="!isReadonly" size="small" @click="layoutNodes">排布</n-button>
        <n-button v-if="!isReadonly" size="small" type="primary" :loading="saving" @click="saveTemplate">保存</n-button>
      </n-space>
    </header>

    <n-spin :show="loading" class="flow-editor-spin">
      <section class="flow-editor-workbench">
        <aside class="flow-plugin-rail" :class="{ 'flow-plugin-rail--collapsed': pluginRailCollapsed }">
          <div class="flow-plugin-rail__toggle">
            <n-button size="tiny" @click="pluginRailCollapsed = !pluginRailCollapsed">
              <template #icon>
                <PanelLeftClose v-if="!pluginRailCollapsed" />
                <PanelLeftOpen v-else />
              </template>
            </n-button>
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
            <div class="flow-canvas-toolbar__lead">
              <h2>编排画布</h2>
              <div class="flow-validation-strip flow-validation-strip--inline">
                <div :class="{ ok: validation.missingRequired === 0 }"><strong>{{ validation.missingRequired }}</strong><span>必填</span></div>
                <div :class="{ ok: validation.disconnected === 0 }"><strong>{{ validation.disconnected }}</strong><span>未连</span></div>
                <div><strong>{{ validation.startNodes }}</strong><span>起点</span></div>
                <div :class="{ ok: validation.terminalNodes >= 1 || nodes.length <= 1 }"><strong>{{ validation.terminalNodes }}</strong><span>终点</span></div>
              </div>
            </div>
            <n-space v-if="!isReadonly" :size="6">
              <n-button size="tiny" @click="selectFirstInvalidNode">定位问题</n-button>
              <n-button size="tiny" type="error" :disabled="!selectedNode" @click="removeSelectedNode">删除节点</n-button>
            </n-space>
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
              @edge-click="handleFlowEdgeClick"
              @node-drag-stop="handleNodeDragStop"
              @connect="handleConnect"
            >
              <Background :gap="24" :size="1" pattern-color="#d8dee9" />
              <Controls position="bottom-left" :show-interactive="false" />
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
              <GitBranch  />
              <p>{{ isReadonly ? '当前模板暂无节点' : '从左侧插件库添加节点' }}</p>
            </div>
          </div>
        </main>

        <FlowSettingPanel
          v-model:collapsed="settingPanelCollapsed"
          :readonly="isReadonly"
          :name="form.name"
          :description="form.description"
          :category="form.category"
          :is-active="form.is_active"
          :is-public="form.is_public"
          :variables="form.variables"
          :notify-config="form.notify_config"
          :initial-tab="settingInitialTab"
          @update:name="form.name = $event"
          @update:description="form.description = $event"
          @update:category="form.category = $event"
          @update:is-active="form.is_active = $event"
          @update:is-public="form.is_public = $event"
          @update:variables="form.variables = $event"
          @update:notify-config="form.notify_config = $event"
        />
      </section>
    </n-spin>

    <n-drawer
      v-model:show="propertyDrawerVisible"
      :width="propertyDrawerWidth"
      placement="right"
     
      class="flow-property-drawer"
      @cancel="closePropertyDrawer"
    ><n-drawer-content>
      <template #header>节点配置</template>
      <div v-if="selectedNode" class="property-panel">
        <div class="property-panel-head">
          <div>
            <h2>{{ selectedNode.name }}</h2>
            <p>{{ flowNodeTypeText(selectedNode.node_type) }}</p>
          </div>
          <n-button v-if="!isReadonly" size="small" @click="duplicateSelectedNode">
            <template #icon><Copy  /></template>
            复制节点
          </n-button>
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

        <n-form v-else :model="selectedNode" label-placement="top" class="node-form">
          <section class="node-config-section">
            <div class="node-config-section__head">
              <div>
                <h3>基础信息</h3>
                <p>节点名称与插件类型。</p>
              </div>
            </div>
            <div class="form-grid-row">
              <div class="form-grid-col" style="grid-column: span 12">
                <n-form-item label="节点名称" required>
                  <n-input v-model:value="selectedNode.name" />
                </n-form-item>
              </div>
              <div class="form-grid-col" style="grid-column: span 12">
                <n-form-item label="节点类型">
                  <n-select v-model:value="selectedNode.node_type" @update:value="resetNodeConfig(selectedNode)" :options="(libraryPlugins || []).map((plugin: any) => ({ label: String(plugin.name), value: String(plugin.type) }))" />
                </n-form-item>
              </div>
            </div>
          </section>

          <section class="node-config-section">
            <div class="node-config-section__head">
              <div>
                <h3>失败处理</h3>
                <p>节点执行失败时的模板策略；运行态另有重试 / 跳过 / 强制失败。</p>
              </div>
            </div>
            <n-form-item label="失败策略">
              <n-radio-group v-model:value="selectedNode.config.failure_policy" size="small">
                <n-radio-button value="pause">失败时暂停</n-radio-button>
                <n-radio-button value="ignore">自动忽略继续</n-radio-button>
                <n-radio-button value="stop">失败终止</n-radio-button>
              </n-radio-group>
            </n-form-item>
          </section>

          <section
            v-if="!isReadonly && selectedNodeOutputHooks.length"
            class="node-config-section"
          >
            <div class="node-config-section__head">
              <div>
                <h3>输出</h3>
                <p>勾选后生成全局变量，可在后续节点用 ${KEY} 或 outputs.节点.字段 引用。</p>
              </div>
            </div>
            <div class="output-hook-list">
              <n-checkbox
                v-for="hook in selectedNodeOutputHooks"
                :key="hook.field"
                :checked="isOutputHooked(hook.field)"
                @update:checked="checked => toggleOutputHook(hook, checked)"
              >
                {{ hook.name }}（{{ hook.field }}）
              </n-checkbox>
            </div>
          </section>

          <template v-if="selectedNode.node_type === 'script'">
            <section class="node-config-section">
              <div class="node-config-section__head">
                <div>
                  <h3>输入</h3>
                  <p>脚本类型、目标主机变量、超时和脚本内容。</p>
                </div>
              </div>
              <div class="form-grid-row">
                <div class="form-grid-col" style="grid-column: span 16">
                  <n-form-item label="脚本类型">
                    <n-radio-group v-model:value="selectedNode.config.script_type" @update:value="handleSelectedScriptTypeChange">
                      <n-radio value="shell">Shell</n-radio>
                      <n-radio value="python">Python</n-radio>
                      <n-radio value="powershell">PowerShell</n-radio>
                      <n-radio value="perl">Perl</n-radio>
                      <n-radio value="javascript">JavaScript</n-radio>
                      <n-radio value="go">Go</n-radio>
                    </n-radio-group>
                  </n-form-item>
                </div>
                <div class="form-grid-col" style="grid-column: span 8">
                  <n-form-item label="超时秒数">
                    <n-input-number v-model:value="selectedNode.config.timeout" :min="1" />
                  </n-form-item>
                </div>
              </div>
              <n-form-item label="目标主机" required>
                <div class="naive-input-group">
                  <n-input v-model:value="selectedNode.config.target_host_ids" placeholder="例如 ${CheckHost}" />
                  <n-dropdown trigger="click" :options="(hostVariableOptions || []).map((o: any) => ({ label: o.label, key: String(o.value) }))" @select="value => bindSelectedNodeHostVariable(String(value))">
                    <n-button>插入变量</n-button>
                  </n-dropdown>
                </div>
              </n-form-item>
              <n-form-item label="脚本内容" required>
                <div class="script-editor-block">
                  <n-button size="small" @click="insertSelectedScriptExample">
                    <template #icon><Code2  /></template>
                    插入示例
                  </n-button>
                  <ScriptEditorWithValidation
                    v-model="selectedNode.config.script_content"
                    class="script-monaco-editor"
                    :language="scriptEditorLanguage"
                    theme="vs-dark"
                    :height="560"
                    :readonly="isReadonly"
                    :auto-validate="true"
                  />
                </div>
              </n-form-item>
              <div class="node-config-hint">
                <Info  />
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
                  <h3>输入</h3>
                  <p>文件来源、远端路径、目标主机都通过变量引用串联。</p>
                </div>
              </div>
              <n-form-item label="目标主机" required>
                <div class="naive-input-group">
                  <n-input v-model:value="selectedNode.config.target_host_ids" placeholder="例如 ${CheckHost}" />
                  <n-dropdown trigger="click" :options="(hostVariableOptions || []).map((o: any) => ({ label: o.label, key: String(o.value) }))" @select="value => bindSelectedNodeHostVariable(String(value))">
                    <n-button>插入变量</n-button>
                  </n-dropdown>
                </div>
              </n-form-item>
              <div class="form-grid-row">
                <div class="form-grid-col" style="grid-column: span 12">
                  <n-form-item label="超时秒数">
                    <n-input-number v-model:value="selectedNode.config.timeout" :min="1" />
                  </n-form-item>
                </div>
                <div class="form-grid-col" style="grid-column: span 12">
                  <n-form-item label="限速 MB/s">
                    <n-input-number v-model:value="selectedNode.config.bandwidth_limit" :min="0" />
                  </n-form-item>
                </div>
              </div>
              <div class="file-source-list">
                <div v-for="(source, index) in selectedNode.config.file_sources" :key="index" class="file-source-row">
                  <div class="naive-input-group">
                    <n-input v-model:value="source.download_url" placeholder="下载地址，支持 ${PackageUrl}" />
                    <n-dropdown trigger="click" :options="(allVariableOptions || []).map((o: any) => ({ label: o.label, key: String(o.value) }))" @select="value => insertFileSourceVariable(source, 'download_url', String(value))">
                      <n-button>插入变量</n-button>
                    </n-dropdown>
                  </div>
                  <div class="naive-input-group">
                    <n-input v-model:value="source.remote_path" placeholder="远端路径，支持 ${DeployPath}" />
                    <n-dropdown trigger="click" :options="(allVariableOptions || []).map((o: any) => ({ label: o.label, key: String(o.value) }))" @select="value => insertFileSourceVariable(source, 'remote_path', String(value))">
                      <n-button>插入变量</n-button>
                    </n-dropdown>
                  </div>
                  <n-button size="small" type="error" :disabled="selectedNode.config.file_sources.length <= 1" @click="removeFileSource(index)">
                    <template #icon><Trash2  /></template>
                  </n-button>
                </div>
                <n-button size="small" @click="addFileSource">
                  <template #icon><Plus  /></template>
                  添加文件来源
                </n-button>
              </div>
            </section>
          </template>

          <template v-else-if="selectedNode.node_type === 'job_plan'">
            <section class="node-config-section">
              <div class="node-config-section__head">
                <div>
                  <h3>输入</h3>
                  <p>选择执行方案，方案变量映射到流水线全局变量。</p>
                </div>
                <n-button size="small" :loading="executionPlanDetailLoading" @click="refreshSelectedExecutionPlan">
                  <template #icon><RefreshCw  /></template>
                  刷新方案
                </n-button>
              </div>
              <n-form-item label="作业执行方案" required>
                <n-select v-model:value="selectedNode.config.execution_plan_id" filterable placeholder="选择作业执行方案" @update:value="handleExecutionPlanChange" :options="(executionPlans || []).map((plan: any) => ({ label: String(plan.name), value: Number(plan.id) }))" />
              </n-form-item>
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
                    <div class="naive-input-group">
                      <n-input
                        :model-value="getExecutionParameterBinding(item.key)"
                        placeholder="例如 ${DeployPath}"
                        @update:value="value => setExecutionParameterBinding(item.key, value)"
                      />
                      <n-dropdown trigger="click" :options="(allVariableOptions || []).map((o: any) => ({ label: o.label, key: String(o.value) }))" @select="value => insertExecutionParameterVariable(item.key, String(value))">
                        <n-button>插入变量</n-button>
                      </n-dropdown>
                    </div>
                  </div>
                  <n-empty v-if="selectedExecutionPlanVariables.length === 0" description="选择执行方案后加载变量" />
                </div>
              </div>
            </section>
          </template>

          <template v-else-if="selectedNode.node_type === 'sub_process'">
            <section class="node-config-section">
              <div class="node-config-section__head">
                <div>
                  <h3>输入</h3>
                  <p>嵌套执行另一个流程模板。子流程结束后按失败策略回传本节点结果。</p>
                </div>
                <n-button
                  v-if="selectedSubProcessTemplateId"
                  size="small"
                  @click="openSelectedSubProcessTemplate"
                >
                  查看子流程
                </n-button>
              </div>
              <n-form-item label="子流程模板" required>
                <n-select
                  v-model:value="selectedNode.config.template_id"
                  filterable
                  clearable
                  placeholder="选择子流程模板"
                  :options="subProcessTemplateOptions"
                />
              </n-form-item>
              <n-alert
                v-if="selectedSubProcessTemplate"
                type="info"
                :bordered="false"
                style="margin-bottom: 12px"
              >
                将启动「{{ selectedSubProcessTemplate.name }}」作为子任务；父流程在本节点等待子任务结束。
              </n-alert>
              <n-form-item label="输入继承">
                <div class="sub-process-inherit">
                  <n-switch v-model:value="selectedNode.config.inherit_inputs" />
                  <span>{{ selectedNode.config.inherit_inputs === false ? '独立输入：用下方 JSON 覆盖父流程变量' : '继承输入：把父流程全局变量原样传入子流程' }}</span>
                </div>
              </n-form-item>
              <n-form-item
                v-if="selectedNode.config.inherit_inputs === false"
                label="独立输入 JSON"
                required
              >
                <n-input
                  type="textarea"
                  v-model:value="selectedNode.config.inputs_text"
                  :autosize="{ minRows: 4, maxRows: 10 }"
                  placeholder='例如 {"DeployPath":"/opt/app"}'
                />
              </n-form-item>
            </section>
          </template>

          <template v-else-if="selectedNode.node_type === 'parallel'">
            <section class="node-config-section">
              <div class="node-config-section__head">
                <div>
                  <h3>并行网关</h3>
                  <p>从本节点拉出多条出边，下游分支会同时启动；每条分支最终应汇入汇聚网关。</p>
                </div>
              </div>
              <n-alert type="info" :bordered="false">
                建议至少 2 条出边。失败策略决定任一分支失败时本节点如何处理。
              </n-alert>
              <n-form-item label="说明">
                <n-input type="textarea" v-model:value="selectedNode.config.description" :autosize="{ minRows: 3, maxRows: 5 }" placeholder="例如：检查与分发并行" />
              </n-form-item>
            </section>
          </template>

          <template v-else-if="selectedNode.node_type === 'join'">
            <section class="node-config-section">
              <div class="node-config-section__head">
                <div>
                  <h3>汇聚网关</h3>
                  <p>等待所有入边分支完成后，再继续唯一下游。通常承接并行网关的各条分支。</p>
                </div>
              </div>
              <n-alert type="info" :bordered="false">
                建议至少 2 条入边、1 条出边。未汇齐前父流程在本节点等待。
              </n-alert>
              <n-form-item label="说明">
                <n-input type="textarea" v-model:value="selectedNode.config.description" :autosize="{ minRows: 3, maxRows: 5 }" placeholder="例如：等待检查与分发完成" />
              </n-form-item>
            </section>
          </template>

          <template v-else>
            <section class="node-config-section">
              <div class="node-config-section__head">
                <div>
                  <h3>{{ selectedNode.node_type === 'manual' ? '人工审批' : flowNodeTypeText(selectedNode.node_type) }}</h3>
                  <p>{{ selectedNode.node_type === 'manual' ? '暂停等待审批：通过后继续，拒绝后流水线失败。' : '条件节点按出边表达式选择下游分支。' }}</p>
                </div>
              </div>
              <n-form-item label="说明">
                <n-input type="textarea" v-model:value="selectedNode.config.description" :autosize="{ minRows: 3, maxRows: 5 }" />
              </n-form-item>
              <n-form-item v-if="selectedNode.node_type === 'manual'" label="审批说明">
                <n-input type="textarea" v-model:value="selectedNode.config.instructions" :autosize="{ minRows: 3, maxRows: 5 }" placeholder="展示给审批人的检查要点" />
              </n-form-item>
            </section>
          </template>
        </n-form>
      </div>
      <n-empty v-else description="请选择画布节点" />
    </n-drawer-content></n-drawer>

    <FlowEdgeConditionDrawer
      v-model:visible="edgeConditionVisible"
      :readonly="isReadonly"
      :source-label="selectedEdgeSourceLabel"
      :target-label="selectedEdgeTargetLabel"
      :condition="selectedEdge?.condition || null"
      @save="saveEdgeCondition"
    />

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
import FlowSettingPanel from './FlowSettingPanel.vue'
import FlowEdgeConditionDrawer from './FlowEdgeConditionDrawer.vue'
import { useMessage, NAlert, NButton, NCheckbox, NCheckboxGroup, NDrawer, NDrawerContent, NDropdown, NEmpty, NForm, NFormItem, NInput, NInputNumber, NRadio, NRadioButton, NRadioGroup, NSelect, NSpace, NSpin, NSwitch } from 'naive-ui'
import {
  evaluateFlowGraph,
  FLOW_NODE_OUTPUT_HOOKS,
  flowNodeConfigDisplayRows,
  flowNodeTypeText,
  flowVariableSelectOptions,
  listHookedOutputFields,
  makeComponentOutputVariable,
  normalizeFlowVariables,
  normalizeFlowNode,
  removeFlowVariable,
  resolveFlowTemplateTopology,
  serializeFlowNode,
  summarizeEdgeCondition,
  summarizeFlowNode,
  upsertFlowVariable,
  validateFlowNodeConfigJson,
  type SupportedFlowNodeType,
} from '../flowUtils'
import { ArrowUpDown, CalendarClock, CalendarDays, CheckCircle2, ChevronLeft, Code2, Copy, GitBranch, GitMerge, Info, Layers, LayoutGrid, PanelLeftClose, PanelLeftOpen, Pencil, Play, Plus, RefreshCw, Save, Search, Share2, Trash2, Upload } from 'lucide-vue-next'

const ScriptEditorWithValidation = defineAsyncComponent(() => import('@/components/ScriptEditorWithValidation.vue'))

const message = useMessage()
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
const settingPanelCollapsed = ref(false)
const settingInitialTab = ref<'variables' | 'base' | 'notify'>('variables')
const edgeConditionVisible = ref(false)
const selectedEdgeKey = ref('')
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
  category: '',
  variables: {} as Record<string, any>,
  notify_config: {
    enabled: false,
    events: ['success', 'failed'] as string[],
    webhook_url: '',
  },
  is_active: true,
  is_public: false,
})
const nodes = ref<FlowNode[]>([])
const edges = ref<FlowEdge[]>([])
const workbenchTitle = computed(() => {
  if (isReadonly.value) return form.name || '流水线详情'
  return isEdit.value ? '编辑流水线' : '新建流水线'
})

const fallbackPlugins: FlowNodePluginOption[] = [
  { type: 'script', name: '脚本执行', description: '快速执行脚本', category: '作业原子', risk: '中', icon: Code2 },
  { type: 'file_transfer', name: '文件分发', description: '上传或下载文件', category: '作业原子', risk: '中', icon: Upload },
  { type: 'job_plan', name: '作业执行方案', description: '调用作业方案', category: '作业编排', risk: '高', icon: CalendarDays },
  { type: 'manual', name: '人工审批', description: '暂停等待通过或拒绝', category: '控制节点', risk: '低', icon: CheckCircle2 },
  { type: 'condition', name: '条件分支', description: '按变量选择分支', category: '控制节点', risk: '低', icon: GitBranch },
  { type: 'parallel', name: '并行网关', description: '并行启动下游', category: '控制节点', risk: '低', icon: Share2 },
  { type: 'join', name: '汇聚网关', description: '等待分支汇聚', category: '控制节点', risk: '低', icon: GitMerge },
  { type: 'sub_process', name: '子流程', description: '嵌套执行模板', category: '流程编排', risk: '中', icon: Layers },
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
    icon: fallbackPlugins.find(item => item.type === plugin.type)?.icon || LayoutGrid,
  }))
})
const selectedNode = computed(() => nodes.value.find(item => item.uuid === selectedUuid.value) || null)
const selectedNodeConfigRows = computed(() => selectedNode.value ? flowNodeConfigDisplayRows(selectedNode.value) : [])
const subProcessTemplateOptions = computed(() =>
  (flowTemplates.value || [])
    .filter(template => template.id && template.id !== currentTemplate.value?.id)
    .map(template => ({
      label: template.name,
      value: template.id as number,
    })),
)
const selectedSubProcessTemplateId = computed(() => {
  const raw = selectedNode.value?.config?.template_id
  const id = Number(raw)
  return Number.isFinite(id) && id > 0 ? id : null
})
const selectedSubProcessTemplate = computed(() =>
  selectedSubProcessTemplateId.value
    ? flowTemplates.value.find(template => template.id === selectedSubProcessTemplateId.value) || null
    : null,
)
const openSelectedSubProcessTemplate = () => {
  if (!selectedSubProcessTemplateId.value) return
  router.push(`/flows/${selectedSubProcessTemplateId.value}/detail`)
}
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
    icon: libraryPlugins.value.find(plugin => plugin.type === node.node_type)?.icon || LayoutGrid,
    selected: selectedUuid.value === node.uuid,
  },
})))
const flowEdges = computed<Edge[]>(() => edges.value.filter(edge => edge.source_uuid && edge.target_uuid).map((edge, index) => {
  const id = `${edge.source_uuid}-${edge.target_uuid}-${index}`
  const label = edge.condition?.default
    ? '默认'
    : (edge.condition && Object.keys(edge.condition).length
      ? summarizeEdgeCondition(edge.condition)
      : '')
  return {
    id,
    source: edge.source_uuid!,
    target: edge.target_uuid!,
    type: 'smoothstep',
    markerEnd: MarkerType.ArrowClosed,
    label,
    data: { edgeIndex: index },
  }
}))
const selectedEdge = computed(() => {
  if (!selectedEdgeKey.value) return null
  const index = edges.value.findIndex((edge, edgeIndex) =>
    `${edge.source_uuid}-${edge.target_uuid}-${edgeIndex}` === selectedEdgeKey.value,
  )
  return index >= 0 ? edges.value[index] : null
})
const selectedEdgeSourceLabel = computed(() => {
  const edge = selectedEdge.value
  if (!edge) return '-'
  return nodes.value.find(item => item.uuid === edge.source_uuid)?.name || edge.source_uuid || '-'
})
const selectedEdgeTargetLabel = computed(() => {
  const edge = selectedEdge.value
  if (!edge) return '-'
  return nodes.value.find(item => item.uuid === edge.target_uuid)?.name || edge.target_uuid || '-'
})
const selectedNodeOutputHooks = computed(() => {
  const type = selectedNode.value?.node_type || ''
  return FLOW_NODE_OUTPUT_HOOKS[type] || []
})
const openSettingTab = (tab: 'variables' | 'base' | 'notify') => {
  settingInitialTab.value = tab
  settingPanelCollapsed.value = false
}
const isOutputHooked = (field: string) => {
  if (!selectedNode.value) return false
  return listHookedOutputFields(form.variables, selectedNode.value.uuid).includes(field)
}
const toggleOutputHook = (
  hook: { field: string; name: string; type?: 'text' | 'number' | 'boolean' | 'secret' | 'host_list' | 'select' },
  checked: boolean,
) => {
  if (!selectedNode.value) return
  if (checked) {
    form.variables = upsertFlowVariable(
      form.variables,
      makeComponentOutputVariable(selectedNode.value, hook.field, hook.name, hook.type || 'text'),
    )
    return
  }
  const key = makeComponentOutputVariable(selectedNode.value, hook.field, hook.name, hook.type || 'text').key
  form.variables = removeFlowVariable(form.variables, key)
}

const normalizeList = <T,>(value: any): T[] => Array.isArray(value) ? value : value?.results || value?.data || []
const normalizePaginatedList = <T,>(value: any): T[] =>
  value && !Array.isArray(value) && Array.isArray(value.results) ? value.results as T[] : []
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
  selectedEdgeKey.value = ''
  openPropertyDrawer()
}
const handleFlowEdgeClick = ({ edge }: { edge: Edge }) => {
  const sourceNode = nodes.value.find(item => item.uuid === edge.source)
  if (sourceNode?.node_type !== 'condition') {
    message.info('仅条件分支节点的出边可配置表达式')
    return
  }
  selectedEdgeKey.value = edge.id
  edgeConditionVisible.value = true
}
const saveEdgeCondition = (condition: Record<string, any>) => {
  const index = edges.value.findIndex((edge, edgeIndex) =>
    `${edge.source_uuid}-${edge.target_uuid}-${edgeIndex}` === selectedEdgeKey.value,
  )
  if (index < 0) return
  edges.value[index] = { ...edges.value[index], condition }
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
    message.info('当前没有需要定位的节点问题')
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
    message.warning('加载执行方案变量失败')
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
    message.warning(`${badNode.name} 的目标主机必须绑定 host_list 全局变量`)
    return false
  }
  return true
}
const loadData = async () => {
  loading.value = true
  try {
    const [planResult, templateListResult, pluginResult] = await Promise.allSettled([
      executionPlanApi.getPlans({ page_size: 200 }),
      flowApi.getTemplates({ page: 1, page_size: 200 }),
      flowApi.getNodePlugins(),
    ])
    executionPlans.value = planResult.status === 'fulfilled' ? normalizeList<ExecutionPlan>(planResult.value) : []
    flowTemplates.value = templateListResult.status === 'fulfilled' ? normalizePaginatedList<FlowTemplate>(templateListResult.value) : []
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
      form.category = template.category || ''
      form.variables = template.variables || {}
      form.notify_config = {
        enabled: Boolean(template.notify_config?.enabled),
        events: Array.isArray(template.notify_config?.events) && template.notify_config.events.length
          ? [...template.notify_config.events]
          : ['success', 'failed'],
        webhook_url: template.notify_config?.webhook_url || '',
      }
      form.is_active = template.is_active
      form.is_public = Boolean(template.is_public)
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
      form.category = ''
      form.variables = {}
      form.notify_config = { enabled: false, events: ['success', 'failed'], webhook_url: '' }
      form.is_active = true
      form.is_public = false
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
    message.error('加载流水线编辑数据失败')
  } finally {
    loading.value = false
  }
}
const saveTemplate = async () => {
  if (isReadonly.value) return
  if (!form.name.trim()) {
    message.warning('请填写流水线名称')
    return
  }
  const blockingIssue = validation.value.issues.find(issue => issue.severity === 'error')
  if (blockingIssue) {
    selectFirstInvalidNode()
    message.warning(blockingIssue.message)
    return
  }
  for (const node of nodes.value) {
    const jsonValidation = validateFlowNodeConfigJson(node)
    if (!jsonValidation.valid) {
      selectedUuid.value = node.uuid
      openPropertyDrawer()
      message.warning(jsonValidation.message || '节点配置格式不正确')
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
    message.success('流水线已保存')
    if (!isEdit.value && result.id) router.replace(`/flows/${result.id}/edit`)
  } catch (error) {
    console.error('保存流水线失败:', error)
    message.error('保存流水线失败')
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
  flex: 1 1 auto;
  width: 100%;
  max-width: 100%;
  height: 100%;
  min-height: 0;
  min-width: 0;
  padding: 0;
  overflow: hidden;
  background: #f5f7fb;
}
.header-switch {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--app-muted);
  font-size: 12px;
  white-space: nowrap;
  cursor: pointer;
}
.flow-editor-command {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 10px;
  align-items: center;
  min-width: 0;
  height: 44px;
  padding: 0 10px;
  background: #fff;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
}
.flow-editor-command__title {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.flow-editor-command__title h1 {
  margin: 0;
  color: var(--app-fg);
  font-size: 14px;
  line-height: 1.2;
  white-space: nowrap;
}
.flow-editor-command__meta {
  color: var(--app-muted);
  font-size: 12px;
  white-space: nowrap;
}
.flow-editor-command__form {
  display: flex;
  flex-wrap: nowrap;
  gap: 8px;
  align-items: center;
  min-width: 0;
  overflow: hidden;
}
.flow-editor-command__form :deep(.n-form-item) {
  margin: 0;
}
.readonly-template-meta {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--app-muted);
  font-size: 12px;
}
.flow-editor-command__actions {
  justify-content: flex-end;
  flex-wrap: nowrap;
}
.flow-editor-spin {
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}
.flow-editor-spin :deep(.n-spin-container),
.flow-editor-spin :deep(.n-spin-content) {
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}
.flow-editor-workbench {
  display: grid;
  grid-template-columns: 200px minmax(0, 1fr) minmax(280px, 360px);
  gap: 8px;
  flex: 1 1 auto;
  width: 100%;
  max-width: 100%;
  height: 100%;
  min-height: 0;
  min-width: 0;
  overflow: hidden;
}
.flow-editor-workbench:has(.flow-setting-panel--collapsed) {
  grid-template-columns: 200px minmax(0, 1fr) 44px;
}
.output-hook-list {
  display: grid;
  gap: 8px;
}
.flow-plugin-rail {
  position: relative;
  display: flex;
  flex-direction: column;
  height: 100%;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  background: #fff;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
}
.flow-plugin-rail :deep(.node-library) {
  flex: 1 1 auto;
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
  grid-template-rows: auto minmax(0, 1fr);
  gap: 6px;
  min-width: 0;
  min-height: 0;
  padding: 8px;
  overflow: hidden;
  background: #fff;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
}
.flow-canvas-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-width: 0;
}
.flow-canvas-toolbar__lead {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.flow-canvas-toolbar h2 {
  margin: 0;
  color: var(--app-fg);
  font-size: 13px;
  font-weight: 650;
  white-space: nowrap;
}
.flow-validation-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 6px;
}
.flow-validation-strip--inline {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.flow-validation-strip div {
  display: inline-flex;
  align-items: baseline;
  gap: 4px;
  min-width: 0;
  padding: 2px 6px;
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
  font-size: 12px;
}
.flow-validation-strip span {
  color: var(--app-muted);
  font-size: 11px;
  white-space: nowrap;
}
.flow-canvas-frame {
  position: relative;
  height: 100%;
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
  min-height: 0;
}
.ops-flow :deep(.vue-flow__controls) {
  left: 8px;
  bottom: 8px;
  margin: 0;
  box-shadow: 0 1px 4px rgba(15, 23, 42, 0.12);
}
.ops-flow :deep(.vue-flow__controls-button) {
  width: 26px;
  height: 26px;
}
.ops-flow :deep(.vue-flow__minimap) {
  right: 8px;
  bottom: 8px;
  margin: 0;
  width: 112px !important;
  height: 72px !important;
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
.sub-process-inherit {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--app-muted);
  font-size: 13px;
  line-height: 1.4;
}
.script-editor-block {
  display: grid;
  gap: 8px;
  width: 100%;
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
  .flow-editor-command {
    height: auto;
    min-height: 44px;
    padding: 6px 10px;
    grid-template-columns: 1fr;
  }
  .flow-editor-command__form {
    flex-wrap: wrap;
  }
}
@media (max-width: 1180px) {
  .flow-editor-workbench {
    grid-template-columns: 180px minmax(0, 1fr) minmax(260px, 320px);
  }
}
@media (max-width: 780px) {
  .flow-editor-workbench {
    grid-template-columns: 1fr;
    grid-template-rows: minmax(180px, 28vh) minmax(0, 1fr) minmax(220px, 36vh);
  }
  .flow-plugin-rail {
    min-height: 0;
  }
  .file-source-row,
  .execution-parameter-row {
    grid-template-columns: 1fr;
  }
}
</style>
