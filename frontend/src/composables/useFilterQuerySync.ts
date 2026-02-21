import { watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

type QueryValue = string | number | boolean | string[] | number[] | undefined | null

export const parseNumberQuery = (value: unknown): number | undefined => {
  if (value === undefined || value === null || value === '') return undefined
  const raw = Array.isArray(value) ? value[0] : value
  const parsed = Number(raw)
  return Number.isFinite(parsed) ? parsed : undefined
}

export const parseBooleanQuery = (value: unknown): boolean | undefined => {
  if (value === undefined || value === null || value === '') return undefined
  const raw = String(Array.isArray(value) ? value[0] : value).toLowerCase()
  if (['1', 'true', 'yes', 'y'].includes(raw)) return true
  if (['0', 'false', 'no', 'n'].includes(raw)) return false
  return undefined
}

export const parseStringArrayQuery = (value: unknown): string[] => {
  if (value === undefined || value === null || value === '') return []
  if (Array.isArray(value)) {
    return value
      .flatMap(item => String(item).split(','))
      .map(item => item.trim())
      .filter(Boolean)
  }
  return String(value)
    .split(',')
    .map(item => item.trim())
    .filter(Boolean)
}

export const toBooleanQuery = (value?: boolean, includeFalse = false): string | undefined => {
  if (value === undefined || value === null) return undefined
  if (value === false && !includeFalse) return undefined
  return value ? '1' : '0'
}

export interface FilterFieldConfig<T extends Record<string, any>> {
  key: keyof T
  queryKey?: string
  toQuery?: (value: any, form: T) => QueryValue
  fromQuery?: (value: unknown, form: T) => any
}

interface UseFilterQuerySyncOptions<T extends Record<string, any>> {
  searchForm: T
  pagination?: { current: number; pageSize: number }
  ordering?: { value: string }
  fields: FilterFieldConfig<T>[]
}

export const useFilterQuerySync = <T extends Record<string, any>>(
  options: UseFilterQuerySyncOptions<T>
) => {
  const route = useRoute()
  const router = useRouter()

  const applyQuery = (query: Record<string, unknown>) => {
    options.fields.forEach(field => {
      const queryKey = field.queryKey || String(field.key)
      if (!(queryKey in query)) return
      const rawValue = query[queryKey]
      const nextValue = field.fromQuery
        ? field.fromQuery(rawValue, options.searchForm)
        : rawValue

      if (nextValue !== undefined) {
        ;(options.searchForm as any)[field.key] = nextValue
      }
    })

    if (options.pagination) {
      const page = parseNumberQuery(query.page)
      const pageSize = parseNumberQuery(query.page_size)
      if (page && page > 0) options.pagination.current = page
      if (pageSize && pageSize > 0) options.pagination.pageSize = pageSize
    }

    if (options.ordering) {
      const rawOrdering = query.ordering
      options.ordering.value = rawOrdering
        ? String(Array.isArray(rawOrdering) ? rawOrdering[0] : rawOrdering)
        : ''
    }
  }

  const buildQuery = () => {
    const nextQuery = { ...route.query } as Record<string, any>

    options.fields.forEach(field => {
      const queryKey = field.queryKey || String(field.key)
      const rawValue = (options.searchForm as any)[field.key]
      const encoded = field.toQuery ? field.toQuery(rawValue, options.searchForm) : rawValue

      if (Array.isArray(encoded)) {
        const normalized = encoded
          .map(item => String(item).trim())
          .filter(Boolean)
        if (normalized.length) {
          nextQuery[queryKey] = normalized.join(',')
        } else {
          delete nextQuery[queryKey]
        }
        return
      }

      if (encoded === undefined || encoded === null || encoded === '') {
        delete nextQuery[queryKey]
        return
      }

      if (typeof encoded === 'boolean') {
        nextQuery[queryKey] = encoded ? '1' : '0'
        return
      }

      nextQuery[queryKey] = String(encoded)
    })

    if (options.pagination) {
      nextQuery.page = String(options.pagination.current)
      nextQuery.page_size = String(options.pagination.pageSize)
    }

    if (options.ordering) {
      if (options.ordering.value) {
        nextQuery.ordering = options.ordering.value
      } else {
        delete nextQuery.ordering
      }
    }

    return nextQuery
  }

  const syncToQuery = () => {
    const query = buildQuery()
    router.replace({ query })
  }

  const initFromQuery = () => {
    applyQuery(route.query as Record<string, unknown>)
  }

  watch(
    () => route.query,
    query => {
      applyQuery(query as Record<string, unknown>)
    }
  )

  return {
    initFromQuery,
    syncToQuery
  }
}
