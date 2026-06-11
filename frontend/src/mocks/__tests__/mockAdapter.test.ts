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
