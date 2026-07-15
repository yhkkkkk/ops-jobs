import type { FlowAuditLog, FlowEdge, FlowNode, FlowNodeRun, FlowRun, FlowNodeType, FlowRunStatus, FlowTemplate } from '@/types'

export type SupportedFlowNodeType = Extract<FlowNodeType, 'script' | 'file_transfer' | 'job_plan' | 'manual' | 'condition' | 'parallel' | 'join' | 'sub_process'>
export type PipelineScope = 'all' | 'selected'

export interface StartVariable {
  key: string
  value: string
}

export type FlowVariableType = 'text' | 'number' | 'boolean' | 'secret' | 'host_list'
export type FlowVariableWidget = 'input' | 'textarea' | 'password' | 'host_list'

export interface FlowVariableDefinition {
  key: string
  name: string
  type: FlowVariableType
  widget: FlowVariableWidget
  default?: any
  has_default?: boolean
  required: boolean
  regex?: string
  show_on_start: boolean
  placeholder?: string
  description?: string
}

export interface BuildStartInputsParams {
  scope: PipelineScope | string
  selectedNodeUuids: string[]
  variables?: StartVariable[]
  variableDefinitions?: FlowVariableDefinition[]
  variableValues?: Record<string, any>
}

export interface FlowNodeJsonValidation {
  valid: boolean
  field?: string
  message?: string
}

export interface FlowGraphValidation {
  missingRequired: number
  disconnected: number
  startNodes: number
  terminalNodes: number
  invalidEdges: number
  issues: FlowGraphIssue[]
}

export type FlowGraphIssueSeverity = 'error' | 'warning'
export type FlowGraphIssueCode =
  | 'missing-required'
  | 'disconnected-node'
  | 'invalid-edge'
  | 'invalid-start'
  | 'missing-terminal'
  | 'cycle'
  | 'condition-no-branch'
  | 'condition-many-defaults'
  | 'condition-missing-expression'
  | 'parallel-branch-count'
  | 'join-incoming-count'
  | 'join-outgoing-count'

export interface FlowGraphIssue {
  code: FlowGraphIssueCode
  severity: FlowGraphIssueSeverity
  message: string
  nodeUuid?: string
  edgeKey?: string
}

export interface FlowTemplateFilters {
  search?: string
  status?: string
  runStatus?: string
}

export interface FlowHealthNotice {
  key: 'empty-topology' | 'inactive-template' | 'unsupported-node' | 'latest-run-failed'
  status: 'success' | 'warning' | 'danger'
  title: string
  description: string
  code: string
}

export interface ConditionBranchSummaryRow {
  targetUuid: string
  conditionText: string
  isDefault: boolean
}

export interface ConditionNodeRunSummary {
  hasDecision: boolean
  matchedCount: number
  defaultUsed: boolean
  rows: ConditionBranchSummaryRow[]
}

export type RunTopologyNodeStatus = FlowRunStatus | 'not_run'
export type RunTopologyEdgeState = 'normal' | 'selected' | 'default' | 'unselected'

export interface RunTopologyNode {
  uuid: string
  name: string
  nodeType: FlowNodeType
  status: RunTopologyNodeStatus
  run?: FlowNodeRun
}

export interface RunTopologyEdge {
  key: string
  sourceUuid: string
  targetUuid: string
  sourceName: string
  targetName: string
  conditionText: string
  state: RunTopologyEdgeState
  isConditionEdge: boolean
}

export interface RunTopology {
  nodes: RunTopologyNode[]
  edges: RunTopologyEdge[]
  executedCount: number
  notRunCount: number
  selectedConditionEdgeCount: number
}

export type FlowRunTimelineEventKind =
  | 'flow'
  | 'node_start'
  | 'node_status'
  | 'manual_confirm'
  | 'skip'
  | 'condition'
  | 'gateway'
  | 'audit'

export interface FlowRunTimelineEvent {
  key: string
  kind: FlowRunTimelineEventKind
  timestamp: string
  title: string
  description: string
  status: FlowRunStatus | 'info'
  nodeRunId?: number
  nodeUuid?: string
  nodeName?: string
  nodeType?: FlowNodeType
}

const hostBindingKeys = new Set([
  'host_ids',
  'target_host_ids',
  'step_target_host_ids',
  'target_hosts',
  'hosts',
])

const displayKeyMap: Record<string, string> = {
  host_ids: '目标主机',
  target_host_ids: '目标主机',
  step_target_host_ids: '目标主机',
  target_hosts: '目标主机',
  hosts: '目标主机',
  remote_path: '远端路径',
  download_url: '下载地址',
  upload_path: '上传路径',
  script_content: '脚本内容',
  execution_plan_id: '作业执行方案',
  execution_record: '关联执行记录',
  execution_record_id: '关联执行记录',
  child_flow_run_id: '关联子流程任务',
  child_run_id: '关联子流程任务',
  execution_parameters: '作业参数',
  current_node: '当前节点',
}

const countHostLikeValue = (value: any) => {
  if (Array.isArray(value)) return value.length
  if (typeof value === 'string') {
    const trimmed = value.trim()
    if (!trimmed) return 0
    if (/^\$\{[^}]+\}$/.test(trimmed)) return null
    try {
      const parsed = JSON.parse(trimmed)
      if (Array.isArray(parsed)) return parsed.length
    } catch {
      // fall through to comma-separated values
    }
    return trimmed.split(',').map(item => item.trim()).filter(Boolean).length
  }
  if (value && typeof value === 'object') {
    if (Array.isArray(value.ids)) return value.ids.length
    if (Array.isArray(value.host_ids)) return value.host_ids.length
  }
  return 0
}

export const sanitizeFlowRunDisplayData = (value: any): any => {
  if (Array.isArray(value)) return value.map(item => sanitizeFlowRunDisplayData(item))
  if (!value || typeof value !== 'object') return value

  return Object.entries(value).reduce<Record<string, any>>((acc, [key, item]) => {
    const displayKey = displayKeyMap[key] || key
    if (key === 'execution_plan_id') {
      acc[displayKey] = '已选择执行方案'
      return acc
    }
    if (key === 'execution_record' || key === 'execution_record_id') {
      acc[displayKey] = '已关联执行记录'
      return acc
    }
    if (key === 'child_flow_run_id' || key === 'child_run_id') {
      acc[displayKey] = '已关联子流程任务'
      return acc
    }
    if (hostBindingKeys.has(key)) {
      if (typeof item === 'string' && /^\s*\$\{[^}]+\}\s*$/.test(item)) {
        acc[displayKey] = `主机变量 ${item.trim()}`
      } else {
        const count = countHostLikeValue(item)
        acc[displayKey] = count === null ? '已绑定主机变量' : count > 0 ? `已选 ${count} 台主机` : '未绑定主机'
      }
      return acc
    }
    acc[displayKey] = sanitizeFlowRunDisplayData(item)
    return acc
  }, {})
}

export const formatFlowRunDisplayJson = (value: Record<string, any> = {}) =>
  JSON.stringify(sanitizeFlowRunDisplayData(value || {}), null, 2)

export interface FlowRunDisplayRow {
  key: string
  value: string
  multiline: boolean
}

export interface FlowNodeConfigDisplayRow {
  label: string
  value: string
  multiline?: boolean
}

const formatRunDisplayValue = (value: any): Pick<FlowRunDisplayRow, 'value' | 'multiline'> => {
  if (value === undefined || value === null || value === '') return { value: '-', multiline: false }
  if (typeof value === 'boolean') return { value: value ? '是' : '否', multiline: false }
  if (Array.isArray(value)) {
    const primitive = value.every(item => item === null || ['string', 'number', 'boolean'].includes(typeof item))
    return primitive
      ? { value: value.length ? value.map(item => String(item)).join(', ') : '-', multiline: false }
      : { value: JSON.stringify(value, null, 2), multiline: true }
  }
  if (typeof value === 'object') return { value: JSON.stringify(value, null, 2), multiline: true }
  return { value: String(value), multiline: false }
}

export const flowRunDisplayRows = (value: Record<string, any> = {}): FlowRunDisplayRow[] =>
  Object.entries(sanitizeFlowRunDisplayData(value || {})).map(([key, item]) => {
    const formatted = formatRunDisplayValue(item)
    return { key, ...formatted }
  })

const flowAuditActionTitle = (log: FlowAuditLog) => {
  const nodeName = log.extra_data?.node_name
  const map: Record<string, string> = {
    start_flow: '启动流程',
    skip_flow_node: nodeName ? `跳过节点 ${nodeName}` : '跳过流程节点',
    retry_flow_node: nodeName ? `重试节点 ${nodeName}` : '重试流程节点',
    confirm_flow_node: nodeName ? `确认节点 ${nodeName}` : '确认人工节点',
    cancel_flow: '取消流程',
  }
  return map[log.action] || log.action_display || log.action
}

const flowAuditDescription = (log: FlowAuditLog) => {
  const extra = log.extra_data || {}
  const pieces = [log.description || log.action_display || log.action]
  if (extra.reason) pieces.push(`原因: ${extra.reason}`)
  if (extra.remark) pieces.push(`备注: ${extra.remark}`)
  if (extra.previous_status || extra.new_status) {
    pieces.push(`${flowRunStatusText(extra.previous_status)} -> ${flowRunStatusText(extra.new_status)}`)
  }
  return pieces.filter(Boolean).join(' / ')
}

export const buildAuditTimelineEvents = (logs: FlowAuditLog[] = []): FlowRunTimelineEvent[] =>
  logs
    .filter(log => Boolean(log.created_at))
    .map(log => ({
      key: `audit-${log.id}`,
      kind: 'audit',
      timestamp: log.created_at,
      title: flowAuditActionTitle(log),
      description: flowAuditDescription(log),
      status: log.success ? 'success' : 'failed',
      nodeRunId: log.extra_data?.node_run_id,
      nodeUuid: log.extra_data?.node_uuid,
      nodeName: log.extra_data?.node_name,
      nodeType: log.extra_data?.node_type,
    }))

export const executionModeText = (mode?: string) => {
  if (mode === 'serial') return '串行'
  if (mode === 'rolling') return '滚动'
  return '并行'
}

export const flowNodeTypeText = (type: FlowNodeType) => {
  const map: Record<SupportedFlowNodeType, string> = {
    script: '脚本执行',
    file_transfer: '文件分发',
    job_plan: '作业执行方案',
    manual: '人工确认',
    condition: '条件分支',
    parallel: '并行网关',
    join: '汇聚网关',
    sub_process: '子流程',
  }
  return map[type as SupportedFlowNodeType] || type
}

export const isSupportedFlowNodeType = (type?: FlowNodeType | string): type is SupportedFlowNodeType =>
  type === 'script' ||
  type === 'file_transfer' ||
  type === 'job_plan' ||
  type === 'manual' ||
  type === 'condition' ||
  type === 'parallel' ||
  type === 'join' ||
  type === 'sub_process'

export const conditionOperatorText = (operator?: string) => {
  const map: Record<string, string> = {
    eq: '等于',
    ne: '不等于',
    gt: '大于',
    gte: '大于等于',
    lt: '小于',
    lte: '小于等于',
    contains: '包含',
    not_contains: '不包含',
    truthy: '为真',
    falsy: '为假',
    empty: '为空',
    not_empty: '不为空',
  }
  return map[operator || 'eq'] || operator || '等于'
}

export const summarizeEdgeCondition = (condition?: Record<string, any>) => {
  if (!condition || Object.keys(condition).length === 0) return '无条件'
  if (condition.default) return '默认分支'
  const variable = condition.variable || condition.left || condition.key || '-'
  const operator = condition.operator || condition.op || 'eq'
  if (['truthy', 'falsy', 'empty', 'not_empty'].includes(operator)) {
    return `${variable} ${conditionOperatorText(operator)}`
  }
  return `${variable} ${conditionOperatorText(operator)} ${condition.value ?? condition.right ?? ''}`.trim()
}

export const summarizeConditionNodeRun = (
  nodeRun?: Pick<FlowNodeRun, 'node_type' | 'outputs'> | null,
): ConditionNodeRunSummary => {
  const outputs = nodeRun?.outputs || {}
  if (nodeRun?.node_type !== 'condition') {
    return { hasDecision: false, matchedCount: 0, defaultUsed: false, rows: [] }
  }

  const selectedEdges = Array.isArray(outputs.selected_edges) ? outputs.selected_edges : []
  const selectedNodeUuids = Array.isArray(outputs.selected_node_uuids) ? outputs.selected_node_uuids : []
  const rows = selectedEdges.length > 0
    ? selectedEdges.map(edge => ({
        targetUuid: edge.target_uuid || edge.targetUuid || '-',
        conditionText: summarizeEdgeCondition(edge.condition),
        isDefault: Boolean(edge.condition?.default),
      }))
    : selectedNodeUuids.map(targetUuid => ({
        targetUuid: String(targetUuid),
        conditionText: outputs.default_used ? '默认分支' : '已选择',
        isDefault: Boolean(outputs.default_used),
      }))

  return {
    hasDecision: rows.length > 0,
    matchedCount: Number(outputs.matched_count || 0),
    defaultUsed: Boolean(outputs.default_used),
    rows,
  }
}

export const flowRunStatusText = (status?: string) => {
  const map: Record<string, string> = {
    pending: '等待中',
    running: '执行中',
    success: '成功',
    failed: '失败',
    paused: '已暂停',
    cancelled: '已取消',
    not_run: '未运行',
  }
  return map[status || 'pending'] || String(status || '-')
}

export const buildRunNodeStatusMap = (nodeRuns: FlowNodeRun[] = []) => {
  const map = new Map<string, FlowNodeRun>()
  nodeRuns.forEach(nodeRun => {
    map.set(nodeRun.node_uuid, nodeRun)
  })
  return map
}

const selectedConditionTargets = (nodeRun?: FlowNodeRun) => {
  const outputs = nodeRun?.outputs || {}
  const selectedEdges = Array.isArray(outputs.selected_edges) ? outputs.selected_edges : []
  const selectedNodeUuids = Array.isArray(outputs.selected_node_uuids) ? outputs.selected_node_uuids : []
  return new Set<string>([
    ...selectedNodeUuids.map(String),
    ...selectedEdges.map(edge => edge.target_uuid || edge.targetUuid).filter(Boolean).map(String),
  ])
}

export const isConditionEdgeSelected = (edge: Pick<FlowEdge, 'target_uuid'>, conditionNodeRun?: FlowNodeRun) => {
  if (!edge.target_uuid || !conditionNodeRun) return false
  return selectedConditionTargets(conditionNodeRun).has(edge.target_uuid)
}

export const buildRunTopology = (
  template?: Pick<FlowTemplate, 'nodes' | 'edges'> | null,
  run?: Pick<FlowRun, 'node_runs'> | null,
): RunTopology => {
  const nodes = template?.nodes || []
  const edges = template?.edges || []
  const nodeRunMap = buildRunNodeStatusMap(run?.node_runs || [])
  const nodeMap = new Map(nodes.map(node => [node.uuid, node]))

  const topologyNodes = nodes.map(node => {
    const nodeRun = nodeRunMap.get(node.uuid)
    const status: RunTopologyNodeStatus = nodeRun?.status || 'not_run'
    return {
      uuid: node.uuid,
      name: node.name,
      nodeType: node.node_type,
      status,
      run: nodeRun,
    }
  })

  const topologyEdges = edges.map((edge, index) => {
    const source = edge.source_uuid ? nodeMap.get(edge.source_uuid) : undefined
    const target = edge.target_uuid ? nodeMap.get(edge.target_uuid) : undefined
    const sourceRun = edge.source_uuid ? nodeRunMap.get(edge.source_uuid) : undefined
    const isConditionEdge = source?.node_type === 'condition'
    const selected = isConditionEdge && isConditionEdgeSelected(edge, sourceRun)
    const isDefault = selected && Boolean(edge.condition?.default)
    const state: RunTopologyEdgeState = isConditionEdge ? (isDefault ? 'default' : selected ? 'selected' : 'unselected') : 'normal'
    return {
      key: String(edge.id || `${edge.source_uuid || 'source'}-${edge.target_uuid || 'target'}-${index}`),
      sourceUuid: edge.source_uuid || '',
      targetUuid: edge.target_uuid || '',
      sourceName: source?.name || edge.source_uuid || '-',
      targetName: target?.name || edge.target_uuid || '-',
      conditionText: summarizeEdgeCondition(edge.condition),
      state,
      isConditionEdge,
    }
  })

  return {
    nodes: topologyNodes,
    edges: topologyEdges,
    executedCount: topologyNodes.filter(node => node.status !== 'not_run').length,
    notRunCount: topologyNodes.filter(node => node.status === 'not_run').length,
    selectedConditionEdgeCount: topologyEdges.filter(edge => edge.state === 'selected' || edge.state === 'default').length,
  }
}

const timelineTime = (value?: string | null) => value || ''

const statusEventTitle = (nodeRun: FlowNodeRun) => {
  if (nodeRun.status === 'success') return `${nodeRun.node_name} 执行成功`
  if (nodeRun.status === 'failed') return `${nodeRun.node_name} 执行失败`
  if (nodeRun.status === 'paused') return `${nodeRun.node_name} 已暂停`
  if (nodeRun.status === 'cancelled') return `${nodeRun.node_name} 已取消`
  if (nodeRun.status === 'running') return `${nodeRun.node_name} 执行中`
  return `${nodeRun.node_name} ${flowRunStatusText(nodeRun.status)}`
}

const statusEventDescription = (nodeRun: FlowNodeRun) => {
  if (nodeRun.error_message) return nodeRun.error_message
  if (nodeRun.node_type === 'sub_process') {
    const childRunId = nodeRun.outputs?.child_flow_run_id || nodeRun.outputs?.child_run_id
    const childStatus = nodeRun.outputs?.child_flow_status || nodeRun.outputs?.child_status
    const pieces = [flowNodeTypeText(nodeRun.node_type)]
    if (childRunId) pieces.push('已关联子流程任务')
    if (childStatus) pieces.push(flowRunStatusText(childStatus))
    return pieces.join(' / ')
  }
  if (nodeRun.execution_record_id) return `${flowNodeTypeText(nodeRun.node_type)} / 已关联执行记录`
  return flowNodeTypeText(nodeRun.node_type)
}

export const buildFlowRunTimeline = (run?: FlowRun | null, auditLogs: FlowAuditLog[] = []): FlowRunTimelineEvent[] => {
  const auditEvents = buildAuditTimelineEvents(auditLogs)
  if (!run) return auditEvents
  const events: Array<FlowRunTimelineEvent & { order: number }> = []
  const nodeNameMap = new Map((run.node_runs || []).map(nodeRun => [nodeRun.node_uuid, nodeRun.node_name]))
  const displayNodeName = (uuid?: string) => uuid ? nodeNameMap.get(uuid) || '未知节点' : '未知节点'
  let order = 0
  const addEvent = (event: FlowRunTimelineEvent) => {
    if (!event.timestamp) return
    events.push({ ...event, order: order++ })
  }

  addEvent({
    key: `flow-created-${run.id}`,
    kind: 'flow',
    timestamp: run.created_at,
    title: `${run.name || run.template_name || '流水线任务'} 已创建`,
    description: `${run.template_name} / ${run.started_by_name || '-'}`,
    status: 'info',
  })
  addEvent({
    key: `flow-started-${run.id}`,
    kind: 'flow',
    timestamp: timelineTime(run.started_at),
    title: `${run.name || run.template_name || '流水线任务'} 已启动`,
    description: `${run.trigger_type || 'manual'} 触发`,
    status: 'running',
  })

  ;(run.node_runs || []).forEach(nodeRun => {
    const typeText = flowNodeTypeText(nodeRun.node_type)
    addEvent({
      key: `node-start-${nodeRun.id}`,
      kind: 'node_start',
      timestamp: timelineTime(nodeRun.started_at || nodeRun.created_at),
      title: `${nodeRun.node_name} 开始执行`,
      description: typeText,
      status: 'running',
      nodeRunId: nodeRun.id,
      nodeUuid: nodeRun.node_uuid,
      nodeName: nodeRun.node_name,
      nodeType: nodeRun.node_type,
    })

    if (nodeRun.node_type === 'condition') {
      const summary = summarizeConditionNodeRun(nodeRun)
      const decisionText = summary.hasDecision
        ? summary.rows.map(row => `${row.isDefault ? '默认' : '命中'} ${displayNodeName(row.targetUuid)}`).join('；')
        : '没有命中的条件，也没有默认分支'
      addEvent({
        key: `condition-${nodeRun.id}`,
        kind: 'condition',
        timestamp: timelineTime(nodeRun.finished_at || nodeRun.started_at || nodeRun.created_at),
        title: `${nodeRun.node_name} 分支决策`,
        description: decisionText,
        status: nodeRun.status,
        nodeRunId: nodeRun.id,
        nodeUuid: nodeRun.node_uuid,
        nodeName: nodeRun.node_name,
        nodeType: nodeRun.node_type,
      })
    }

    if (nodeRun.node_type === 'parallel' || nodeRun.node_type === 'join') {
      addEvent({
        key: `gateway-${nodeRun.id}`,
        kind: 'gateway',
        timestamp: timelineTime(nodeRun.finished_at || nodeRun.started_at || nodeRun.created_at),
        title: `${nodeRun.node_name} 网关通过`,
        description: typeText,
        status: nodeRun.status,
        nodeRunId: nodeRun.id,
        nodeUuid: nodeRun.node_uuid,
        nodeName: nodeRun.node_name,
        nodeType: nodeRun.node_type,
      })
    }

    if (nodeRun.outputs?.confirmed_at) {
      addEvent({
        key: `manual-confirm-${nodeRun.id}`,
        kind: 'manual_confirm',
        timestamp: String(nodeRun.outputs.confirmed_at),
        title: `${nodeRun.node_name} 人工确认`,
        description: `${nodeRun.outputs.confirmed_by || '-'}${nodeRun.outputs.confirm_remark ? ` / ${nodeRun.outputs.confirm_remark}` : ''}`,
        status: 'success',
        nodeRunId: nodeRun.id,
        nodeUuid: nodeRun.node_uuid,
        nodeName: nodeRun.node_name,
        nodeType: nodeRun.node_type,
      })
    }

    if (nodeRun.outputs?.skipped_at) {
      addEvent({
        key: `skip-${nodeRun.id}`,
        kind: 'skip',
        timestamp: String(nodeRun.outputs.skipped_at),
        title: `${nodeRun.node_name} 已跳过`,
        description: nodeRun.outputs.skip_reason || 'manual skip',
        status: 'success',
        nodeRunId: nodeRun.id,
        nodeUuid: nodeRun.node_uuid,
        nodeName: nodeRun.node_name,
        nodeType: nodeRun.node_type,
      })
    }

    addEvent({
      key: `node-status-${nodeRun.id}`,
      kind: 'node_status',
      timestamp: timelineTime(nodeRun.finished_at || (nodeRun.status === 'paused' || nodeRun.node_type === 'sub_process' ? nodeRun.started_at || nodeRun.created_at : '')),
      title: statusEventTitle(nodeRun),
      description: statusEventDescription(nodeRun),
      status: nodeRun.status,
      nodeRunId: nodeRun.id,
      nodeUuid: nodeRun.node_uuid,
      nodeName: nodeRun.node_name,
      nodeType: nodeRun.node_type,
    })
  })

  addEvent({
    key: `flow-finished-${run.id}`,
    kind: 'flow',
    timestamp: timelineTime(run.finished_at),
    title: `${run.name || run.template_name || '流水线任务'} ${flowRunStatusText(run.status)}`,
    description: run.error_message || run.template_name,
    status: run.status,
  })

  auditEvents.forEach(event => events.push({ ...event, order: order++ }))

  return events
    .sort((left, right) => {
      const timeDiff = new Date(left.timestamp).getTime() - new Date(right.timestamp).getTime()
      return timeDiff || left.order - right.order
    })
    .map(({ order: _order, ...event }) => event)
}

export const buildLatestRunMap = (runs: FlowRun[]) => {
  const map = new Map<number, FlowRun>()
  runs.forEach(run => {
    const current = map.get(run.template)
    const currentTime = current ? new Date(current.started_at || current.created_at).getTime() : 0
    const runTime = new Date(run.started_at || run.created_at).getTime()
    if (!current || runTime > currentTime) map.set(run.template, run)
  })
  return map
}

const runTime = (run: FlowRun) => new Date(run.started_at || run.created_at).getTime()

export const getRecentFlowRuns = (runs: FlowRun[], limit = 3) =>
  [...runs].sort((left, right) => runTime(right) - runTime(left)).slice(0, limit)

export const buildFlowHealthNotices = (
  templates: FlowTemplate[],
  latestRuns: Map<number, FlowRun>,
): FlowHealthNotice[] => {
  const notices: FlowHealthNotice[] = []
  const emptyTopologyCount = templates.filter(template => (template.nodes || []).length === 0).length
  const inactiveCount = templates.filter(template => !template.is_active).length
  const unsupportedNodeCount = templates.reduce((count, template) =>
    count + (template.nodes || []).filter(node => !isSupportedFlowNodeType(node.node_type)).length, 0)
  const failedLatestRunCount = templates.filter(template => {
    const run = template.id ? latestRuns.get(template.id) : undefined
    return run?.status === 'failed'
  }).length

  if (emptyTopologyCount > 0) {
    notices.push({
      key: 'empty-topology',
      status: 'warning',
      title: `${emptyTopologyCount} 个模板没有节点`,
      description: '新建后还未完成插件编排，启动前需要补齐拓扑。',
      code: 'P1',
    })
  }
  if (inactiveCount > 0) {
    notices.push({
      key: 'inactive-template',
      status: 'warning',
      title: `${inactiveCount} 个模板处于停用状态`,
      description: '停用模板无法直接启动，可用于草稿或待审核流程。',
      code: 'P2',
    })
  }
  if (unsupportedNodeCount > 0) {
    notices.push({
      key: 'unsupported-node',
      status: 'danger',
      title: `${unsupportedNodeCount} 个节点暂未支持前端编辑`,
      description: '节点配置会保留，但需要补齐对应插件编辑器后再开放修改。',
      code: 'P0',
    })
  }
  if (failedLatestRunCount > 0) {
    notices.push({
      key: 'latest-run-failed',
      status: 'danger',
      title: `${failedLatestRunCount} 个模板最近执行失败`,
      description: '建议优先查看失败实例，确认是否需要回滚或修复参数。',
      code: 'P0',
    })
  }

  if (notices.length === 0) {
    notices.push({
      key: 'empty-topology',
      status: 'success',
      title: '模板健康检查通过',
      description: '未发现空拓扑、停用模板、失败实例或暂不支持节点。',
      code: 'OK',
    })
  }
  return notices
}

export const filterFlowTemplates = (
  templates: FlowTemplate[],
  filters: FlowTemplateFilters,
  latestRuns: Map<number, FlowRun>,
) => {
  const search = (filters.search || '').trim().toLowerCase()
  return templates.filter(item => {
    const run = item.id ? latestRuns.get(item.id) : undefined
    const matchesSearch =
      !search ||
      item.name.toLowerCase().includes(search) ||
      (item.description || '').toLowerCase().includes(search) ||
      (item.created_by_name || '').toLowerCase().includes(search)
    const matchesStatus = !filters.status || (filters.status === 'active' ? item.is_active : !item.is_active)
    const matchesRun = !filters.runStatus || run?.status === filters.runStatus
    return matchesSearch && matchesStatus && matchesRun
  })
}

export const parseLooseValue = (value: string) => {
  const trimmed = value.trim()
  if (!trimmed) return ''
  if (trimmed === 'true') return true
  if (trimmed === 'false') return false
  if (!Number.isNaN(Number(trimmed))) return Number(trimmed)
  try {
    return JSON.parse(trimmed)
  } catch {
    return value
  }
}

export const flowVariableReference = (key: string) => `\${${key}}`

export const normalizeFlowVariables = (variables: Record<string, any> = {}): FlowVariableDefinition[] =>
  Object.entries(variables).map(([key, raw]) => {
    const value = raw && typeof raw === 'object' && !Array.isArray(raw) ? raw : {}
    const rawType = String(value.type || 'text')
    const type = (rawType === 'password' ? 'secret' : rawType) as FlowVariableType
    const widget = (value.widget || (type === 'secret' ? 'password' : type === 'host_list' ? 'host_list' : 'input')) as FlowVariableWidget
    return {
      key,
      name: String(value.name || value.label || key),
      type,
      widget,
      default: value.default,
      has_default: Boolean(value.has_default),
      required: Boolean(value.required),
      regex: value.regex ? String(value.regex) : undefined,
      show_on_start: value.show_on_start !== false,
      placeholder: value.placeholder ? String(value.placeholder) : undefined,
      description: value.description ? String(value.description) : undefined,
    }
  })

export const serializeFlowVariables = (definitions: FlowVariableDefinition[] = []) =>
  definitions.reduce<Record<string, any>>((acc, item) => {
    const key = item.key.trim()
    if (!key) return acc
    acc[key] = {
      name: item.name || key,
      type: item.type || 'text',
      widget: item.widget || 'input',
      default: item.default,
      has_default: Boolean(item.has_default),
      required: Boolean(item.required),
      regex: item.regex || '',
      show_on_start: item.show_on_start !== false,
      placeholder: item.placeholder || '',
      description: item.description || '',
    }
    return acc
  }, {})

export const flowVariableSelectOptions = (definitions: FlowVariableDefinition[] = [], type?: FlowVariableType) =>
  definitions
    .filter(item => !type || item.type === type)
    .map(item => ({
      label: `${item.name || item.key} (${flowVariableReference(item.key)})`,
      value: flowVariableReference(item.key),
      key: item.key,
    }))

const buildStandardVariableInputs = (definitions: FlowVariableDefinition[] = [], values: Record<string, any> = {}) =>
  definitions.reduce<Record<string, any>>((acc, item) => {
    const value = Object.prototype.hasOwnProperty.call(values, item.key) ? values[item.key] : item.default
    acc[item.key] = value
    return acc
  }, {})

export const buildScheduledInputs = (
  definitions: FlowVariableDefinition[] = [],
  values: Record<string, any> = {},
) => buildStandardVariableInputs(definitions, values)
export const buildStartInputs = ({
  scope,
  selectedNodeUuids,
  variables,
  variableDefinitions,
  variableValues,
}: BuildStartInputsParams) => {
  const variableInputs = variableDefinitions
    ? buildStandardVariableInputs(variableDefinitions, variableValues)
    : (variables || []).reduce<Record<string, any>>((acc, item) => {
        const key = item.key.trim()
        if (!key) return acc
        acc[key] = parseLooseValue(item.value)
        return acc
      }, {})


  return {
    ...variableInputs,
    __execution_scope: scope,
    __selected_node_uuids: scope === 'selected' ? [...selectedNodeUuids] : [],
  }
}

export const canStartFlow = (scope: PipelineScope | string, selectedNodeUuids: string[]) =>
  scope !== 'selected' || selectedNodeUuids.length > 0

export const canSkipFlowNodeRun = (nodeRun?: Pick<FlowNodeRun, 'status'> | null) =>
  nodeRun?.status === 'failed' || nodeRun?.status === 'paused'

export const canRetryFlowNodeRun = (nodeRun?: Pick<FlowNodeRun, 'status'> | null) =>
  nodeRun?.status === 'failed' || nodeRun?.status === 'paused'

export const canConfirmManualNodeRun = (nodeRun?: Pick<FlowNodeRun, 'node_type' | 'status'> | null) =>
  nodeRun?.node_type === 'manual' && nodeRun.status === 'paused'

export const canCancelFlowRun = (run?: Pick<FlowRun, 'status'> | null) =>
  run?.status === 'pending' || run?.status === 'running' || run?.status === 'paused'

export const parseFileSources = (text?: string, fallback?: any[]) => {
  if (Array.isArray(fallback)) return fallback
  if (!text) return []
  try {
    const value = JSON.parse(text)
    return Array.isArray(value) ? value : []
  } catch {
    return []
  }
}

export const validFileSources = (config: Record<string, any>) =>
  parseFileSources(config.file_sources_text, config.file_sources)
    .filter(source => source.download_url?.trim() && source.remote_path?.trim())

export const isNodeReady = (node: FlowNode) => {
  const config = node.config || {}
  if (!node.name?.trim()) return false
  if (node.node_type === 'script') return Boolean(config.script_content?.trim() && config.target_host_ids)
  if (node.node_type === 'file_transfer') return Boolean(config.target_host_ids && validFileSources(config).length > 0)
  if (node.node_type === 'job_plan') return Boolean(config.execution_plan_id)
  if (node.node_type === 'sub_process') return Boolean(config.template_id)
  if (node.node_type === 'manual') return true
  if (node.node_type === 'condition') return true
  return true
}

export const summarizeFlowNode = (node: FlowNode) => {
  const config = node.config || {}
  const targetHostText = summarizeTargetHostBinding(config.target_host_ids)
  if (node.node_type === 'script') {
    return `${config.script_type || 'shell'} / ${targetHostText} / ${config.timeout || 300}s`
  }
  if (node.node_type === 'file_transfer') {
    return `${targetHostText} / ${validFileSources(config).length} 个文件源 / 限速 ${config.bandwidth_limit || 0} MB/s`
  }
  if (node.node_type === 'job_plan') {
    return `${config.execution_plan_id ? '已选择执行方案' : '未选择执行方案'} / ${executionModeText(config.execution_mode)}`
  }
  if (node.node_type === 'sub_process') {
    return `${config.template_id ? '已选择子流程' : '未选择子流程'} / ${config.inherit_inputs === false ? '独立输入' : '继承输入'}`
  }
  if (node.node_type === 'manual') {
    return config.instructions?.trim() || '等待人工确认后继续'
  }
  if (node.node_type === 'condition') {
    return config.description?.trim() || '按出边条件选择分支'
  }
  if (node.node_type === 'parallel') {
    return config.description?.trim() || '并行启动所有下游分支'
  }
  if (node.node_type === 'join') {
    return config.description?.trim() || '等待所有活跃上游分支完成'
  }
  return '-'
}

const formatBindings = (bindings?: Record<string, any>) => {
  const rows = Object.entries(bindings || {})
    .filter(([key, value]) => key && value !== undefined && value !== null && value !== '')
    .map(([key, value]) => `${key} -> ${String(value)}`)
  return rows.length ? rows.join('\n') : '未配置'
}

export const flowNodeConfigDisplayRows = (node: FlowNode): FlowNodeConfigDisplayRow[] => {
  const config = node.config || {}
  if (node.node_type === 'script') {
    return [
      { label: '脚本类型', value: String(config.script_type || 'shell') },
      { label: '目标主机', value: summarizeTargetHostBinding(config.target_host_ids) },
      { label: '超时时间', value: `${config.timeout || 300}s` },
      { label: '脚本内容', value: config.script_content || '未配置', multiline: true },
    ]
  }
  if (node.node_type === 'file_transfer') {
    const sources = validFileSources(config)
    return [
      { label: '目标主机', value: summarizeTargetHostBinding(config.target_host_ids) },
      { label: '文件源', value: sources.length ? sources.map(source => `${source.download_url || '-'} -> ${source.remote_path || '-'}`).join('\n') : '未配置', multiline: true },
      { label: '超时时间', value: `${config.timeout || 600}s` },
      { label: '限速', value: `${config.bandwidth_limit || 0} MB/s` },
    ]
  }
  if (node.node_type === 'job_plan') {
    return [
      { label: '执行方案', value: config.execution_plan_id ? '已选择执行方案' : '未选择' },
      { label: '执行模式', value: executionModeText(config.execution_mode) },
      { label: '变量映射', value: formatBindings(config.execution_parameter_bindings), multiline: true },
    ]
  }
  if (node.node_type === 'sub_process') {
    return [
      { label: '子流程模板', value: config.template_id ? '已选择子流程' : '未选择' },
      { label: '输入继承', value: config.inherit_inputs === false ? '独立输入' : '继承父流程输入' },
      { label: '输入映射', value: config.inputs ? JSON.stringify(config.inputs, null, 2) : '未配置', multiline: true },
    ]
  }
  if (node.node_type === 'manual') {
    return [
      { label: '确认说明', value: config.instructions || '等待人工确认后继续', multiline: true },
    ]
  }
  if (node.node_type === 'condition') {
    return [
      { label: '分支说明', value: config.description || '按出边条件选择分支', multiline: true },
    ]
  }
  if (node.node_type === 'parallel') {
    return [{ label: '网关说明', value: config.description || '并行启动所有下游分支', multiline: true }]
  }
  if (node.node_type === 'join') {
    return [{ label: '网关说明', value: config.description || '等待所有活跃上游分支完成', multiline: true }]
  }
  return [{ label: '节点配置', value: summarizeFlowNode(node), multiline: true }]
}

export const summarizeTargetHostBinding = (value: any) => {
  if (Array.isArray(value)) return value.length ? `已选 ${value.length} 台主机` : '未绑定主机变量'
  if (typeof value === 'string') {
    const trimmed = value.trim()
    if (!trimmed) return '未绑定主机变量'
    if (/^\$\{[^}]+\}$/.test(trimmed)) return `主机变量 ${trimmed}`
    const jsonArrayMatch = trimmed.match(/^\[(.*)\]$/)
    const pieces = jsonArrayMatch ? jsonArrayMatch[1].split(',') : trimmed.split(',')
    const hostCount = pieces.map(item => item.trim().replace(/^['"]|['"]$/g, '')).filter(Boolean).length
    if (hostCount > 0 && (jsonArrayMatch || pieces.length > 1 || /^\d+$/.test(trimmed))) return `已选 ${hostCount} 台主机`
    return '已绑定主机'
  }
  if (value && typeof value === 'object') return '动态主机配置'
  return '未绑定主机变量'
}

export const evaluateFlowGraph = (nodes: FlowNode[], edges: FlowEdge[]): FlowGraphValidation => {
  const nodeUuids = new Set(nodes.map(node => node.uuid))
  const nodeMap = new Map(nodes.map(node => [node.uuid, node]))
  const validEdges = edges.filter(edge =>
    Boolean(edge.source_uuid && edge.target_uuid && nodeUuids.has(edge.source_uuid) && nodeUuids.has(edge.target_uuid))
  )
  const incoming = new Set(validEdges.map(edge => edge.target_uuid))
  const outgoing = new Set(validEdges.map(edge => edge.source_uuid))
  const connected = new Set(validEdges.flatMap(edge => [edge.source_uuid, edge.target_uuid]).filter(Boolean))
  const outgoingEdgesByNode = new Map<string, FlowEdge[]>()
  const incomingEdgesByNode = new Map<string, FlowEdge[]>()
  validEdges.forEach(edge => {
    if (edge.source_uuid) outgoingEdgesByNode.set(edge.source_uuid, [...(outgoingEdgesByNode.get(edge.source_uuid) || []), edge])
    if (edge.target_uuid) incomingEdgesByNode.set(edge.target_uuid, [...(incomingEdgesByNode.get(edge.target_uuid) || []), edge])
  })

  const issues: FlowGraphIssue[] = []
  nodes.forEach(node => {
    if (!isNodeReady(node)) {
      issues.push({
        code: 'missing-required',
        severity: 'error',
        nodeUuid: node.uuid,
        message: `${node.name || node.uuid} 缺少必填配置`,
      })
    }
    if (nodes.length > 1 && !connected.has(node.uuid)) {
      issues.push({
        code: 'disconnected-node',
        severity: 'error',
        nodeUuid: node.uuid,
        message: `${node.name || node.uuid} 未连接到流程拓扑`,
      })
    }
  })

  edges.forEach((edge, index) => {
    if (!validEdges.includes(edge)) {
      issues.push({
        code: 'invalid-edge',
        severity: 'error',
        edgeKey: `${edge.source_uuid || 'source'}-${edge.target_uuid || 'target'}-${index}`,
        message: `连线 ${edge.source_uuid || '-'} -> ${edge.target_uuid || '-'} 指向不存在的节点`,
      })
    }
  })

  if (nodes.length > 1 && nodes.filter(node => !incoming.has(node.uuid)).length !== 1) {
    issues.push({
      code: 'invalid-start',
      severity: 'error',
      message: '流程必须保留一个明确的起始节点',
    })
  }
  if (nodes.length > 1 && nodes.filter(node => !outgoing.has(node.uuid)).length < 1) {
    issues.push({
      code: 'missing-terminal',
      severity: 'error',
      message: '流程至少需要一个结束节点',
    })
  }
  if (hasGraphCycle(validEdges)) {
    issues.push({
      code: 'cycle',
      severity: 'error',
      message: '流程拓扑存在环路，执行器无法按 DAG 推进',
    })
  }

  nodes.forEach(node => {
    const nodeOutgoingEdges = outgoingEdgesByNode.get(node.uuid) || []
    const nodeIncomingEdges = incomingEdgesByNode.get(node.uuid) || []
    if (node.node_type === 'condition') {
      if (nodeOutgoingEdges.length === 0) {
        issues.push({
          code: 'condition-no-branch',
          severity: 'error',
          nodeUuid: node.uuid,
          message: `${node.name || node.uuid} 至少需要一条分支连线`,
        })
      }
      const defaultCount = nodeOutgoingEdges.filter(edge => edge.condition?.default).length
      if (defaultCount > 1) {
        issues.push({
          code: 'condition-many-defaults',
          severity: 'error',
          nodeUuid: node.uuid,
          message: `${node.name || node.uuid} 只能设置一个默认分支`,
        })
      }
      nodeOutgoingEdges.forEach(edge => {
        const condition = edge.condition || {}
        const operator = condition.operator || condition.op || 'eq'
        const variable = condition.variable || condition.left || condition.key
        const needsExpectedValue = !['truthy', 'falsy', 'empty', 'not_empty'].includes(operator)
        if (!condition.default && (!variable || (needsExpectedValue && condition.value === undefined && condition.right === undefined))) {
          issues.push({
            code: 'condition-missing-expression',
            severity: 'error',
            nodeUuid: node.uuid,
            edgeKey: `${edge.source_uuid}-${edge.target_uuid}`,
            message: `${node.name || node.uuid} 到 ${nodeMap.get(edge.target_uuid || '')?.name || edge.target_uuid || '-'} 的分支缺少判断变量`,
          })
        }
      })
    }
    if (node.node_type === 'parallel' && nodeOutgoingEdges.length < 2) {
      issues.push({
        code: 'parallel-branch-count',
        severity: 'warning',
        nodeUuid: node.uuid,
        message: `${node.name || node.uuid} 通常需要至少两个下游分支`,
      })
    }
    if (node.node_type === 'join') {
      if (nodeIncomingEdges.length < 2) {
        issues.push({
          code: 'join-incoming-count',
          severity: 'warning',
          nodeUuid: node.uuid,
          message: `${node.name || node.uuid} 通常需要至少两个上游分支`,
        })
      }
      if (nodeOutgoingEdges.length > 1) {
        issues.push({
          code: 'join-outgoing-count',
          severity: 'warning',
          nodeUuid: node.uuid,
          message: `${node.name || node.uuid} 建议只保留一个下游出口`,
        })
      }
    }
  })

  return {
    missingRequired: nodes.filter(node => !isNodeReady(node)).length,
    disconnected: nodes.filter(node => !connected.has(node.uuid) && nodes.length > 1).length,
    startNodes: nodes.filter(node => !incoming.has(node.uuid)).length,
    terminalNodes: nodes.filter(node => !outgoing.has(node.uuid)).length,
    invalidEdges: edges.length - validEdges.length,
    issues,
  }
}

const hasPath = (edges: FlowEdge[], from: string, to: string, visited: Set<string>): boolean => {
  if (from === to) return true
  if (visited.has(from)) return false
  visited.add(from)
  return edges
    .filter(edge => edge.source_uuid === from)
    .some(edge => Boolean(edge.target_uuid && hasPath(edges, edge.target_uuid, to, visited)))
}

export const createsCycle = (edges: FlowEdge[], source: string, target: string) =>
  hasPath(edges, target, source, new Set<string>())

const hasGraphCycle = (edges: FlowEdge[]) => {
  const outgoing = new Map<string, string[]>()
  edges.forEach(edge => {
    if (!edge.source_uuid || !edge.target_uuid) return
    outgoing.set(edge.source_uuid, [...(outgoing.get(edge.source_uuid) || []), edge.target_uuid])
  })

  const visiting = new Set<string>()
  const visited = new Set<string>()
  const visit = (uuid: string): boolean => {
    if (visiting.has(uuid)) return true
    if (visited.has(uuid)) return false
    visiting.add(uuid)
    for (const target of outgoing.get(uuid) || []) {
      if (visit(target)) return true
    }
    visiting.delete(uuid)
    visited.add(uuid)
    return false
  }

  return [...outgoing.keys()].some(visit)
}

export const normalizeFlowNode = (node: FlowNode): FlowNode => {
  const config = { ...(node.config || {}) }
  if (!config.failure_policy) config.failure_policy = node.node_type === 'job_plan' ? 'pause' : 'stop'
  if (node.node_type === 'file_transfer') {
    config.file_sources = parseFileSources(config.file_sources_text, config.file_sources)
  }
  if (node.node_type === 'sub_process' && !config.inputs_text) {
    config.inputs_text = JSON.stringify(config.inputs || {}, null, 2)
  }
  return { ...node, config }
}

export const resolveFlowTemplateTopology = (
  template: Pick<FlowTemplate, 'nodes' | 'edges'>,
  fallbackNodes: FlowNode[] = [],
  fallbackEdges: FlowEdge[] = [],
) => ({
  nodes: Array.isArray(template.nodes) && template.nodes.length > 0 ? template.nodes : fallbackNodes,
  edges: Array.isArray(template.edges) && template.edges.length > 0 ? template.edges : fallbackEdges,
})

export const validateFlowNodeConfigJson = (node: FlowNode): FlowNodeJsonValidation => {
  const config = node.config || {}
  const checks: Array<{ field: string; label: string; value?: string }> = []
  if (node.node_type === 'sub_process') {
    checks.push({ field: 'inputs_text', label: '子流程输入 JSON', value: config.inputs_text || '{}' })
  }

  for (const check of checks) {
    try {
      const parsed = JSON.parse(check.value || '{}')
      if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') {
        return { valid: false, field: check.field, message: `${node.name || node.uuid} 的 ${check.label} 必须是 JSON 对象` }
      }
    } catch (error) {
      return {
        valid: false,
        field: check.field,
        message: `${node.name || node.uuid} 的 ${check.label} 格式不正确: ${(error as Error).message}`,
      }
    }
  }
  return { valid: true }
}

export const serializeFlowNode = (node: FlowNode): FlowNode => {
  const config = { ...(node.config || {}) }
  if (node.node_type === 'file_transfer') {
    config.file_sources = validFileSources(config)
    delete config.file_sources_text
  }
  if (node.node_type === 'job_plan') {
    delete config.execution_parameters_text
    delete config.execution_parameters
  }
  if (node.node_type === 'sub_process') {
    config.inputs = JSON.parse(config.inputs_text || '{}')
    delete config.inputs_text
  }
  return { ...node, config }
}
