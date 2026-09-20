import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const testDir = dirname(fileURLToPath(import.meta.url))

describe('flow pagination contract', () => {
  it('requests paginated templates and latest runs instead of loading every run', () => {
    const source = readFileSync(resolve(testDir, '../../views/flows/index.vue'), 'utf8')

    expect(source).toContain('page: templatePagination.current')
    expect(source).toContain('page_size: templatePagination.pageSize')
    expect(source).toContain('run_status: filters.runStatus')
    expect(source).toContain("template_ids: templateIds.join(',')")
    expect(source).toContain('page_size: templateIds.length')
    expect(source).toContain('latest_per_template: 1')
    expect(source).not.toContain('flowApi.getRuns()')
  })

  it('keeps the task center on the paginated run API', () => {
    const source = readFileSync(resolve(testDir, '../../views/flows/tasks.vue'), 'utf8')

    expect(source).toContain('page: pagination.current')
    expect(source).toContain('page_size: pagination.pageSize')
    expect(source).not.toContain('flowApi.getRuns()')
    expect(source).toContain('@page-change="handlePageChange"')
  })

  it('does not use an array fallback for paginated workflow templates', () => {
    const source = readFileSync(resolve(testDir, '../../views/flows/components/FlowTemplateWorkbench.vue'), 'utf8')

    expect(source).toContain('normalizePaginatedList<FlowTemplate>')
    expect(source).not.toContain('normalizeList<FlowTemplate>(templateListResult.value)')
  })

  it('limits Vitest discovery to source tests and keeps e2e outside the unit suite', () => {
    const config = readFileSync(resolve(testDir, '../../../vite.config.ts'), 'utf8')

    expect(config).toContain("include: ['src/**/*.{test,spec}.*']")
    expect(config).toContain("exclude: ['e2e/**",)
  })
})
