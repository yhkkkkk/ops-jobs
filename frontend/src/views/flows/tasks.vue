<template>
  <div class="app-page flow-task-page">
    <PageHeader eyebrow="标准运维" title="执行任务" description="">
      <template #actions>
        <n-space>
          <n-button @click="router.push('/flows')"><template #icon><GitBranch  /></template>流程模板</n-button>
          <n-button @click="loadTasks"><template #icon><RefreshCw  /></template>刷新</n-button>
        </n-space>
      </template>
    </PageHeader>

    <DataToolbar title="筛选执行任务" description="按任务、流程、状态和触发方式定位运行实例。" :active-count="activeFilterCount">
      <div class="app-filter-grid flow-task-filter-grid">
        <n-input v-model:value="filters.search" clearable placeholder="任务名称或流程模板" @press-enter="resetPage" @clear="resetPage" />
        <n-select v-model:value="filters.status" clearable placeholder="任务状态" @update:value="resetPage" :options="(statusOptions || []).map((item: any) => ({ label: String(item.label), value: String(item.value) }))" />
                <n-select v-model:value="filters.trigger" clearable placeholder="触发方式" @update:value="resetPage" :options="selectOptions1" />
        <div class="app-filter-grid__actions"><n-space><n-button type="primary" @click="resetPage"><template #icon><Search  /></template>搜索</n-button><n-button @click="resetFilters"><template #icon><RefreshCw  /></template>重置</n-button></n-space></div>
      </div>
    </DataToolbar>

    <DetailPanel title="执行任务" :description="`共 ${pagination.total} 个任务，当前页 ${filteredTasks.length} 个`">
      <n-data-table
        class="flow-task-table"
        :row-key="(row: any) => row.id"
        :loading="loading"
        :columns="columns"
        :data="filteredTasks"
        :pagination="tablePagination"
      />
    </DetailPanel>
  </div>
</template>

<script setup lang="ts">
import { computed, h, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { flowApi } from '@/api/ops'
import { DataToolbar, DetailPanel, PageHeader, StatusBadge } from '@/components/app'
import type { FlowRun, FlowRunStatus } from '@/types'
import { flowRunStatusText } from './flowUtils'
import { NButton, NDataTable, NInput, NSelect, NSpace, type DataTableColumns, useMessage } from 'naive-ui'
import { Eye, GitBranch, RefreshCw, Search } from 'lucide-vue-next'

const message = useMessage()
const router = useRouter()
const loading = ref(false)
const tasks = ref<FlowRun[]>([])
const filters = reactive({ search: '', status: '', trigger: '' })
const pagination = reactive({ current: 1, pageSize: 15, total: 0, showTotal: true, showPageSize: true })
const statusOptions: Array<{ value: FlowRunStatus; label: string }> = [
  { value: 'pending', label: '等待中' }, { value: 'running', label: '执行中' }, { value: 'paused', label: '已暂停' },
  { value: 'success', label: '成功' }, { value: 'failed', label: '失败' }, { value: 'cancelled', label: '已取消' },
]
const columns: DataTableColumns<any> = [
  {
    title: '任务',
    key: 'task',
    minWidth: 260,
    render: (row) =>
      h('div', { class: 'task-name-cell' }, [
        h(NButton, { text: true, size: 'small', onClick: () => openTask(row) }, { default: () => row.name || row.template_name || '未命名任务' }),
        h('span', `${triggerText(row.trigger_type)} / ${row.started_by_name || '-'}`),
      ]),
  },
  {
    title: '流程模板',
    key: 'template',
    minWidth: 190,
    render: (row) =>
      h(NButton, { text: true, size: 'small', onClick: () => router.push(`/flows/${row.template}/detail`) }, { default: () => row.template_name || '-' }),
  },
  {
    title: '状态',
    key: 'status',
    width: 110,
    render: (row) => h(StatusBadge, { status: row.status, text: statusText(row.status) }),
  },
  { title: '开始时间', key: 'startedAt', width: 180, render: (row) => formatTime(row.started_at || row.created_at) },
  {
    title: '操作',
    key: 'actions',
    width: 92,
    render: (row) =>
      h(NButton, { text: true, size: 'small', onClick: () => openTask(row) }, {
        icon: () => h(Eye, { size: 14 }),
        default: () => '查看',
      }),
  },
]

const tablePagination = computed(() => ({
  page: pagination.current,
  pageSize: pagination.pageSize,
  itemCount: pagination.total,
  onChange: (page: number) => handlePageChange(page),
  onUpdatePageSize: (size: number) => handlePageSizeChange(size),
}))
const normalizePage = <T,>(value: any) => {
  const content = value?.results ? value : value?.data?.results ? value.data : value?.data
  return {
    items: (content?.results || []) as T[],
    total: Number(content?.total ?? content?.results?.length ?? 0),
  }
}
const statusText = (status: FlowRunStatus) => flowRunStatusText(status)
const triggerText = (value: string) => ({ manual: '手动触发', scheduled: '定时触发', api: 'API 触发' }[value] || value || '-')
const formatTime = (value?: string | null) => value ? new Date(value).toLocaleString('zh-CN') : '-'
const filteredTasks = computed(() => {
  const keyword = filters.search.trim().toLowerCase()
  return tasks.value.filter(task => (!keyword || `${task.name || ''} ${task.template_name || ''}`.toLowerCase().includes(keyword)) && (!filters.status || task.status === filters.status) && (!filters.trigger || task.trigger_type === filters.trigger))
})
const activeFilterCount = computed(() => Number(Boolean(filters.search)) + Number(Boolean(filters.status)) + Number(Boolean(filters.trigger)))
const resetPage = () => { pagination.current = 1; loadTasks() }
const resetFilters = () => { filters.search = ''; filters.status = ''; filters.trigger = ''; resetPage() }
const openTask = (task: FlowRun) => router.push(`/flows/runs/${task.id}`)
const loadTasks = async () => {
  loading.value = true
  try {
    const response = await flowApi.getRuns({
      search: filters.search,
      status: filters.status,
      trigger_type: filters.trigger,
      page: pagination.current,
      page_size: pagination.pageSize,
    })
    const page = normalizePage<FlowRun>(response)
    tasks.value = page.items
    pagination.total = page.total
  } catch (error) {
    console.error('加载流水线任务失败:', error)
    message.error('加载流水线任务失败')
  } finally {
    loading.value = false
  }
}
const handlePageChange = (page: number) => { pagination.current = page; loadTasks() }
const handlePageSizeChange = (pageSize: number) => { pagination.pageSize = pageSize; pagination.current = 1; loadTasks() }
onMounted(loadTasks)

// 机械转换生成的静态下拉选项
const selectOptions1 = [{ label: '手动触发', value: 'manual' }, { label: '定时触发', value: 'scheduled' }, { label: 'API 触发', value: 'api' }]
</script>

<style scoped>
.flow-task-page { display: grid; gap: 12px; min-width: 0; padding: 0; overflow-x: clip; }
.flow-task-filter-grid { grid-template-columns: minmax(240px, 360px) 160px 160px minmax(0, 1fr); align-items: end; }
.flow-task-filter-grid .app-filter-grid__actions { display: flex; justify-content: flex-end; }
.flow-task-table { min-width: 0; }
.task-name-cell { display: grid; gap: 3px; min-width: 0; }
.task-name-cell :deep(.arco-link) { justify-content: flex-start; font-weight: 650; }
.task-name-cell span { overflow: hidden; color: var(--app-muted); font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
:deep(.arco-table-th) { background: #fff; }
@media (max-width: 900px) { .flow-task-filter-grid { grid-template-columns: 1fr 1fr; } }
@media (max-width: 640px) { .flow-task-filter-grid { grid-template-columns: 1fr; } .flow-task-filter-grid .app-filter-grid__actions { justify-content: flex-start; } }
</style>
