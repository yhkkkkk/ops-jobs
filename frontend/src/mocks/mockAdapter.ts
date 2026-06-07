import type {
  AxiosAdapter,
  AxiosResponse,
  InternalAxiosRequestConfig,
  Method,
} from 'axios'

export interface MockRouteContext {
  config: InternalAxiosRequestConfig
  data: any
  params: Record<string, string>
  query: Record<string, any>
}

export interface MockRoute {
  method: Method | 'any'
  pattern: string
  handler: (context: MockRouteContext) => any | Promise<any>
}

interface CreateMockAxiosAdapterOptions {
  enabled: boolean
  strict?: boolean
  latencyMs: number
  fallbackAdapter: AxiosAdapter
  routes: MockRoute[]
}

interface CompiledMockRoute extends MockRoute {
  keys: string[]
  regexp: RegExp
  score: number
}

const API_PREFIX_RE = /^\/api(?=\/|$)/

const escapeRegExp = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

const compilePattern = (pattern: string) => {
  const keys: string[] = []
  const source = pattern
    .replace(/\/+$/, '')
    .split('/')
    .map((part) => {
      if (part.startsWith(':')) {
        keys.push(part.slice(1))
        return '([^/]+)'
      }
      return escapeRegExp(part)
    })
    .join('/')

  return {
    keys,
    regexp: new RegExp(`^${source}/?$`),
  }
}

const compileRoutes = (routes: MockRoute[]): CompiledMockRoute[] => {
  return routes.map((route) => ({
    ...route,
    ...compilePattern(route.pattern),
    score: route.pattern
      .split('/')
      .filter(Boolean)
      .reduce((score, part) => score + (part.startsWith(':') ? 1 : 10), 0),
  })).sort((a, b) => b.score - a.score || b.pattern.length - a.pattern.length)
}

const normalizePath = (config: InternalAxiosRequestConfig) => {
  const rawUrl = config.url || '/'
  const url = new URL(rawUrl, 'http://mock.local')
  const pathname = url.pathname.replace(API_PREFIX_RE, '') || '/'
  const query = Object.fromEntries(url.searchParams.entries())

  return {
    pathname,
    query: {
      ...query,
      ...(config.params || {}),
    },
  }
}

const parseRequestData = (data: any) => {
  if (!data || typeof data !== 'string') return data

  try {
    return JSON.parse(data)
  } catch {
    return data
  }
}

const delay = (ms: number) => {
  if (ms <= 0) return Promise.resolve()
  return new Promise((resolve) => setTimeout(resolve, ms))
}

const findRoute = (
  routes: CompiledMockRoute[],
  method: string,
  pathname: string
) => {
  for (const route of routes) {
    if (route.method !== 'any' && route.method.toLowerCase() !== method) continue

    const match = pathname.match(route.regexp)
    if (!match) continue

    const params = route.keys.reduce<Record<string, string>>((acc, key, index) => {
      acc[key] = decodeURIComponent(match[index + 1])
      return acc
    }, {})

    return { route, params }
  }

  return null
}

export const createMockAxiosAdapter = ({
  enabled,
  strict = false,
  latencyMs,
  fallbackAdapter,
  routes,
}: CreateMockAxiosAdapterOptions): AxiosAdapter => {
  const compiledRoutes = compileRoutes(routes)

  return async (config: InternalAxiosRequestConfig): Promise<AxiosResponse> => {
    if (!enabled) {
      return fallbackAdapter(config)
    }

    const method = (config.method || 'get').toLowerCase()
    const { pathname, query } = normalizePath(config)
    const match = findRoute(compiledRoutes, method, pathname)

    if (!match && !strict) {
      return fallbackAdapter(config)
    }

    if (!match) {
      const label = `${method.toUpperCase()} ${pathname.endsWith('/') ? pathname : `${pathname}/`}`

      return {
        data: {
          success: false,
          message: `Mock route not implemented: ${label}`,
          content: null,
        },
        status: 501,
        statusText: 'Not Implemented',
        headers: {
          'x-mock-api': 'miss',
        },
        config,
        request: { mocked: true, missed: true },
      }
    }

    await delay(latencyMs)

    const content = await match.route.handler({
      config,
      data: parseRequestData(config.data),
      params: match.params,
      query,
    })

    return {
      data: {
        success: true,
        message: 'mock',
        content,
      },
      status: 200,
      statusText: 'OK',
      headers: {
        'x-mock-api': 'true',
      },
      config,
      request: { mocked: true },
    }
  }
}
