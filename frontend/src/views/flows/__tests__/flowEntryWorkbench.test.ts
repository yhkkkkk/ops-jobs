import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const testDir = dirname(fileURLToPath(import.meta.url))
const source = (file: string) => readFileSync(resolve(testDir, `../${file}`), 'utf8')

describe('flow entry workbench', () => {
  it('uses the same compact operations-table hierarchy for templates and tasks', () => {
    const templates = source('index.vue')
    const tasks = source('tasks.vue')

    for (const page of [templates, tasks]) {
      expect(page).toContain('<PageHeader')
      expect(page).toContain('<DataToolbar')
      expect(page).toContain('<DetailPanel')
      expect(page).toContain('<a-table')
    }
    expect(templates).toContain('流水线任务')
    expect(tasks).toContain('流程模板')
  })

  it('keeps task list rows business-facing instead of displaying raw run ids', () => {
    const tasks = source('tasks.vue')

    expect(tasks).not.toContain('任务 #${record.id}')
    expect(tasks).not.toContain('#{{ record.id }}')
    expect(tasks).toContain('执行任务')
  })
})