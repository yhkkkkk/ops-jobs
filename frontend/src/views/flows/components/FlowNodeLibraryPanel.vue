<template>
  <aside class="node-library">
    <div class="workbench-panel-head">
      <div>
        <h2>节点插件库</h2>
        <p>拖入画布，或点击串到末尾。</p>
      </div>
    </div>
    <a-input v-model="search" class="node-search" allow-clear placeholder="搜索脚本、文件、作业、子流程" />
    <div class="scenario-box">
      <div class="scenario-box__head">
        <h3>标准场景</h3>
        <span>模板化编排</span>
      </div>
      <button v-for="scenario in scenarios" :key="scenario.key" type="button" class="scenario-row" @click="emit('applyScenario', scenario.key)">
        <strong>{{ scenario.name }}</strong>
        <em>{{ scenario.description }}</em>
      </button>
    </div>
    <button
      v-for="plugin in filteredPlugins"
      :key="plugin.type"
      class="plugin-card"
      type="button"
      draggable="true"
      @click="emit('addNode', plugin.type)"
      @dragstart="handlePluginDragStart($event, plugin)"
    >
      <span class="plugin-card__icon"><component :is="plugin.icon" /></span>
      <span>
        <strong>{{ plugin.name }}</strong>
        <small>{{ plugin.category }} / {{ plugin.risk }}</small>
      </span>
    </button>
    <a-empty v-if="filteredPlugins.length === 0" description="没有匹配的节点类型" />

    <div class="library-guide">
      <h3>配置顺序</h3>
      <ol>
        <li>添加节点并连线</li>
        <li>逐个补齐右侧字段</li>
        <li>切到预览检查状态</li>
        <li>保存模板后启动执行</li>
      </ol>
    </div>
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
}>()

const emit = defineEmits<{
  addNode: [type: SupportedFlowNodeType]
  applyScenario: [key: 'release' | 'dispatch']
}>()

const search = ref('')
const filteredPlugins = computed(() => {
  const keyword = search.value.trim().toLowerCase()
  if (!keyword) return props.plugins
  return props.plugins.filter(plugin =>
    plugin.name.toLowerCase().includes(keyword) ||
    plugin.description.toLowerCase().includes(keyword) ||
    plugin.type.includes(keyword)
  )
})

const handlePluginDragStart = (event: DragEvent, plugin: FlowNodePluginOption) => {
  if (!event.dataTransfer) return
  event.dataTransfer.effectAllowed = 'copy'
  event.dataTransfer.setData('application/x-flow-node-type', plugin.type)
  event.dataTransfer.setData('text/plain', plugin.type)
}
</script>

<style scoped>
.node-library {
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: auto;
  padding: 10px;
  background: #fff;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
}
.workbench-panel-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 8px;
}
.workbench-panel-head h2 { margin: 0; color: var(--app-fg); font-size: 15px; line-height: 1.3; }
.workbench-panel-head p { margin: 4px 0 0; color: var(--app-muted); font-size: 12px; line-height: 1.4; }
.node-search { margin-bottom: 8px; }
.scenario-box {
  display: grid;
  gap: 5px;
  margin-bottom: 8px;
  padding: 8px;
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
.scenario-box h3 { margin: 0; color: var(--app-fg); font-size: 13px; line-height: 1.3; }
.scenario-box span { color: var(--app-muted); font-size: 12px; }
.scenario-row {
  display: grid;
  gap: 1px;
  width: 100%;
  padding: 7px 8px;
  text-align: left;
  background: #fff;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
  cursor: pointer;
}
.scenario-row:hover { border-color: var(--app-accent); }
.scenario-box strong { color: var(--app-fg); font-size: 12px; line-height: 1.35; }
.scenario-box em { color: var(--app-muted); font-size: 12px; font-style: normal; line-height: 1.4; }
.plugin-card {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  min-height: 42px;
  padding: 7px 8px;
  margin-bottom: 6px;
  text-align: left;
  background: #fff;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
  cursor: pointer;
}
.plugin-card:hover { border-color: var(--app-accent); background: var(--app-accent-soft); }
.plugin-card:active { cursor: grabbing; }
.plugin-card__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 24px;
  width: 24px;
  height: 24px;
  color: var(--app-accent);
  background: var(--app-accent-soft);
  border-radius: var(--app-radius-sm);
}
.plugin-card > span:last-child { min-width: 0; }
.plugin-card strong,
.plugin-card small { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.plugin-card strong { color: var(--app-fg); font-size: 13px; line-height: 1.35; }
.plugin-card small {
  margin-top: 2px;
  color: var(--app-meta);
  font-family: var(--app-mono);
  font-size: 11px;
  line-height: 1.3;
}
.library-guide { margin-top: auto; padding-top: 12px; border-top: 1px solid var(--app-border); }
.library-guide h3 { margin: 0 0 8px; color: var(--app-fg); font-size: 13px; }
.library-guide ol { display: grid; gap: 6px; margin: 0; padding-left: 18px; color: var(--app-muted); font-size: 12px; line-height: 1.45; }
.status-legend {
  display: grid;
  gap: 7px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--app-border);
  color: var(--app-muted);
  font-size: 12px;
}
.status-legend span { display: inline-flex; align-items: center; gap: 7px; }
.legend-dot { width: 7px; height: 7px; border-radius: var(--app-radius-pill); background: var(--app-muted); }
.legend-dot--success { background: var(--app-success); }
.legend-dot--warn { background: var(--app-warn); }
.legend-dot--danger { background: var(--app-danger); }
</style>
