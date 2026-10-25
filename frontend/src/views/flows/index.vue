<template>
  <div class="app-page flows-page">
    <PageHeader eyebrow="标准运维" title="流程模板" description="">
      <template #actions>
        <n-space>
          <n-button @click="router.push('/flows/tasks')"><template #icon><History  /></template>流水线任务</n-button>
          <n-button @click="loadData"><template #icon><RefreshCw  /></template>刷新</n-button>
          <n-button type="primary" @click="router.push('/flows/create')"><template #icon><Plus  /></template>新建流程</n-button>
        </n-space>
      </template>
    </PageHeader>

    <DataToolbar title="筛选流程模板" description="我的流程 / 公共目录；按名称、状态和最近执行结果定位。" :active-count="activeFilterCount">
      <div class="app-filter-grid flows-filter-grid">
        <n-radio-group v-model:value="catalogScope" size="small" @update:value="handleCatalogScopeChange">
          <n-radio-button value="mine">我的流程</n-radio-button>
          <n-radio-button value="public">公共目录</n-radio-button>
        </n-radio-group>
        <n-input v-model:value="filters.search" clearable placeholder="搜索模板名称、描述、负责人" @press-enter="loadData" @clear="loadData" />
                <n-select v-model:value="filters.status" clearable placeholder="模板状态" @update:value="loadData" :options="selectOptions1" />
                <n-select v-model:value="filters.runStatus" clearable placeholder="执行状态" @update:value="loadData" :options="selectOptions2" />
        <div class="app-filter-grid__actions">
          <n-space>
            <n-button type="primary" @click="loadData">
              <template #icon><Search  /></template>
              搜索
            </n-button>
            <n-button @click="resetFilters">重置</n-button>
          </n-space>
        </div>
      </div>
    </DataToolbar>

    <DetailPanel :title="catalogScope === 'public' ? '公共流程' : '流程模板'" :description="`共 ${templatePagination.total} 个模板，当前页 ${filteredTemplates.length} 个`">
      <template #extra>
        <n-radio-group v-model:value="listViewMode" size="small">
          <n-radio-button value="table">列表</n-radio-button>
          <n-radio-button value="card">卡片</n-radio-button>
        </n-radio-group>
      </template>

      <n-data-table
        v-if="listViewMode === 'table'"
        :row-key="(row: any) => row.id"
        class="flow-standard-table pipeline-table"
        :columns="templateColumns"
        :data="filteredTemplates"
        :loading="loading"
        :pagination="tablePagination"
      />

      <div v-else class="pipeline-template-grid" :aria-busy="loading">
        <article
          v-for="record in filteredTemplates"
          :key="record.id"
          class="pipeline-template-card"
        >
          <header class="pipeline-template-card__head">
            <div>
              <button type="button" class="pipeline-template-card__title" @click="openDetailDrawer(record)">
                {{ record.name }}
              </button>
              <p>{{ record.description || '暂无描述' }}</p>
            </div>
            <StatusBadge
              :status="record.is_active ? 'success' : 'muted'"
              :text="record.is_active ? '启用' : '停用'"
            />
          </header>
          <div class="pipeline-template-card__meta">
            <span>{{ record.nodes?.length || 0 }} 节点 / {{ record.edges?.length || 0 }} 连线</span>
            <span>{{ templateNodeTypeSummary(record) }}</span>
            <span>{{ record.created_by_name || '-' }} · {{ formatTime(record.updated_at || record.created_at) }}</span>
          </div>
          <div class="pipeline-template-card__run" v-if="latestRun(record.id)">
            <div>
              <n-button text size="small" @click="router.push(`/flows/runs/${latestRun(record.id)!.id}`)">
                {{ latestRunTitle(latestRun(record.id)) }}
              </n-button>
              <span>{{ latestRunTrigger(latestRun(record.id)) }} / {{ latestRunActor(latestRun(record.id)) }}</span>
            </div>
            <StatusBadge
              :status="latestRun(record.id)!.status"
              :text="statusText(latestRun(record.id)!.status)"
            />
          </div>
          <div v-else class="pipeline-template-card__run pipeline-template-card__run--empty">暂无执行</div>
          <footer class="pipeline-template-card__actions">
            <n-button
              v-if="canStartTemplate(record)"
              type="primary"
              size="small"
              @click="openStartModal(record)"
            >
              <template #icon><Play :size="14" /></template>
              新建任务
            </n-button>
            <n-button
              v-if="canManageTemplate(record)"
              size="small"
              @click="router.push(`/flows/${record.id}/edit`)"
            >
              编辑
            </n-button>
            <n-dropdown
              trigger="click"
              :options="pipelineRowActions(record)"
              @select="(key: string) => onPipelineRowAction(key, record)"
            >
              <n-button size="small" aria-label="更多操作">
                <template #icon><MoreHorizontal :size="16" /></template>
              </n-button>
            </n-dropdown>
          </footer>
        </article>
        <n-empty
          v-if="!loading && filteredTemplates.length === 0"
          description="暂无流程模板"
          class="pipeline-template-grid__empty"
        />
        <div v-if="filteredTemplates.length > 0" class="pipeline-template-grid__pager">
          <n-pagination
            v-model:page="templatePagination.current"
            v-model:page-size="templatePagination.pageSize"
            :item-count="templatePagination.total"
            show-size-picker
            :page-sizes="[12, 24, 48]"
            @update:page="handlePageChange"
            @update:page-size="handlePageSizeChange"
          />
        </div>
      </div>
    </DetailPanel>

    <FlowStartModal
      v-model:visible="startVisible"
      :template="selectedTemplate"
      @started="handleFlowStarted"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, h, onMounted, reactive, ref, resolveDirective, type VNode, watch, withDirectives } from 'vue'
import { useRouter } from 'vue-router'
import { flowApi } from '@/api/ops'
import type { FlowRun, FlowRunStatus, FlowTemplate } from '@/types'
import { DataToolbar, DetailPanel, PageHeader, StatusBadge } from '@/components/app'
import MetaInfoLines from '@/components/MetaInfoLines.vue'
import FlowStartModal from './components/FlowStartModal.vue'
import { NButton, NDataTable, NDropdown, NEmpty, NInput, NPagination, NRadioButton, NRadioGroup, NSelect, NSpace, type DataTableColumns, useDialog, useMessage } from 'naive-ui'
import {
  buildLatestRunMap,
  filterFlowTemplates,
  flowNodeTypeText,
  flowRunStatusText,
  type SupportedFlowNodeType,
} from './flowUtils'
import { Copy, FileText, History, MoreHorizontal, Pencil, Play, Plus, RefreshCw, Search, Trash2 } from 'lucide-vue-next'
import { useAuthStore } from '@/stores/auth'

const message = useMessage()
const dialog = useDialog()
const router = useRouter()
const authStore = useAuthStore()
const loading = ref(false)
const listViewMode = ref<'table' | 'card'>('table')
const catalogScope = ref<'mine' | 'public'>('mine')
const startVisible = ref(false)
const selectedTemplate = ref<FlowTemplate | null>(null)
const templates = ref<FlowTemplate[]>([])
const runs = ref<FlowRun[]>([])
const filters = reactive({ search: '', status: '', runStatus: '' })

const templatePagination = reactive({ current: 1, pageSize: 12, total: 0, showTotal: true, showPageSize: true })


const activeFilterCount = computed(() => Number(Boolean(filters.search)) + Number(Boolean(filters.status)) + Number(Boolean(filters.runStatus)))
const latestRunMap = computed(() => buildLatestRunMap(runs.value))
const filteredTemplates = computed(() => filterFlowTemplates(templates.value, filters, latestRunMap.value))

watch(filteredTemplates, value => {
  if (!templatePagination.total) templatePagination.total = value.length
}, { immediate: true })
watch(() => [filters.search, filters.status, filters.runStatus], () => {
  templatePagination.current = 1
})

const normalizePage = <T,>(value: any, fallbackPageSize: number) => {
  const content = value?.results ? value : value?.data?.results ? value.data : value?.data
  if (content && Array.isArray(content.results)) {
    return {
      items: content.results as T[],
      total: Number(content.total ?? content.results.length),
      page: Number(content.page ?? 1),
      pageSize: Number(content.page_size ?? fallbackPageSize),
    }
  }
  return { items: [] as T[], total: 0, page: 1, pageSize: fallbackPageSize }
}
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
    const templateList = await flowApi.getTemplates({
      search: filters.search,
      status: filters.status,
      run_status: filters.runStatus,
      is_public: catalogScope.value === 'public' ? true : undefined,
      page: templatePagination.current,
      page_size: templatePagination.pageSize,
    })
    const templatePage = normalizePage<FlowTemplate>(templateList, templatePagination.pageSize)
    templates.value = templatePage.items
    templatePagination.total = templatePage.total
    const templateIds = templatePage.items.map(template => template.id).filter(Boolean)
    if (templateIds.length) {
      const runList = await flowApi.getRuns({
        template_ids: templateIds.join(','),
        page: 1,
        page_size: templateIds.length,
        latest_per_template: 1,
      })
      runs.value = normalizePage<FlowRun>(runList, templateIds.length).items
    } else {
      runs.value = []
    }
  } catch (error) {
    console.error('加载流水线失败:', error)
    message.error('加载流水线失败')
  } finally {
    loading.value = false
  }
}

const handlePageChange = (page: number) => {
  templatePagination.current = page
  loadData()
}

const handlePageSizeChange = (pageSize: number) => {
  templatePagination.pageSize = pageSize
  templatePagination.current = 1
  loadData()
}

const resetFilters = () => {
  filters.search = ''
  filters.status = ''
  filters.runStatus = ''
  templatePagination.current = 1
  loadData()
}

const handleCatalogScopeChange = () => {
  templatePagination.current = 1
  loadData()
}

const openTemplateDetail = (record: FlowTemplate) => {
  if (record.id) router.push(`/flows/${record.id}/detail`)
}

const openDetailDrawer = (record: FlowTemplate) => {
  openTemplateDetail(record)
}

const canManageTemplate = (record: FlowTemplate) => {
  if (authStore.isAdmin) return true
  const userId = authStore.user?.id
  return Boolean(userId && record.created_by === userId)
}

const canStartTemplate = (record: FlowTemplate) => {
  if (!record.is_active) return false
  if (canManageTemplate(record)) return true
  return Boolean(record.is_public)
}

const openStartModal = (record: FlowTemplate) => {
  if (!canStartTemplate(record)) {
    message.warning('无权启动该流程模板')
    return
  }
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
    message.success('已复制流水线')
    await loadData()
    if (copied.id) router.push(`/flows/${copied.id}/edit`)
  } catch (error) {
    console.error('复制流水线失败:', error)
    message.error('复制流水线失败')
  }
}

const confirmDeleteTemplate = (record: FlowTemplate) => {
  dialog.warning({
    title: '删除流水线',
    content: `确认删除“${record.name}”？删除后不可恢复。`,
    onPositiveClick: async () => {
      if (!record.id) return
      await flowApi.deleteTemplate(record.id)
      message.success('已删除流水线')
      loadData()
    },
  })
}

onMounted(loadData)

// 机械转换生成的静态下拉选项
const selectOptions1 = [{ label: '启用', value: 'active' }, { label: '停用', value: 'inactive' }]
const selectOptions2 = [{ label: '等待中', value: 'pending' }, { label: '执行中', value: 'running' }, { label: '成功', value: 'success' }, { label: '失败', value: 'failed' }, { label: '已暂停', value: 'paused' }, { label: '已取消', value: 'cancelled' }]

const withPerm = (vnode: VNode, value: unknown) => {
  const perm = resolveDirective('permission')
  return perm ? withDirectives(vnode, [[perm, value]]) : vnode
}

const pipelineRowActions = (record: FlowTemplate) => {
  const actions = [
    { label: '详情', key: 'detail', icon: () => h(FileText, { size: 14 }) },
  ]
  if (canManageTemplate(record)) {
    actions.push({ label: '编辑', key: 'edit', icon: () => h(Pencil, { size: 14 }) })
  }
  actions.push({ label: '复制', key: 'copy', icon: () => h(Copy, { size: 14 }) })
  if (canManageTemplate(record)) {
    actions.push({ label: '删除', key: 'delete', icon: () => h(Trash2, { size: 14 }), props: { class: 'danger' } } as any)
  }
  return actions
}

const onPipelineRowAction = (key: string, record: FlowTemplate) => {
  if (key === 'detail') openTemplateDetail(record)
  if (key === 'edit') {
    if (!canManageTemplate(record)) {
      message.warning('无权编辑该流程模板')
      return
    }
    router.push(`/flows/${record.id}/edit`)
  }
  if (key === 'copy') copyTemplate(record)
  if (key === 'delete') {
    if (!canManageTemplate(record)) {
      message.warning('无权删除该流程模板')
      return
    }
    confirmDeleteTemplate(record)
  }
}

const templateColumns: DataTableColumns<any> = [
  {
    title: '流水线',
    key: 'name',
    width: 260,
    ellipsis: { tooltip: true },
    render: (row) =>
      h('div', { class: 'pipeline-name-cell' }, [
        h(NButton, { text: true, size: 'small', onClick: () => openDetailDrawer(row) }, { default: () => row.name }),
        h('span', row.description || '暂无描述'),
      ]),
  },
  {
    title: '状态',
    key: 'status',
    align: 'center',
    width: 82,
    render: (row) =>
      h(StatusBadge, {
        status: row.is_active ? 'success' : 'muted',
        text: row.is_active ? '启用' : '停用',
      }),
  },
  {
    title: '拓扑',
    key: 'topology',
    width: 160,
    render: (row) =>
      h('div', { class: 'pipeline-topology' }, [
        h('span', [h('strong', String(row.nodes?.length || 0)), ' 节点']),
        h('span', [h('strong', String(row.edges?.length || 0)), ' 连线']),
        h('em', templateNodeTypeSummary(row)),
      ]),
  },
  {
    title: '最近执行',
    key: 'latestRun',
    width: 190,
    render: (row) => {
      const run = latestRun(row.id)
      if (!run) return h('span', { class: 'table-muted' }, '暂无执行')
      return h('div', { class: 'pipeline-run-summary' }, [
        h('div', { class: 'pipeline-run-summary__main' }, [
          h(NButton, {
            text: true, size: 'small',
            onClick: () => router.push(`/flows/runs/${run.id}`),
          }, { default: () => latestRunTitle(run) }),
          h('span', `${latestRunTrigger(run)} / ${latestRunActor(run)}`),
          h('time', latestRunTime(run)),
        ]),
        h(StatusBadge, { status: run.status, text: statusText(run.status) }),
      ])
    },
  },
  {
    title: '负责人/更新',
    key: 'owner',
    width: 150,
    render: (row) =>
      h(MetaInfoLines, {
        createdText: row.created_by_name || '-',
        updatedText: formatTime(row.updated_at || row.created_at),
      }),
  },
  {
    title: '操作',
    key: 'actions',
    align: 'left',
    width: 140,
    render: (row) =>
      h('div', { class: 'table-row-actions pipeline-actions' }, [
        canStartTemplate(row)
          ? h(NButton, {
              text: true, size: 'small',
              onClick: () => openStartModal(row),
            }, { icon: () => h(Play, { size: 14 }), default: () => '新建任务' })
          : null,
        h(NDropdown, {
          trigger: 'click',
          options: pipelineRowActions(row),
          onSelect: (key: string) => onPipelineRowAction(key, row),
        }, {
          default: () => h(NButton, { class: 'pipeline-more-btn', text: true, size: 'small', 'aria-label': '更多操作' }, {
            icon: () => h(MoreHorizontal, { size: 16 }),
          }),
        }),
      ].filter(Boolean)),
  },
]

const tablePagination = computed(() => ({
  page: templatePagination.current,
  pageSize: templatePagination.pageSize,
  itemCount: templatePagination.total,
  onChange: (page: number) => handlePageChange(page),
  onUpdatePageSize: (size: number) => handlePageSizeChange(size),
}))
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
.pipeline-template-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
  min-width: 0;
}
.pipeline-template-card {
  display: grid;
  gap: 12px;
  min-width: 0;
  padding: 14px;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
  background: var(--app-surface, #fff);
}
.pipeline-template-card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}
.pipeline-template-card__title {
  display: block;
  padding: 0;
  border: 0;
  background: none;
  color: var(--app-fg);
  font: inherit;
  font-weight: 650;
  text-align: left;
  cursor: pointer;
}
.pipeline-template-card__title:hover {
  color: var(--app-accent);
}
.pipeline-template-card__head p,
.pipeline-template-card__meta,
.pipeline-template-card__run span {
  margin: 4px 0 0;
  color: var(--app-muted);
  font-size: 12px;
  line-height: 1.4;
}
.pipeline-template-card__meta {
  display: grid;
  gap: 4px;
}
.pipeline-template-card__run {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
  align-items: center;
  min-width: 0;
  padding-top: 4px;
  border-top: 1px solid var(--app-border);
}
.pipeline-template-card__run--empty {
  display: block;
  color: var(--app-muted);
  font-size: 12px;
}
.pipeline-template-card__run > div {
  display: grid;
  gap: 2px;
  min-width: 0;
}
.pipeline-template-card__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
.pipeline-template-grid__empty {
  grid-column: 1 / -1;
  padding: 32px 0;
}
.pipeline-template-grid__pager {
  grid-column: 1 / -1;
  display: flex;
  justify-content: flex-end;
  padding-top: 4px;
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
  grid-template-columns: auto minmax(200px, 320px) 140px 140px minmax(0, 1fr);
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
