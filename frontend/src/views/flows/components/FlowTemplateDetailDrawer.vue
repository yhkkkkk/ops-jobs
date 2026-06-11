<template>
  <a-drawer :visible="visible" title="流水线详情" :width="620" unmount-on-close @update:visible="emit('update:visible', $event)">
    <template v-if="template">
      <a-descriptions :column="1" bordered size="medium">
        <a-descriptions-item label="名称">{{ template.name }}</a-descriptions-item>
        <a-descriptions-item label="描述">{{ template.description || '-' }}</a-descriptions-item>
        <a-descriptions-item label="状态">
          <StatusBadge :status="template.is_active ? 'success' : 'muted'" :text="template.is_active ? '启用' : '停用'" />
        </a-descriptions-item>
        <a-descriptions-item label="拓扑">{{ template.nodes?.length || 0 }} 个节点 / {{ template.edges?.length || 0 }} 条连线</a-descriptions-item>
        <a-descriptions-item label="最近执行">
          <template v-if="latestRun">
            <StatusBadge :status="latestRun.status" :text="flowRunStatusText(latestRun.status)" />
            <a-link class="drawer-run-link" @click="emit('openRun', latestRun.id)">#{{ latestRun.id }}</a-link>
          </template>
          <span v-else>-</span>
        </a-descriptions-item>
      </a-descriptions>

      <section class="drawer-section">
        <h3>节点清单</h3>
        <a-table row-key="uuid" size="small" :data="template.nodes || []" :pagination="false">
          <template #columns>
            <a-table-column title="节点" data-index="name" />
            <a-table-column title="类型" :width="132">
              <template #cell="{ record }">{{ flowNodeTypeText(record.node_type) }}</template>
            </a-table-column>
            <a-table-column title="配置摘要">
              <template #cell="{ record }">{{ summarizeFlowNode(record) }}</template>
            </a-table-column>
          </template>
        </a-table>
      </section>

      <section class="drawer-section">
        <h3>变量</h3>
        <pre class="json-block">{{ formatJson(template.variables) }}</pre>
      </section>
    </template>
  </a-drawer>
</template>

<script setup lang="ts">
import type { FlowRun, FlowTemplate } from '@/types'
import { StatusBadge } from '@/components/app'
import { flowNodeTypeText, flowRunStatusText, summarizeFlowNode } from '../flowUtils'

defineProps<{
  visible: boolean
  template: FlowTemplate | null
  latestRun?: FlowRun
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  openRun: [runId: number]
}>()

const formatJson = (value: Record<string, any>) => JSON.stringify(value || {}, null, 2)
</script>

<style scoped>
.drawer-section { display: grid; gap: 10px; margin-top: 18px; }
.drawer-section h3 { margin: 0; color: var(--app-fg); font-size: 14px; }
.drawer-run-link { margin-left: 8px; }
.json-block {
  max-height: 240px;
  margin: 0;
  overflow: auto;
  padding: 12px;
  color: var(--app-fg);
  background: var(--app-surface-soft);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
  font-family: var(--app-mono);
  font-size: 12px;
  line-height: 1.55;
}
</style>
