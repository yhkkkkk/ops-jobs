<template>
  <div class="app-page flow-task-page">
    <PageHeader eyebrow="标准运维" title="执行任务" description="">
      <template #actions>
        <a-space>
          <a-button @click="router.push('/flows')"><template #icon><icon-branch /></template>流程模板</a-button>
          <a-button @click="loadTasks"><template #icon><icon-refresh /></template>刷新</a-button>
        </a-space>
      </template>
    </PageHeader>

    <DataToolbar title="筛选执行任务" description="按任务、流程、状态和触发方式定位运行实例。" :active-count="activeFilterCount">
      <div class="app-filter-grid flow-task-filter-grid">
        <a-input v-model="filters.search" allow-clear placeholder="任务名称或流程模板" @press-enter="resetPage" @clear="resetPage" />
        <a-select v-model="filters.status" allow-clear placeholder="任务状态" @change="resetPage">
          <a-option v-for="item in statusOptions" :key="item.value" :value="item.value">{{ item.label }}</a-option>
        </a-select>
        <a-select v-model="filters.trigger" allow-clear placeholder="触发方式" @change="resetPage">
          <a-option value="manual">手动触发</a-option><a-option value="scheduled">定时触发</a-option><a-option value="api">API 触发</a-option>
        </a-select>
        <div class="app-filter-grid__actions"><a-space><a-button type="primary" @click="resetPage"><template #icon><icon-search /></template>搜索</a-button><a-button @click="resetFilters"><template #icon><icon-refresh /></template>重置</a-button></a-space></div>
      </div>
    </DataToolbar>

    <DetailPanel title="执行任务" :description="`共 ${pagination.total} 个任务，当前页 ${filteredTasks.length} 个`">
      <a-table class="flow-task-table" row-key="id" :loading="loading" :columns="columns" :data="filteredTasks" :pagination="pagination" :scroll="{ x: 960 }">
        <template #task="{ record }"><div class="task-name-cell"><a-link @click="openTask(record)">{{ record.name || record.template_name || '未命名任务' }}</a-link><span>{{ triggerText(record.trigger_type) }} / {{ record.started_by_name || '-' }}</span></div></template>
        <template #template="{ record }"><a-link @click="router.push(`/flows/${record.template}/detail`)">{{ record.template_name || '-' }}</a-link></template>
        <template #status="{ record }"><StatusBadge :status="record.status" :text="statusText(record.status)" /></template>
        <template #startedAt="{ record }">{{ formatTime(record.started_at || record.created_at) }}</template>
        <template #actions="{ record }"><a-button type="text" size="small" @click="openTask(record)"><template #icon><icon-eye /></template>查看</a-button></template>
      </a-table>
    </DetailPanel>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import { flowApi } from '@/api/ops'
import { DataToolbar, DetailPanel, PageHeader, StatusBadge } from '@/components/app'
import type { FlowRun, FlowRunStatus } from '@/types'
import { flowRunStatusText } from './flowUtils'

const router = useRouter()
const loading = ref(false)
const tasks = ref<FlowRun[]>([])
const filters = reactive({ search: '', status: '', trigger: '' })
const pagination = reactive({ current: 1, pageSize: 15, total: 0, showTotal: true, showPageSize: true })
const statusOptions: Array<{ value: FlowRunStatus; label: string }> = [
  { value: 'pending', label: '等待中' }, { value: 'running', label: '执行中' }, { value: 'paused', label: '已暂停' },
  { value: 'success', label: '成功' }, { value: 'failed', label: '失败' }, { value: 'cancelled', label: '已取消' },
]
const columns = [
  { title: '任务', key: 'task', slotName: 'task', minWidth: 260 }, { title: '流程模板', key: 'template', slotName: 'template', minWidth: 190 },
  { title: '状态', key: 'status', slotName: 'status', width: 110 }, { title: '开始时间', key: 'startedAt', slotName: 'startedAt', width: 180 },
  { title: '操作', key: 'actions', slotName: 'actions', width: 92, fixed: 'right' },
]
const normalizeList = <T,>(value: any): T[] => Array.isArray(value) ? value : value?.results || value?.data || []
const statusText = (status: FlowRunStatus) => flowRunStatusText(status)
const triggerText = (value: string) => ({ manual: '手动触发', scheduled: '定时触发', api: 'API 触发' }[value] || value || '-')
const formatTime = (value?: string | null) => value ? new Date(value).toLocaleString('zh-CN') : '-'
const filteredTasks = computed(() => {
  const keyword = filters.search.trim().toLowerCase()
  return tasks.value.filter(task => (!keyword || `${task.name || ''} ${task.template_name || ''}`.toLowerCase().includes(keyword)) && (!filters.status || task.status === filters.status) && (!filters.trigger || task.trigger_type === filters.trigger))
})
const activeFilterCount = computed(() => Number(Boolean(filters.search)) + Number(Boolean(filters.status)) + Number(Boolean(filters.trigger)))
const resetPage = () => { pagination.current = 1 }
const resetFilters = () => { filters.search = ''; filters.status = ''; filters.trigger = ''; resetPage() }
const openTask = (task: FlowRun) => router.push(`/flows/runs/${task.id}`)
const loadTasks = async () => { loading.value = true; try { tasks.value = normalizeList<FlowRun>(await flowApi.getRuns()) } catch (error) { console.error('加载流水线任务失败:', error); Message.error('加载流水线任务失败') } finally { loading.value = false } }
watch(filteredTasks, value => { pagination.total = value.length }, { immediate: true })
onMounted(loadTasks)
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