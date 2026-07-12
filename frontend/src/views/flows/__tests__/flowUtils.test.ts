import { describe, expect, it } from 'vitest'
import {
  buildLatestRunMap,
  buildAuditTimelineEvents,
  buildFlowHealthNotices,
  buildFlowRunTimeline,
  buildRunNodeStatusMap,
  buildRunTopology,
  buildScheduledInputs,
  buildStartInputs,
  canCancelFlowRun,
  canConfirmManualNodeRun,
  canRetryFlowNodeRun,
  canSkipFlowNodeRun,
  canStartFlow,
  createsCycle,
  evaluateFlowGraph,
  filterFlowTemplates,
  flowNodeConfigDisplayRows,
  flowRunDisplayRows,
  formatFlowRunDisplayJson,
  flowVariableReference,
  flowVariableSelectOptions,
  getRecentFlowRuns,
  isSupportedFlowNodeType,
  isConditionEdgeSelected,
  isNodeReady,
  normalizeFlowNode,
  resolveFlowTemplateTopology,
  normalizeFlowVariables,
  parseLooseValue,
  serializeFlowNode,
  sanitizeFlowRunDisplayData,
  summarizeConditionNodeRun,
  summarizeEdgeCondition,
  summarizeFlowNode,
  validateFlowNodeConfigJson,
} from '../flowUtils'
import type { FlowAuditLog, FlowEdge, FlowNode, FlowNodeRun, FlowRun, FlowTemplate } from '@/types'

const makeNode = (patch: Partial<FlowNode>): FlowNode => ({
  uuid: patch.uuid || 'node-a',
  name: patch.name || '节点',
  node_type: patch.node_type || 'script',
  config: patch.config || {},
  position: patch.position || { x: 0, y: 0 },
})

const makeRun = (patch: Partial<FlowRun>): FlowRun => ({
  id: patch.id || 1,
  template: patch.template || 1,
  template_name: patch.template_name || '流水线',
  status: patch.status || 'success',
  trigger_type: patch.trigger_type || 'manual',
  started_by: patch.started_by || 1,
  started_by_name: patch.started_by_name || 'admin',
  inputs: patch.inputs || {},
  outputs: patch.outputs || {},
  created_at: patch.created_at || '2026-06-10T09:00:00Z',
  started_at: patch.started_at,
  finished_at: patch.finished_at,
  node_runs: patch.node_runs || [],
})

const makeNodeRun = (patch: Partial<FlowNodeRun>): FlowNodeRun => ({
  id: patch.id || 1,
  node: patch.node || 1,
  node_name: patch.node_name || '节点',
  node_uuid: patch.node_uuid || 'node-a',
  node_type: patch.node_type || 'script',
  status: patch.status || 'success',
  inputs: patch.inputs || {},
  outputs: patch.outputs || {},
  error_message: patch.error_message || '',
  execution_record: patch.execution_record,
  execution_record_id: patch.execution_record_id,
  created_at: patch.created_at || '2026-06-10T09:00:00Z',
  started_at: patch.started_at,
  finished_at: patch.finished_at,
})

const makeAuditLog = (patch: Partial<FlowAuditLog>): FlowAuditLog => ({
  id: patch.id || 1,
  user: patch.user || 1,
  user_name: patch.user_name || 'admin',
  user_full_name: patch.user_full_name || 'admin',
  action: patch.action || 'start_flow',
  action_display: patch.action_display || patch.action || 'start_flow',
  resource_type: patch.resource_type ?? 1,
  resource_type_name: patch.resource_type_name || 'flow run',
  resource_id: patch.resource_id ?? 1,
  resource_name: patch.resource_name || '流水线 #1',
  description: patch.description || '启动流程',
  ip_address: patch.ip_address || '127.0.0.1',
  user_agent: patch.user_agent || '',
  success: patch.success ?? true,
  error_message: patch.error_message || '',
  extra_data: patch.extra_data || {},
  created_at: patch.created_at || '2026-06-10T09:00:00Z',
})

describe('flow utils', () => {
  it('keeps the newest run per template for list display', () => {
    const map = buildLatestRunMap([
      makeRun({ id: 1, template: 7, created_at: '2026-06-10T09:00:00Z' }),
      makeRun({ id: 2, template: 7, created_at: '2026-06-10T10:00:00Z' }),
      makeRun({ id: 3, template: 8, created_at: '2026-06-10T08:00:00Z' }),
    ])

    expect(map.get(7)?.id).toBe(2)
    expect(map.get(8)?.id).toBe(3)
  })

  it('sorts recent flow runs by execution time and limits the result', () => {
    const recent = getRecentFlowRuns([
      makeRun({ id: 1, created_at: '2026-06-10T09:00:00Z' }),
      makeRun({ id: 2, started_at: '2026-06-10T11:00:00Z' }),
      makeRun({ id: 3, created_at: '2026-06-10T10:00:00Z' }),
    ], 2)

    expect(recent.map(run => run.id)).toEqual([2, 3])
  })

  it('builds actionable health notices for templates and latest runs', () => {
    const templates = [
      {
        id: 1,
        name: '空模板',
        description: '',
        variables: {},
        is_active: true,
        nodes: [],
        edges: [],
      },
      {
        id: 2,
        name: '停用模板',
        description: '',
        variables: {},
        is_active: false,
        nodes: [makeNode({ uuid: 'unsupported-1', node_type: 'unsupported' as any })],
        edges: [],
      },
    ]
    const latestRuns = buildLatestRunMap([
      makeRun({ id: 1, template: 2, status: 'failed', created_at: '2026-06-10T10:00:00Z' }),
    ])

    expect(buildFlowHealthNotices(templates, latestRuns).map(item => item.key)).toEqual([
      'empty-topology',
      'inactive-template',
      'unsupported-node',
      'latest-run-failed',
    ])
  })

  it('builds start inputs with typed variables, selected scope, and node overrides', () => {
    const inputs = buildStartInputs({
      scope: 'selected',
      selectedNodeUuids: ['script-1'],
      variables: [
        { key: 'env', value: 'prod' },
        { key: 'batch', value: '3' },
        { key: 'dry_run', value: 'false' },
        { key: 'extra', value: '{"region":"cn"}' },
      ],
      nodes: [makeNode({ uuid: 'script-1' }), makeNode({ uuid: 'file-1' })],
      nodeOverrides: {
        'script-1': '{"timeout":600}',
        'file-1': '{"ignored":true}',
      },
    })

    expect(inputs).toEqual({
      env: 'prod',
      batch: 3,
      dry_run: false,
      extra: { region: 'cn' },
      __execution_scope: 'selected',
      __selected_node_uuids: ['script-1'],
      __node_overrides: {
        'script-1': { timeout: 600 },
      },
    })
  })

  it('builds start inputs from standard flow variable definitions', () => {
    const definitions = normalizeFlowVariables({
      CheckHost: {
        name: '执行脚本机器',
        type: 'host_list',
        widget: 'host_list',
        default: [1, 2],
        required: true,
        show_on_start: true,
      },
      ReleaseVersion: {
        name: '发布版本',
        type: 'text',
        widget: 'input',
        default: 'v1.0.0',
        regex: '^v',
        show_on_start: true,
      },
      SecretToken: {
        name: '密钥',
        type: 'secret',
        widget: 'password',
        default: 'from-default',
        show_on_start: false,
      },
    })

    expect(flowVariableReference('CheckHost')).toBe('${CheckHost}')
    expect(flowVariableSelectOptions(definitions, 'host_list')).toEqual([
      { label: '执行脚本机器 (${CheckHost})', value: '${CheckHost}', key: 'CheckHost' },
    ])

    const inputs = buildStartInputs({
      scope: 'all',
      selectedNodeUuids: [],
      variableDefinitions: definitions,
      variableValues: {
        CheckHost: [3],
        ReleaseVersion: 'v2.0.0',
      },
      nodes: [],
      nodeOverrides: {},
    })

    expect(inputs).toEqual({
      CheckHost: [3],
      ReleaseVersion: 'v2.0.0',
      SecretToken: 'from-default',
      __execution_scope: 'all',
      __selected_node_uuids: [],
      __node_overrides: {},
    })
  })

  it('builds scheduled inputs from the complete flow variable definition set', () => {
    const definitions = normalizeFlowVariables({
      CheckHost: { type: 'host_list', default: [1], required: true },
      ReleaseVersion: { type: 'text', default: 'v1.0.0', required: true },
      HiddenToken: { type: 'secret', default: 'template-secret', show_on_start: false },
    })

    expect(buildScheduledInputs(definitions, {
      CheckHost: [2, 3],
      ReleaseVersion: 'v2.0.0',
    })).toEqual({
      CheckHost: [2, 3],
      ReleaseVersion: 'v2.0.0',
      HiddenToken: 'template-secret',
    })
  })
  it('allows full-scope starts without selected nodes but requires nodes for selected scope', () => {
    expect(canStartFlow('all', [])).toBe(true)
    expect(canStartFlow('selected', [])).toBe(false)
    expect(canStartFlow('selected', ['script-1'])).toBe(true)
  })

  it('allows skip actions only for failed or paused node runs', () => {
    expect(canSkipFlowNodeRun(makeNodeRun({ status: 'failed' }))).toBe(true)
    expect(canSkipFlowNodeRun(makeNodeRun({ status: 'paused' }))).toBe(true)
    expect(canSkipFlowNodeRun(makeNodeRun({ status: 'running' }))).toBe(false)
    expect(canSkipFlowNodeRun(makeNodeRun({ status: 'success' }))).toBe(false)
  })

  it('allows retry actions only for failed or paused node runs', () => {
    expect(canRetryFlowNodeRun(makeNodeRun({ status: 'failed' }))).toBe(true)
    expect(canRetryFlowNodeRun(makeNodeRun({ status: 'paused' }))).toBe(true)
    expect(canRetryFlowNodeRun(makeNodeRun({ status: 'running' }))).toBe(false)
    expect(canRetryFlowNodeRun(makeNodeRun({ status: 'success' }))).toBe(false)
  })

  it('allows manual confirmation only for paused manual node runs', () => {
    expect(canConfirmManualNodeRun(makeNodeRun({ node_type: 'manual', status: 'paused' }))).toBe(true)
    expect(canConfirmManualNodeRun(makeNodeRun({ node_type: 'manual', status: 'failed' }))).toBe(false)
    expect(canConfirmManualNodeRun(makeNodeRun({ node_type: 'script', status: 'paused' }))).toBe(false)
  })

  it('allows cancel actions only for active flow runs', () => {
    expect(canCancelFlowRun(makeRun({ status: 'pending' }))).toBe(true)
    expect(canCancelFlowRun(makeRun({ status: 'running' }))).toBe(true)
    expect(canCancelFlowRun(makeRun({ status: 'paused' }))).toBe(true)
    expect(canCancelFlowRun(makeRun({ status: 'failed' }))).toBe(false)
    expect(canCancelFlowRun(makeRun({ status: 'success' }))).toBe(false)
    expect(canCancelFlowRun(makeRun({ status: 'cancelled' }))).toBe(false)
  })

  it('summarizes condition node branch outputs for run detail', () => {
    const summary = summarizeConditionNodeRun(makeNodeRun({
      node_type: 'condition',
      outputs: {
        matched_count: 1,
        default_used: false,
        selected_node_uuids: ['prod-script'],
        selected_edges: [
          {
            target_uuid: 'prod-script',
            condition: { variable: 'inputs.env', operator: 'eq', value: 'prod' },
          },
        ],
      },
    }))

    expect(summary.hasDecision).toBe(true)
    expect(summary.defaultUsed).toBe(false)
    expect(summary.rows).toEqual([
      {
        targetUuid: 'prod-script',
        conditionText: 'inputs.env 等于 prod',
        isDefault: false,
      },
    ])
  })

  it('summarizes default and empty condition branch decisions', () => {
    const defaultSummary = summarizeConditionNodeRun(makeNodeRun({
      node_type: 'condition',
      outputs: {
        matched_count: 0,
        default_used: true,
        selected_node_uuids: ['fallback-script'],
        selected_edges: [{ target_uuid: 'fallback-script', condition: { default: true } }],
      },
    }))
    const emptySummary = summarizeConditionNodeRun(makeNodeRun({
      node_type: 'condition',
      outputs: {
        matched_count: 0,
        default_used: false,
        selected_node_uuids: [],
        selected_edges: [],
      },
    }))

    expect(defaultSummary.rows[0]).toEqual({
      targetUuid: 'fallback-script',
      conditionText: '默认分支',
      isDefault: true,
    })
    expect(emptySummary.hasDecision).toBe(false)
    expect(emptySummary.rows).toEqual([])
  })

  it('builds a chronological flow run event timeline', () => {
    const timeline = buildFlowRunTimeline(makeRun({
      id: 9,
      template_name: '发布流水线',
      status: 'success',
      created_at: '2026-06-10T09:00:00Z',
      started_at: '2026-06-10T09:00:05Z',
      finished_at: '2026-06-10T09:02:00Z',
      node_runs: [
        makeNodeRun({
          id: 1,
          node_name: '发布前检查',
          node_uuid: 'check',
          node_type: 'script',
          status: 'success',
          created_at: '2026-06-10T09:00:06Z',
          started_at: '2026-06-10T09:00:08Z',
          finished_at: '2026-06-10T09:00:20Z',
          execution_record_id: 101,
        }),
      ],
    }))

    expect(timeline.map(event => event.key)).toEqual([
      'flow-created-9',
      'flow-started-9',
      'node-start-1',
      'node-status-1',
      'flow-finished-9',
    ])
    expect(timeline[3]).toMatchObject({
      kind: 'node_status',
      title: '发布前检查 执行成功',
      description: '脚本执行 / 关联执行记录 #101',
      status: 'success',
    })
  })

  it('adds timeline events for manual confirmations and skipped nodes', () => {
    const timeline = buildFlowRunTimeline(makeRun({
      node_runs: [
        makeNodeRun({
          id: 10,
          node_name: '人工确认',
          node_uuid: 'manual-1',
          node_type: 'manual',
          status: 'success',
          started_at: '2026-06-10T09:00:00Z',
          finished_at: '2026-06-10T09:05:00Z',
          outputs: {
            confirmed_at: '2026-06-10T09:04:00Z',
            confirmed_by: 'admin',
            confirm_remark: 'checked',
          },
        }),
        makeNodeRun({
          id: 11,
          node_name: '可跳过检查',
          node_uuid: 'skip-1',
          status: 'success',
          started_at: '2026-06-10T09:06:00Z',
          finished_at: '2026-06-10T09:06:10Z',
          outputs: {
            skipped_at: '2026-06-10T09:06:05Z',
            skip_reason: 'manual skip',
          },
        }),
      ],
    }))

    expect(timeline.find(event => event.kind === 'manual_confirm')).toMatchObject({
      title: '人工确认 人工确认',
      description: 'admin / checked',
      status: 'success',
    })
    expect(timeline.find(event => event.kind === 'skip')).toMatchObject({
      title: '可跳过检查 已跳过',
      description: 'manual skip',
      status: 'success',
    })
  })

  it('builds persistent audit timeline events and merges them chronologically', () => {
    const auditLogs = [
      makeAuditLog({
        id: 20,
        action: 'confirm_flow_node',
        description: '确认人工节点: 人工确认',
        created_at: '2026-06-10T09:04:00Z',
        extra_data: {
          node_run_id: 10,
          node_uuid: 'manual-1',
          node_name: '人工确认',
          node_type: 'manual',
          previous_status: 'paused',
          new_status: 'success',
          remark: 'checked',
        },
      }),
    ]

    expect(buildAuditTimelineEvents(auditLogs)[0]).toMatchObject({
      key: 'audit-20',
      kind: 'audit',
      title: '确认节点 人工确认',
      description: '确认人工节点: 人工确认 / 备注: checked / 已暂停 -> 成功',
      status: 'success',
      nodeRunId: 10,
      nodeUuid: 'manual-1',
      nodeType: 'manual',
    })

    const timeline = buildFlowRunTimeline(makeRun({
      created_at: '2026-06-10T09:00:00Z',
      started_at: '2026-06-10T09:01:00Z',
      node_runs: [
        makeNodeRun({
          id: 10,
          node_name: '人工确认',
          node_uuid: 'manual-1',
          node_type: 'manual',
          status: 'paused',
          started_at: '2026-06-10T09:02:00Z',
        }),
      ],
    }), auditLogs)

    expect(timeline.map(event => event.key)).toContain('audit-20')
    expect(timeline.findIndex(event => event.key === 'audit-20')).toBeGreaterThan(
      timeline.findIndex(event => event.key === 'node-status-10'),
    )
  })

  it('adds timeline events for condition decisions and gateways', () => {
    const timeline = buildFlowRunTimeline(makeRun({
      node_runs: [
        makeNodeRun({
          id: 20,
          node_name: '环境判断',
          node_uuid: 'condition-1',
          node_type: 'condition',
          status: 'success',
          started_at: '2026-06-10T09:00:00Z',
          finished_at: '2026-06-10T09:00:01Z',
          outputs: {
            selected_edges: [
              { target_uuid: 'prod-script', condition: { variable: 'env', operator: 'eq', value: 'prod' } },
            ],
          },
        }),
        makeNodeRun({
          id: 21,
          node_name: '生产发布',
          node_uuid: 'prod-script',
          node_type: 'script',
          status: 'success',
          started_at: '2026-06-10T09:00:02Z',
          finished_at: '2026-06-10T09:00:03Z',
        }),
        makeNodeRun({
          id: 22,
          node_name: '并行网关',
          node_uuid: 'parallel-1',
          node_type: 'parallel',
          status: 'success',
          started_at: '2026-06-10T09:00:04Z',
          finished_at: '2026-06-10T09:00:05Z',
        }),
      ],
    }))

    expect(timeline.find(event => event.kind === 'condition')).toMatchObject({
      title: '环境判断 分支决策',
      description: '命中 生产发布',
    })
    expect(timeline.find(event => event.kind === 'gateway')).toMatchObject({
      title: '并行网关 网关通过',
      description: '并行网关',
      status: 'success',
    })
  })

  it('adds timeline context for subprocess child flow runs', () => {
    const timeline = buildFlowRunTimeline(makeRun({
      node_runs: [
        makeNodeRun({
          id: 30,
          node_name: '发布子流程',
          node_uuid: 'sub-1',
          node_type: 'sub_process',
          status: 'running',
          started_at: '2026-06-10T09:00:00Z',
          outputs: {
            child_flow_run_id: 88,
            child_flow_status: 'running',
          },
        }),
      ],
    }))

    expect(timeline.find(event => event.key === 'node-status-30')).toMatchObject({
      kind: 'node_status',
      title: '发布子流程 执行中',
      description: '子流程 / 子流程实例 #88 / 执行中',
      status: 'running',
    })
  })

  it('builds run topology with executed and not-run template nodes', () => {
    const template = {
      id: 1,
      name: '发布流水线',
      variables: {},
      is_active: true,
      nodes: [
        makeNode({ uuid: 'start', name: '开始', node_type: 'script' }),
        makeNode({ uuid: 'prod', name: '生产发布', node_type: 'job_plan' }),
        makeNode({ uuid: 'stage', name: '预发发布', node_type: 'job_plan' }),
      ],
      edges: [
        { source_uuid: 'start', target_uuid: 'prod' },
        { source_uuid: 'start', target_uuid: 'stage' },
      ],
    }
    const run = makeRun({
      node_runs: [
        makeNodeRun({ node_uuid: 'start', node_name: '开始', status: 'success' }),
        makeNodeRun({ node_uuid: 'prod', node_name: '生产发布', status: 'running' }),
      ],
    })

    const topology = buildRunTopology(template, run)

    expect(topology.executedCount).toBe(2)
    expect(topology.notRunCount).toBe(1)
    expect(topology.nodes.map(node => [node.uuid, node.status])).toEqual([
      ['start', 'success'],
      ['prod', 'running'],
      ['stage', 'not_run'],
    ])
    expect(topology.edges).toHaveLength(2)
  })

  it('marks condition topology edges as selected, default, or unselected', () => {
    const conditionRun = makeNodeRun({
      node_uuid: 'branch',
      node_type: 'condition',
      outputs: {
        default_used: false,
        selected_node_uuids: ['prod'],
        selected_edges: [
          {
            source_uuid: 'branch',
            target_uuid: 'prod',
            condition: { variable: 'inputs.env', operator: 'eq', value: 'prod' },
          },
        ],
      },
    })
    const template = {
      id: 1,
      name: '条件流水线',
      variables: {},
      is_active: true,
      nodes: [
        makeNode({ uuid: 'branch', name: '按环境分支', node_type: 'condition' }),
        makeNode({ uuid: 'prod', name: '生产', node_type: 'script' }),
        makeNode({ uuid: 'fallback', name: '兜底', node_type: 'script' }),
      ],
      edges: [
        { source_uuid: 'branch', target_uuid: 'prod', condition: { variable: 'inputs.env', operator: 'eq', value: 'prod' } },
        { source_uuid: 'branch', target_uuid: 'fallback', condition: { default: true } },
      ],
    }
    const topology = buildRunTopology(template, makeRun({ node_runs: [conditionRun] }))

    expect(isConditionEdgeSelected({ target_uuid: 'prod' }, conditionRun)).toBe(true)
    expect(isConditionEdgeSelected({ target_uuid: 'fallback' }, conditionRun)).toBe(false)
    expect(topology.edges.map(edge => [edge.targetUuid, edge.state, edge.conditionText])).toEqual([
      ['prod', 'selected', 'inputs.env 等于 prod'],
      ['fallback', 'unselected', '默认分支'],
    ])
    expect(topology.selectedConditionEdgeCount).toBe(1)
  })

  it('marks selected default condition topology edge distinctly', () => {
    const template = {
      id: 1,
      name: '默认分支流水线',
      variables: {},
      is_active: true,
      nodes: [
        makeNode({ uuid: 'branch', name: '按环境分支', node_type: 'condition' }),
        makeNode({ uuid: 'fallback', name: '兜底', node_type: 'script' }),
      ],
      edges: [
        { source_uuid: 'branch', target_uuid: 'fallback', condition: { default: true } },
      ],
    }
    const run = makeRun({
      node_runs: [
        makeNodeRun({
          node_uuid: 'branch',
          node_type: 'condition',
          outputs: {
            default_used: true,
            selected_node_uuids: ['fallback'],
            selected_edges: [{ source_uuid: 'branch', target_uuid: 'fallback', condition: { default: true } }],
          },
        }),
      ],
    })

    expect(buildRunTopology(template, run).edges[0].state).toBe('default')
    expect(buildRunNodeStatusMap(run.node_runs).get('branch')?.node_type).toBe('condition')
  })

  it('filters templates by their actual latest run status instead of any historical run status', () => {
    const templates = [
      {
        id: 1,
        name: '发布流水线',
        description: '',
        variables: {},
        is_active: true,
        nodes: [],
        edges: [],
      },
      {
        id: 2,
        name: '备份流水线',
        description: '',
        variables: {},
        is_active: true,
        nodes: [],
        edges: [],
      },
    ]
    const latestRuns = buildLatestRunMap([
      makeRun({ id: 1, template: 1, status: 'failed', created_at: '2026-06-10T09:00:00Z' }),
      makeRun({ id: 2, template: 1, status: 'success', created_at: '2026-06-10T10:00:00Z' }),
      makeRun({ id: 3, template: 2, status: 'failed', created_at: '2026-06-10T10:30:00Z' }),
    ])

    expect(filterFlowTemplates(templates, { search: '', status: '', runStatus: 'failed' }, latestRuns).map(item => item.id)).toEqual([2])
  })

  it('summarizes node config and checks required fields consistently', () => {
    const script = makeNode({
      node_type: 'script',
      config: { script_type: 'shell', script_content: 'hostname', target_host_ids: '${CheckHost}', timeout: 60 },
    })
    const file = makeNode({
      node_type: 'file_transfer',
      config: {
        target_host_ids: '${CheckHost}',
        file_sources: [{ download_url: '${PackageUrl}', remote_path: '${DeployPath}' }],
        bandwidth_limit: 10,
      },
    })
    const plan = makeNode({
      node_type: 'job_plan',
      config: { execution_plan_id: 42, execution_mode: 'rolling' },
    })
    const condition = makeNode({
      node_type: 'condition',
      config: { description: '按环境分支' },
    })
    const parallel = makeNode({
      node_type: 'parallel',
      config: { description: '并行检查' },
    })
    const join = makeNode({
      node_type: 'join',
      config: { description: '检查汇聚' },
    })

    expect(summarizeFlowNode(script)).toBe('shell / 主机变量 ${CheckHost} / 60s')
    expect(summarizeFlowNode(file)).toBe('主机变量 ${CheckHost} / 1 个文件源 / 限速 10 MB/s')
    expect(summarizeFlowNode(plan)).toBe('方案 #42 / 滚动')
    expect(summarizeFlowNode(condition)).toBe('按环境分支')
    expect(summarizeFlowNode(parallel)).toBe('并行检查')
    expect(summarizeFlowNode(join)).toBe('检查汇聚')
    expect(summarizeFlowNode(makeNode({
      node_type: 'sub_process',
      config: { template_id: 8, inherit_inputs: false },
    }))).toBe('模板 #8 / 独立输入')
    expect(isNodeReady(script)).toBe(true)
    expect(isNodeReady(makeNode({ node_type: 'script', config: { script_content: '' } }))).toBe(false)
    expect(isNodeReady(file)).toBe(true)
    expect(isNodeReady(plan)).toBe(true)
    expect(isNodeReady(condition)).toBe(true)
  })

  it('builds readable node config rows for template detail inspectors', () => {
    expect(flowNodeConfigDisplayRows(makeNode({
      node_type: 'script',
      config: {
        script_type: 'shell',
        target_host_ids: '${CheckHost}',
        timeout: 60,
        script_content: 'echo ${ReleaseVersion}',
      },
    }))).toEqual([
      { label: '脚本类型', value: 'shell' },
      { label: '目标主机', value: '主机变量 ${CheckHost}' },
      { label: '超时时间', value: '60s' },
      { label: '脚本内容', value: 'echo ${ReleaseVersion}', multiline: true },
    ])

    expect(flowNodeConfigDisplayRows(makeNode({
      node_type: 'job_plan',
      config: {
        execution_plan_id: 301,
        execution_mode: 'rolling',
        execution_parameter_bindings: {
          env: '${ReleaseEnv}',
          hosts: '${CheckHost}',
        },
      },
    }))).toEqual([
      { label: '执行方案', value: '#301' },
      { label: '执行模式', value: '滚动' },
      { label: '变量映射', value: 'env -> ${ReleaseEnv}\nhosts -> ${CheckHost}', multiline: true },
    ])
  })

  it('summarizes legacy host id arrays by count instead of leaking meaningless ids', () => {
    const script = makeNode({
      node_type: 'script',
      config: { script_type: 'shell', script_content: 'hostname', target_host_ids: [1, 2], timeout: 60 },
    })
    const file = makeNode({
      node_type: 'file_transfer',
      config: {
        target_host_ids: [3],
        file_sources: [{ download_url: '${PackageUrl}', remote_path: '${DeployPath}' }],
        bandwidth_limit: 10,
      },
    })

    expect(summarizeFlowNode(script)).toBe('shell / 已选 2 台主机 / 60s')
    expect(summarizeFlowNode(file)).toBe('已选 1 台主机 / 1 个文件源 / 限速 10 MB/s')
    expect(summarizeFlowNode(script)).not.toContain('1,2')
  })

  it('summarizes legacy host id strings by count instead of leaking raw ids', () => {
    const csvHosts = makeNode({
      node_type: 'script',
      config: { script_type: 'shell', script_content: 'hostname', target_host_ids: '1,2', timeout: 60 },
    })
    const jsonHosts = makeNode({
      node_type: 'file_transfer',
      config: {
        target_host_ids: '[3,4]',
        file_sources: [{ download_url: '${PackageUrl}', remote_path: '${DeployPath}' }],
        bandwidth_limit: 10,
      },
    })

    expect(summarizeFlowNode(csvHosts)).toBe('shell / 已选 2 台主机 / 60s')
    expect(summarizeFlowNode(jsonHosts)).toBe('已选 2 台主机 / 1 个文件源 / 限速 10 MB/s')
    expect(summarizeFlowNode(csvHosts)).not.toContain('1,2')
    expect(summarizeFlowNode(jsonHosts)).not.toContain('[3,4]')
  })

  it('formats flow run input data for operators without leaking raw host ids', () => {
    const display = sanitizeFlowRunDisplayData({
      host_ids: [1, 3],
      remote_path: '/data/releases/current/app.tar.gz',
      execution_plan_id: 301,
      nested: {
        target_host_ids: '4,5',
      },
      variable_host: '${CheckHost}',
    })

    expect(display).toEqual({
      目标主机: '已选 2 台主机',
      远端路径: '/data/releases/current/app.tar.gz',
      作业执行方案: 301,
      nested: {
        目标主机: '已选 2 台主机',
      },
      variable_host: '${CheckHost}',
    })

    const json = formatFlowRunDisplayJson({ host_ids: [1, 3] })
    expect(json).toContain('"目标主机": "已选 2 台主机"')
    expect(json).not.toContain('host_ids')
    expect(json).not.toContain('[\n    1')
  })

  it('builds operator-facing display rows for run inputs and outputs', () => {
    expect(flowRunDisplayRows({
      host_ids: [1, 3],
      remote_path: '/data/releases/current/app.tar.gz',
      nested: { transferred: 1 },
    })).toEqual([
      { key: '目标主机', value: '已选 2 台主机', multiline: false },
      { key: '远端路径', value: '/data/releases/current/app.tar.gz', multiline: false },
      { key: 'nested', value: '{\n  "transferred": 1\n}', multiline: true },
    ])
  })

  it('evaluates graph topology and rejects cyclic connections', () => {
    const nodes = [
      makeNode({ uuid: 'a', config: { script_content: 'echo a', target_host_ids: '${CheckHost}' } }),
      makeNode({ uuid: 'b', config: { script_content: 'echo b', target_host_ids: '${CheckHost}' } }),
      makeNode({ uuid: 'c', config: { script_content: '', target_host_ids: '${CheckHost}' } }),
    ]
    const edges: FlowEdge[] = [
      { source_uuid: 'a', target_uuid: 'b' },
      { source_uuid: 'b', target_uuid: 'c' },
    ]

    expect(evaluateFlowGraph(nodes, edges)).toEqual({
      missingRequired: 1,
      disconnected: 0,
      startNodes: 1,
      terminalNodes: 1,
      invalidEdges: 0,
      issues: [
        expect.objectContaining({ code: 'missing-required', nodeUuid: 'c', severity: 'error' }),
      ],
    })
    expect(createsCycle(edges, 'c', 'a')).toBe(true)
    expect(createsCycle(edges, 'a', 'c')).toBe(false)
  })

  it('reports edges that point to nodes missing from the current graph', () => {
    const nodes = [
      makeNode({ uuid: 'a', config: { script_content: 'echo a', target_host_ids: '${CheckHost}' } }),
      makeNode({ uuid: 'b', config: { script_content: 'echo b', target_host_ids: '${CheckHost}' } }),
    ]
    const edges: FlowEdge[] = [
      { source_uuid: 'a', target_uuid: 'b' },
      { source_uuid: 'b', target_uuid: 'missing' },
    ]

    expect(evaluateFlowGraph(nodes, edges).invalidEdges).toBe(1)
    expect(evaluateFlowGraph(nodes, edges).issues).toEqual([
      expect.objectContaining({ code: 'invalid-edge', severity: 'error' }),
    ])
  })

  it('reports condition, parallel, join, and cycle topology issues', () => {
    const condition = makeNode({ uuid: 'condition', name: '条件', node_type: 'condition' })
    const prod = makeNode({ uuid: 'prod', name: '生产', config: { script_content: 'echo prod', target_host_ids: '${CheckHost}' } })
    const fallback = makeNode({ uuid: 'fallback', name: '默认', config: { script_content: 'echo fallback', target_host_ids: '${CheckHost}' } })
    const parallel = makeNode({ uuid: 'parallel', name: '并行', node_type: 'parallel' })
    const join = makeNode({ uuid: 'join', name: '汇聚', node_type: 'join' })
    const edges: FlowEdge[] = [
      { source_uuid: 'condition', target_uuid: 'prod', condition: {} },
      { source_uuid: 'condition', target_uuid: 'fallback', condition: { default: true } },
      { source_uuid: 'prod', target_uuid: 'parallel' },
      { source_uuid: 'parallel', target_uuid: 'join' },
      { source_uuid: 'join', target_uuid: 'condition' },
    ]

    const issueCodes = evaluateFlowGraph([condition, prod, fallback, parallel, join], edges).issues.map(issue => issue.code)

    expect(issueCodes).toContain('condition-missing-expression')
    expect(issueCodes).toContain('parallel-branch-count')
    expect(issueCodes).toContain('join-incoming-count')
    expect(issueCodes).toContain('cycle')
  })

  it('reports multiple default condition branches', () => {
    const branch = makeNode({ uuid: 'branch', name: '条件', node_type: 'condition' })
    const left = makeNode({ uuid: 'left', config: { script_content: 'echo left', target_host_ids: '${CheckHost}' } })
    const right = makeNode({ uuid: 'right', config: { script_content: 'echo right', target_host_ids: '${CheckHost}' } })
    const validation = evaluateFlowGraph(
      [branch, left, right],
      [
        { source_uuid: 'branch', target_uuid: 'left', condition: { default: true } },
        { source_uuid: 'branch', target_uuid: 'right', condition: { default: true } },
      ],
    )

    expect(validation.issues).toContainEqual(expect.objectContaining({ code: 'condition-many-defaults' }))
  })

  it('identifies only node types supported by the current editor', () => {
    expect(isSupportedFlowNodeType('script')).toBe(true)
    expect(isSupportedFlowNodeType('file_transfer')).toBe(true)
    expect(isSupportedFlowNodeType('job_plan')).toBe(true)
    expect(isSupportedFlowNodeType('manual')).toBe(true)
    expect(isSupportedFlowNodeType('condition')).toBe(true)
    expect(isSupportedFlowNodeType('parallel')).toBe(true)
    expect(isSupportedFlowNodeType('join')).toBe(true)
    expect(isSupportedFlowNodeType('sub_process')).toBe(true)
  })

  it('summarizes edge conditions for branch labels', () => {
    expect(summarizeEdgeCondition({ default: true })).toBe('默认分支')
    expect(summarizeEdgeCondition({ variable: 'inputs.env', operator: 'eq', value: 'prod' })).toBe('inputs.env 等于 prod')
    expect(summarizeEdgeCondition({ variable: 'outputs.check.success_count', operator: 'gt', value: 0 })).toBe('outputs.check.success_count 大于 0')
    expect(summarizeEdgeCondition({ variable: 'dry_run', operator: 'truthy' })).toBe('dry_run 为真')
  })

  it('normalizes and serializes editable node config without leaking UI-only text fields', () => {
    const normalized = normalizeFlowNode(makeNode({
      node_type: 'job_plan',
      config: { execution_parameter_bindings: { env: '${ReleaseEnv}' } },
    }))
    expect(normalized.config.failure_policy).toBe('pause')
    expect(normalized.config.execution_parameter_bindings).toEqual({ env: '${ReleaseEnv}' })

    const serialized = serializeFlowNode(makeNode({
      node_type: 'job_plan',
      config: {
        execution_plan_id: 1,
        execution_parameter_bindings: { env: '${ReleaseEnv}' },
        execution_parameters_text: '{"env":"stage"}',
        execution_parameters: { env: 'stage' },
      },
    }))
    expect(serialized.config.execution_parameter_bindings).toEqual({ env: '${ReleaseEnv}' })
    expect(serialized.config.execution_parameters).toBeUndefined()
    expect(serialized.config.execution_parameters_text).toBeUndefined()

    const subProcess = serializeFlowNode(makeNode({
      node_type: 'sub_process',
      config: { template_id: 2, inputs_text: '{"env":"prod"}' },
    }))
    expect(subProcess.config.inputs).toEqual({ env: 'prod' })
    expect(validateFlowNodeConfigJson(subProcess).valid).toBe(true)
    expect(validateFlowNodeConfigJson(makeNode({
      node_type: 'sub_process',
      config: { template_id: 2, inputs_text: '[' },
    }))).toEqual(expect.objectContaining({
      valid: false,
      field: 'inputs_text',
    }))
    expect(subProcess.config.inputs_text).toBeUndefined()
  })

  it('hydrates template topology from dedicated node and edge results when detail omits them', () => {
    const fallbackNodes = [
      makeNode({ uuid: 'script-1', name: '脚本检查', config: { script_content: 'hostname', target_host_ids: '${CheckHost}' } }),
      makeNode({ uuid: 'plan-1', name: '执行方案', node_type: 'job_plan', config: { execution_plan_id: 301 } }),
    ]
    const fallbackEdges: FlowEdge[] = [{ source_uuid: 'script-1', target_uuid: 'plan-1' }]
    const templateWithoutTopology: FlowTemplate = {
      id: 801,
      name: '发布流水线',
      description: '',
      variables: {},
      is_active: true,
      nodes: [],
      edges: [],
    }

    expect(resolveFlowTemplateTopology(templateWithoutTopology, fallbackNodes, fallbackEdges)).toEqual({
      nodes: fallbackNodes,
      edges: fallbackEdges,
    })

    const templateWithTopology: FlowTemplate = {
      ...templateWithoutTopology,
      nodes: [makeNode({ uuid: 'detail-node', name: '详情节点' })],
      edges: [{ source_uuid: 'detail-node', target_uuid: 'detail-node' }],
    }

    expect(resolveFlowTemplateTopology(templateWithTopology, fallbackNodes, fallbackEdges)).toEqual({
      nodes: templateWithTopology.nodes,
      edges: templateWithTopology.edges,
    })
  })

  it('drops legacy job plan execution parameter JSON in favor of variable bindings', () => {
    const serialized = serializeFlowNode(makeNode({
      node_type: 'job_plan',
      config: {
        execution_plan_id: 1,
        execution_parameter_bindings: { hosts: '${CheckHost}' },
        execution_parameters_text: '{bad json',
        execution_parameters: { hosts: [1] },
      },
    }))

    expect(serialized.config.execution_parameter_bindings).toEqual({ hosts: '${CheckHost}' })
    expect(serialized.config.execution_parameters_text).toBeUndefined()
    expect(serialized.config.execution_parameters).toBeUndefined()
  })

  it('parses loose form values for start variables', () => {
    expect(parseLooseValue('true')).toBe(true)
    expect(parseLooseValue('12')).toBe(12)
    expect(parseLooseValue('{"a":1}')).toEqual({ a: 1 })
    expect(parseLooseValue('prod')).toBe('prod')
  })
})
