import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const testDir = dirname(fileURLToPath(import.meta.url))
const editorSource = readFileSync(resolve(testDir, '../editor.vue'), 'utf8')
const workbenchSource = readFileSync(resolve(testDir, '../components/FlowTemplateWorkbench.vue'), 'utf8')
const variableEditorSource = readFileSync(resolve(testDir, '../components/FlowVariableEditor.vue'), 'utf8')

describe('flow editor layout', () => {
  it('keeps node properties in a drawer instead of a third workbench column', () => {
    expect(editorSource).toContain('<FlowTemplateWorkbench mode="edit"')
    expect(workbenchSource).toContain('<a-drawer')
    expect(workbenchSource).toContain('v-model:visible="propertyDrawerVisible"')
    expect(workbenchSource).toContain('@cancel="closePropertyDrawer"')
    expect(workbenchSource).toContain("const FLOW_PROPERTY_DRAWER_WIDTH = '760px'")
    expect(workbenchSource).not.toContain('<aside v-if="selectedNode" class="property-panel">')
    expect(workbenchSource).not.toContain('editor-workbench--no-selection')
    expect(workbenchSource).toMatch(/grid-template-columns:\s*220px\s+minmax\(0,\s*1fr\);/)
  })

  it('keeps script node configuration close to the job step editor pattern', () => {
    expect(workbenchSource).toContain('<a-radio-group v-model="selectedNode.config.script_type"')
    expect(workbenchSource).toContain('@click="insertSelectedScriptExample"')
    expect(workbenchSource).toContain(':height="560"')
    expect(workbenchSource).toContain('class="node-config-hint"')
  })

  it('does not expose editable runtime status preview in template editing', () => {
    expect(workbenchSource).not.toContain('label="状态预览"')
    expect(workbenchSource).not.toContain('selectedPreviewStatus')
    expect(workbenchSource).not.toContain('previewOverrides')
    expect(workbenchSource).not.toContain('previewModeOptions')
  })

  it('configures job plan nodes through plan variables instead of raw JSON first', () => {
    expect(workbenchSource).toContain('@change="handleExecutionPlanChange"')
    expect(workbenchSource).toContain('selectedExecutionPlanVariables')
    expect(workbenchSource).toContain('class="execution-parameter-list"')
    expect(workbenchSource).toContain('@input="value => setExecutionParameterBinding(item.key, value)"')
    expect(workbenchSource).toContain('insertExecutionParameterVariable')
    expect(workbenchSource).toContain('execution_parameter_bindings')
    expect(workbenchSource).not.toContain('label="执行参数 JSON"')
  })

  it('uses the standard flow variable editor and variable bindings for node targets', () => {
    expect(workbenchSource).toContain('<FlowVariableEditor v-if="!isReadonly" v-model="form.variables"')
    expect(workbenchSource).toContain('hostVariableOptions')
    expect(workbenchSource).toContain('placeholder="例如 ${CheckHost}"')
    expect(workbenchSource).toContain('bindSelectedNodeHostVariable')
    expect(workbenchSource).toContain('insertFileSourceVariable')
    expect(workbenchSource).not.toContain('placeholder="绑定 host_list 全局变量"')
    expect(workbenchSource).not.toContain('title="流水线变量 JSON"')
  })
  it('uses a textual global-variable default for host-list values', () => {
    expect(variableEditorSource).not.toContain('HostSelector')
    expect(variableEditorSource).toContain('每行一个 IP 或主机名（可选）')
    expect(variableEditorSource).not.toContain('默认值；主机列表用逗号分隔 ID')
  })
  it('keeps a newly added global-variable draft row until the user supplies its key', () => {
    const addVariableSource = variableEditorSource.match(/const addVariable = \(\) => \{([\s\S]*?)\n\}/)?.[1] || ''
    expect(addVariableSource).toContain('draft.push')
    expect(addVariableSource).not.toContain('emitChange()')
  })
})