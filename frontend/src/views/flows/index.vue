<template>
  <div class="app-page flows-page">
    <PageHeader eyebrow="标准运维" title="流程模板" description="">
      <template #actions>
        <a-space>
          <a-button @click="router.push('/flows/tasks')"><template #icon><icon-history /></template>流水线任务</a-button>
          <a-button @click="loadData"><template #icon><icon-refresh /></template>刷新</a-button>
          <a-button type="primary" @click="router.push('/flows/create')"><template #icon><icon-plus /></template>新建流程</a-button>
        </a-space>
      </template>
    </PageHeader>

    <DataToolbar title="筛选流程模板" description="按名称、状态和最近执行结果定位模板。" :active-count="activeFilterCount">
      <div class="app-filter-grid flows-filter-grid">
        <a-input v-model="filters.search" allow-clear placeholder="搜索模板名称、描述、负责人" @press-enter="loadData" @clear="loadData" />
        <a-select v-model="filters.status" allow-clear placeholder="模板状态" @change="loadData">
          <a-option value="active">启用</a-option>
          <a-option value="inactive">停用</a-option>
        </a-select>
        <a-select v-model="filters.runStatus" allow-clear placeholder="执行状态" @change="loadData">
          <a-option value="pending">等待中</a-option>
          <a-option value="running">执行中</a-option>
          <a-option value="success">成功</a-option>
          <a-option value="failed">失败</a-option>
          <a-option value="paused">已暂停</a-option>
          <a-option value="cancelled">已取消</a-option>
        </a-select>
        <div class="app-filter-grid__actions">
          <a-space>
            <a-button type="primary" @click="loadData">
              <template #icon><icon-search /></template>
              搜索
            </a-button>
            <a-button @click="resetFilters">重置</a-button>
          </a-space>
        </div>
      </div>
    </DataToolbar>

    <DetailPanel title="流程模板" :description="`共 ${templatePagination.total} 个模板，当前页 ${filteredTemplates.length} 个`">
    <a-table
      row-key="id"
      class="flow-standard-table pipeline-table"
      :columns="templateColumns"
      :data="filteredTemplates"
      :loading="loading"
      :pagination="templatePagination"
      :scroll="{ x: 980 }"
    >
      <template #name="{ record }">
        <div class="pipeline-name-cell">
          <a-link @click="openDetailDrawer(record)">{{ record.name }}</a-link>
          <span>{{ record.description || '暂无描述' }}</span>
        </div>
      </template>

      <template #status="{ record }">
        <StatusBadge :status="record.is_active ? 'success' : 'muted'" :text="record.is_active ? '启用' : '停用'" />
      </template>

      <template #topology="{ record }">
        <div class="pipeline-topology">
          <span><strong>{{ record.nodes?.length || 0 }}</strong> 节点</span>
          <span><strong>{{ record.edges?.length || 0 }}</strong> 连线</span>
          <em>{{ templateNodeTypeSummary(record) }}</em>
        </div>
      </template>

      <template #latestRun="{ record }">
        <div v-if="latestRun(record.id)" class="pipeline-run-summary">
          <div class="pipeline-run-summary__main">
            <a-link @click="router.push(`/flows/runs/${latestRun(record.id)?.id}`)">{{ latestRunTitle(latestRun(record.id)) }}</a-link>
            <span>{{ latestRunTrigger(latestRun(record.id)) }} / {{ latestRunActor(latestRun(record.id)) }}</span>
            <time>{{ latestRunTime(latestRun(record.id)) }}</time>
          </div>
          <StatusBadge :status="latestRun(record.id)?.status" :text="statusText(latestRun(record.id)?.status)" />
        </div>
        <span v-else class="table-muted">暂无执行</span>
      </template>

      <template #owner="{ record }">
        <MetaInfoLines
          :created-text="record.created_by_name || '-'"
          :updated-text="formatTime(record.updated_at || record.created_at)"
        />
      </template>

      <template #actions="{ record }">
        <div class="table-row-actions pipeline-actions">
          <a-button type="text" size="small" :disabled="!record.is_active" @click="openStartModal(record)">
            <template #icon><icon-play-arrow /></template>
            启动
          </a-button>
          <a-dropdown>
            <a-button class="pipeline-more-btn" type="text" size="small" aria-label="更多操作">
              <template #icon><icon-more /></template>
            </a-button>
            <template #content>
              <a-doption @click="openTemplateDetail(record)">
                <template #icon><icon-file /></template>
                详情
              </a-doption>
              <a-doption @click="router.push(`/flows/${record.id}/edit`)">
                <template #icon><icon-edit /></template>
                编辑
              </a-doption>
              <a-doption @click="copyTemplate(record)">
                <template #icon><icon-copy /></template>
                复制
              </a-doption>
              <a-doption class="danger-option" @click="confirmDeleteTemplate(record)">
                <template #icon><icon-delete /></template>
                删除
              </a-doption>
            </template>
          </a-dropdown>
        </div>
      </template>
    </a-table>
    </DetailPanel>

    <FlowStartModal
      v-model:visible="startVisible"
      :template="selectedTemplate"
      @started="handleFlowStarted"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Message, Modal } from '@arco-design/web-vue'
import { flowApi } from '@/api/ops'
import type { FlowRun, FlowRunStatus, FlowTemplate } from '@/types'
import { DataToolbar, DetailPanel, PageHeader, StatusBadge } from '@/components/app'
import MetaInfoLines from '@/components/MetaInfoLines.vue'
import FlowStartModal from './components/FlowStartModal.vue'
import {
  buildLatestRunMap,
  filterFlowTemplates,
  flowNodeTypeText,
  flowRunStatusText,
  type SupportedFlowNodeType,
} from './flowUtils'

const router = useRouter()
const loading = ref(false)
const startVisible = ref(false)
const selectedTemplate = ref<FlowTemplate | null>(null)
const templates = ref<FlowTemplate[]>([])
const runs = ref<FlowRun[]>([])
const filters = reactive({ search: '', status: '', runStatus: '' })

const templatePagination = reactive({ current: 1, pageSize: 12, total: 0, showTotal: true, showPageSize: true })

const templateColumns = [
  { title: '流水线', dataIndex: 'name', key: 'name', slotName: 'name', width: 260, ellipsis: true, tooltip: true },
  { title: '状态', dataIndex: 'is_active', key: 'status', slotName: 'status', align: 'center', width: 82 },
  { title: '拓扑', key: 'topology', slotName: 'topology', width: 160 },
  { title: '最近执行', key: 'latestRun', slotName: 'latestRun', width: 190 },
  { title: '负责人/更新', dataIndex: 'updated_at', key: 'owner', slotName: 'owner', width: 150 },
  { title: '操作', key: 'actions', slotName: 'actions', align: 'left', width: 140, fixed: 'right' },
]

const activeFilterCount = computed(() => Number(Boolean(filters.search)) + Number(Boolean(filters.status)) + Number(Boolean(filters.runStatus)))
const latestRunMap = computed(() => buildLatestRunMap(runs.value))
const filteredTemplates = computed(() => filterFlowTemplates(templates.value, filters, latestRunMap.value))

watch(filteredTemplates, value => { templatePagination.total = value.length }, { immediate: true })
watch(() => [filters.search, filters.status, filters.runStatus], () => {
  templatePagination.current = 1
})

const normalizeList = <T,>(value: any): T[] => Array.isArray(value) ? value : value?.results || value?.data || []
const latestRun = (templateId?: number) => templateId ? latestRunMap.value.get(templateId) : undefined
const statusText = (status?: FlowRunStatus) => flowRunStatusText(status)
const formatTime = (value?: string | null) => value ? new Date(value).toLocaleString('zh-CN') : '-'
const latestRunTitle = (run?: FlowRun) => run ? `${run.template_name || templateName(run.template)}执行单` : '暂无执行'
const latestRunTrigger = (run?: FlowRun) => ({ manual: '手动触发', scheduled: '定时触发', api: 'API 触发' }[run?.trigger_type || ''] || run?.trigger_type || '手动触发')
const latestRunActor = (run?: FlowRun) => run?.started_by_name || '-'
const latestRunTime = (run?: FlowRun) => formatTime(run?.started_at || run?.created_at)
const templateName = (id?: number) => templates.value.find(item => item.id === id)?.name || '未知模板'
const nodeTypeCount = (template: FlowTemplate, type: SupportedFlowNodeType) => (template.nodes || []).filter(node => node.node_type === type).length
const templateNodeTypeSummary = (template: FlowTemplate) => {
  const rows = [
    ['脚本', nodeTypeCount(template, 'script')],
    ['文件', nodeTypeCount(template, 'file_transfer')],
    ['作业', nodeTypeCount(template, 'job_plan')],
    ['子流程', nodeTypeCount(template, 'sub_process')],
  ].filter(([, count]) => Number(count) > 0)
  return rows.length ? rows.map(([label, count]) => `${label} ${count}`).join(' / ') : flowNodeTypeText(template.nodes?.[0]?.node_type as SupportedFlowNodeType) || '未编排'
}
const loadData = async () => {
  loading.value = true
  try {
    const [templateList, runList] = await Promise.all([
      flowApi.getTemplates({ search: filters.search, status: filters.status }),
      flowApi.getRuns(),
    ])
    templates.value = normalizeList<FlowTemplate>(templateList)
    runs.value = normalizeList<FlowRun>(runList)
  } catch (error) {
    console.error('加载流水线失败:', error)
    Message.error('加载流水线失败')
  } finally {
    loading.value = false
  }
}

const resetFilters = () => {
  filters.search = ''
  filters.status = ''
  filters.runStatus = ''
  loadData()
}

const openTemplateDetail = (record: FlowTemplate) => {
  if (record.id) router.push(`/flows/${record.id}/detail`)
}

const openDetailDrawer = (record: FlowTemplate) => {
  openTemplateDetail(record)
}

const openStartModal = (record: FlowTemplate) => {
  selectedTemplate.value = record
  startVisible.value = true
}

const handleFlowStarted = (run: FlowRun) => {
  router.push(`/flows/runs/${run.id}`)
}

const copyTemplate = async (record: FlowTemplate) => {
  if (!record.id) return
  try {
    const copied = await flowApi.copyTemplate(record.id, { name: `${record.name} 副本` })
    Message.success('已复制流水线')
    await loadData()
    if (copied.id) router.push(`/flows/${copied.id}/edit`)
  } catch (error) {
    console.error('复制流水线失败:', error)
    Message.error('复制流水线失败')
  }
}

const confirmDeleteTemplate = (record: FlowTemplate) => {
  Modal.warning({
    title: '删除流水线',
    content: `确认删除“${record.name}”？删除后不可恢复。`,
    hideCancel: false,
    onOk: async () => {
      if (!record.id) return
      await flowApi.deleteTemplate(record.id)
      Message.success('已删除流水线')
      loadData()
    },
  })
}

onMounted(loadData)
</script>

<style scoped>
.flows-page {
  display: grid;
  gap: 12px;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  padding: 0;
  overflow-x: clip;
}
.flows-page-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  min-width: 0;
}
.flows-page-head__actions {
  flex: 0 0 auto;
}
.flows-filter-grid {
  grid-template-columns: minmax(240px, 360px) 150px 150px minmax(0, 1fr);
  align-items: end;
}
.flows-filter-grid .app-filter-grid__actions {
  display: flex;
  justify-content: flex-end;
}
.flow-standard-table,
.pipeline-table {
  width: 100%;
  max-width: 100%;
  min-width: 0;
}
.flow-standard-table :deep(.arco-table-container) {
  max-width: 100%;
  border-radius: var(--app-radius-sm);
}
.pipeline-name-cell {
  display: grid;
  gap: 4px;
  min-width: 0;
}
.pipeline-name-cell :deep(.arco-link) {
  justify-content: flex-start;
  font-weight: 650;
}
.pipeline-name-cell span,
.table-muted {
  overflow: hidden;
  color: var(--app-muted);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.pipeline-topology {
  display: grid;
  gap: 3px;
  color: var(--app-muted);
  font-size: 12px;
}
.pipeline-topology span {
  display: inline-flex;
  gap: 4px;
}
.pipeline-topology strong {
  color: var(--app-fg);
  font-family: var(--app-mono);
}
.pipeline-topology em {
  overflow: hidden;
  font-style: normal;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.pipeline-run-summary {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
  align-items: center;
  min-width: 0;
}
.pipeline-run-summary__main {
  display: grid;
  gap: 3px;
  min-width: 0;
}
.pipeline-run-summary__main :deep(.arco-link) {
  justify-content: flex-start;
  min-width: 0;
  font-weight: 650;
}
.pipeline-run-summary__main span,
.pipeline-run-summary__main time {
  overflow: hidden;
  color: var(--app-muted);
  font-size: 12px;
  line-height: 1.35;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.pipeline-run-summary__main time {
  color: var(--app-meta);
  font-family: var(--app-mono);
  font-size: 11px;
}
.pipeline-actions {
  display: flex;
  flex-wrap: nowrap;
  gap: 4px;
  align-items: center;
  min-width: 0;
}
.pipeline-actions :deep(.arco-btn) {
  flex: 0 0 auto;
  padding-inline: 6px;
}
.pipeline-more-btn {
  width: 30px;
  padding-inline: 0 !important;
}
.danger-option {
  color: var(--app-danger);
}
:deep(.arco-table-th) {
  background: #fff;
}
:deep(.arco-table-td) {
  vertical-align: top;
}
@media (max-width: 960px) {
  .flows-page-head {
    display: grid;
  }
  .flows-filter-grid {
    grid-template-columns: 1fr 1fr;
  }
}
@media (max-width: 720px) {
  .flows-filter-grid {
    grid-template-columns: 1fr;
  }
  .flows-filter-grid .app-filter-grid__actions {
    justify-content: flex-start;
  }
}
</style>
