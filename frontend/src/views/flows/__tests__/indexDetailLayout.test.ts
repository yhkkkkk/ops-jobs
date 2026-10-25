import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const testDir = dirname(fileURLToPath(import.meta.url))
const indexSource = readFileSync(resolve(testDir, '../index.vue'), 'utf8')
const workbenchSource = readFileSync(resolve(testDir, '../components/FlowTemplateWorkbench.vue'), 'utf8')

describe('flow list and detail presentation', () => {
  it('renders latest runs as readable operational summaries instead of cramped id/time fragments', () => {
    expect(indexSource).toContain("class: 'pipeline-run-summary'")
    expect(indexSource).toContain('latestRunTitle')
    expect(indexSource).toContain('latestRunTrigger')
    expect(indexSource).toContain('latestRunActor')
    expect(indexSource).toContain('latestRunTime')
    expect(indexSource).not.toContain('<a-link')
    expect(indexSource).not.toContain('latestRunMeta')
  })

  it('keeps the flow list table as default and offers an optional SOPS-like card view', () => {
    expect(indexSource).not.toContain('class="pipeline-template-list"')
    expect(indexSource).toContain("listViewMode = ref<'table' | 'card'>('table')")
    expect(indexSource).toContain('v-if="listViewMode === \'table\'"')
    expect(indexSource).toContain('class="pipeline-template-card"')
    expect(indexSource).toContain('onClick: () => openDetailDrawer(row)')
    expect(indexSource).toContain("title: '状态'")
    expect(indexSource).toContain("title: '拓扑'")
    expect(indexSource).toContain("title: '最近执行'")
    expect(indexSource).toContain("title: '负责人/更新'")
    expect(indexSource).toContain("title: '操作'")
    expect(indexSource).toContain('<n-data-table')
    expect(indexSource).not.toContain('key="runs" title="执行记录"')
    expect(indexSource).not.toContain('runColumns')
    expect(indexSource).not.toContain('<a-button type="text" size="small" @click="router.push(`/flows/${record.id}/edit`)">')
    expect(indexSource).not.toContain('.pipeline-table { display: none; }')
    expect(indexSource).not.toContain('overflow-x: hidden !important;')
  })

  it('shows template details through the same workbench used by editing', () => {
    expect(workbenchSource).toContain("mode?: 'edit' | 'readonly'")
    expect(workbenchSource).toContain('class="flow-editor-workbench"')
    expect(workbenchSource).toContain('class="flow-plugin-rail"')
    expect(workbenchSource).toContain('class="flow-canvas-stage"')
    expect(workbenchSource).toContain(':nodes-draggable="!isReadonly"')
    expect(workbenchSource).toContain(':nodes-connectable="!isReadonly"')
    expect(workbenchSource).not.toContain('readonly-flow-workbench')
    expect(workbenchSource).not.toContain('readonly-rail-content')
  })

  it('shows selected node configuration and variable bindings instead of raw json in template detail', () => {
    expect(workbenchSource).toContain('selectedNode')
    expect(workbenchSource).toContain('selectedNodeConfigRows')
    expect(workbenchSource).toContain('flowNodeConfigDisplayRows')
    expect(workbenchSource).toContain('节点配置')
    expect(workbenchSource).toContain('<FlowSettingPanel')
    expect(workbenchSource).not.toContain('<pre>{{ selectedNode')
    expect(workbenchSource).not.toContain('key="raw"')
  })

  it('does not fall back to raw node uuids for missing topology endpoints', () => {
    expect(workbenchSource).toContain('未知节点')
    expect(workbenchSource).not.toContain('return node?.name || uuid || \'-\'')
  })
})
