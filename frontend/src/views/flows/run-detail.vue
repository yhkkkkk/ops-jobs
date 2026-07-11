<template>
  <div class="app-page pipeline-run-page standard-run-detail">
    <header class="run-head app-card">
      <div>
        <p>流水线执行</p>
        <h1>{{ run ? run.template_name : '执行详情' }}</h1>
        <span>{{ run ? `执行 #${run.id} / ${triggerText(run.trigger_type)} / ${run.started_by_name || '-'}` : '查看节点状态、输出和关联执行记录。' }}</span>
      </div>
      <a-space>
        <a-button @click="router.push('/flows')">返回流水线</a-button>
        <a-button
          v-if="canCancelCurrentRun"
          status="danger"
          :loading="cancelingRun"
          @click="handleCancelRun"
        >
          <template #icon><icon-close /></template>
          取消流程
        </a-button>
        <a-button @click="loadRun">
          <template #icon><icon-refresh /></template>
          刷新
        </a-button>
      </a-space>
    </header>

    <a-spin :loading="loading" class="run-spin">
      <template v-if="run">
        <section class="run-status app-card">
          <StatusBadge :status="run.status" :text="statusText(run.status)" />
          <div>
            <span>总节点</span>
            <strong>{{ run.node_runs.length }}</strong>
          </div>
          <div>
            <span>成功</span>
            <strong>{{ countByStatus('success') }}</strong>
          </div>
          <div>
            <span>失败</span>
            <strong>{{ countByStatus('failed') }}</strong>
          </div>
          <div>
            <span>暂停</span>
            <strong>{{ countByStatus('paused') }}</strong>
          </div>
          <div>
            <span>耗时</span>
            <strong>{{ durationText(run.started_at, run.finished_at) }}</strong>
          </div>
        </section>

        <a-alert
          v-if="blockingNode"
          class="run-focus-alert"
          :type="blockingNode.status === 'failed' ? 'error' : 'warning'"
          show-icon
        >
          <template #title>
            当前定位：{{ blockingNode.node_name }}（{{ statusText(blockingNode.status) }}）
          </template>
          <span>
            {{ blockingNode.error_message || (blockingNode.execution_record_id ? `关联执行记录 #${blockingNode.execution_record_id}，等待结果回写后推进。` : '请关注节点输出和调度状态。') }}
          </span>
        </a-alert>

        <div class="run-layout">
          <DetailPanel title="执行上下文" dense>
            <a-descriptions :column="2" bordered size="medium">
              <a-descriptions-item label="执行 ID">#{{ run.id }}</a-descriptions-item>
              <a-descriptions-item label="触发方式">{{ triggerText(run.trigger_type) }}</a-descriptions-item>
              <a-descriptions-item label="开始时间">{{ formatTime(run.started_at || run.created_at) }}</a-descriptions-item>
              <a-descriptions-item label="结束时间">{{ formatTime(run.finished_at) }}</a-descriptions-item>
              <a-descriptions-item label="发起人">{{ run.started_by_name || '-' }}</a-descriptions-item>
              <a-descriptions-item label="错误信息">{{ run.error_message || '-' }}</a-descriptions-item>
            </a-descriptions>
          </DetailPanel>

          <DetailPanel title="运行输入 / 汇总输出" dense>
            <a-tabs size="small">
              <a-tab-pane key="inputs" title="输入变量">
                <FlowVariableReadOnlyPanel mode="value" :values="run.inputs || {}" empty-text="本次执行没有输入变量" />
              </a-tab-pane>
              <a-tab-pane key="outputs" title="输出结果">
                <FlowRunDataView :value="run.outputs || {}" empty-text="本次执行暂无汇总输出" />
              </a-tab-pane>
            </a-tabs>
          </DetailPanel>
        </div>

        <DetailPanel title="执行拓扑" description="基于模板拓扑展示本次执行实际覆盖的节点和条件分支。" dense>
          <div class="readonly-run-topology">
            <a-alert v-if="templateLoadError" class="topology-alert" type="warning" show-icon>
              {{ templateLoadError }}
            </a-alert>
            <template v-else>
            <div class="topology-summary">
              <div>
                <span>模板节点</span>
                <strong>{{ runTopology.nodes.length }}</strong>
              </div>
              <div>
                <span>已生成运行</span>
                <strong>{{ runTopology.executedCount }}</strong>
              </div>
              <div>
                <span>未运行</span>
                <strong>{{ runTopology.notRunCount }}</strong>
              </div>
              <div>
                <span>命中分支</span>
                <strong>{{ runTopology.selectedConditionEdgeCount }}</strong>
              </div>
            </div>

            <div class="topology-grid">
              <div class="topology-nodes">
                <article
                  v-for="node in runTopology.nodes"
                  :key="node.uuid"
                  :class="['topology-node', `topology-node--${node.status}`]"
                >
                  <div class="topology-node__main">
                    <span>{{ nodeTypeText(node.nodeType) }}</span>
                    <strong>{{ node.name }}</strong>
                    <em>{{ topologyNodeMeta(node) }}</em>
                    <a-link v-if="childFlowRunId(node.run)" class="sub-run-link" @click="openChildFlowRun(node.run!)">子流程 #{{ childFlowRunId(node.run) }}</a-link>
                  </div>
                  <StatusBadge
                    v-if="node.status !== 'not_run'"
                    :status="node.status"
                    :text="topologyStatusText(node.status)"
                  />
                  <span v-else class="topology-status topology-status--not-run">未运行</span>
                </article>
              </div>

              <div class="topology-edges">
                <div v-if="runTopology.edges.length === 0" class="topology-empty">
                  当前模板没有连线
                </div>
                <article
                  v-for="edge in runTopology.edges"
                  :key="edge.key"
                  :class="['topology-edge', `topology-edge--${edge.state}`]"
                >
                  <span class="topology-edge__state">{{ edgeStateText(edge.state) }}</span>
                  <div>
                    <strong>{{ edge.sourceName }} -> {{ edge.targetName }}</strong>
                    <em>{{ edge.conditionText }}</em>
                  </div>
                </article>
              </div>
            </div>
            </template>
          </div>
        </DetailPanel>

        <DetailPanel title="节点运行路径" description="按节点运行顺序展示状态、耗时、输出和关联执行记录。" dense>
          <div class="run-path run-path-table">
            <article v-for="(nodeRun, index) in run.node_runs" :key="nodeRun.id" :class="['run-node', `run-node--${nodeRun.status}`]">
              <div class="run-node__index">{{ index + 1 }}</div>
              <div class="run-node__main">
                <div class="run-node__head">
                  <div>
                    <span>{{ nodeTypeText(nodeRun.node_type) }}</span>
                    <h3>{{ nodeRun.node_name }}</h3>
                  </div>
                  <div class="run-node__actions">
                    <StatusBadge :status="nodeRun.status" :text="statusText(nodeRun.status)" />
                    <a-button
                      v-if="canRetryNodeRun(nodeRun)"
                      size="mini"
                      :loading="retryingNodeId === nodeRun.id"
                      @click="handleRetryNode(nodeRun)"
                    >
                      <template #icon><icon-refresh /></template>
                      重试
                    </a-button>
                    <a-button
                      v-if="canSkipNodeRun(nodeRun)"
                      size="mini"
                      status="warning"
                      :loading="skippingNodeId === nodeRun.id"
                      @click="handleSkipNode(nodeRun)"
                    >
                      跳过继续
                    </a-button>
                    <a-button
                      v-if="canConfirmNodeRun(nodeRun)"
                      size="mini"
                      type="primary"
                      :loading="confirmingNodeId === nodeRun.id"
                      @click="handleConfirmManualNode(nodeRun)"
                    >
                      确认继续
                    </a-button>
                  </div>
                </div>
                <dl>
                  <div>
                    <dt>开始</dt>
                    <dd>{{ formatTime(nodeRun.started_at || nodeRun.created_at) }}</dd>
                  </div>
                  <div>
                    <dt>结束</dt>
                    <dd>{{ formatTime(nodeRun.finished_at) }}</dd>
                  </div>
                  <div>
                    <dt>关联执行记录</dt>
                    <dd>
                      <a-link v-if="nodeRun.execution_record_id" @click="router.push(`/execution-records/${nodeRun.execution_record_id}`)">#{{ nodeRun.execution_record_id }}</a-link>
                      <span v-else>-</span>
                    </dd>
                  </div>
                  <div>
                    <dt>子流程实例</dt>
                    <dd>
                      <a-link v-if="childFlowRunId(nodeRun)" @click="openChildFlowRun(nodeRun)">#{{ childFlowRunId(nodeRun) }}</a-link>
                      <span v-else>-</span>
                    </dd>
                  </div>
                </dl>
                <a-alert v-if="nodeRun.error_message" type="error" show-icon>{{ nodeRun.error_message }}</a-alert>
                <a-alert v-else-if="nodeRun.node_type === 'sub_process' && childFlowRunId(nodeRun)" type="info" show-icon>
                  子流程实例 #{{ childFlowRunId(nodeRun) }} / {{ statusText(childFlowStatus(nodeRun) || nodeRun.status) }}
                </a-alert>
                <a-alert v-else-if="nodeRun.status === 'paused' && nodeRun.node_type === 'manual'" type="warning" show-icon>
                  {{ nodeRun.inputs.instructions || '人工确认节点等待确认。确认后流水线会继续执行后续节点。' }}
                </a-alert>
                <a-alert v-else-if="nodeRun.status === 'paused' && nodeRun.execution_record_id" type="warning" show-icon>
                  作业执行方案已提交，等待执行记录 #{{ nodeRun.execution_record_id }} 完成后继续推进流水线。
                </a-alert>
                <div v-if="nodeRun.node_type === 'condition'" class="condition-branch-summary">
                  <div class="condition-branch-summary__head">
                    <span>分支结果</span>
                    <strong v-if="conditionSummary(nodeRun).hasDecision">
                      {{ conditionSummary(nodeRun).defaultUsed ? '使用默认分支' : `命中 ${conditionSummary(nodeRun).matchedCount || conditionSummary(nodeRun).rows.length} 条分支` }}
                    </strong>
                    <strong v-else>未选择下游分支</strong>
                  </div>
                  <div v-if="conditionSummary(nodeRun).hasDecision" class="condition-branch-list">
                    <div v-for="row in conditionSummary(nodeRun).rows" :key="`${nodeRun.id}-${row.targetUuid}`" class="condition-branch-row">
                      <span>{{ row.isDefault ? '默认' : '命中' }}</span>
                      <strong>{{ nodeNameByUuid(row.targetUuid) }}</strong>
                      <em>{{ row.conditionText }}</em>
                    </div>
                  </div>
                  <a-empty v-else description="没有命中的条件，也没有默认分支" />
                </div>
                <div class="node-host-summary">
                  <span>目标主机</span>
                  <strong>{{ formatHostDisplay(nodeRun.inputs?.target_hosts || nodeRun.inputs?.hosts || nodeRun.outputs?.target_hosts || nodeRun.outputs?.hosts) }}</strong>
                </div>
                <div class="node-data-grid">
                  <div>
                    <span>输入</span>
                    <FlowRunDataView :value="nodeRun.inputs || {}" empty-text="该节点暂无输入" />
                  </div>
                  <div>
                    <span>输出</span>
                    <FlowRunDataView :value="nodeRun.outputs || {}" empty-text="该节点暂无输出" />
                  </div>
                </div>
              </div>
            </article>
          </div>
        </DetailPanel>

        <DetailPanel title="操作时间线" description="按时间展示流程实例、节点状态、人工确认、跳过和分支决策。" dense>
          <a-alert v-if="operationLogLoadError" class="timeline-alert" type="warning" show-icon>
            {{ operationLogLoadError }}
          </a-alert>
          <div class="run-timeline">
            <article
              v-for="event in runTimeline"
              :key="event.key"
              :class="['timeline-event', `timeline-event--${event.status}`]"
            >
              <div class="timeline-event__marker" />
              <div class="timeline-event__main">
                <div class="timeline-event__head">
                  <strong>{{ event.title }}</strong>
                  <span>{{ formatTime(event.timestamp) }}</span>
                </div>
                <p>{{ event.description }}</p>
                <div class="timeline-event__meta">
                  <span>{{ eventKindText(event.kind) }}</span>
                  <span v-if="event.nodeType">{{ nodeTypeText(event.nodeType) }}</span>
                  <span v-if="event.nodeName">{{ event.nodeName }}</span>
                </div>
              </div>
            </article>
          </div>
        </DetailPanel>

        <DetailPanel title="节点运行表" dense>
          <a-table row-key="id" :data="run.node_runs" :pagination="false">
            <template #columns>
              <a-table-column title="节点" data-index="node_name" />
              <a-table-column title="类型" :width="132">
                <template #cell="{ record }">{{ nodeTypeText(record.node_type) }}</template>
              </a-table-column>
              <a-table-column title="状态" :width="116">
                <template #cell="{ record }"><StatusBadge :status="record.status" :text="statusText(record.status)" /></template>
              </a-table-column>
              <a-table-column title="关联执行记录" :width="130">
                <template #cell="{ record }">
                  <a-link v-if="record.execution_record_id" @click="router.push(`/execution-records/${record.execution_record_id}`)">#{{ record.execution_record_id }}</a-link>
                  <span v-else>-</span>
                </template>
              </a-table-column>
              <a-table-column title="子流程实例" :width="130">
                <template #cell="{ record }">
                  <a-link v-if="childFlowRunId(record)" @click="openChildFlowRun(record)">#{{ childFlowRunId(record) }}</a-link>
                  <span v-else>-</span>
                </template>
              </a-table-column>
              <a-table-column title="错误信息">
                <template #cell="{ record }">{{ record.error_message || '-' }}</template>
              </a-table-column>
            </template>
          </a-table>
        </DetailPanel>
      </template>
      <template v-else>
        <DetailPanel title="执行拓扑" description="基于模板拓扑展示本次执行实际覆盖的节点和条件分支。" dense>
          <div class="readonly-run-topology">
            <a-empty description="未找到流水线执行实例或暂无访问权限" />
          </div>
        </DetailPanel>
        <DetailPanel title="节点运行路径" description="按节点运行顺序展示状态、耗时、输出和关联执行记录。" dense>
          <div class="run-path-table">
            <a-empty description="暂无节点运行路径" />
          </div>
        </DetailPanel>
      </template>
    </a-spin>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Message, Modal } from '@arco-design/web-vue'
import { flowApi } from '@/api/ops'
import type { FlowAuditLog, FlowNodeRun, FlowNodeType, FlowRun, FlowRunStatus, FlowTemplate } from '@/types'
import { DetailPanel, StatusBadge } from '@/components/app'
import FlowRunDataView from './components/FlowRunDataView.vue'
import FlowVariableReadOnlyPanel from './components/FlowVariableReadOnlyPanel.vue'
import {
  buildFlowRunTimeline,
  buildRunTopology,
  canCancelFlowRun,
  canConfirmManualNodeRun,
  canRetryFlowNodeRun,
  canSkipFlowNodeRun,
  flowNodeTypeText,
  flowRunStatusText,
  type FlowRunTimelineEventKind,
  type RunTopologyEdgeState,
  type RunTopologyNode,
  type RunTopologyNodeStatus,
  summarizeConditionNodeRun,
} from './flowUtils'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const cancelingRun = ref(false)
const retryingNodeId = ref<number | null>(null)
const skippingNodeId = ref<number | null>(null)
const confirmingNodeId = ref<number | null>(null)
const run = ref<FlowRun | null>(null)
const template = ref<FlowTemplate | null>(null)
const operationLogs = ref<FlowAuditLog[]>([])
const templateLoadError = ref('')
const operationLogLoadError = ref('')
const blockingNode = computed(() =>
  run.value?.node_runs.find(item => ['failed', 'paused', 'running'].includes(item.status)) || null
)
const canCancelCurrentRun = computed(() => canCancelFlowRun(run.value))
const runTopology = computed(() => buildRunTopology(template.value, run.value))
const runTimeline = computed(() => buildFlowRunTimeline(run.value, operationLogs.value))

const countByStatus = (status: FlowRunStatus) => run.value?.node_runs.filter(item => item.status === status).length || 0
const statusText = (status: FlowRunStatus) => ({ pending: '等待中', running: '执行中', success: '成功', failed: '失败', paused: '已暂停', cancelled: '已取消' }[status] || status)
const topologyStatusText = (status: RunTopologyNodeStatus) => flowRunStatusText(status)
const nodeTypeText = (type: FlowNodeType) => flowNodeTypeText(type)
const edgeStateText = (state: RunTopologyEdgeState) => {
  if (state === 'selected') return '命中'
  if (state === 'default') return '默认'
  if (state === 'unselected') return '未走'
  return '连线'
}
const eventKindText = (kind: FlowRunTimelineEventKind) => {
  const map: Record<FlowRunTimelineEventKind, string> = {
    flow: '流程',
    node_start: '节点开始',
    node_status: '节点状态',
    manual_confirm: '人工确认',
    skip: '跳过',
    condition: '分支',
    gateway: '网关',
    audit: '审计',
  }
  return map[kind]
}
const canSkipNodeRun = (nodeRun: FlowNodeRun) => nodeRun.node_type !== 'manual' && canSkipFlowNodeRun(nodeRun)
const canRetryNodeRun = (nodeRun: FlowNodeRun) => nodeRun.node_type !== 'manual' && canRetryFlowNodeRun(nodeRun)
const canConfirmNodeRun = (nodeRun: FlowNodeRun) => canConfirmManualNodeRun(nodeRun)
const conditionSummary = (nodeRun: FlowNodeRun) => summarizeConditionNodeRun(nodeRun)
const childFlowRunId = (nodeRun?: Pick<FlowNodeRun, 'outputs'> | null) =>
  nodeRun?.outputs?.child_flow_run_id || nodeRun?.outputs?.child_run_id
const childFlowStatus = (nodeRun?: Pick<FlowNodeRun, 'outputs'> | null) =>
  nodeRun?.outputs?.child_flow_status || nodeRun?.outputs?.child_status
const openChildFlowRun = (nodeRun: Pick<FlowNodeRun, 'outputs'>) => {
  const id = childFlowRunId(nodeRun)
  if (id) router.push(`/flows/runs/${id}`)
}
const nodeNameByUuid = (uuid: string) => {
  const nodeRun = run.value?.node_runs.find(item => item.node_uuid === uuid)
  const topologyNode = runTopology.value.nodes.find(item => item.uuid === uuid)
  return nodeRun?.node_name || topologyNode?.name || '未知节点'
}
const topologyNodeMeta = (node: RunTopologyNode) => {
  const pieces = [topologyStatusText(node.status)]
  const recordId = node.run?.execution_record_id
  if (recordId) pieces.push(`执行记录 #${recordId}`)
  const childId = childFlowRunId(node.run)
  if (childId) pieces.push(`子流程 #${childId}`)
  return pieces.join(' / ')
}
const triggerText = (trigger: string) => {
  if (trigger === 'manual') return '手动触发'
  if (trigger === 'scheduled') return '定时触发'
  if (trigger === 'api') return 'API 触发'
  return trigger || '-'
}
const formatHostDisplay = (value: any) => {
  if (!value || (Array.isArray(value) && value.length === 0)) return '未绑定主机变量'
  if (typeof value === 'string') {
    const trimmed = value.trim()
    if (!trimmed) return '未绑定主机变量'
    if (/^\$\{[^}]+\}$/.test(trimmed)) return `主机变量 ${trimmed}`
    return trimmed
  }
  if (Array.isArray(value)) {
    const objectHosts = value.filter(item => item && typeof item === 'object')
    if (objectHosts.length) {
      return objectHosts
        .map(item => [item.name || item.hostname, item.internal_ip || item.public_ip || item.ip_address, item.status_display || item.status].filter(Boolean).join(' / '))
        .join('；')
    }
    return `已选择 ${value.length} 台主机`
  }
  if (typeof value === 'object') {
    return [value.name || value.hostname, value.internal_ip || value.public_ip || value.ip_address, value.status_display || value.status]
      .filter(Boolean)
      .join(' / ') || '动态主机配置'
  }
  return String(value)
}

const formatTime = (value?: string | null) => value ? new Date(value).toLocaleString('zh-CN') : '-'
const durationText = (start?: string | null, end?: string | null) => {
  if (!start) return '-'
  const startTime = new Date(start).getTime()
  const endTime = end ? new Date(end).getTime() : Date.now()
  const seconds = Math.max(0, Math.round((endTime - startTime) / 1000))
  if (seconds < 60) return `${seconds}s`
  return `${Math.floor(seconds / 60)}m ${seconds % 60}s`
}

const loadRun = async () => {
  loading.value = true
  try {
    templateLoadError.value = ''
    operationLogLoadError.value = ''
    const currentRun = await flowApi.getRun(Number(route.params.id))
    run.value = currentRun
    try {
      operationLogs.value = await flowApi.getRunOperationLogs(currentRun.id)
    } catch (error) {
      console.error('加载流水线操作审计失败:', error)
      operationLogs.value = []
      operationLogLoadError.value = '操作审计加载失败，当前展示由运行数据推导的时间线。'
    }
    try {
      template.value = await flowApi.getTemplate(currentRun.template)
    } catch (error) {
      console.error('加载流水线模板拓扑失败:', error)
      template.value = null
      templateLoadError.value = '模板拓扑加载失败，已保留节点运行路径和原始输出用于排查。'
    }
  } catch (error) {
    console.error('加载流水线执行详情失败:', error)
    Message.error('加载流水线执行详情失败')
  } finally {
    loading.value = false
  }
}

const handleSkipNode = (nodeRun: FlowNodeRun) => {
  if (!run.value || !canSkipNodeRun(nodeRun)) return
  Modal.confirm({
    title: '确认跳过节点',
    content: `确定要跳过节点"${nodeRun.node_name}"并继续执行后续节点吗？`,
    okText: '跳过继续',
    onOk: async () => {
      skippingNodeId.value = nodeRun.id
      try {
        run.value = await flowApi.skipRunNode(run.value!.id, {
          node_run_id: nodeRun.id,
          reason: 'manual skip',
        })
        Message.success('已跳过节点，流水线继续执行')
      } catch (error) {
        console.error('跳过流水线节点失败:', error)
        Message.error('跳过流水线节点失败')
      } finally {
        skippingNodeId.value = null
      }
    },
  })
}

const handleRetryNode = (nodeRun: FlowNodeRun) => {
  if (!run.value || !canRetryNodeRun(nodeRun)) return
  Modal.confirm({
    title: '确认重试节点',
    content: `确定要重试节点"${nodeRun.node_name}"吗？成功后流水线会继续执行后续节点。`,
    okText: '重试节点',
    onOk: async () => {
      retryingNodeId.value = nodeRun.id
      try {
        run.value = await flowApi.retryRunNode(run.value!.id, {
          node_run_id: nodeRun.id,
        })
        Message.success('节点已重试')
      } catch (error) {
        console.error('重试流水线节点失败:', error)
        Message.error('重试流水线节点失败')
      } finally {
        retryingNodeId.value = null
      }
    },
  })
}

const handleConfirmManualNode = (nodeRun: FlowNodeRun) => {
  if (!run.value || !canConfirmNodeRun(nodeRun)) return
  Modal.confirm({
    title: '确认继续执行',
    content: `确认节点"${nodeRun.node_name}"已完成人工检查，并继续执行后续节点吗？`,
    okText: '确认继续',
    onOk: async () => {
      confirmingNodeId.value = nodeRun.id
      try {
        run.value = await flowApi.confirmManualNode(run.value!.id, {
          node_run_id: nodeRun.id,
          remark: 'manual confirm',
        })
        Message.success('人工确认完成，流水线继续执行')
      } catch (error) {
        console.error('确认人工节点失败:', error)
        Message.error('确认人工节点失败')
      } finally {
        confirmingNodeId.value = null
      }
    },
  })
}

const handleCancelRun = () => {
  if (!run.value || !canCancelCurrentRun.value) return
  Modal.confirm({
    title: '确认取消流程',
    content: `确定要取消流水线执行 #${run.value.id} 吗？正在运行或暂停的节点会被标记为已取消。`,
    okText: '取消流程',
    okButtonProps: { status: 'danger' },
    onOk: async () => {
      cancelingRun.value = true
      try {
        run.value = await flowApi.cancelRun(run.value!.id)
        Message.success('流程已取消')
      } catch (error) {
        console.error('取消流水线失败:', error)
        Message.error('取消流水线失败')
      } finally {
        cancelingRun.value = false
      }
    },
  })
}

onMounted(loadRun)
</script>

<style scoped>
.pipeline-run-page { display: grid; gap: 10px; padding: 0; }
.run-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 16px 18px;
}
.run-head p { margin: 0 0 5px; color: var(--app-accent); font-size: 12px; font-weight: 700; }
.run-head h1 { margin: 0; color: var(--app-fg); font-size: 22px; line-height: 1.25; }
.run-head span { display: block; margin-top: 5px; color: var(--app-muted); font-size: 13px; line-height: 1.45; }
.run-spin { display: block; }
.run-focus-alert { margin-top: 8px; }
.timeline-alert { margin-bottom: 10px; }
.run-status {
  display: grid;
  grid-template-columns: auto repeat(5, minmax(0, 1fr));
  gap: 10px;
  align-items: center;
  padding: 14px 16px;
}
.run-status div {
  min-width: 0;
  padding-left: 12px;
  border-left: 1px solid var(--app-border);
}
.run-status span { display: block; color: var(--app-muted); font-size: 12px; }
.run-status strong { display: block; margin-top: 4px; overflow: hidden; color: var(--app-fg); font-family: var(--app-mono); font-size: 18px; line-height: 1.1; text-overflow: ellipsis; white-space: nowrap; }
.run-layout { display: grid; grid-template-columns: minmax(0, 1.1fr) minmax(340px, .9fr); gap: 10px; margin: 8px 0; }
.run-timeline {
  display: grid;
  gap: 8px;
  max-height: 420px;
  overflow: auto;
  padding-right: 4px;
}
.timeline-event {
  display: grid;
  grid-template-columns: 14px minmax(0, 1fr);
  gap: 10px;
  align-items: start;
  min-width: 0;
}
.timeline-event__marker {
  width: 10px;
  height: 10px;
  margin-top: 13px;
  background: var(--app-muted);
  border: 2px solid #fff;
  border-radius: var(--app-radius-pill);
  box-shadow: 0 0 0 1px var(--app-border);
}
.timeline-event--success .timeline-event__marker { background: var(--app-success); box-shadow: 0 0 0 1px color-mix(in srgb, var(--app-success) 30%, var(--app-border)); }
.timeline-event--failed .timeline-event__marker { background: var(--app-danger); box-shadow: 0 0 0 1px color-mix(in srgb, var(--app-danger) 30%, var(--app-border)); }
.timeline-event--running .timeline-event__marker,
.timeline-event--paused .timeline-event__marker { background: var(--app-warn); box-shadow: 0 0 0 1px color-mix(in srgb, var(--app-warn) 30%, var(--app-border)); }
.timeline-event--cancelled .timeline-event__marker { background: var(--app-muted); }
.timeline-event__main {
  display: grid;
  gap: 6px;
  min-width: 0;
  padding: 10px 12px;
  background: #fff;
  border: 1px solid var(--app-border);
  border-left: 3px solid var(--app-border);
  border-radius: var(--app-radius-sm);
}
.timeline-event--success .timeline-event__main { border-left-color: var(--app-success); }
.timeline-event--failed .timeline-event__main { border-left-color: var(--app-danger); }
.timeline-event--running .timeline-event__main,
.timeline-event--paused .timeline-event__main { border-left-color: var(--app-warn); }
.timeline-event__head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  min-width: 0;
}
.timeline-event__head strong,
.timeline-event__head span,
.timeline-event p {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.timeline-event__head strong { color: var(--app-fg); font-size: 14px; line-height: 1.35; }
.timeline-event__head span { flex-shrink: 0; color: var(--app-muted); font-family: var(--app-mono); font-size: 12px; }
.timeline-event p { margin: 0; color: var(--app-muted); font-size: 12px; line-height: 1.45; }
.timeline-event__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  min-width: 0;
}
.timeline-event__meta span {
  display: inline-flex;
  align-items: center;
  max-width: 100%;
  height: 22px;
  padding: 0 7px;
  overflow: hidden;
  color: var(--app-muted);
  background: var(--app-surface-soft);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-pill);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.topology-alert { margin-bottom: 10px; }
.topology-summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
  margin-bottom: 8px;
}
.topology-summary div {
  min-width: 0;
  padding: 8px 10px;
  background: var(--app-surface-soft);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
}
.topology-summary span {
  display: block;
  color: var(--app-muted);
  font-size: 12px;
}
.topology-summary strong {
  display: block;
  margin-top: 4px;
  color: var(--app-fg);
  font-family: var(--app-mono);
  font-size: 18px;
  line-height: 1.1;
}
.topology-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(320px, .95fr);
  align-items: start;
  gap: 10px;
}
.topology-nodes,
.topology-edges {
  display: grid;
  align-content: start;
  gap: 8px;
  min-width: 0;
}
.topology-node {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 10px;
  align-items: center;
  min-height: 58px;
  padding: 8px 10px;
  background: #fff;
  border: 1px solid var(--app-border);
  border-left: 3px solid var(--app-border);
  border-radius: var(--app-radius-sm);
}
.topology-node--success { border-left-color: var(--app-success); }
.topology-node--failed { border-left-color: var(--app-danger); }
.topology-node--running,
.topology-node--paused { border-left-color: var(--app-warn); }
.topology-node--cancelled,
.topology-node--not_run { border-left-color: var(--app-muted); opacity: .78; }
.topology-node__main { display: grid; min-width: 0; gap: 3px; }
.topology-node__main span {
  color: var(--app-accent);
  font-size: 12px;
  font-weight: 700;
}
.topology-node__main strong,
.topology-node__main em {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.topology-node__main strong { color: var(--app-fg); font-size: 14px; line-height: 1.3; }
.topology-node__main em { color: var(--app-muted); font-family: var(--app-mono); font-size: 11px; font-style: normal; }
.sub-run-link {
  width: fit-content;
  font-size: 12px;
  line-height: 1.35;
}
.topology-status {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 58px;
  height: 24px;
  padding: 0 8px;
  border-radius: var(--app-radius-pill);
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
}
.topology-status--not-run {
  color: var(--app-muted);
  background: var(--app-surface-soft);
  border: 1px solid var(--app-border);
}
.topology-empty {
  padding: 14px;
  color: var(--app-muted);
  background: var(--app-surface-soft);
  border: 1px dashed var(--app-border);
  border-radius: var(--app-radius-sm);
  font-size: 13px;
}
.topology-edge {
  display: grid;
  grid-template-columns: 52px minmax(0, 1fr);
  gap: 10px;
  align-items: center;
  min-height: 50px;
  padding: 8px 10px;
  background: #fff;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
}
.topology-edge--selected { border-color: color-mix(in srgb, var(--app-success) 30%, var(--app-border)); background: var(--app-success-soft); }
.topology-edge--default { border-color: color-mix(in srgb, var(--app-accent) 30%, var(--app-border)); background: color-mix(in srgb, var(--app-accent) 8%, #fff); }
.topology-edge--unselected { opacity: .66; }
.topology-edge__state {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 42px;
  height: 24px;
  color: var(--app-muted);
  background: var(--app-surface-soft);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-pill);
  font-size: 12px;
  font-weight: 700;
}
.topology-edge--selected .topology-edge__state { color: var(--app-success); background: #fff; border-color: color-mix(in srgb, var(--app-success) 28%, var(--app-border)); }
.topology-edge--default .topology-edge__state { color: var(--app-accent); background: #fff; border-color: color-mix(in srgb, var(--app-accent) 28%, var(--app-border)); }
.topology-edge div { display: grid; min-width: 0; gap: 4px; }
.topology-edge strong,
.topology-edge em {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.topology-edge strong { color: var(--app-fg); font-size: 13px; line-height: 1.35; }
.topology-edge em { color: var(--app-muted); font-size: 12px; font-style: normal; }
.run-path { display: grid; gap: 8px; }
.run-path-table { min-width: 0; }
.run-node { display: grid; grid-template-columns: 34px minmax(0, 1fr); gap: 10px; }
.run-node__index {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  margin-top: 10px;
  color: var(--app-muted);
  background: var(--app-surface-soft);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-pill);
  font-family: var(--app-mono);
  font-size: 12px;
  font-weight: 700;
}
.run-node--success .run-node__index { color: var(--app-success); background: var(--app-success-soft); border-color: color-mix(in srgb, var(--app-success) 24%, transparent); }
.run-node--failed .run-node__index { color: var(--app-danger); background: var(--app-danger-soft); border-color: color-mix(in srgb, var(--app-danger) 24%, transparent); }
.run-node--running .run-node__index, .run-node--paused .run-node__index { color: var(--app-warn); background: var(--app-warn-soft); border-color: color-mix(in srgb, var(--app-warn) 24%, transparent); }
.run-node__main { display: grid; gap: 8px; padding: 10px; background: #fff; border: 1px solid var(--app-border); border-radius: var(--app-radius-sm); }
.run-node__head { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
.run-node__head span { color: var(--app-accent); font-size: 12px; font-weight: 700; }
.run-node__head h3 { margin: 4px 0 0; color: var(--app-fg); font-size: 15px; line-height: 1.3; }
.run-node__actions { display: inline-flex; align-items: center; gap: 8px; flex-shrink: 0; }
.run-node dl {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
  margin: 0;
}
.run-node dl div { min-width: 0; padding: 8px; background: var(--app-surface-soft); border-radius: var(--app-radius-sm); }
.run-node dt, .run-node dd { margin: 0; font-size: 12px; line-height: 1.45; }
.run-node dt { color: var(--app-muted); }
.run-node dd { overflow: hidden; color: var(--app-fg); text-overflow: ellipsis; white-space: nowrap; }
.condition-branch-summary {
  display: grid;
  gap: 8px;
  padding: 10px;
  background: var(--app-surface-soft);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
}
.condition-branch-summary__head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}
.condition-branch-summary__head span {
  color: var(--app-muted);
  font-size: 12px;
}
.condition-branch-summary__head strong {
  overflow: hidden;
  color: var(--app-fg);
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.condition-branch-list { display: grid; gap: 6px; }
.condition-branch-row {
  display: grid;
  grid-template-columns: 46px minmax(0, 1fr) minmax(0, 1.2fr);
  gap: 8px;
  align-items: center;
  padding: 8px;
  background: #fff;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
}
.condition-branch-row span {
  color: var(--app-accent);
  font-size: 12px;
  font-weight: 700;
}
.condition-branch-row strong,
.condition-branch-row em {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.condition-branch-row strong { color: var(--app-fg); font-size: 12px; }
.condition-branch-row em { color: var(--app-muted); font-size: 12px; font-style: normal; }
.node-host-summary {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr);
  gap: 8px;
  align-items: center;
  padding: 8px 10px;
  background: var(--app-surface-soft);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
}
.node-host-summary span {
  color: var(--app-muted);
  font-size: 12px;
}
.node-host-summary strong {
  overflow: hidden;
  color: var(--app-fg);
  font-size: 12px;
  font-weight: 500;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.node-data-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.node-data-grid > div { min-width: 0; }
.node-data-grid > div > span { display: block; margin-bottom: 5px; color: var(--app-muted); font-size: 12px; }
:deep(.arco-table-th) { background: #fff; }
@media (max-width: 1080px) {
  .run-status { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .run-layout, .topology-grid, .node-data-grid { grid-template-columns: 1fr; }
}
@media (max-width: 720px) {
  .run-head { flex-direction: column; align-items: stretch; }
  .run-status, .topology-summary, .run-node dl { grid-template-columns: 1fr; }
  .topology-node, .topology-edge { grid-template-columns: 1fr; }
  .timeline-event__head { display: grid; }
  .timeline-event__head span { white-space: normal; }
  .condition-branch-row { grid-template-columns: 1fr; }
}
</style>
