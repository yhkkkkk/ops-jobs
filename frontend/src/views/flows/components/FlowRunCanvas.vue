<template>
  <div class="flow-run-canvas">
    <VueFlow
      v-if="flowNodes.length > 0"
      :nodes="flowNodes"
      :edges="flowEdges"
      :nodes-draggable="false"
      :nodes-connectable="false"
      :edges-updatable="false"
      :elements-selectable="true"
      fit-view-on-init
      class="ops-flow ops-flow--run"
      @node-click="onNodeClick"
    >
      <Background :gap="24" :size="1" pattern-color="#d8dee9" />
      <Controls position="bottom-left" />
      <MiniMap pannable zoomable node-color="#dbe7f6" mask-color="rgba(247, 248, 250, 0.76)" />

      <template #node-ops="{ data }">
        <div
          :class="[
            'ops-node-card',
            `ops-node-card--status-${data.status}`,
            { 'ops-node-card--selected': data.selected },
          ]"
        >
          <Handle type="target" :position="Position.Left" />
          <div class="ops-node-card__top">
            <span>{{ data.typeText }}</span>
            <em class="ops-node-card__status">{{ data.statusText }}</em>
          </div>
          <strong>{{ data.label }}</strong>
          <em>{{ data.summary }}</em>
          <div v-if="data.actions?.length" class="ops-node-card__actions" @click.stop @mousedown.stop>
            <button
              v-for="action in data.actions"
              :key="action.key"
              type="button"
              :class="['ops-node-card__action', `ops-node-card__action--${action.key}`]"
              :disabled="action.loading"
              @click.stop="emitAction(action.key, data.nodeRun)"
            >
              {{ action.label }}
            </button>
          </div>
          <Handle type="source" :position="Position.Right" />
        </div>
      </template>
    </VueFlow>
    <div v-else class="flow-run-canvas__empty">当前任务没有可展示的拓扑节点</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { MiniMap } from '@vue-flow/minimap'
import { Handle, MarkerType, Position, VueFlow } from '@vue-flow/core'
import type { Edge, Node } from '@vue-flow/core'
import type { FlowEdge, FlowNode, FlowNodeRun, FlowRun } from '@/types'
import {
  buildRunTopology,
  canConfirmManualNodeRun,
  canForceFailFlowNodeRun,
  canRejectManualNodeRun,
  canRetryFlowNodeRun,
  canSkipFlowNodeRun,
  flowNodeTypeText,
  flowRunStatusText,
  type RunTopologyNodeStatus,
} from '../flowUtils'

export type FlowRunCanvasAction = 'retry' | 'skip' | 'force_fail' | 'confirm' | 'reject'

type CanvasNodeAction = {
  key: FlowRunCanvasAction
  label: string
  loading?: boolean
}

const props = defineProps<{
  nodes: FlowNode[]
  edges: FlowEdge[]
  run: FlowRun | null
  selectedUuid?: string | null
  busyNodeId?: number | null
  busyAction?: FlowRunCanvasAction | null
}>()

const emit = defineEmits<{
  (e: 'select-node', payload: { uuid: string; nodeRun?: FlowNodeRun }): void
  (e: 'node-action', payload: { action: FlowRunCanvasAction; nodeRun: FlowNodeRun }): void
}>()

const topology = computed(() =>
  buildRunTopology({ nodes: props.nodes || [], edges: props.edges || [] }, props.run),
)

const nodeByUuid = computed(() => new Map((props.nodes || []).map((node) => [node.uuid, node])))

const statusSummary = (status: RunTopologyNodeStatus, nodeRun?: FlowNodeRun) => {
  if (status === 'not_run') return '未运行'
  if (nodeRun?.error_message) return nodeRun.error_message
  if (nodeRun?.execution_record_id) return '已关联执行记录'
  return flowRunStatusText(status)
}

const nodeActions = (nodeRun?: FlowNodeRun | null): CanvasNodeAction[] => {
  if (!nodeRun) return []
  const actions: CanvasNodeAction[] = []
  const loading = props.busyNodeId === nodeRun.id
  if (nodeRun.node_type !== 'manual' && canRetryFlowNodeRun(nodeRun)) {
    actions.push({ key: 'retry', label: '重试', loading: loading && props.busyAction === 'retry' })
  }
  if (nodeRun.node_type !== 'manual' && canSkipFlowNodeRun(nodeRun)) {
    actions.push({ key: 'skip', label: '跳过', loading: loading && props.busyAction === 'skip' })
  }
  if (canForceFailFlowNodeRun(nodeRun)) {
    actions.push({ key: 'force_fail', label: '强制失败', loading: loading && props.busyAction === 'force_fail' })
  }
  if (canConfirmManualNodeRun(nodeRun)) {
    actions.push({ key: 'confirm', label: '通过', loading: loading && props.busyAction === 'confirm' })
  }
  if (canRejectManualNodeRun(nodeRun)) {
    actions.push({ key: 'reject', label: '拒绝', loading: loading && props.busyAction === 'reject' })
  }
  return actions
}

const flowNodes = computed<Node[]>(() =>
  topology.value.nodes.map((node, index) => {
    const templateNode = nodeByUuid.value.get(node.uuid)
    const x = templateNode?.position?.x
    const y = templateNode?.position?.y
    return {
      id: node.uuid,
      type: 'ops',
      position: {
        x: typeof x === 'number' ? x : 80 + (index % 4) * 220,
        y: typeof y === 'number' ? y : 100 + Math.floor(index / 4) * 120,
      },
      data: {
        label: node.name,
        typeText: flowNodeTypeText(node.nodeType),
        status: node.status,
        statusText: node.status === 'not_run' ? '未运行' : flowRunStatusText(node.status),
        summary: statusSummary(node.status, node.run),
        selected: props.selectedUuid === node.uuid,
        nodeRun: node.run,
        actions: nodeActions(node.run),
      },
    }
  }),
)

const edgeStroke = (state: string) => {
  if (state === 'selected' || state === 'default') return '#18a058'
  if (state === 'unselected') return '#c0c4cc'
  return '#8292a6'
}

const flowEdges = computed<Edge[]>(() =>
  topology.value.edges
    .filter((edge) => edge.sourceUuid && edge.targetUuid)
    .map((edge) => ({
      id: edge.key,
      source: edge.sourceUuid,
      target: edge.targetUuid,
      type: 'smoothstep',
      markerEnd: MarkerType.ArrowClosed,
      label: edge.isConditionEdge
        ? (edge.state === 'default' ? '默认' : edge.state === 'selected' ? '命中' : edge.state === 'unselected' ? '未走' : '')
        : '',
      style: {
        stroke: edgeStroke(edge.state),
        strokeWidth: edge.state === 'selected' || edge.state === 'default' ? 2.5 : 1.5,
        opacity: edge.state === 'unselected' ? 0.45 : 1,
      },
      labelStyle: { fill: edgeStroke(edge.state), fontSize: 11, fontWeight: 600 },
    })),
)

const onNodeClick = ({ node }: { node: Node }) => {
  emit('select-node', {
    uuid: String(node.id),
    nodeRun: node.data?.nodeRun as FlowNodeRun | undefined,
  })
}

const emitAction = (action: FlowRunCanvasAction, nodeRun?: FlowNodeRun) => {
  if (!nodeRun) return
  emit('node-action', { action, nodeRun })
}
</script>

<style scoped>
.flow-run-canvas {
  position: relative;
  height: 420px;
  border: 1px solid var(--app-border, #e5e6eb);
  border-radius: 8px;
  overflow: hidden;
  background: #f7f8fa;
}

.ops-flow {
  width: 100%;
  height: 100%;
}

.flow-run-canvas__empty {
  display: grid;
  place-content: center;
  height: 100%;
  color: #86909c;
  font-size: 13px;
}

.ops-node-card {
  display: grid;
  gap: 2px;
  width: 176px;
  min-height: 58px;
  padding: 6px 8px;
  background: #fff;
  border: 1px solid #e5e6eb;
  border-left: 3px solid #8292a6;
  border-radius: 6px;
  box-shadow: 0 4px 10px rgba(15, 23, 42, 0.06);
}

.ops-node-card--selected {
  box-shadow: 0 0 0 2px rgba(32, 128, 240, 0.25), 0 8px 18px rgba(15, 23, 42, 0.08);
}

.ops-node-card--status-success { border-left-color: #18a058; }
.ops-node-card--status-failed { border-left-color: #d03050; }
.ops-node-card--status-running { border-left-color: #2080f0; }
.ops-node-card--status-paused { border-left-color: #f0a020; }
.ops-node-card--status-cancelled { border-left-color: #c0c4cc; }
.ops-node-card--status-cancelled .ops-node-card__status { color: #86909c; }
.ops-node-card--status-not_run { border-left-color: #c0c4cc; opacity: 0.78; }

.ops-node-card__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  min-width: 0;
}

.ops-node-card__top span {
  overflow: hidden;
  color: #4e5969;
  font-size: 10px;
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ops-node-card__status {
  flex-shrink: 0;
  font-size: 10px;
  font-style: normal;
  color: #86909c;
}

.ops-node-card--status-success .ops-node-card__status { color: #18a058; }
.ops-node-card--status-failed .ops-node-card__status { color: #d03050; }
.ops-node-card--status-running .ops-node-card__status { color: #2080f0; }
.ops-node-card--status-paused .ops-node-card__status { color: #f0a020; }

.ops-node-card strong,
.ops-node-card em {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ops-node-card strong {
  color: #1d2129;
  font-size: 12px;
  line-height: 1.25;
}

.ops-node-card > em {
  color: #86909c;
  font-size: 10px;
  font-style: normal;
}

.ops-node-card__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 4px;
}

.ops-node-card__action {
  padding: 1px 6px;
  border: 1px solid #e5e6eb;
  border-radius: 4px;
  background: #fff;
  color: #4e5969;
  font-size: 10px;
  line-height: 1.4;
  cursor: pointer;
}

.ops-node-card__action:disabled {
  opacity: 0.55;
  cursor: wait;
}

.ops-node-card__action--confirm {
  border-color: color-mix(in srgb, #18a058 35%, #e5e6eb);
  color: #18a058;
}

.ops-node-card__action--reject,
.ops-node-card__action--skip,
.ops-node-card__action--force_fail {
  border-color: color-mix(in srgb, #d03050 28%, #e5e6eb);
  color: #d03050;
}

.ops-node-card__action--retry {
  border-color: color-mix(in srgb, #2080f0 30%, #e5e6eb);
  color: #2080f0;
}
</style>
