<template>
  <a-drawer :visible="visible" title="流水线详情" :width="drawerWidth" unmount-on-close @update:visible="emit('update:visible', $event)">
    <template v-if="template">
      <div class="readonly-flow-workbench">
        <main class="readonly-flow-preview">
          <div class="readonly-section-head">
            <div>
              <h3>只读编排</h3>
              <p>{{ template.nodes?.length || 0 }} 个节点 / {{ template.edges?.length || 0 }} 条连线</p>
            </div>
            <StatusBadge :status="template.is_active ? 'success' : 'muted'" :text="template.is_active ? '启用' : '停用'" />
          </div>

          <div v-if="(template.nodes || []).length" class="readonly-node-list">
            <article
              v-for="(node, index) in template.nodes || []"
              :key="node.uuid"
              :class="['readonly-node-card', { 'readonly-node-card--active': selectedNode?.uuid === node.uuid }]"
              @click="selectedNodeUuid = node.uuid"
            >
              <span class="readonly-node-index">{{ index + 1 }}</span>
              <div>
                <strong>{{ node.name }}</strong>
                <em>{{ flowNodeTypeText(node.node_type) }} / {{ summarizeFlowNode(node) }}</em>
              </div>
            </article>
          </div>
          <a-empty v-else description="当前流水线没有节点" />

          <div class="readonly-edge-list">
            <div class="readonly-edge-list__head">
              <strong>连线</strong>
              <span>{{ template.edges?.length || 0 }} 条</span>
            </div>
            <div v-if="(template.edges || []).length" class="readonly-edge-rows">
              <div v-for="edge in template.edges || []" :key="`${edge.source_uuid}-${edge.target_uuid}`" class="readonly-edge-row">
                <span>{{ nodeName(edge.source_uuid) }}</span>
                <icon-arrow-right />
                <span>{{ nodeName(edge.target_uuid) }}</span>
              </div>
            </div>
            <a-empty v-else description="当前流水线没有连线" />
          </div>
        </main>

        <aside class="readonly-flow-side">
          <a-tabs class="readonly-inspector-tabs" size="small">
            <a-tab-pane key="node" title="节点配置">
              <section class="drawer-section drawer-section--tight">
                <div class="inspector-node-head">
                  <div>
                    <h3>{{ selectedNode?.name || '未选择节点' }}</h3>
                    <span>{{ selectedNode ? flowNodeTypeText(selectedNode.node_type) : '点击左侧节点查看配置' }}</span>
                  </div>
                  <StatusBadge v-if="selectedNode" status="muted" text="只读" />
                </div>
                <div v-if="selectedNode" class="node-config-rows">
                  <div v-for="row in selectedNodeConfigRows" :key="row.label" class="node-config-row">
                    <span>{{ row.label }}</span>
                    <pre v-if="row.multiline">{{ row.value }}</pre>
                    <strong v-else>{{ row.value }}</strong>
                  </div>
                </div>
                <a-empty v-else description="请选择一个节点" />
              </section>
            </a-tab-pane>

            <a-tab-pane key="variables" title="全局变量">
              <section class="drawer-section drawer-section--tight">
                <FlowVariableReadOnlyPanel :variables="template.variables || {}" empty-text="当前流水线没有全局变量定义" />
              </section>
            </a-tab-pane>

            <a-tab-pane key="meta" title="基本信息">
              <section class="drawer-section drawer-section--tight">
                <h3>基本信息</h3>
                <a-descriptions :column="1" bordered size="medium">
                  <a-descriptions-item label="名称">{{ template.name }}</a-descriptions-item>
                  <a-descriptions-item label="描述">{{ template.description || '-' }}</a-descriptions-item>
                  <a-descriptions-item label="负责人">{{ template.created_by_name || '-' }}</a-descriptions-item>
                  <a-descriptions-item label="更新时间">{{ formatTime(template.updated_at || template.created_at) }}</a-descriptions-item>
                </a-descriptions>
              </section>

              <section class="drawer-section">
                <h3>最近执行</h3>
                <div v-if="latestRun" class="drawer-latest-run">
                  <div>
                    <a-link @click="emit('openRun', latestRun.id)">执行 {{ latestRun.id }}</a-link>
                    <span>{{ latestRun.started_by_name || '-' }}</span>
                    <span>{{ formatTime(latestRun.started_at || latestRun.created_at) }}</span>
                  </div>
                  <StatusBadge :status="latestRun.status" :text="flowRunStatusText(latestRun.status)" />
                </div>
                <span v-else class="drawer-muted">暂无执行记录</span>
              </section>
            </a-tab-pane>
          </a-tabs>
        </aside>
      </div>
    </template>
  </a-drawer>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { FlowNode, FlowRun, FlowTemplate } from '@/types'
import { StatusBadge } from '@/components/app'
import { flowNodeConfigDisplayRows, flowNodeTypeText, flowRunStatusText, summarizeFlowNode } from '../flowUtils'
import FlowVariableReadOnlyPanel from './FlowVariableReadOnlyPanel.vue'

const props = defineProps<{
  visible: boolean
  template: FlowTemplate | null
  latestRun?: FlowRun
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  openRun: [runId: number]
}>()

const visible = computed(() => props.visible)
const template = computed(() => props.template)
const latestRun = computed(() => props.latestRun)
const drawerWidth = 'min(1080px, calc(100vw - 24px))'
const selectedNodeUuid = ref('')
const selectedNode = computed<FlowNode | undefined>(() =>
  props.template?.nodes?.find(item => item.uuid === selectedNodeUuid.value) || props.template?.nodes?.[0]
)
const selectedNodeConfigRows = computed(() => selectedNode.value ? flowNodeConfigDisplayRows(selectedNode.value) : [])

watch(template, current => {
  selectedNodeUuid.value = current?.nodes?.[0]?.uuid || ''
}, { immediate: true })

const nodeName = (uuid?: string) => {
  const node = props.template?.nodes?.find(item => item.uuid === uuid)
  return node?.name || '未知节点'
}
const formatTime = (value?: string | null) => value ? new Date(value).toLocaleString('zh-CN') : '-'
</script>

<style scoped>
.readonly-flow-workbench {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 360px;
  gap: 12px;
  min-width: 0;
}
.readonly-flow-preview,
.readonly-flow-side {
  min-width: 0;
}
.readonly-flow-preview {
  display: grid;
  align-content: start;
  gap: 12px;
  padding: 12px;
  background: #f7f9fc;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
}
.readonly-section-head,
.readonly-edge-list__head,
.drawer-latest-run {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 10px;
  min-width: 0;
}
.readonly-section-head h3,
.drawer-section h3 {
  margin: 0;
  color: var(--app-fg);
  font-size: 14px;
  line-height: 1.35;
}
.readonly-section-head p {
  margin: 3px 0 0;
  color: var(--app-muted);
  font-size: 12px;
}
.readonly-node-list,
.readonly-edge-rows,
.readonly-flow-side {
  display: grid;
  gap: 8px;
}
.readonly-node-card {
  display: grid;
  grid-template-columns: 28px minmax(0, 1fr);
  gap: 10px;
  align-items: center;
  min-width: 0;
  min-height: 58px;
  padding: 9px 10px;
  background: #fff;
  border: 1px solid var(--app-border);
  border-left: 3px solid var(--app-accent);
  border-radius: var(--app-radius-sm);
  cursor: pointer;
  transition: border-color 160ms ease, box-shadow 160ms ease, background 160ms ease;
}
.readonly-node-card--active {
  background: color-mix(in srgb, var(--app-accent) 6%, #fff);
  border-color: color-mix(in srgb, var(--app-accent) 34%, var(--app-border));
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--app-accent) 18%, transparent);
}
.readonly-node-index {
  display: grid;
  place-items: center;
  width: 24px;
  height: 24px;
  color: var(--app-accent);
  background: var(--app-accent-soft);
  border-radius: var(--app-radius-pill);
  font-family: var(--app-mono);
  font-size: 11px;
  font-weight: 700;
}
.readonly-node-card div {
  display: grid;
  gap: 3px;
  min-width: 0;
}
.readonly-node-card strong,
.readonly-node-card em,
.readonly-edge-row span,
.drawer-latest-run span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.readonly-node-card strong {
  color: var(--app-fg);
  font-size: 13px;
  line-height: 1.35;
}
.readonly-node-card em {
  color: var(--app-muted);
  font-size: 12px;
  font-style: normal;
  line-height: 1.35;
}
.readonly-edge-list {
  display: grid;
  gap: 8px;
  padding-top: 10px;
  border-top: 1px solid var(--app-border);
}
.readonly-edge-list__head strong,
.readonly-edge-list__head span {
  font-size: 12px;
}
.readonly-edge-list__head strong { color: var(--app-fg); }
.readonly-edge-list__head span { color: var(--app-muted); }
.readonly-edge-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  gap: 8px;
  align-items: center;
  min-width: 0;
  padding: 8px 10px;
  color: var(--app-muted);
  background: #fff;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
  font-size: 12px;
}
.readonly-edge-row span { color: var(--app-fg); }
.drawer-section { display: grid; gap: 10px; margin-top: 12px; }
.drawer-section--tight { margin-top: 0; }
.drawer-section h3 { margin: 0; color: var(--app-fg); font-size: 14px; }
.readonly-inspector-tabs {
  min-width: 0;
}
.inspector-node-head {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  min-width: 0;
}
.inspector-node-head div {
  display: grid;
  gap: 3px;
  min-width: 0;
}
.inspector-node-head span {
  overflow: hidden;
  color: var(--app-muted);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.node-config-rows {
  display: grid;
  gap: 8px;
  max-height: 560px;
  overflow: auto;
  padding-right: 4px;
}
.node-config-row {
  display: grid;
  gap: 5px;
  min-width: 0;
  padding: 8px 10px;
  background: var(--app-surface-soft);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
}
.node-config-row span {
  color: var(--app-muted);
  font-size: 11px;
  line-height: 1.35;
}
.node-config-row strong,
.node-config-row pre {
  margin: 0;
  color: var(--app-fg);
  font-size: 12px;
  line-height: 1.45;
}
.node-config-row strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.node-config-row pre {
  max-height: 180px;
  overflow: auto;
  font-family: var(--app-mono);
  white-space: pre-wrap;
  word-break: break-word;
}
.drawer-latest-run {
  padding: 10px 12px;
  background: var(--app-surface-soft);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
}
.drawer-latest-run div {
  display: grid;
  gap: 4px;
  min-width: 0;
}
.drawer-latest-run span,
.drawer-muted {
  color: var(--app-muted);
  font-size: 12px;
}
@media (max-width: 980px) {
  .readonly-flow-workbench { grid-template-columns: 1fr; }
}
</style>
