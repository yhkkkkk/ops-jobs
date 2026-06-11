<template>
  <div class="app-page pipelines-page">
    <header class="app-page-header pipeline-head">
      <div class="pipeline-head__main">
        <p class="app-page-eyebrow">作业链路</p>
        <h1 class="app-page-title">运维流水线</h1>
        <p class="app-page-desc">用一张表判断模板状态、最近执行和下一步操作。</p>
      </div>
      <div class="pipeline-health">
        <div>
          <span>模板</span>
          <strong>{{ templates.length }}</strong>
        </div>
        <div>
          <span>运行中</span>
          <strong>{{ runCount('running') }}</strong>
        </div>
        <div>
          <span>异常</span>
          <strong>{{ runCount('failed') }}</strong>
        </div>
      </div>
      <a-space class="pipeline-head__actions">
        <a-button @click="loadData">
          <template #icon><icon-refresh /></template>
          刷新
        </a-button>
        <a-button type="primary" @click="router.push('/flows/create')">
          <template #icon><icon-plus /></template>
          新建流水线
        </a-button>
      </a-space>
    </header>

    <DataToolbar title="筛选流水线" :active-count="activeFilterCount">
      <div class="app-filter-grid pipeline-filter-grid">
        <div class="pipeline-filter-search">
          <a-input v-model="filters.search" allow-clear placeholder="搜索名称、描述、负责人" @press-enter="loadData" @clear="loadData" />
        </div>
        <div>
          <a-select v-model="filters.status" allow-clear placeholder="启用状态" @change="loadData">
            <a-option value="active">启用</a-option>
            <a-option value="inactive">停用</a-option>
          </a-select>
        </div>
        <div>
          <a-select v-model="filters.runStatus" allow-clear placeholder="最近执行" @change="loadData">
            <a-option value="running">执行中</a-option>
            <a-option value="success">成功</a-option>
            <a-option value="failed">失败</a-option>
            <a-option value="paused">已暂停</a-option>
          </a-select>
        </div>
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

    <DetailPanel title="流水线模板" :description="`共 ${filteredTemplates.length} 条，启用 ${activeTemplateCount} 条`">
      <a-table
        row-key="id"
        class="pipeline-table"
        :columns="columns"
        :data="filteredTemplates"
        :loading="loading"
        :pagination="tablePagination"
        :scroll="{ x: 1280 }"
        @page-change="handlePageChange"
        @page-size-change="handlePageSizeChange"
      >
        <template #name="{ record }">
          <div class="pipeline-name-cell">
            <a-link class="pipeline-link" @click="router.push(`/flows/${record.id}/edit`)">{{ record.name }}</a-link>
            <span>{{ record.description || '暂无描述' }}</span>
          </div>
        </template>

        <template #status="{ record }">
          <StatusBadge :status="record.is_active ? 'success' : 'muted'" :text="record.is_active ? '启用' : '停用'" />
        </template>

        <template #topology="{ record }">
          <div class="pipeline-topology">
            <div>
              <strong>{{ record.nodes?.length || 0 }}</strong>
              <span>节点</span>
              <i />
              <strong>{{ record.edges?.length || 0 }}</strong>
              <span>连线</span>
            </div>
            <div class="pipeline-type-chips">
              <a-tag size="small">脚本 {{ nodeTypeCount(record, 'script') }}</a-tag>
              <a-tag size="small">文件 {{ nodeTypeCount(record, 'file_transfer') }}</a-tag>
              <a-tag size="small">作业 {{ nodeTypeCount(record, 'job_plan') }}</a-tag>
              <a-tag size="small">子流程 {{ nodeTypeCount(record, 'sub_process') }}</a-tag>
            </div>
          </div>
        </template>

        <template #latestRun="{ record }">
          <div v-if="latestRun(record.id)" class="pipeline-run-cell">
            <StatusBadge :status="latestRun(record.id)?.status" :text="statusText(latestRun(record.id)?.status)" />
            <a-link @click="router.push(`/flows/runs/${latestRun(record.id)?.id}`)">#{{ latestRun(record.id)?.id }}</a-link>
            <span>{{ formatTime(latestRun(record.id)?.started_at || latestRun(record.id)?.created_at) }}</span>
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
            <a-button type="text" size="small" @click="router.push(`/flows/${record.id}/edit`)">
              <template #icon><icon-edit /></template>
              编辑
            </a-button>
            <a-button type="text" size="small" :disabled="!record.is_active" @click="openStartModal(record)">
              <template #icon><icon-play-arrow /></template>
              启动
            </a-button>
            <a-dropdown>
              <a-button class="pipeline-more-btn" type="text" size="small" aria-label="更多操作">
                <template #icon><icon-more /></template>
              </a-button>
              <template #content>
                <a-doption @click="openDetailDrawer(record)">
                  <template #icon><icon-file /></template>
                  详情
                </a-doption>
                <a-doption v-if="latestRun(record.id)" @click="router.push(`/flows/runs/${latestRun(record.id)?.id}`)">
                  <template #icon><icon-history /></template>
                  最近执行
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

    <section class="pipeline-insights">
      <DetailPanel title="最近执行实例" description="按启动时间展示最近的流水线运行">
        <div class="pipeline-run-timeline">
          <div v-for="run in recentRuns" :key="run.id" class="pipeline-run-row">
            <span class="mono-time">{{ formatTime(run.started_at || run.created_at) }}</span>
            <div>
              <strong>{{ run.template_name || `模板 #${run.template}` }}</strong>
              <small>#{{ run.id }} / {{ run.started_by_name || '-' }}</small>
            </div>
            <StatusBadge :status="run.status" :text="statusText(run.status)" />
          </div>
          <a-empty v-if="recentRuns.length === 0" description="暂无执行实例" />
        </div>
      </DetailPanel>

      <DetailPanel title="模板健康提醒" description="执行前需要优先关注的模板问题">
        <div class="pipeline-health-list">
          <div v-for="notice in healthNotices" :key="notice.key" :class="['pipeline-health-row', `pipeline-health-row--${notice.status}`]">
            <span>{{ notice.status === 'success' ? 'OK' : '!' }}</span>
            <div>
              <strong>{{ notice.title }}</strong>
              <small>{{ notice.description }}</small>
            </div>
            <em>{{ notice.code }}</em>
          </div>
        </div>
      </DetailPanel>
    </section>

    <FlowTemplateDetailDrawer
      v-model:visible="detailVisible"
      :template="detailTemplate"
      :latest-run="detailTemplate ? latestRun(detailTemplate.id) : undefined"
      @open-run="openRunDetail"
    />

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
import type { FlowNode, FlowNodeType, FlowRun, FlowRunStatus, FlowTemplate } from '@/types'
import { DataToolbar, DetailPanel, StatusBadge } from '@/components/app'
import MetaInfoLines from '@/components/MetaInfoLines.vue'
import FlowStartModal from './components/FlowStartModal.vue'
import FlowTemplateDetailDrawer from './components/FlowTemplateDetailDrawer.vue'
import {
  buildFlowHealthNotices,
  buildLatestRunMap,
  filterFlowTemplates,
  flowNodeTypeText,
  flowRunStatusText,
  getRecentFlowRuns,
  summarizeFlowNode,
  type SupportedFlowNodeType,
} from './flowUtils'

const router = useRouter()
const loading = ref(false)
const startVisible = ref(false)
const detailVisible = ref(false)
const selectedTemplate = ref<FlowTemplate | null>(null)
const detailTemplate = ref<FlowTemplate | null>(null)
const templates = ref<FlowTemplate[]>([])
const runs = ref<FlowRun[]>([])

const filters = reactive({ search: '', status: '', runStatus: '' })
const pagination = reactive({ current: 1, pageSize: 10, total: 0, showTotal: true, showPageSize: true })

const columns = [
  { title: '流水线', dataIndex: 'name', key: 'name', slotName: 'name', width: 330, ellipsis: true, tooltip: true },
  { title: '状态', dataIndex: 'is_active', key: 'status', slotName: 'status', align: 'center', width: 92 },
  { title: '拓扑', key: 'topology', slotName: 'topology', width: 180 },
  { title: '最近执行', key: 'latestRun', slotName: 'latestRun', width: 250 },
  { title: '负责人/更新', dataIndex: 'updated_at', key: 'owner', slotName: 'owner', width: 190 },
  { title: '操作', key: 'actions', slotName: 'actions', align: 'center', width: 190, fixed: 'right' },
]

const activeTemplateCount = computed(() => templates.value.filter(item => item.is_active).length)
const activeFilterCount = computed(() => Number(Boolean(filters.search)) + Number(Boolean(filters.status)) + Number(Boolean(filters.runStatus)))
const latestRunMap = computed(() => buildLatestRunMap(runs.value))
const filteredTemplates = computed(() => {
  return filterFlowTemplates(templates.value, filters, latestRunMap.value)
})
const tablePagination = computed(() => ({
  ...pagination,
  total: filteredTemplates.value.length,
}))
const recentRuns = computed(() => getRecentFlowRuns(runs.value, 3))
const healthNotices = computed(() => buildFlowHealthNotices(templates.value, latestRunMap.value))

const latestRun = (templateId?: number) => templateId ? latestRunMap.value.get(templateId) : undefined
const runCount = (status: FlowRunStatus) => runs.value.filter(item => item.status === status).length
const statusText = (status?: FlowRunStatus) => flowRunStatusText(status)
const nodeTypeText = (type: FlowNodeType) => flowNodeTypeText(type)
const nodeTypeCount = (template: FlowTemplate, type: SupportedFlowNodeType) =>
  (template.nodes || []).filter(node => node.node_type === type).length
const formatTime = (value?: string | null) => value ? new Date(value).toLocaleString('zh-CN') : '-'
const nodeConfigSummary = (node: FlowNode) => summarizeFlowNode(node)

const loadData = async () => {
  loading.value = true
  try {
    const [templateList, runList] = await Promise.all([
      flowApi.getTemplates({ search: filters.search, status: filters.status }),
      flowApi.getRuns(),
    ])
    templates.value = templateList
    runs.value = runList
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

const handlePageChange = (page: number) => {
  pagination.current = page
}

const handlePageSizeChange = (pageSize: number) => {
  pagination.pageSize = pageSize
  pagination.current = 1
}

const openDetailDrawer = (record: FlowTemplate) => {
  detailTemplate.value = record
  detailVisible.value = true
}

const openStartModal = (record: FlowTemplate) => {
  selectedTemplate.value = record
  startVisible.value = true
}

const handleFlowStarted = (run: FlowRun) => {
  router.push(`/flows/runs/${run.id}`)
}

const openRunDetail = (runId: number) => {
  router.push(`/flows/runs/${runId}`)
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

watch(
  () => [filters.search, filters.status, filters.runStatus],
  () => {
    pagination.current = 1
  },
)
</script>

<style scoped>
.pipelines-page { display: grid; gap: 12px; padding: 0; }
.pipeline-head {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(260px, auto) auto;
  gap: 14px;
  align-items: center;
  padding: 0;
}
.pipeline-head__main { min-width: 0; }
.pipeline-health { display: grid; grid-template-columns: repeat(3, minmax(72px, 1fr)); gap: 1px; overflow: hidden; border: 1px solid var(--app-border); border-radius: var(--app-radius-sm); background: var(--app-border); }
.pipeline-health div { padding: 7px 10px; background: #fff; }
.pipeline-health span { display: block; color: var(--app-muted); font-size: 12px; }
.pipeline-health strong { display: block; margin-top: 3px; color: var(--app-fg); font-family: var(--app-mono); font-size: 17px; line-height: 1; }
.pipeline-filter-grid {
  align-items: end;
  grid-template-columns: minmax(240px, 360px) 150px 150px minmax(0, 1fr);
}
.pipeline-filter-search { min-width: 0; }
.pipeline-filter-grid .app-filter-grid__actions {
  display: flex;
  align-items: flex-end;
  justify-content: flex-end;
  justify-self: end;
  min-height: 32px;
}
.pipeline-filter-grid .app-filter-grid__actions :deep(.arco-space) { flex-wrap: nowrap; }
.pipeline-name-cell { display: grid; gap: 4px; min-width: 0; }
.pipeline-link { font-weight: 650; }
.pipeline-name-cell span, .table-muted { color: var(--app-muted); font-size: 12px; }
.pipeline-topology { display: grid; gap: 5px; color: var(--app-muted); font-size: 12px; }
.pipeline-topology > div:first-child { display: inline-flex; align-items: center; gap: 5px; }
.pipeline-topology strong { color: var(--app-fg); font-family: var(--app-mono); font-size: 14px; }
.pipeline-topology i { width: 1px; height: 14px; background: var(--app-border); }
.pipeline-type-chips { display: flex; flex-wrap: wrap; gap: 4px; }
.pipeline-run-cell { display: flex; align-items: center; gap: 8px; min-width: 0; }
.pipeline-run-cell span:last-child { overflow: hidden; color: var(--app-muted); font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.pipeline-table { width: 100%; }
.pipeline-table :deep(.arco-table-container) {
  overflow: hidden;
  background: #fff;
  border-radius: var(--app-radius-sm);
}
.pipeline-table :deep(.arco-table-content),
.pipeline-table :deep(.arco-table-body) {
  background: #fff;
}
.pipeline-table :deep(.arco-table-col-fixed-right),
.pipeline-table :deep(.arco-table-th-fixed-right),
.pipeline-table :deep(.arco-table-td-fixed-right),
.pipeline-table :deep(.arco-table-cell-fixed-right) {
  background: #fff;
  box-shadow: -8px 0 14px rgba(15, 23, 42, .06);
  overflow: hidden;
  z-index: 2;
}
.pipeline-actions {
  display: grid;
  grid-template-columns: auto auto 30px;
  gap: 4px;
  align-items: center;
  width: 100%;
  justify-content: center;
  overflow: hidden;
  padding: 0 10px 0 6px;
}
.pipeline-actions :deep(.arco-btn) {
  flex: 0 0 auto;
  min-width: 30px;
  padding-inline: 5px;
}
.pipeline-more-btn {
  width: 28px;
  padding-inline: 0 !important;
}
.danger-option { color: var(--app-danger); }
.pipeline-insights {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(280px, .85fr);
  gap: 12px;
}
.pipeline-run-timeline,
.pipeline-health-list {
  display: grid;
  gap: 8px;
}
.pipeline-run-row,
.pipeline-health-row {
  display: grid;
  grid-template-columns: 138px minmax(0, 1fr) auto;
  gap: 10px;
  align-items: center;
  padding: 10px 12px;
  background: #fff;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
}
.pipeline-run-row strong,
.pipeline-health-row strong {
  display: block;
  overflow: hidden;
  color: var(--app-fg);
  font-size: 13px;
  line-height: 1.35;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.pipeline-run-row small,
.pipeline-health-row small {
  display: block;
  margin-top: 2px;
  overflow: hidden;
  color: var(--app-muted);
  font-size: 12px;
  line-height: 1.4;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.mono-time {
  color: var(--app-meta);
  font-family: var(--app-mono);
  font-size: 12px;
  white-space: nowrap;
}
.pipeline-health-row {
  grid-template-columns: 28px minmax(0, 1fr) auto;
}
.pipeline-health-row > span {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  color: var(--app-warn);
  background: var(--app-warn-soft);
  border-radius: var(--app-radius-pill);
  font-family: var(--app-mono);
  font-size: 11px;
  font-weight: 700;
}
.pipeline-health-row--success > span {
  color: var(--app-success);
  background: var(--app-success-soft);
}
.pipeline-health-row--danger > span {
  color: var(--app-danger);
  background: var(--app-danger-soft);
}
.pipeline-health-row em {
  color: var(--app-meta);
  font-family: var(--app-mono);
  font-size: 12px;
  font-style: normal;
}
:deep(.arco-table-th) { background: #fff; }
:deep(.arco-table-td) { vertical-align: top; }
@media (max-width: 1180px) {
  .pipeline-head { grid-template-columns: 1fr; align-items: stretch; }
  .pipeline-health { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .pipeline-head__actions { justify-content: flex-start; }
  .pipeline-filter-grid { grid-template-columns: 1fr 1fr; }
  .pipeline-insights { grid-template-columns: 1fr; }
}
@media (max-width: 720px) {
  .pipeline-filter-grid, .pipeline-health { grid-template-columns: 1fr; }
  .pipeline-filter-grid .app-filter-grid__actions { justify-self: start; }
  .pipeline-run-row,
  .pipeline-health-row { grid-template-columns: 1fr; align-items: flex-start; }
}
</style>
