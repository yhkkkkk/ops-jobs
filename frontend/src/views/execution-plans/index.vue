<template>
  <div
    class="app-page execution-plans-page"
    v-page-permissions="{
      resourceType: 'executionplan',
      permissions: ['view', 'add', 'change', 'delete', 'execute'],
      resourceIds: plans.map(p => p.id)
    }"
  >
    <PageHeader
      eyebrow="执行编排"
      title="执行方案管理"
      description="基于作业模板创建和维护具体执行方案，跟踪步骤、引用和同步状态。"
    >
      <template #actions>
        <n-space>
          <n-button @click="handleRefresh">
            <template #icon>
              <RefreshCw  />
            </template>
            刷新
          </n-button>
<n-dropdown
            trigger="click"
            :options="[
              { label: '基于作业模板创建', key: 'select-template' },
              { label: '空白方案', key: 'blank' },
            ]"
            @select="handleCreateAction"
          >
            <n-button
              type="primary"
              v-permission="{ resourceType: 'executionplan', permission: 'add' }"
            >
              <template #icon>
                <Plus  />
              </template>
              创建方案
              <ChevronDown :size="14" />
            </n-button>
          </n-dropdown>
          <n-button
            secondary
            :disabled="selectedRowKeys.length === 0"
            @click="handleBatchSync"
            v-permission="{ resourceType: 'executionplan', permission: 'change' }"
          >
            <template #icon>
              <RefreshCw  />
            </template>
            批量同步
          </n-button>
        </n-space>
      </template>
    </PageHeader>

    <DataToolbar
      title="筛选执行方案"
      description="按方案名称、所属模板、维护人和收藏状态定位执行编排。"
      :active-count="executionPlanActiveFilterCount"
    >
      <div class="form-grid-row">
        <div class="form-grid-col" style="grid-column: span 4">
          <n-input
            v-model:value="searchForm.search"
            placeholder="方案名称"
            clearable
            @press-enter="handleSearch"
            @clear="handleSearch"
            style="width: 100%"
          />
        </div>
        <div class="form-grid-col" style="grid-column: span 4">
          <n-select
            v-model:value="searchForm.template_id"
            placeholder="所属模板"
            clearable
            @update:value="handleSearch"
            @clear="handleSearch"
            style="width: 100%"
            :loading="templateLoading" :options="(templates || []).map((template: any) => ({ label: String(template.name), value: String(template.id) }))" />
        </div>
        <div class="form-grid-col" style="grid-column: span 3">
          <n-select
            v-model:value="searchForm.created_by"
            placeholder="创建者"
            clearable
            filterable
           
            @search="handleCreatorSearch"
            @update:value="handleSearch"
            @clear="handleSearch"
            style="width: 100%" :options="(filteredCreators || []).map((user: any) => ({ label: String(user.name), value: String(user.id) }))" />
        </div>
        <div class="form-grid-col" style="grid-column: span 3">
          <n-select
            v-model:value="searchForm.updated_by"
            placeholder="更新者"
            clearable
            filterable
           
            @search="handleUpdaterSearch"
            @update:value="handleSearch"
            @clear="handleSearch"
            style="width: 100%" :options="(filteredUpdaters || []).map((user: any) => ({ label: String(user.name), value: String(user.id) }))" />
        </div>
        <div class="form-grid-col" style="grid-column: span 4">
          <div class="filter-group">
            <div class="filter-switch">
              <span class="filter-label">收藏</span>
              <n-switch v-model:value="searchForm.favorites_only" @change="handleSearch" />
            </div>
            <div class="filter-switch">
              <span class="filter-label">我的方案</span>
              <n-switch v-model:value="searchForm.my_plans_only" @change="handleSearch" />
            </div>
          </div>
        </div>
        <div class="form-grid-col" style="grid-column: span 6">
          <div class="search-actions">
            <n-space>
              <n-button type="primary" @click="handleSearch">
                <template #icon>
                  <Search  />
                </template>
                搜索
              </n-button>
              <n-button @click="handleReset">
                <template #icon>
                  <RefreshCw  />
                </template>
                重置
              </n-button>
            </n-space>
          </div>
        </div>
      </div>
      <ActiveFiltersBar
        :items="activeFilterItems"
        @clear="handleClearFilter"
        @clear-all="handleReset"
      />
    </DataToolbar>

    <DetailPanel
      title="方案列表"
      :description="`共 ${pagination.total} 个方案，当前页 ${plans.length} 个`"
    >
      <n-data-table
        :columns="columns"
        :data="plans"
        :loading="loading"
        :pagination="tablePagination"
        :checked-row-keys="selectedRowKeys"
        :row-key="(row: any) => row.id"
        remote
        @update:checked-row-keys="handleSelectionChange"
      />
    </DetailPanel>
    <BatchSyncPreviewModal
      v-model="batchSyncModalVisible"
      :plan-ids="batchSyncPlanIds"
      @sync-success="handleBatchSyncSuccess"
    />

    <!-- 模板选择弹窗 -->
    <n-modal preset="card" :style="{ width: '800px' }"
      v-model:show="templateSelectVisible"
      title="选择作业模板"
     
      @ok="handleTemplateSelect"
      @cancel="handleTemplateSelectCancel"
    >
      <div class="template-select-content">
        <n-input
          v-model:value="templateSearchText"
          placeholder="搜索模板名称"
          clearable
          style="margin-bottom: 16px"
        >
          <template #prefix>
            <Search  />
          </template>
        </n-input>

        <n-data-table
          :columns="templateColumns"
          :data="filteredTemplatesForSelect"
          :loading="templateLoading"
          :pagination="false"
          :row-key="(row: any) => row.id"
          :checked-row-keys="selectedTemplateKeys"
          max-height="400px"
          :row-props="(row: any) => ({ onClick: () => handleTemplateRowClick(row) })"
          @update:checked-row-keys="(keys: any[]) => handleTemplateRowSelect(keys)"
        />
      </div>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, h, onMounted, reactive, ref, resolveDirective, type VNode, withDirectives } from 'vue'
import { useRouter } from 'vue-router'
import { executionPlanApi, jobTemplateApi } from '@/api/ops'
import { scheduledJobApi } from '@/api/scheduler'
import type { ExecutionPlan, JobTemplate } from '@/types'
import { usePermissionsStore } from '@/stores/permissions'
import { useFavoritesStore } from '@/stores/favorites'
import { useAuthStore } from '@/stores/auth'
import { defineAsyncComponent } from 'vue'
import MetaInfoLines from '@/components/MetaInfoLines.vue'
import ActiveFiltersBar from '@/components/ActiveFiltersBar.vue'
import { useFilterQuerySync, parseBooleanQuery, parseNumberQuery, toBooleanQuery } from '@/composables/useFilterQuerySync'
import { DataToolbar, DetailPanel, PageHeader, countActiveFilters } from '@/components/app'
import { NButton, NDataTable, NDropdown, NInput, NModal, NSelect, NSpace, NSwitch, NTag, type DataTableColumns, useDialog, useMessage } from 'naive-ui'
import { CalendarClock, ChevronDown, Eye, FileText, MoreHorizontal, Pencil, Play, Plus, RefreshCw, Search, Star, Trash2 } from 'lucide-vue-next'
// @ts-ignore - some editors/tsserver may not immediately include newly added .vue files in project file list
const BatchSyncPreviewModal = defineAsyncComponent(() => import('./components/BatchSyncPreviewModal.vue'))

const permissionsStore = usePermissionsStore()
const favoritesStore = useFavoritesStore()
const authStore = useAuthStore()

const message = useMessage()
const dialog = useDialog()
const router = useRouter()

// 响应式数据
const loading = ref(false)
const templateLoading = ref(false)
const plans = ref<ExecutionPlan[]>([])
const templates = ref<JobTemplate[]>([])

// 可用用户列表（创建者）
const availableUsers = ref<Array<{id: number, username: string, name: string}>>([])

// 创建者搜索过滤结果
const filteredCreators = ref<Array<{id: number, username: string, name: string}>>([])

// 更新者搜索过滤结果
const filteredUpdaters = ref<Array<{id: number, username: string, name: string}>>([])

// 模板选择相关
const templateSelectVisible = ref(false)
const templateSearchText = ref('')
const selectedTemplateKeys = ref<number[]>([])

// 批量操作相关
const selectedRowKeys = ref<number[]>([])
// rowSelection 配置（与 Agent 页面一致）
const rowSelection = reactive({
  type: 'checkbox',
  showCheckedAll: true,
  onlyCurrent: false
})
// 批量同步模态状态
const batchSyncModalVisible = ref(false)
let batchSyncPlanIds: number[] = []

const defaultSearchForm = () => ({
  search: '',
  template_id: undefined as number | undefined,
  favorites_only: false,
  my_plans_only: false,
  created_by: undefined as number | undefined,
  updated_by: undefined as number | undefined
})

// 搜索表单
const searchForm = reactive(defaultSearchForm())

// 收藏相关方法
const isFavorite = (id: number) => favoritesStore.isFavorite('execution_plan', id)

const toggleFavorite = async (id: number) => {
  try {
    const isFavorited = await favoritesStore.toggleFavorite('execution_plan', id, 'personal')
    message.success(isFavorited ? '已添加到收藏' : '已取消收藏')
  } catch (e) {
    console.error('切换收藏状态失败:', e)
    message.error('操作失败')
  }
}

// 排序
const ordering = ref('')

// 分页配置
const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  showTotal: true,
  showPageSize: true,
  pageSizeOptions: ['10', '20', '50', '100']
})

const { initFromQuery, syncToQuery } = useFilterQuerySync({
  searchForm,
  pagination,
  ordering,
  fields: [
    { key: 'search' },
    {
      key: 'template_id',
      toQuery: (value?: number) => (value ? String(value) : undefined),
      fromQuery: (value) => parseNumberQuery(value)
    },
    {
      key: 'favorites_only',
      toQuery: (value: boolean) => toBooleanQuery(value),
      fromQuery: (value) => parseBooleanQuery(value) ?? false
    },
    {
      key: 'my_plans_only',
      toQuery: (value: boolean) => toBooleanQuery(value),
      fromQuery: (value) => parseBooleanQuery(value) ?? false
    },
    {
      key: 'created_by',
      toQuery: (value?: number) => (value ? String(value) : undefined),
      fromQuery: (value) => parseNumberQuery(value)
    },
    {
      key: 'updated_by',
      toQuery: (value?: number) => (value ? String(value) : undefined),
      fromQuery: (value) => parseNumberQuery(value)
    }
  ]
})

const resolveUserName = (id?: number) => {
  if (!id) return ''
  return availableUsers.value.find(user => user.id === id)?.name || String(id)
}

const resolveTemplateName = (id?: number) => {
  if (!id) return ''
  return templates.value.find(template => template.id === id)?.name || String(id)
}

const activeFilterItems = computed(() => [
  { key: 'search', label: '方案名称', display: searchForm.search },
  { key: 'template_id', label: '所属模板', display: resolveTemplateName(searchForm.template_id) },
  { key: 'created_by', label: '创建者', display: searchForm.my_plans_only ? '' : resolveUserName(searchForm.created_by) },
  { key: 'updated_by', label: '更新者', display: resolveUserName(searchForm.updated_by) },
  { key: 'favorites_only', label: '收藏', display: searchForm.favorites_only ? '仅收藏' : '' },
  { key: 'my_plans_only', label: '我的方案', display: searchForm.my_plans_only ? '仅我的' : '' }
])

const executionPlanActiveFilterCount = computed(() => countActiveFilters(searchForm as unknown as Record<string, unknown>))

const handleClearFilter = (key: string) => {
  const defaults = defaultSearchForm()
  if (key in defaults) {
    ;(searchForm as any)[key] = (defaults as any)[key]
  }
  pagination.current = 1
  syncToQuery()
  fetchPlans()
}

// 表格列配置
const renderPlanName = (row: any) =>
  h('div', { class: 'plan-name' }, [
    h('div', { class: 'plan-name-row' }, [
      h(NButton, {
        text: true, size: 'tiny', class: 'favorite-btn',
        onClick: (e: MouseEvent) => { e.stopPropagation(); toggleFavorite(row.id) },
      }, {
        icon: () => h(Star, {
          size: 14,
          fill: isFavorite(row.id) ? '#f59e0b' : 'none',
          stroke: isFavorite(row.id) ? '#f59e0b' : 'currentColor',
        }),
      }),
      h(NButton, { text: true, size: 'small', onClick: () => handleView(row) }, { default: () => row.name }),
    ]),
    h('div', { class: 'plan-desc' }, row.description || '无描述'),
  ])

const renderPlanStats = (row: any) =>
  h('div', { class: 'stats-info' }, [
    h('div', { class: 'stat-item' }, [h('span', { class: 'stat-label' }, '步骤:'), h('span', { class: 'stat-value' }, String(row.step_count || 0))]),
    h('div', { class: 'stat-item' }, [h('span', { class: 'stat-label' }, '执行:'), h('span', { class: 'stat-value' }, String(row.total_executions || 0))]),
    h('div', { class: 'stat-item' }, [h('span', { class: 'stat-label' }, '成功率:'), h('span', { class: 'stat-value' }, `${row.success_rate || 0}%`)]),
  ])

const planRowActions = (row: any) => [
  { label: '编辑', key: 'edit', disabled: !canEditPlan(row.id), icon: () => h(Pencil, { size: 14 }) },
  { label: '执行', key: 'execute', disabled: !canExecutePlan(row.id), icon: () => h(Play, { size: 14 }) },
  { label: '定时执行', key: 'schedule', disabled: !canExecutePlan(row.id), icon: () => h(CalendarClock, { size: 14 }) },
  { label: '删除方案', key: 'delete', disabled: !canDeletePlan(row.id), icon: () => h(Trash2, { size: 14 }), props: { class: 'danger' } },
]

const onPlanRowAction = (key: string, row: any) => {
  if (key === 'edit') handleClickEdit(row)
  if (key === 'execute') handleClickExecute(row)
  if (key === 'schedule') handleClickSchedule(row)
  if (key === 'delete') handleClickMoreAction('delete', row)
}

const columns: DataTableColumns<any> = [
  {
    title: '方案名称',
    key: 'name',
    width: 250,
    ellipsis: { tooltip: true },
    render: renderPlanName,
  },
  {
    title: '所属模板',
    key: 'template',
    width: 200,
    ellipsis: { tooltip: true },
    render: (row) =>
      h('div', { class: 'template-info' }, [
        h('div', { class: 'template-name' }, row.template_name),
        h('div', { class: 'template-category' }, row.template_category || '未分类'),
      ]),
  },
  { title: '统计信息', key: 'stats', width: 180, render: renderPlanStats },
  {
    title: '被引用',
    key: 'references',
    width: 120,
    render: (row) =>
      h(NButton, { text: true, size: 'small', class: 'reference-link', onClick: () => handleViewReferences(row) }, {
        default: () => h('div', { class: 'meta-line' }, `定时：${row.scheduled_job_ref_count || 0}`),
      }),
  },
  {
    title: '创建/更新',
    key: 'created_info',
    width: 240,
    render: (row) =>
      h(MetaInfoLines, {
        createdText: `创建：${formatDateTime(row.created_at)} · ${row.created_by_name || '-'}`,
        updatedText: `更新：${row.updated_at ? formatDateTime(row.updated_at) : '-'} · ${row.updated_by_name || row.created_by_name || '-'}`,
      }),
  },
  {
    title: '操作',
    key: 'actions',
    width: 124,
    align: 'center',
    render: (row) =>
      h(NSpace, { class: 'table-row-actions', wrap: false, wrapItem: false, align: 'center' }, {
        default: () => [
          withPerm(
            h(NButton, { text: true, size: 'small', onClick: () => handleView(row) }, {
              icon: () => h(Eye, { size: 14 }),
              default: () => '查看',
            }),
            { resourceType: 'executionplan', permission: 'view', resourceId: row.id },
          ),
          h(NDropdown, {
            trigger: 'click',
            options: planRowActions(row),
            onSelect: (key: string) => onPlanRowAction(key, row),
          }, {
            default: () => h(NButton, { text: true, size: 'small', 'aria-label': '更多操作' }, {
              icon: () => h(MoreHorizontal, { size: 16 }),
            }),
          }),
        ],
      }),
  },
]

// 模板选择表格列配置
const templateColumns: DataTableColumns<any> = [
  {
    title: '模板名称',
    key: 'name',
    width: 250,
    render: (row) =>
      h('div', { class: 'template-name' }, [
        h('div', { class: 'name' }, row.name),
        h('div', { class: 'desc' }, row.description || '无描述'),
      ]),
  },
  {
    title: '分类',
    key: 'category',
    width: 100,
    render: (row) => row.category
      ? h(NTag, { type: 'info' }, { default: () => row.category })
      : h('span', { class: 'text-gray' }, '未分类'),
  },
  {
    title: '统计',
    key: 'stats',
    width: 120,
    render: (row) =>
      h('div', { class: 'stats' }, [
        h('span', `步骤: ${row.step_count || 0}`),
        h('span', `方案: ${row.plan_count || 0}`),
      ]),
  },
  { title: '创建时间', key: 'created_at', width: 150, render: (row) => formatDateTime(row.created_at) },
]

const tablePagination = computed(() => ({
  page: pagination.current,
  pageSize: pagination.pageSize,
  itemCount: pagination.total,
  pageSizes: [10, 20, 50, 100],
  showSizePicker: true,
  onChange: (page: number) => handlePageChange(page),
  onUpdatePageSize: (size: number) => handlePageSizeChange(size),
}))

const withPerm = (vnode: VNode, value: unknown) => {
  const perm = resolveDirective('permission')
  return perm ? withDirectives(vnode, [[perm, value]]) : vnode
}


// 过滤后的模板列表（用于选择）
const filteredTemplatesForSelect = computed(() => {
  if (!templateSearchText.value) return templates.value

  const search = templateSearchText.value.toLowerCase()
  return templates.value.filter(template =>
    template.name.toLowerCase().includes(search) ||
    (template.description && template.description.toLowerCase().includes(search))
  )
})

// 获取执行方案列表
const fetchPlans = async () => {
  try {
    loading.value = true
    const params = {
      page: pagination.current,
      page_size: pagination.pageSize,
      ordering: ordering.value || undefined,
      search: searchForm.search || undefined,
      template: searchForm.template_id || undefined,
      // 如果启用“我的方案”，把创建者传给后端以便服务器端过滤
      created_by: searchForm.my_plans_only ? authStore.user?.id : (searchForm.created_by || undefined),
      updated_by: searchForm.updated_by || undefined
    }

    const response = await executionPlanApi.getPlans(params)
    let resultPlans = response.results || []

    // 前端过滤收藏
    if (searchForm.favorites_only) {
      resultPlans = resultPlans.filter(p => favoritesStore.isFavorite('execution_plan', p.id))
    }

    // 前端过滤我的方案
    if (searchForm.my_plans_only) {
      resultPlans = resultPlans.filter(p => p.created_by === authStore.user?.id)
    }

    plans.value = resultPlans
    pagination.total = searchForm.favorites_only ? resultPlans.length : (response.total || 0)

    // 异步加载收藏状态
    await favoritesStore.batchCheckFavorites('execution_plan', resultPlans.map(p => p.id))

    // 拉取可用用户列表
    await fetchAvailableUsers()
  } catch (error) {
    console.error('获取执行方案列表失败:', error)
    message.error('获取执行方案列表失败')
  } finally {
    loading.value = false
  }
}

// 获取可用用户列表（创建者）
const fetchAvailableUsers = async () => {
  try {
    // 从当前执行方案列表中提取唯一用户列表
    if (plans.value.length > 0) {
      const userMap = new Map<number, {id: number, username: string, name: string}>()
      const appendUser = (id?: number, name?: string) => {
        if (!id || !name) return
        userMap.set(id, { id, username: name, name })
      }

      plans.value.forEach(plan => {
        appendUser(plan.created_by, plan.created_by_name)
        appendUser(plan.updated_by, plan.updated_by_name)
      })
      availableUsers.value = Array.from(userMap.values()).sort((a, b) => a.name.localeCompare(b.name))
      // 初始化过滤结果为全部用户
      filteredCreators.value = [...availableUsers.value]
      filteredUpdaters.value = [...availableUsers.value]
    }
  } catch (error) {
    console.error('获取用户列表失败:', error)
  }
}

const filterUsers = (searchValue: string) => {
  if (!searchValue.trim()) {
    return [...availableUsers.value]
  }

  const searchTerm = searchValue.toLowerCase().trim()
  return availableUsers.value.filter(user =>
    user.name.toLowerCase().includes(searchTerm) ||
    user.username.toLowerCase().includes(searchTerm)
  )
}

// 处理创建者搜索
const handleCreatorSearch = (searchValue: string) => {
  filteredCreators.value = filterUsers(searchValue)
}

// 处理更新者搜索
const handleUpdaterSearch = (searchValue: string) => {
  filteredUpdaters.value = filterUsers(searchValue)
}

// 获取模板列表（用于筛选）
const fetchTemplates = async () => {
  try {
    templateLoading.value = true
    const response = await jobTemplateApi.getTemplates({ page_size: 20 })
    templates.value = response.results || []
  } catch (error) {
    console.error('获取模板列表失败:', error)
  } finally {
    templateLoading.value = false
  }
}

// 搜索
const handleSearch = () => {
  pagination.current = 1
  syncToQuery()
  fetchPlans()
}

// 重置搜索
const handleReset = () => {
  Object.assign(searchForm, defaultSearchForm())
  // 重置创建者/更新者过滤
  filteredCreators.value = [...availableUsers.value]
  filteredUpdaters.value = [...availableUsers.value]
  pagination.current = 1
  syncToQuery()
  fetchPlans()
}

// 刷新
const handleRefresh = () => {
  fetchPlans()
}

// 分页处理
const handlePageChange = (page: number) => {
  pagination.current = page
  selectedRowKeys.value = [] // 清空选择
  syncToQuery()
  fetchPlans()
}

const handlePageSizeChange = (pageSize: number) => {
  pagination.pageSize = pageSize
  pagination.current = 1
  selectedRowKeys.value = [] // 清空选择
  syncToQuery()
  fetchPlans()
}

// 创建方案操作
const handleCreateAction = (action: string) => {
  if (action === 'select-template') {
    templateSelectVisible.value = true
    if (templates.value.length === 0) {
      fetchTemplates()
    }
  } else if (action === 'blank') {
    router.push('/execution-plans/create')
  }
}

// 模板选择
const handleTemplateRowSelect = (selectedKeys: number[]) => {
  selectedTemplateKeys.value = selectedKeys
}

const handleTemplateRowClick = (record: any) => {
  if (record && record.id) {
    selectedTemplateKeys.value = [record.id]
  }
}

const handleSelectionChange = (rowKeys: (string | number)[]) => {
  selectedRowKeys.value = rowKeys as number[]
}

// 确认选择模板
const handleTemplateSelect = () => {
  if (selectedTemplateKeys.value.length === 0) {
    message.warning('请选择一个模板')
    return
  }

  const templateId = selectedTemplateKeys.value[0]
  router.push(`/execution-plans/create?template_id=${templateId}`)
  templateSelectVisible.value = false
}

// 取消模板选择
const handleTemplateSelectCancel = () => {
  templateSelectVisible.value = false
  selectedTemplateKeys.value = []
  templateSearchText.value = ''
}

// 批量同步 - 打开预览模态，由模态执行真正的同步
const handleBatchSync = () => {
  if (selectedRowKeys.value.length === 0) {
    message.warning('请先选择要同步的执行方案')
    return
  }
  batchSyncPlanIds = [...selectedRowKeys.value]
  batchSyncModalVisible.value = true
}

const handleBatchSyncSuccess = () => {
  selectedRowKeys.value = []
  batchSyncModalVisible.value = false
  fetchPlans()
}

// 查看方案
const handleView = (plan: ExecutionPlan) => {
  router.push(`/execution-plans/detail/${plan.id}`)
}

// 编辑方案
const handleEdit = (plan: ExecutionPlan) => {
  router.push(`/execution-plans/${plan.id}/edit`)
}

const canEditPlan = (planId: number): boolean => {
  if (permissionsStore.isSuperUser) return true
  return (
    permissionsStore.hasPermission('executionplan', 'change', planId) ||
    permissionsStore.hasPermission('executionplan', 'change')
  )
}

const handleClickEdit = (plan: ExecutionPlan) => {
  if (!canEditPlan(plan.id)) {
    message.warning('没有权限执行此操作，请联系管理员开放权限')
    return
  }
  handleEdit(plan)
}

// 执行方案
const handleExecute = (plan: ExecutionPlan) => {
  router.push(`/execution-plans/detail/${plan.id}/execute`)
}

const handleSchedule = (plan: ExecutionPlan) => {
  router.push(`/scheduled-tasks/create?plan_id=${plan.id}`)
}

const canExecutePlan = (planId: number): boolean => {
  if (permissionsStore.isSuperUser) return true
  return (
    permissionsStore.hasPermission('executionplan', 'execute', planId) ||
    permissionsStore.hasPermission('executionplan', 'execute')
  )
}

const handleClickExecute = (plan: ExecutionPlan) => {
  if (!canExecutePlan(plan.id)) {
    message.warning('没有权限执行此操作，请联系管理员开放权限')
    return
  }
  handleExecute(plan)
}

const handleClickSchedule = (plan: ExecutionPlan) => {
  if (!canExecutePlan(plan.id)) {
    message.warning('没有权限执行此操作，请联系管理员开放权限')
    return
  }
  handleSchedule(plan)
}

// 更多操作
const handleMoreAction = async (action: string, plan: ExecutionPlan) => {
  switch (action) {
    case 'delete':
      handleDelete(plan)
      break
  }
}

const handleClickMoreAction = async (action: string, plan: ExecutionPlan) => {
  if (action === 'delete' && !canDeletePlan(plan.id)) {
    message.warning('没有权限执行此操作，请联系管理员开放权限')
    return
  }
  await handleMoreAction(action, plan)
}

// 删除方案
const handleDelete = async (plan: ExecutionPlan) => {
  let jobRefs: Array<{ id: number; name: string }> = []
  let total = 0
  try {
    const res = await scheduledJobApi.list({ execution_plan: plan.id, page_size: 5 })
    jobRefs = res.results || []
    total = res.total || jobRefs.length
  } catch (error) {
    console.error('获取定时任务引用失败:', error)
  }

  const hasRefs = total > 0
  const sampleNames = jobRefs.map(item => item.name).join('、')
  const refText = total > 5 ? `${sampleNames} 等 ${total} 个` : (sampleNames || '无')

  dialog.warning({
    title: hasRefs ? '无法删除' : '确认删除',
    content: `执行方案「${plan.name}」引用情况：定时任务(${total})：${refText}`,
    positiveText: '确认删除',
    negativeText: '取消',
    positiveButtonProps: { type: 'error', disabled: hasRefs },
    onPositiveClick: async () => {
      if (hasRefs) return
      try {
        await executionPlanApi.deletePlan(plan.id)
        message.success('方案删除成功')
        await fetchPlans()
      } catch (error: any) {
        const message = error?.response?.data?.message || '删除方案失败'
        console.error('删除方案失败:', error)
        message.error(message)
      }
    }
  })
}

const handleViewReferences = async (plan: ExecutionPlan) => {
  let references = { scheduled_jobs: [] as Array<{ id: number; name: string }> }
  try {
    references = await executionPlanApi.getReferences(plan.id)
  } catch (error: any) {
    const message = error?.response?.data?.message || '获取引用关系失败'
    message.error(message)
    console.error('获取引用关系失败:', error)
    return
  }

  const resolveHref = (path: string) => router.resolve({ path }).href

  let modalClose: (() => void) | null = null

  const renderLinks = (items: Array<{ id: number; name: string }>) => {
    if (!items.length) return '无'
    const sample = items.slice(0, 5)
    const nodes: any[] = []
    sample.forEach((item, index) => {
      const path = `/scheduled-tasks/detail/${item.id}`
      nodes.push(h('a', {
        href: resolveHref(path),
        style: 'color: #165DFF; text-decoration: none; cursor: pointer;',
        onClick: (event: MouseEvent) => {
          event.preventDefault()
          if (modalClose) modalClose()
          const routeUrl = router.resolve({ path })
          window.open(routeUrl.href, '_blank')
        }
      }, item.name))
      if (index < sample.length - 1) nodes.push('、')
    })
    if (items.length > 5) nodes.push(` 等 ${items.length} 个`)
    return h('span', {}, nodes)
  }

  const content = h('div', { style: 'line-height:1.6;' }, [
    h('div', { style: 'margin-bottom:6px;' }, `方案：${plan.name}`),
    h('div', { style: 'font-weight:600;' }, '引用情况'),
    h('div', {}, [
      `定时任务(${references.scheduled_jobs.length}): `,
      renderLinks(references.scheduled_jobs)
    ])
  ])

  const modal = dialog.info({
    title: '引用关系',
    content: () => content,
    positiveText: '关闭'
  })
  modalClose = modal?.destroy
}

// 格式化日期时间
const formatDateTime = (dateTime: string) => {
  if (!dateTime) return '-'
  const date = new Date(dateTime)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

const canDeletePlan = (planId: number): boolean => {
  if (permissionsStore.isSuperUser) return true
  return (
    permissionsStore.hasPermission('executionplan', 'delete', planId) ||
    permissionsStore.hasPermission('executionplan', 'delete')
  )
}

// 生命周期
onMounted(() => {
  initFromQuery()
  fetchPlans()
  fetchTemplates()
})
</script>

<style scoped>
.execution-plans-page {
  padding: 0;
}

.page-header {
  background: white;
  border-radius: 6px;
  margin-bottom: 16px;
  padding: 20px 24px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.header-left h2 {
  margin: 0 0 4px 0;
  font-size: 20px;
  font-weight: 600;
  color: var(--app-fg);
}

.header-desc {
  margin: 0;
  color: var(--app-muted);
  font-size: 14px;
}

.mb-4 {
  margin-bottom: 16px;
}

/* 搜索按钮定位（与作业模板一致） */
.search-actions {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  width: 100%;
}

.filter-group {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  height: 32px;
}

.filter-switch {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 32px;
}

.filter-label {
  color: var(--app-muted);
  font-size: 12px;
}

/* 表格内容样式 */
.plan-name {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.plan-name-row {
  display: flex;
  align-items: center;
  gap: 4px;
}

.favorite-btn {
  padding: 0 4px;
  min-width: auto;
}

.favorite-icon {
  font-size: 14px;
  color: var(--app-muted);
  transition: color 0.2s;
}

.favorite-icon.active {
  color: var(--color-warning-6);
}

.favorite-btn:hover .favorite-icon {
  color: var(--color-warning-5);
}

.plan-desc {
  font-size: 12px;
  color: var(--app-muted);
  line-height: 1.4;
}

.template-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.template-name {
  font-weight: 500;
  color: var(--app-fg);
}

.template-category {
  font-size: 12px;
  color: var(--app-muted);
}

.reference-link {
  display: inline-block;
}

.reference-link:hover .meta-line {
  color: var(--app-accent);
}

.meta-line {
  font-size: 12px;
  line-height: 1.4;
  color: var(--app-muted);
}

.stats-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
}

.stat-label {
  color: var(--app-muted);
  min-width: 32px;
}

.stat-value {
  color: var(--app-fg);
  font-weight: 500;
}

.created-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.created-by {
  font-weight: 500;
  color: var(--app-fg);
}

.created-time {
  font-size: 12px;
  color: var(--app-muted);
}

.disabled-option {
  opacity: 0.5;
  cursor: not-allowed;
}

/* 表格样式优化 */
:deep(.arco-table) {
  .arco-table-th {
    background-color: #fff !important;
    font-weight: 600;
  }

  .arco-table-td {
    border-bottom: 1px solid var(--app-border);
  }

  .arco-table-tbody .arco-table-tr:hover .arco-table-td {
    background-color: var(--app-surface);
  }


}

/* 模板选择弹窗样式 */
.template-select-content {
  max-height: 500px;
}

.template-name .name {
  font-weight: 500;
  color: var(--app-fg);
  margin-bottom: 4px;
}

.template-name .desc {
  font-size: 12px;
  color: var(--app-muted);
}

.stats {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 12px;
  color: var(--app-muted);
}

.template-select-content ::deep(.arco-table-selection) {
  width: 50px;
}

.text-gray {
  color: var(--app-muted);
}
</style>
