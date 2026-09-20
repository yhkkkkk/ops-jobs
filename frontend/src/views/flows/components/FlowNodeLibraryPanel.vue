<template>
  <aside :class="['node-library', { 'node-library--readonly': readonly }]">
    <div class="workbench-panel-head">
      <div>
        <h2>节点插件库</h2>
        <p>标准插件 / 场景模板</p>
      </div>
    </div>
    <a-input v-model="search" class="node-search" allow-clear placeholder="搜索执行动作或流程控制" />
    <div class="node-library-note">
      控制节点由流程引擎处理，不是 Agent 执行动作。
    </div>
    <div class="scenario-box">
      <div class="scenario-box__head">
        <h3>标准场景</h3>
        <span>模板化编排</span>
      </div>
      <button v-for="scenario in scenarios" :key="scenario.key" type="button" class="scenario-row" :disabled="readonly" @click="handleScenarioClick(scenario.key)">
        <strong>{{ scenario.name }}</strong>
        <em>{{ scenario.description }}</em>
      </button>
    </div>
    <section v-for="group in groupedPlugins" :key="group.key" class="plugin-group">
      <div class="plugin-group__head">
        <h3>{{ group.title }}</h3>
        <span>{{ group.description }}</span>
      </div>
      <button
        v-for="plugin in group.plugins"
        :key="plugin.type"
        class="plugin-card"
        type="button"
        :disabled="readonly"
        :draggable="!readonly"
        @click="handlePluginClick(plugin.type)"
        @dragstart="handlePluginDragStart($event, plugin)"
      >
        <span class="plugin-card__icon"><component :is="plugin.icon" /></span>
        <span>
          <strong>{{ plugin.name }}</strong>
          <small>{{ plugin.category }} / {{ plugin.risk }}</small>
        </span>
      </button>
    </section>
    <a-empty v-if="groupedPlugins.every(group => group.plugins.length === 0)" description="没有匹配的节点类型" />

    <div class="status-legend">
      <span><i class="legend-dot legend-dot--success" /> 成功</span>
      <span><i class="legend-dot legend-dot--warn" /> 执行/暂停</span>
      <span><i class="legend-dot legend-dot--danger" /> 失败</span>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { SupportedFlowNodeType } from '../flowUtils'

export interface FlowNodePluginOption {
  type: SupportedFlowNodeType
  name: string
  description: string
  category: string
  risk: string
  icon: string
}

export interface FlowScenarioOption {
  key: 'release' | 'dispatch'
  name: string
  description: string
}

const props = defineProps<{
  plugins: FlowNodePluginOption[]
  scenarios: FlowScenarioOption[]
  readonly?: boolean
}>()

const emit = defineEmits<{
  addNode: [type: SupportedFlowNodeType]
  applyScenario: [key: 'release' | 'dispatch']
}>()

const search = ref('')
const readonly = computed(() => props.readonly === true)
const filteredPlugins = computed(() => {
  const keyword = search.value.trim().toLowerCase()
  if (!keyword) return props.plugins
  return props.plugins.filter(plugin =>
    plugin.name.toLowerCase().includes(keyword) ||
    plugin.description.toLowerCase().includes(keyword) ||
    plugin.type.includes(keyword)
  )
})
const executionNodeTypes: SupportedFlowNodeType[] = ['script', 'file_transfer', 'job_plan']
const controlNodeTypes: SupportedFlowNodeType[] = ['manual', 'condition', 'parallel', 'join', 'sub_process']
const groupedPlugins = computed(() => [
  {
    key: 'execution',
    title: '执行动作',
    description: '由 Agent 执行脚本、文件和作业方案',
    plugins: filteredPlugins.value.filter(plugin => executionNodeTypes.includes(plugin.type)),
  },
  {
    key: 'control',
    title: '流程控制',
    description: '由流程引擎负责暂停、分支、并行和汇聚',
    plugins: filteredPlugins.value.filter(plugin => controlNodeTypes.includes(plugin.type)),
  },
])

const handlePluginDragStart = (event: DragEvent, plugin: FlowNodePluginOption) => {
  if (readonly.value) {
    event.preventDefault()
    return
  }
  if (!event.dataTransfer) return
  event.dataTransfer.effectAllowed = 'copy'
  event.dataTransfer.setData('application/x-flow-node-type', plugin.type)
  event.dataTransfer.setData('text/plain', plugin.type)
}
const handlePluginClick = (type: SupportedFlowNodeType) => {
  if (!readonly.value) emit('addNode', type)
}
const handleScenarioClick = (key: 'release' | 'dispatch') => {
  if (!readonly.value) emit('applyScenario', key)
}
</script>

<style scoped>
.node-library {
  display: flex;
  flex-direction: column;
  min-height: 0;
  min-width: 0;
  overflow: auto;
  padding: 7px;
  background: #fff;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
}
.workbench-panel-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 6px;
}
.workbench-panel-head h2 { margin: 0; color: var(--app-fg); font-size: 14px; line-height: 1.25; }
.workbench-panel-head p { margin: 3px 0 0; color: var(--app-muted); font-size: 11px; line-height: 1.35; }
.node-search {
  width: 100%;
  margin-bottom: 6px;
}
.node-search :deep(.arco-input-wrapper) {
  width: 100%;
  height: 30px;
  font-size: 12px;
}
.node-library-note {
  margin: 0 0 6px;
  padding: 6px 7px;
  color: var(--app-muted);
  font-size: 11px;
  line-height: 1.45;
  background: var(--app-surface-soft);
  border-left: 2px solid var(--app-accent);
}
.scenario-box {
  display: grid;
  gap: 3px;
  margin-bottom: 6px;
  padding: 6px;
  background: var(--app-surface-soft);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
}
.scenario-box__head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 8px;
}
.scenario-box h3 { margin: 0; color: var(--app-fg); font-size: 12px; line-height: 1.25; }
.scenario-box span { color: var(--app-muted); font-size: 11px; }
.scenario-row {
  display: grid;
  width: 100%;
  min-width: 0;
  padding: 5px 6px;
  text-align: left;
  background: #fff;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
  cursor: pointer;
}
.scenario-row:hover { border-color: var(--app-accent); }
.scenario-box strong { overflow: hidden; color: var(--app-fg); font-size: 12px; line-height: 1.3; text-overflow: ellipsis; white-space: nowrap; }
.scenario-box em { overflow: hidden; color: var(--app-muted); font-size: 11px; font-style: normal; line-height: 1.3; text-overflow: ellipsis; white-space: nowrap; }
.plugin-card {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  min-width: 0;
  min-height: 32px;
  padding: 4px 6px;
  margin-bottom: 4px;
  text-align: left;
  background: #fff;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
  cursor: pointer;
}
.plugin-group {
  display: grid;
  gap: 2px;
  margin-bottom: 5px;
}
.plugin-group__head {
  display: grid;
  gap: 1px;
  padding: 4px 2px 3px;
}
.plugin-group__head h3 {
  margin: 0;
  color: var(--app-fg);
  font-size: 12px;
  line-height: 1.3;
}
.plugin-group__head span {
  color: var(--app-muted);
  font-size: 10px;
  line-height: 1.3;
}
.plugin-card:hover { border-color: var(--app-accent); background: var(--app-accent-soft); }
.plugin-card:active { cursor: grabbing; }
.node-library--readonly .scenario-row,
.node-library--readonly .plugin-card {
  cursor: default;
  opacity: .74;
}
.node-library--readonly .scenario-row:hover,
.node-library--readonly .plugin-card:hover {
  background: #fff;
  border-color: var(--app-border);
}
.plugin-card__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 20px;
  width: 20px;
  height: 20px;
  color: var(--app-accent);
  background: var(--app-accent-soft);
  border-radius: var(--app-radius-sm);
}
.plugin-card__icon svg { font-size: 13px; }
.plugin-card > span:last-child { min-width: 0; }
.plugin-card strong,
.plugin-card small { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.plugin-card strong { color: var(--app-fg); font-size: 12px; line-height: 1.2; }
.plugin-card small {
  color: var(--app-meta);
  font-family: var(--app-mono);
  font-size: 10px;
  line-height: 1.2;
}
.status-legend {
  display: grid;
  gap: 4px;
  margin-top: auto;
  padding-top: 7px;
  border-top: 1px solid var(--app-border);
  color: var(--app-muted);
  font-size: 11px;
}
.status-legend span { display: inline-flex; align-items: center; gap: 7px; }
.legend-dot { width: 7px; height: 7px; border-radius: var(--app-radius-pill); background: var(--app-muted); }
.legend-dot--success { background: var(--app-success); }
.legend-dot--warn { background: var(--app-warn); }
.legend-dot--danger { background: var(--app-danger); }
</style>
