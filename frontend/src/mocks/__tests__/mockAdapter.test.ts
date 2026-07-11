import type { AxiosAdapter, InternalAxiosRequestConfig } from 'axios'
import { describe, expect, it, vi } from 'vitest'
import { createMockAxiosAdapter, type MockRoute } from '../mockAdapter'
import { mockRoutes } from '../routes'

const makeConfig = (url: string, method = 'get'): InternalAxiosRequestConfig => ({
  url,
  method,
  headers: {} as any,
})

describe('mock route page contracts', () => {
  const adapter = createMockAxiosAdapter({
    enabled: true,
    strict: true,
    latencyMs: 0,
    fallbackAdapter: vi.fn<AxiosAdapter>(),
    routes: mockRoutes,
  })

  it('returns host group tree nodes with visible counts', async () => {
    const response = await adapter(makeConfig('/hosts/groups/tree/'))
    const [root] = response.data.content

    expect(root).toMatchObject({
      name: '生产环境',
      host_count: expect.any(Number),
      online_count: expect.any(Number),
      offline_count: expect.any(Number),
    })
  })

  it('returns execution records with list-page display fields', async () => {
    const response = await adapter(makeConfig('/executor/execution-records/'))
    const [record] = response.data.content.results

    expect(record).toMatchObject({
      name: expect.any(String),
      execution_type: expect.stringMatching(/^[a-z_]+$/),
      status: expect.stringMatching(/^[a-z_]+$/),
      executed_by_name: expect.any(String),
      created_at: expect.any(String),
    })
  })

  it('returns audit logs with table display fields', async () => {
    const response = await adapter(makeConfig('/permissions/audit-logs/'))
    const [log] = response.data.content.results

    expect(log).toMatchObject({
      user_name: expect.any(String),
      action: expect.any(String),
      action_display: expect.any(String),
      description: expect.any(String),
      ip_address: expect.any(String),
      success: expect.any(Boolean),
    })
  })

  it('returns flow node plugins for the pipeline editor', async () => {
    const response = await adapter(makeConfig('/flows/nodes/plugins/'))

    expect(response.status).toBe(200)
    expect(response.data.content.map((plugin: { type: string }) => plugin.type)).toEqual([
      'script',
      'file_transfer',
      'job_plan',
      'manual',
      'condition',
      'parallel',
      'join',
      'sub_process',
    ])
    expect(response.data.content[0]).toMatchObject({
      name: expect.any(String),
      category: expect.any(String),
      description: expect.any(String),
      config_schema: expect.any(Object),
    })
  })

  it('supports flow template copy and run operation mock routes', async () => {
    const copied = await adapter({
      ...makeConfig('/flows/templates/801/copy/', 'post'),
      data: JSON.stringify({ name: '生产发布前置检查流程 副本' }),
    })
    expect(copied.status).toBe(200)
    expect(copied.data.content).toMatchObject({
      name: expect.stringContaining('生产发布前置检查流程 副本'),
      is_active: false,
      nodes: expect.any(Array),
      edges: expect.any(Array),
    })

    const logs = await adapter(makeConfig('/flows/runs/8801/operation_logs/'))
    expect(logs.status).toBe(200)
    expect(logs.data.content[0]).toMatchObject({
      action: expect.any(String),
      extra_data: expect.objectContaining({ flow_run_id: 8801 }),
    })

    const cancel = await adapter({
      ...makeConfig('/flows/runs/8801/cancel/', 'post'),
      data: JSON.stringify({}),
    })
    expect(cancel.data.content.status).toBe('cancelled')

    const retry = await adapter({
      ...makeConfig('/flows/runs/8802/retry_node/', 'post'),
      data: JSON.stringify({ node_run_id: 8821 }),
    })
    expect(retry.data.content.node_runs[0].status).toBe('success')
  })

  it('starts mock flow runs with selected scope, condition outputs, and audit logs', async () => {
    const created = await adapter({
      ...makeConfig('/flows/templates/', 'post'),
      data: JSON.stringify({
        name: 'Mock 条件流程',
        nodes: [
          { uuid: 'branch', name: '按环境分支', node_type: 'condition', config: {} },
          { uuid: 'prod', name: '生产确认', node_type: 'manual', config: { instructions: 'check prod' } },
          { uuid: 'fallback', name: '回退检查', node_type: 'script', config: { script_content: 'echo fallback' } },
        ],
        edges: [
          { source_uuid: 'branch', target_uuid: 'prod', condition: { variable: 'inputs.env', operator: 'eq', value: 'prod' } },
          { source_uuid: 'branch', target_uuid: 'fallback', condition: { default: true } },
        ],
      }),
    })
    const templateId = created.data.content.id

    const started = await adapter({
      ...makeConfig(`/flows/templates/${templateId}/start/`, 'post'),
      data: JSON.stringify({        inputs: {
          env: 'prod',
          __execution_scope: 'selected',
          __selected_node_uuids: ['branch', 'prod'],
        },
      }),
    })

    expect(started.data.content.status).toBe('paused')
    expect(started.data.content.node_runs.map((nodeRun: any) => nodeRun.node_uuid)).toEqual(['branch', 'prod'])
    expect(started.data.content.node_runs[0]).toMatchObject({
      node_uuid: 'branch',
      status: 'success',
      outputs: expect.objectContaining({
        matched_count: 1,
        selected_node_uuids: ['prod'],
      }),
    })
    expect(started.data.content.node_runs[1]).toMatchObject({
      node_uuid: 'prod',
      status: 'paused',
    })

    const logs = await adapter(makeConfig(`/flows/runs/${started.data.content.id}/operation_logs/`))
    expect(logs.data.content[0]).toMatchObject({
      action: 'start_flow',
      extra_data: expect.objectContaining({ new_status: 'paused' }),
    })
  })

  it('advances mock condition and manual runs through reachable branches', async () => {
    const created = await adapter({
      ...makeConfig('/flows/templates/', 'post'),
      data: JSON.stringify({
        name: 'Mock 人工分支继续流程',
        nodes: [
          { uuid: 'branch', name: '按环境分支', node_type: 'condition', config: {} },
          { uuid: 'prod', name: '生产确认', node_type: 'manual', config: { instructions: 'check prod' } },
          { uuid: 'deploy', name: '部署检查', node_type: 'script', config: { script_content: 'echo deploy' } },
          { uuid: 'fallback', name: '回退检查', node_type: 'script', config: { script_content: 'echo fallback' } },
        ],
        edges: [
          { source_uuid: 'branch', target_uuid: 'prod', condition: { variable: 'inputs.env', operator: 'eq', value: 'prod' } },
          { source_uuid: 'branch', target_uuid: 'fallback', condition: { default: true } },
          { source_uuid: 'prod', target_uuid: 'deploy', condition: {} },
        ],
      }),
    })
    const templateId = created.data.content.id

    const started = await adapter({
      ...makeConfig(`/flows/templates/${templateId}/start/`, 'post'),
      data: JSON.stringify({ inputs: { env: 'prod' } }),
    })

    expect(started.data.content.status).toBe('paused')
    expect(started.data.content.node_runs.map((nodeRun: any) => nodeRun.node_uuid)).toEqual(['branch', 'prod'])
    expect(started.data.content.node_runs[0].outputs.selected_node_uuids).toEqual(['prod'])

    const manualRun = started.data.content.node_runs.find((nodeRun: any) => nodeRun.node_uuid === 'prod')
    const confirmed = await adapter({
      ...makeConfig(`/flows/runs/${started.data.content.id}/confirm_manual_node/`, 'post'),
      data: JSON.stringify({ node_run_id: manualRun.id, remark: 'ok' }),
    })

    expect(confirmed.data.content.status).toBe('success')
    expect(confirmed.data.content.node_runs.map((nodeRun: any) => nodeRun.node_uuid)).toEqual(['branch', 'prod', 'deploy'])
    expect(confirmed.data.content.node_runs).not.toEqual(
      expect.arrayContaining([expect.objectContaining({ node_uuid: 'fallback' })]),
    )
    expect(confirmed.data.content.node_runs.at(-1)).toMatchObject({
      node_uuid: 'deploy',
      status: 'success',
    })
  })

  it('matches implicit truthy condition branches like the backend runner', async () => {
    const created = await adapter({
      ...makeConfig('/flows/templates/', 'post'),
      data: JSON.stringify({
        name: 'Mock truthy 条件流程',
        nodes: [
          { uuid: 'branch', name: '按变量分支', node_type: 'condition', config: {} },
          { uuid: 'truthy', name: '命中分支', node_type: 'script', config: { script_content: 'echo truthy' } },
          { uuid: 'fallback', name: '默认分支', node_type: 'script', config: { script_content: 'echo fallback' } },
        ],
        edges: [
          { source_uuid: 'branch', target_uuid: 'truthy', condition: { variable: 'inputs.env' } },
          { source_uuid: 'branch', target_uuid: 'fallback', condition: { default: true } },
        ],
      }),
    })

    const started = await adapter({
      ...makeConfig(`/flows/templates/${created.data.content.id}/start/`, 'post'),
      data: JSON.stringify({ inputs: { env: 'prod' } }),
    })

    expect(started.data.content.status).toBe('success')
    expect(started.data.content.node_runs.map((nodeRun: any) => nodeRun.node_uuid)).toEqual(['branch', 'truthy'])
    expect(started.data.content.node_runs[0].outputs).toMatchObject({
      matched_count: 1,
      selected_node_uuids: ['truthy'],
    })
  })

  it('completes mock subprocess runs and continues parent downstream nodes', async () => {
    const child = await adapter({
      ...makeConfig('/flows/templates/', 'post'),
      data: JSON.stringify({
        name: 'Mock 子流程',
        nodes: [
          { uuid: 'child-script', name: '子流程脚本', node_type: 'script', config: { script_content: 'echo child' } },
        ],
        edges: [],
      }),
    })
    const parent = await adapter({
      ...makeConfig('/flows/templates/', 'post'),
      data: JSON.stringify({
        name: 'Mock 父流程',
        nodes: [
          { uuid: 'sub', name: '执行子流程', node_type: 'sub_process', config: { template_id: child.data.content.id, inputs: { child_only: 'yes' } } },
          { uuid: 'after', name: '父流程后置', node_type: 'script', config: { script_content: 'echo after' } },
        ],
        edges: [
          { source_uuid: 'sub', target_uuid: 'after', condition: {} },
        ],
      }),
    })

    const started = await adapter({
      ...makeConfig(`/flows/templates/${parent.data.content.id}/start/`, 'post'),
      data: JSON.stringify({ inputs: { env: 'prod' } }),
    })

    const subRun = started.data.content.node_runs.find((nodeRun: any) => nodeRun.node_uuid === 'sub')
    expect(started.data.content.status).toBe('success')
    expect(started.data.content.node_runs.map((nodeRun: any) => nodeRun.node_uuid)).toEqual(['sub', 'after'])
    expect(subRun).toMatchObject({
      status: 'success',
      outputs: expect.objectContaining({
        sub_process: true,
        child_status: 'success',
        child_flow_run_id: expect.any(Number),
      }),
    })

    const childRun = await adapter(makeConfig(`/flows/runs/${subRun.outputs.child_flow_run_id}/`))
    expect(childRun.data.content).toMatchObject({
      template: child.data.content.id,
      status: 'success',
    })
  })

  it('rejects invalid mock manual confirmations like the backend', async () => {
    const created = await adapter({
      ...makeConfig('/flows/templates/', 'post'),
      data: JSON.stringify({
        name: 'Mock 非人工确认流程',
        nodes: [
          { uuid: 'script', name: '脚本', node_type: 'script', config: { script_content: 'echo ok' } },
        ],
        edges: [],
      }),
    })
    const started = await adapter({
      ...makeConfig(`/flows/templates/${created.data.content.id}/start/`, 'post'),
      data: JSON.stringify({ inputs: {} }),
    })

    const confirmed = await adapter({
      ...makeConfig(`/flows/runs/${started.data.content.id}/confirm_manual_node/`, 'post'),
      data: JSON.stringify({ node_run_id: started.data.content.node_runs[0].id }),
    })

    expect(confirmed.status).toBe(400)
    expect(confirmed.data).toMatchObject({
      success: false,
      content: expect.objectContaining({ node_run_id: expect.any(String) }),
    })
  })
})

describe('createMockAxiosAdapter', () => {
  it('delegates to the fallback adapter when mock mode is disabled', async () => {
    const fallback = vi.fn<AxiosAdapter>(async (config) => ({
      data: { ok: true },
      status: 200,
      statusText: 'OK',
      headers: {},
      config,
    }))

    const adapter = createMockAxiosAdapter({
      enabled: false,
      latencyMs: 0,
      fallbackAdapter: fallback,
      routes: [
        {
          method: 'get',
          pattern: '/dashboard/overview/',
          handler: () => ({ total: 1 }),
        },
      ],
    })

    const response = await adapter(makeConfig('/dashboard/overview/'))

    expect(fallback).toHaveBeenCalledOnce()
    expect(response.data).toEqual({ ok: true })
  })

  it('wraps matched mock content like the real backend response envelope', async () => {
    const fallback = vi.fn<AxiosAdapter>()
    const routes: MockRoute[] = [
      {
        method: 'get',
        pattern: '/dashboard/overview/',
        handler: () => ({ templates: 12, plans: 8 }),
      },
    ]
    const adapter = createMockAxiosAdapter({
      enabled: true,
      latencyMs: 0,
      fallbackAdapter: fallback,
      routes,
    })

    const response = await adapter(makeConfig('/dashboard/overview/'))

    expect(fallback).not.toHaveBeenCalled()
    expect(response.status).toBe(200)
    expect(response.data).toEqual({
      success: true,
      message: 'mock',
      content: { templates: 12, plans: 8 },
    })
  })

  it('matches dynamic route params and query params before calling handlers', async () => {
    const fallback = vi.fn<AxiosAdapter>()
    const adapter = createMockAxiosAdapter({
      enabled: true,
      latencyMs: 0,
      fallbackAdapter: fallback,
      routes: [
        {
          method: 'post',
          pattern: '/agents/:id/control/',
          handler: ({ params, query, data }) => ({
            id: params.id,
            reason: query.reason,
            action: data.action,
          }),
        },
      ],
    })

    const response = await adapter({
      ...makeConfig('/agents/42/control/?reason=manual', 'post'),
      data: JSON.stringify({ action: 'restart' }),
    })

    expect(response.data.content).toEqual({
      id: '42',
      reason: 'manual',
      action: 'restart',
    })
  })

  it('delegates unknown routes to the fallback adapter', async () => {
    const fallback = vi.fn<AxiosAdapter>(async (config) => ({
      data: { passthrough: true },
      status: 200,
      statusText: 'OK',
      headers: {},
      config,
    }))
    const adapter = createMockAxiosAdapter({
      enabled: true,
      latencyMs: 0,
      fallbackAdapter: fallback,
      routes: [],
    })

    const response = await adapter(makeConfig('/not-covered/'))

    expect(fallback).toHaveBeenCalledOnce()
    expect(response.data).toEqual({ passthrough: true })
  })

  it('returns an explicit mock miss response for unknown routes in strict mode', async () => {
    const fallback = vi.fn<AxiosAdapter>()
    const adapter = createMockAxiosAdapter({
      enabled: true,
      strict: true,
      latencyMs: 0,
      fallbackAdapter: fallback,
      routes: [],
    })

    const response = await adapter(makeConfig('/not-covered/'))

    expect(fallback).not.toHaveBeenCalled()
    expect(response.status).toBe(501)
    expect(response.data).toEqual({
      success: false,
      message: 'Mock route not implemented: GET /not-covered/',
      content: null,
    })
  })

  it('prefers static routes over dynamic routes even when dynamic routes are declared first', async () => {
    const adapter = createMockAxiosAdapter({
      enabled: true,
      latencyMs: 0,
      fallbackAdapter: vi.fn<AxiosAdapter>(),
      routes: [
        {
          method: 'get',
          pattern: '/agents/:id/',
          handler: ({ params }) => ({ kind: 'agent-detail', id: params.id }),
        },
        {
          method: 'get',
          pattern: '/agents/agent_servers/',
          handler: () => ({ kind: 'agent-servers' }),
        },
      ],
    })

    const response = await adapter(makeConfig('/agents/agent_servers/'))

    expect(response.data.content).toEqual({ kind: 'agent-servers' })
  })
})
