import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const testDir = dirname(fileURLToPath(import.meta.url))
const source = readFileSync(resolve(testDir, '../run-detail.vue'), 'utf8')
const dataViewSource = readFileSync(resolve(testDir, '../components/FlowRunDataView.vue'), 'utf8')
const variablePanelSource = readFileSync(resolve(testDir, '../components/FlowVariableReadOnlyPanel.vue'), 'utf8')

describe('flow run detail presentation', () => {
  it('renders run data through an operator-facing formatter instead of raw json ids', () => {
    expect(source).toContain('<FlowRunDataView')
    expect(dataViewSource).toContain('flowRunDisplayRows')
    expect(dataViewSource).toContain('formatFlowRunDisplayJson')
    expect(source).not.toContain('formatJson(nodeRun.inputs)')
    expect(source).not.toContain('<pre>{{ formatRunJson(nodeRun.inputs) }}</pre>')
  })

  it('does not expose raw node uuids in timeline or topology labels', () => {
    expect(source).toContain('event.nodeName')
    expect(source).toContain('topologyNodeMeta(node)')
    expect(source).not.toContain('<span v-if="event.nodeUuid">{{ event.nodeUuid }}</span>')
    expect(source).not.toContain('<em>{{ node.uuid }}</em>')
    expect(source).not.toContain('`${nodeRun.node_name}（${uuid}）`')
  })

  it('uses operator-facing labels instead of raw run and execution record ids', () => {
    expect(source).not.toContain('执行 #${run.id}')
    expect(source).not.toContain('关联执行记录 #${nodeRun.execution_record_id}')
    expect(source).not.toContain('子流程 #${childFlowRunId(nodeRun)}')
    expect(source).toContain('查看执行记录')
    expect(source).toContain('查看子流程任务')
  })
  it('uses compact detail panels for the run inspection page', () => {
    expect(source).toContain('<DetailPanel title="执行拓扑" description="基于任务创建时固化的流程定义展示本次执行覆盖的节点和条件分支。" dense>')
    expect(source).toContain('<DetailPanel title="节点运行路径" description="按节点运行顺序展示状态、耗时、输出和关联执行记录。" dense>')
    expect(source).toContain('class="node-data-grid"')
    expect(source).toContain('definition_snapshot')
    expect(source).toContain('topologyTemplate')
  })

  it('prioritizes topology and node path before operation timeline like a task inspection page', () => {
    expect(source.indexOf('title="执行拓扑"')).toBeLessThan(source.indexOf('title="节点运行路径"'))
    expect(source.indexOf('title="节点运行路径"')).toBeLessThan(source.indexOf('title="操作时间线"'))
  })
  it('renders top-level host variables without exposing internal host ids or control inputs', () => {
    expect(source).toContain(':variables="topologyTemplate?.variables || {}"')
    expect(variablePanelSource).toContain('已解析 ${value.length} 台主机')
    expect(variablePanelSource).toContain("!key.startsWith('__')")
    expect(variablePanelSource).not.toContain('return value.length ? value.join')
  })
})