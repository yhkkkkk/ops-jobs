import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const listPages = [
  '../accounts/index.vue',
  '../script-templates/index.vue',
  '../job-templates/index.vue',
  '../execution-plans/index.vue',
  '../scheduled-tasks/index.vue'
]

describe('job platform list page shell', () => {
  it('uses the shared app components for core list pages instead of the legacy card shell', () => {
    for (const page of listPages) {
      const source = readFileSync(resolve(__dirname, page), 'utf8')

      expect(source).toContain('<PageHeader')
      expect(source).toContain('<DataToolbar')
      expect(source).toContain('<DetailPanel')
      expect(source).not.toContain('legacy-app-page')
      expect(source).not.toContain('<div class="page-header">')
      expect(source).not.toContain('<a-card class="mb-4">')
    }
  })

  it('keeps list page eyebrow copy localized', () => {
    const forbiddenEnglish = [
      'Resource inventory',
      'Execution records',
      'Audit trail',
      'Server accounts',
      'Script templates',
      'Execution plans',
      'Scheduled tasks'
    ]

    const pages = [
      '../hosts/index.vue',
      '../execution-records/index.vue',
      '../audit-logs/index.vue',
      ...listPages
    ]

    for (const page of pages) {
      const source = readFileSync(resolve(__dirname, page), 'utf8')
      for (const text of forbiddenEnglish) {
        expect(source).not.toContain(text)
      }
    }
  })

  it('does not force horizontal table scrolling on core list pages', () => {
    const pages = [
      '../hosts/index.vue',
      '../execution-records/index.vue',
      '../audit-logs/index.vue',
      ...listPages
    ]

    for (const page of pages) {
      const source = readFileSync(resolve(__dirname, page), 'utf8')
      expect(source).not.toMatch(/:scroll="\{\s*x:/)
      expect(source).not.toMatch(/fixed:\s*['"]right['"]/)
    }
  })

  it('keeps template pages responsive instead of fixed-width grids and columns', () => {
    const templatePages = [
      '../script-templates/index.vue',
      '../job-templates/index.vue'
    ]

    for (const page of templatePages) {
      const source = readFileSync(resolve(__dirname, page), 'utf8')
      const columnsBlock = source.match(/const columns = \[[\s\S]*?\n\]/)?.[0] ?? ''

      expect(source).not.toContain('<a-row :gutter="16">')
      expect(source).toContain('class="app-filter-grid')
      expect(source).toContain('class="template-data-table"')
      expect(columnsBlock).not.toContain("title: '描述'")
    }
  })

  it('keeps dense operational tables compact instead of spreading actions and duplicate name columns', () => {
    const scriptTemplates = readFileSync(resolve(__dirname, '../script-templates/index.vue'), 'utf8')
    const jobTemplates = readFileSync(resolve(__dirname, '../job-templates/index.vue'), 'utf8')
    const scheduledTasks = readFileSync(resolve(__dirname, '../scheduled-tasks/index.vue'), 'utf8')
    const scheduledColumns = scheduledTasks.match(/const columns = \[[\s\S]*?\n\]/)?.[0] ?? ''

    expect(scriptTemplates).toContain('class="template-description"')
    expect(scriptTemplates).toContain('class="template-primary-action"')
    expect(jobTemplates).toContain('class="template-description"')
    expect(jobTemplates).not.toContain('@click="handleEdit(record)"\n              v-permission')

    expect(scheduledTasks).toContain('slotName: \'task\'')
    expect(scheduledTasks).toContain('class="task-name-cell"')
    expect(scheduledTasks).toContain('class="scheduled-primary-action"')
    expect(scheduledTasks).toContain('class="scheduled-more-action"')
    expect(scheduledColumns).not.toContain("title: '执行方案'")
    expect(scheduledColumns).not.toContain("title: '模板名称'")
    expect(scheduledColumns).not.toContain('width: 96')
  })
})
