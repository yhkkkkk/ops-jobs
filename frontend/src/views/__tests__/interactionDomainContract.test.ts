// @vitest-environment happy-dom

import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { defineComponent, nextTick } from 'vue'
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import FlowNodeLibraryPanel, { type FlowNodePluginOption } from '../flows/components/FlowNodeLibraryPanel.vue'
import HostGroupTreeNode from '../hosts/components/HostGroupTreeNode.vue'

const viewsDir = resolve(__dirname, '..')
const readView = (relativePath: string) => readFileSync(resolve(viewsDir, relativePath), 'utf8')

const ButtonStub = defineComponent({
  emits: ['click'],
  template: '<button type="button" @click="$emit(\'click\', $event)"><slot /><slot name="icon" /></button>',
})

const hostGroup = {
  id: 1,
  name: '生产环境',
  total_host_count: 3,
  created_at: '2026-09-19T00:00:00Z',
  updated_at: '2026-09-19T00:00:00Z',
  children: [{
    id: 2,
    name: 'Web 集群',
    total_host_count: 2,
    created_at: '2026-09-19T00:00:00Z',
    updated_at: '2026-09-19T00:00:00Z',
    children: [],
  }],
}

const mountHostGroup = (readOnly = false) => mount(HostGroupTreeNode, {
  props: {
    group: hostGroup,
    level: 0,
    selectedGroupId: null,
    expandedGroups: [1],
    readOnly,
  },
  global: {
    stubs: {
      AButton: ButtonStub,
      ADropdown: true,
      ADoption: true,
      IconDown: true,
      IconFolder: true,
      IconMore: true,
      IconEdit: true,
      IconFolderAdd: true,
      IconWifi: true,
      IconDelete: true,
    },
  },
})

const plugins: FlowNodePluginOption[] = [
  { type: 'script', name: '脚本执行', description: '执行脚本', category: '作业原子', risk: '中', icon: 'span' },
  { type: 'file_transfer', name: '文件传输', description: '传输文件', category: '作业原子', risk: '中', icon: 'span' },
  { type: 'job_plan', name: '作业执行方案', description: '执行方案', category: '作业编排', risk: '高', icon: 'span' },
  { type: 'manual', name: '人工确认', description: '等待确认', category: '控制节点', risk: '低', icon: 'span' },
  { type: 'condition', name: '条件分支', description: '条件路由', category: '控制节点', risk: '低', icon: 'span' },
  { type: 'parallel', name: '并行网关', description: '并行启动', category: '控制节点', risk: '低', icon: 'span' },
  { type: 'join', name: '汇聚网关', description: '等待汇聚', category: '控制节点', risk: '低', icon: 'span' },
  { type: 'sub_process', name: '子流程', description: '执行子流程', category: '控制节点', risk: '低', icon: 'span' },
]

describe('interaction and domain boundary contracts', () => {
  it('opens the host-group context menu and emits the same four actions as the dropdown', async () => {
    const wrapper = mountHostGroup()
    const actionEvents = ['edit-group', 'add-subgroup', 'test-connection', 'delete-group']

    for (const [index, eventName] of actionEvents.entries()) {
      await wrapper.get('.group-item').trigger('contextmenu', { clientX: 24, clientY: 36 })
      const items = wrapper.findAll('[role="menuitem"]')
      expect(items).toHaveLength(4)
      await items[index].trigger('click')
      expect(wrapper.emitted(eventName)?.at(-1)).toEqual([hostGroup])
    }

    wrapper.unmount()
  })

  it('does not open write actions in read-only mode', async () => {
    const wrapper = mountHostGroup(true)

    await wrapper.get('.group-item').trigger('contextmenu')
    expect(wrapper.find('[role="menu"]').exists()).toBe(false)
    expect(wrapper.findAll('[role="menuitem"]')).toHaveLength(0)

    wrapper.unmount()
  })

  it('keeps only one context menu open while switching between recursive nodes', async () => {
    const wrapper = mountHostGroup()
    const groupItems = wrapper.findAll('.group-item')

    expect(groupItems).toHaveLength(2)
    await groupItems[0].trigger('contextmenu')
    expect(wrapper.findAll('[role="menu"]')).toHaveLength(1)

    await groupItems[1].trigger('contextmenu')
    await nextTick()
    expect(wrapper.findAll('[role="menu"]')).toHaveLength(1)
    expect(wrapper.find('[role="menu"]')?.element.parentElement?.textContent).toContain('Web 集群')

    wrapper.unmount()
  })

  it('renders the eight node types in their actual execution and control groups', () => {
    const wrapper = mount(FlowNodeLibraryPanel, {
      props: { plugins, scenarios: [] },
      global: { stubs: { AInput: true, AEmpty: true } },
    })
    const groups = wrapper.findAll('.plugin-group')

    expect(groups).toHaveLength(2)
    expect(groups[0].get('h3').text()).toBe('执行动作')
    expect(groups[0].findAll('.plugin-card').map(item => item.get('strong').text())).toEqual([
      '脚本执行', '文件传输', '作业执行方案',
    ])
    expect(groups[1].get('h3').text()).toBe('流程控制')
    expect(groups[1].findAll('.plugin-card').map(item => item.get('strong').text())).toEqual([
      '人工确认', '条件分支', '并行网关', '汇聚网关', '子流程',
    ])
    expect(wrapper.text()).toContain('控制节点由流程引擎处理，不是 Agent 执行动作。')

    wrapper.unmount()
  })

  it('uses distinct scheduling names without the old ambiguous user-facing terms', () => {
    const executionPlanSources = [
      readView('scheduled-tasks/index.vue'),
      readView('scheduled-tasks/editor.vue'),
      readView('scheduled-tasks/detail.vue'),
    ].join('\n')
    const pipelineSources = [
      readView('flows/components/FlowTemplateWorkbench.vue'),
      readView('flows/components/FlowScheduleDrawer.vue'),
    ].join('\n')

    expect(executionPlanSources).toContain('执行方案定时任务')
    expect(executionPlanSources).not.toContain('title="定时任务"')
    expect(executionPlanSources).not.toContain("'定时任务'")
    expect(executionPlanSources).not.toContain('>定时任务<')
    expect(pipelineSources).toContain('流水线定时调度')
    expect(pipelineSources).not.toContain('<template #title>定时调度</template>')
    expect(pipelineSources).not.toContain('当前模板没有定时调度')
    expect(pipelineSources).not.toContain("Message.success('定时调度已保存')")
  })
})
