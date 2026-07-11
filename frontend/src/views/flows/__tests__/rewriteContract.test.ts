import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const testDir = dirname(fileURLToPath(import.meta.url))
const flowsDir = resolve(testDir, '..')
const source = (relativePath: string) => readFileSync(resolve(flowsDir, relativePath), 'utf8')

describe('rewritten flows frontend contract', () => {
  it('adds a readonly template detail route beside edit and run detail pages', () => {
    const routerSource = readFileSync(resolve(testDir, '../../../router/index.ts'), 'utf8')
    expect(routerSource).toContain("path: '/flows/:id/detail'")
    expect(routerSource).toContain("component: () => import('@/views/flows/detail.vue')")
    expect(routerSource).toContain("name: 'FlowDetail'")
  })

  it('uses a standard template table on the flows index without a separate run tab', () => {
    const indexSource = source('index.vue')
    expect(indexSource).toContain('flow-standard-table')
    expect(indexSource).toContain('openTemplateDetail')
    expect(indexSource).toContain("router.push(`/flows/${record.id}/detail`)")
    expect(indexSource).toContain("{ title: '最近执行'")
    expect(indexSource).not.toContain('v-model:active-key="activeTab"')
    expect(indexSource).not.toContain('key="runs" title="执行记录"')
    expect(indexSource).not.toContain('runColumns')
    expect(indexSource).not.toContain('filteredRuns')
    expect(indexSource).not.toContain('pipeline-template-card')
    expect(indexSource).not.toContain('agent_server_id')
  })

  it('keeps editing as plugin rail plus canvas plus drawer inspector', () => {
    const editorSource = source('editor.vue')
    const workbenchSource = source('components/FlowTemplateWorkbench.vue')
    expect(editorSource).toContain('<FlowTemplateWorkbench mode="edit"')
    expect(workbenchSource).toContain('flow-editor-shell')
    expect(workbenchSource).toContain('class="flow-plugin-rail"')
    expect(workbenchSource).toContain('class="flow-canvas-stage"')
    expect(workbenchSource).toContain('<a-drawer')
    expect(workbenchSource).toContain('v-model:visible="propertyDrawerVisible"')
    expect(workbenchSource).toContain('<FlowVariableEditor v-if="!isReadonly" v-model="form.variables"')
    expect(workbenchSource).toContain('<ScriptEditorWithValidation')
    expect(workbenchSource).toContain('execution_parameter_bindings')
    expect(workbenchSource).not.toContain('状态预览')
    expect(workbenchSource).not.toContain('agent_server_id')
  })

  it('provides a readonly detail page through the shared template workbench', () => {
    const detailSource = source('detail.vue')
    const workbenchSource = source('components/FlowTemplateWorkbench.vue')
    expect(detailSource).toContain('<FlowTemplateWorkbench mode="readonly"')
    expect(detailSource).not.toContain('<VueFlow')
    expect(detailSource).not.toContain('readonly-rail-content')
    expect(detailSource).not.toContain('查看配置')
    expect(workbenchSource).toContain("mode?: 'edit' | 'readonly'")
    expect(workbenchSource).toContain('flow-editor-shell')
    expect(workbenchSource).toContain('class="flow-plugin-rail"')
    expect(workbenchSource).toContain('class="flow-canvas-stage"')
    expect(workbenchSource).toContain('<VueFlow')
    expect(workbenchSource).toContain(':nodes-draggable="!isReadonly"')
    expect(workbenchSource).toContain(':nodes-connectable="!isReadonly"')
    expect(workbenchSource).toContain('FlowVariableReadOnlyPanel')
    expect(workbenchSource).toContain('flowNodeConfigDisplayRows')
    expect(detailSource).not.toContain('readonly-topology-stage')
    expect(detailSource).not.toContain('readonly-flow-workspace')
    expect(detailSource).not.toContain('draggable="true"')
    expect(detailSource).not.toContain('agent_server_id')
  })

  it('shows run detail as readonly topology, run path and sanitized data views', () => {
    const runDetailSource = source('run-detail.vue')
    expect(runDetailSource).toContain('standard-run-detail')
    expect(runDetailSource).toContain('readonly-run-topology')
    expect(runDetailSource).toContain('run-path-table')
    expect(runDetailSource).toContain('FlowRunDataView')
    expect(runDetailSource).toContain('formatHostDisplay')
    expect(runDetailSource).not.toContain('host_id')
    expect(runDetailSource).not.toContain('agent_server_id')
  })
})
