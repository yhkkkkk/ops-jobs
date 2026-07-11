import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const testDir = dirname(fileURLToPath(import.meta.url))

describe('flow variable read only panel', () => {
  it('renders variables through a read-only form and a taller json view', () => {
    const source = readFileSync(resolve(testDir, '../components/FlowVariableReadOnlyPanel.vue'), 'utf8')

    expect(source).toContain('title="只读表单"')
    expect(source).toContain('title="JSON"')
    expect(source).toContain('normalizeFlowVariables')
    expect(source).toContain('max-height: 520px')
    expect(source).toContain('class="variable-readonly-table"')
    expect(source).not.toContain('variable-readonly-row__meta')
  })

  it('is used by the shared workbench and run detail views', () => {
    const workbench = readFileSync(resolve(testDir, '../components/FlowTemplateWorkbench.vue'), 'utf8')
    const runDetail = readFileSync(resolve(testDir, '../run-detail.vue'), 'utf8')

    expect(workbench).toContain('<FlowVariableReadOnlyPanel')
    expect(runDetail).toContain('<FlowVariableReadOnlyPanel')
  })
})
