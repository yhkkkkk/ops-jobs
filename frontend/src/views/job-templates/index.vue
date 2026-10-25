<template>
  <div
    class="app-page job-templates-page"
    v-page-permissions="{
      resourceType: 'jobtemplate',
      permissions: ['view', 'add', 'change', 'delete'],
      resourceIds: templates.map(t => t.id)
    }"
  >
    <PageHeader
      dense
      eyebrow="作业资产"
      title="作业模板"
      description="维护模板步骤、标签、执行方案引用和同步状态。"
    >
      <template #actions>
        <n-space>
          <n-button @click="fetchTemplates">
            <template #icon>
              <RefreshCw  />
            </template>
            刷新
          </n-button>
          <n-button
            type="primary"
            @click="handleCreate"
            v-permission="{ resourceType: 'jobtemplate', permission: 'add' }"
          >
            <template #icon>
              <Plus  />
            </template>
            新建模板
          </n-button>
        </n-space>
      </template>
    </PageHeader>

    <DataToolbar
      title="筛选作业模板"
      description="按名称、分类、标签、维护人和收藏状态过滤作业资产。"
      :active-count="jobTemplateActiveFilterCount"
    >
      <div class="app-filter-grid template-filter-grid">
        <div>
          <n-input
            v-model:value="searchForm.search"
            placeholder="模板名称"
            clearable
            @press-enter="handleSearch"
            @clear="handleSearch"
          />
        </div>
        <div>
                    <n-select
            v-model:value="searchForm.category"
            placeholder="分类"
            clearable
            @update:value="handleSearch"
            @clear="handleSearch" :options="(availableTags || []).map((tag: any) => ({ label: String(tag), value: String(tag) }))" />
        </div>
        <div>
          <n-select
            v-model:value="searchForm.created_by"
            placeholder="创建者"
            clearable
            filterable
           
            @search="handleCreatorSearch"
            @update:value="handleSearch"
            @clear="handleSearch" :options="(filteredCreators || []).map((user: any) => ({ label: String(user.name), value: String(user.id) }))" />
        </div>
        <div>
          <n-select
            v-model:value="searchForm.updated_by"
            placeholder="更新者"
            clearable
            filterable
           
            @search="handleUpdaterSearch"
            @update:value="handleSearch"
            @clear="handleSearch" :options="(filteredUpdaters || []).map((user: any) => ({ label: String(user.name), value: String(user.id) }))" />
        </div>
        <div>
          <div class="filter-group">
            <div class="filter-switch">
              <span class="filter-label">收藏</span>
              <n-switch v-model:value="searchForm.favorites_only" @change="handleSearch" />
            </div>
            <div class="filter-switch">
              <span class="filter-label">我的作业</span>
              <n-switch v-model:value="searchForm.my_templates_only" @change="handleSearch" />
            </div>
          </div>
        </div>
        <div class="app-filter-grid__actions">
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
      class="template-table-panel"
      title="模板列表"
      :description="`共 ${pagination.total} 个模板，当前页 ${templates.length} 个`"
    >
      <n-data-table
        class="template-data-table"
        :columns="columns"
        :data="templates"
        :loading="loading"
        :pagination="tablePagination"
        remote
        :row-key="(row: any) => row.id"
      />
    </DetailPanel>

    <!-- 同步确认对话框 -->
    <SyncConfirmModal
      v-model:visible="syncModalVisible"
      :template-id="syncTemplateId"
      :template-name="syncTemplateName"
      @sync-success="handleSyncSuccess"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, h, onMounted, reactive, ref, resolveDirective, type VNode, withDirectives } from 'vue'
import { useRouter } from 'vue-router'
import { jobTemplateApi } from '@/api/ops'
import type { JobTemplate } from '@/types'
import SyncConfirmModal from './components/SyncConfirmModal.vue'
import { usePermissionsStore } from '@/stores/permissions'
import { useFavoritesStore } from '@/stores/favorites'
import MetaInfoLines from '@/components/MetaInfoLines.vue'
import ActiveFiltersBar from '@/components/ActiveFiltersBar.vue'
import { useFilterQuerySync, parseBooleanQuery, parseNumberQuery, parseStringArrayQuery, toBooleanQuery } from '@/composables/useFilterQuerySync'
import { useAuthStore } from '@/stores/auth'
import { DataToolbar, DetailPanel, PageHeader, countActiveFilters } from '@/components/app'
import { NBadge, NButton, NDataTable, NDropdown, NInput, NSelect, NSpace, NSwitch, NTag, type DataTableColumns, useDialog, useMessage } from 'naive-ui'
import { Copy, Eye, List, MoreHorizontal, Pencil, Plus, RefreshCw, Search, Star, Trash2 } from 'lucide-vue-next'

const permissionsStore = usePermissionsStore()
const favoritesStore = useFavoritesStore()
const authStore = useAuthStore()

const message = useMessage()
const dialog = useDialog()
const router = useRouter()

// 响应式数据
const loading = ref(false)
const templates = ref<JobTemplate[]>([])

// 同步确认对话框
const syncModalVisible = ref(false)
const syncTemplateId = ref<number>()
const syncTemplateName = ref<string>()

const defaultSearchForm = () => ({
  search: '',
  category: '',
  tags: [] as string[],
  favorites_only: false,
  my_templates_only: false,
  created_by: undefined as number | undefined,
  updated_by: undefined as number | undefined
})

// 搜索表单
const searchForm = reactive(defaultSearchForm())

// 收藏相关方法
const isFavorite = (id: number) => favoritesStore.isFavorite('job_template', id)

const toggleFavorite = async (id: number) => {
  try {
    const isFavorited = await favoritesStore.toggleFavorite('job_template', id, 'personal')
    message.success(isFavorited ? '已添加到收藏' : '已取消收藏')
  } catch (e) {
    console.error('切换收藏状态失败:', e)
    message.error('操作失败')
  }
}

// 可用标签列表
const availableTags = ref<string[]>([])

// 可用用户列表（创建者）
const availableUsers = ref<Array<{id: number, username: string, name: string}>>([])

// 创建者搜索过滤结果
const filteredCreators = ref<Array<{id: number, username: string, name: string}>>([])

// 更新者搜索过滤结果
const filteredUpdaters = ref<Array<{id: number, username: string, name: string}>>([])

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
    { key: 'category' },
    {
      key: 'tags',
      toQuery: (value: string[]) => (value && value.length ? value.join(',') : undefined),
      fromQuery: (value) => parseStringArrayQuery(value)
    },
    {
      key: 'favorites_only',
      toQuery: (value: boolean) => toBooleanQuery(value),
      fromQuery: (value) => parseBooleanQuery(value) ?? false
    },
    {
      key: 'my_templates_only',
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

const activeFilterItems = computed(() => [
  { key: 'search', label: '模板名称', display: searchForm.search },
  { key: 'category', label: '分类', display: searchForm.category ? getCategoryText(searchForm.category) : '' },
  { key: 'tags', label: '标签', display: searchForm.tags.length ? searchForm.tags.join('、') : '' },
  { key: 'created_by', label: '创建者', display: searchForm.my_templates_only ? '' : resolveUserName(searchForm.created_by) },
  { key: 'updated_by', label: '更新者', display: resolveUserName(searchForm.updated_by) },
  { key: 'favorites_only', label: '收藏', display: searchForm.favorites_only ? '仅收藏' : '' },
  { key: 'my_templates_only', label: '我的作业', display: searchForm.my_templates_only ? '仅我的' : '' }
])

const jobTemplateActiveFilterCount = computed(() => countActiveFilters(searchForm as unknown as Record<string, unknown>))

const handleClearFilter = (key: string) => {
  const defaults = defaultSearchForm()
  if (key in defaults) {
    ;(searchForm as any)[key] = (defaults as any)[key]
  }
  pagination.current = 1
  syncToQuery()
  fetchTemplates()
}

// 表格列配置
const renderTagsCell = (row: any) => {
  if (row.tag_list && row.tag_list.length > 0) {
    return h('div', { class: 'tags-container' }, [
      h(NSpace, { wrap: true }, {
        default: () => [
          ...row.tag_list.slice(0, 2).map((tag: any) =>
            h(NTag, { size: 'small', class: 'tag-item' }, {
              default: () => [h('strong', `${tag.key}:`), ` ${tag.value}`],
            })),
          row.tag_list.length > 2
            ? h(NTag, { size: 'small', class: 'tag-more' }, { default: () => `+${row.tag_list.length - 2}` })
            : null,
        ],
      }),
    ])
  }
  return h('span', { class: 'text-gray-400' }, '无标签')
}

const templateRowActions = (row: any) => [
  { label: '编辑', key: 'edit', disabled: !canEditTemplate(row.id), icon: () => h(Pencil, { size: 14 }) },
  { label: '新增执行方案', key: 'createPlan', disabled: !canCreatePlan, icon: () => h(Plus, { size: 14 }) },
  { label: '查看执行方案', key: 'viewPlans', disabled: !canViewPlans, icon: () => h(List, { size: 14 }) },
  { label: '同步方案', key: 'sync', disabled: !canSyncPlans, icon: () => h(RefreshCw, { size: 14 }) },
  { label: '复制', key: 'copy', disabled: !canCopyTemplate, icon: () => h(Copy, { size: 14 }) },
  { label: '删除', key: 'delete', disabled: !canDeleteTemplate(row.id), icon: () => h(Trash2, { size: 14 }), props: { class: 'danger' } },
]

const onTemplateRowAction = (key: string, row: any) => {
  if (key === 'edit') handleClickEditTemplate(row)
  if (key === 'createPlan') handleClickCreatePlan(row)
  if (key === 'viewPlans') handleClickViewPlans(row)
  if (key === 'sync') handleClickSync(row)
  if (key === 'copy') handleClickCopyTemplate(row)
  if (key === 'delete') handleClickDeleteTemplate(row)
}

const columns: DataTableColumns<any> = [
  {
    title: '模板名称',
    key: 'name',
    ellipsis: { tooltip: true },
    render: (row) =>
      h('div', { class: 'template-name-cell' }, [
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
        h('div', { class: 'template-name-main' }, [
          h(NButton, { text: true, size: 'small', class: 'template-link', onClick: () => handleView(row) }, { default: () => row.name }),
          h('div', { class: 'template-description' }, row.description || '暂无描述'),
        ]),
      ]),
  },
  {
    title: '分类',
    key: 'category',
    render: (row) => row.category
      ? h(NTag, { type: getCategoryColor(row.category) as any }, { default: () => getCategoryText(row.category) })
      : h('span', { class: 'text-gray-400' }, '未分类'),
  },
  { title: '标签', key: 'tags', render: renderTagsCell },
  {
    title: '步骤数',
    key: 'step_count',
    render: (row) => h(NBadge, { value: row.step_count, max: 99 }),
  },
  {
    title: '执行方案',
    key: 'plan_count',
    render: (row) =>
      h(NSpace, { class: 'table-row-actions', size: 4, wrap: false, wrapItem: false, align: 'center' }, {
        default: () => [
          h(NBadge, { value: row.plan_count, max: 99 }),
          row.has_unsync_plans ? h(NTag, { type: 'warning', size: 'small' }, { default: () => '有未同步' }) : null,
        ],
      }),
  },
  {
    title: '被引用',
    key: 'references',
    render: (row) =>
      h(NButton, { text: true, size: 'small', class: 'reference-link', onClick: () => handleViewReferences(row) }, {
        default: () => [
          h('div', { class: 'meta-line' }, `方案：${row.plan_count || 0}`),
          h('div', { class: 'meta-line' }, `定时：${row.scheduled_job_ref_count || 0}`),
        ],
      }),
  },
  {
    title: '创建信息',
    key: 'created_at',
    render: (row) =>
      h(MetaInfoLines, {
        createdText: `创建：${formatDate(row.created_at)} · ${row.created_by_name || '-'}`,
        updatedText: `更新：${row.updated_at ? formatDate(row.updated_at) : '-'} · ${row.updated_by_name || row.created_by_name || '-'}`,
      }),
  },
  {
    title: '操作',
    key: 'actions',
    render: (row) =>
      h(NSpace, { class: 'table-row-actions', wrap: false, wrapItem: false, align: 'center' }, {
        default: () => [
          withPerm(
            h(NButton, { text: true, size: 'small', class: 'template-primary-action', onClick: () => handleView(row) }, {
              icon: () => h(Eye, { size: 14 }),
              default: () => '查看',
            }),
            { resourceType: 'jobtemplate', permission: 'view', resourceId: row.id },
          ),
          h(NDropdown, {
            trigger: 'click',
            options: templateRowActions(row),
            onSelect: (key: string) => onTemplateRowAction(key, row),
          }, {
            default: () => h(NButton, { text: true, size: 'small', 'aria-label': '更多操作' }, {
              icon: () => h(MoreHorizontal, { size: 16 }),
            }),
          }),
        ],
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

const withPerm = (vnode: VNode, value: unknown) => {
  const perm = resolveDirective('permission')
  return perm ? withDirectives(vnode, [[perm, value]]) : vnode
}

// 获取可用标签列表
const fetchAvailableTags = async () => {
  try {
    const response = await jobTemplateApi.getTags()
    const tags = Array.isArray(response?.tags) ? response.tags : Array.isArray(response) ? response : []
    availableTags.value = tags.sort()
  } catch (error) {
    console.error('获取标签列表失败:', error)
  }
}

// 获取可用用户列表（创建者）
const fetchAvailableUsers = async () => {
  try {
    // 从当前模板列表中提取唯一用户列表
    if (templates.value.length > 0) {
      const userMap = new Map<number, {id: number, username: string, name: string}>()
      const appendUser = (id?: number, name?: string) => {
        if (!id || !name) return
        userMap.set(id, { id, username: name, name })
      }

      templates.value.forEach(template => {
        appendUser(template.created_by, template.created_by_name)
        appendUser(template.updated_by, template.updated_by_name)
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

// 获取作业模板列表
const fetchTemplates = async () => {
  try {
    loading.value = true
    const params = {
      page: pagination.current,
      page_size: pagination.pageSize,
      ordering: ordering.value || undefined,
      search: searchForm.search || undefined,
      category: searchForm.category || undefined,
      tags: searchForm.tags.length > 0 ? searchForm.tags.join(',') : undefined,
      // 如果启用“我的作业”，让后端返回只属于当前用户的模板
      created_by: searchForm.my_templates_only ? authStore.user?.id : (searchForm.created_by || undefined),
      updated_by: searchForm.updated_by || undefined
    }

    // 过滤空值
    Object.keys(params).forEach(key => {
      if (params[key] === undefined ||
          (Array.isArray(params[key]) && params[key].length === 0)) {
        delete params[key]
      }
    })

    const response = await jobTemplateApi.getTemplates(params)
    let resultTemplates = response.results || []

    // 前端过滤收藏
    if (searchForm.favorites_only) {
      resultTemplates = resultTemplates.filter(t => favoritesStore.isFavorite('job_template', t.id))
    }

    // 前端过滤我的作业
    if (searchForm.my_templates_only) {
      resultTemplates = resultTemplates.filter(t => t.created_by === authStore.user?.id)
    }

    templates.value = resultTemplates
    pagination.total = searchForm.favorites_only ? resultTemplates.length : (response.total || 0)

    // 异步刷新标签列表，确保下拉选项完整
    await fetchAvailableTags()

    // 拉取可用用户列表
    await fetchAvailableUsers()

    // 异步加载收藏状态
    await favoritesStore.batchCheckFavorites('job_template', resultTemplates.map(t => t.id))
  } catch (error) {
    console.error('获取作业模板列表失败:', error)
    message.error('获取作业模板列表失败')
  } finally {
    loading.value = false
  }
}

// 搜索
const handleSearch = () => {
  pagination.current = 1
  syncToQuery()
  fetchTemplates()
}

// 重置搜索
const handleReset = () => {
  Object.assign(searchForm, defaultSearchForm())
  // 重置创建者/更新者过滤
  filteredCreators.value = [...availableUsers.value]
  filteredUpdaters.value = [...availableUsers.value]
  pagination.current = 1
  syncToQuery()
  fetchTemplates()
}

// 分页处理
const handlePageChange = (page: number) => {
  pagination.current = page
  syncToQuery()
  fetchTemplates()
}

const handlePageSizeChange = (pageSize: number) => {
  pagination.pageSize = pageSize
  pagination.current = 1
  syncToQuery()
  fetchTemplates()
}

// 操作处理
const handleCreate = () => {
  router.push('/job-templates/create')
}

const handleView = (record: JobTemplate) => {
  router.push(`/job-templates/detail/${record.id}`)
}

const handleEdit = (record: JobTemplate) => {
  router.push(`/job-templates/${record.id}/edit`)
}

const handleCreatePlan = (record: JobTemplate) => {
  router.push(`/execution-plans/create?template_id=${record.id}`)
}

const handleViewPlans = (record: JobTemplate) => {
  router.push(`/execution-plans?template_id=${record.id}`)
}

const handleCopy = async (record: JobTemplate) => {
  try {
    // 获取模板的完整详情
    const templateDetail = await jobTemplateApi.getTemplate(record.id)

    // 创建复制的模板数据
    const copiedTemplate = {
      name: `${templateDetail.name}_副本`,
      description: templateDetail.description,
      category: templateDetail.category,
      tags: templateDetail.tag_list || [],
      global_parameters: templateDetail.global_parameters || {},
      steps: templateDetail.steps || []
    }

    // 将复制数据存储到sessionStorage
    sessionStorage.setItem('copyTemplateData', JSON.stringify(copiedTemplate))

    // 跳转到编辑器页面
    await router.push('/job-templates/create?action=copy')
    message.success('模板数据已复制，请修改模板名称后保存')
  } catch (error) {
    console.error('复制模板失败:', error)
    message.error('复制模板失败')
  }
}

const handleDelete = async (record: JobTemplate) => {
  let references = { execution_plans: [] as Array<{ id: number; name: string }>, scheduled_jobs: [] as Array<{ id: number; name: string }> }
  try {
    references = await jobTemplateApi.getReferences(record.id)
  } catch (error) {
    console.error('获取引用关系失败:', error)
  }

  const planCount = references.execution_plans.length
  const jobCount = references.scheduled_jobs.length
  const hasRefs = planCount > 0 || jobCount > 0

  const formatNames = (items: Array<{ name: string }>) => {
    if (!items.length) return '无'
    const sample = items.slice(0, 5).map(item => item.name).join('、')
    return items.length > 5 ? `${sample} 等 ${items.length} 个` : sample
  }

  const content = h('div', { style: 'line-height:1.6;' }, [
    h('div', {}, `将删除作业模板“${record.name}”。`),
    h('div', { style: 'margin-top:8px;font-weight:600;' }, '引用情况'),
    h('div', {}, `执行方案(${planCount}): ${formatNames(references.execution_plans)}`),
    h('div', {}, `定时任务(${jobCount}): ${formatNames(references.scheduled_jobs)}`),
    hasRefs ? h('div', { style: 'margin-top:8px;color:#f53f3f;' }, '存在引用，无法删除') : null
  ])

  dialog.warning({
    title: hasRefs ? '无法删除' : '确认删除',
    content: () => content,
    positiveButtonProps: { type: 'error', disabled: hasRefs },
    onPositiveClick: async () => {
      if (hasRefs) return
      try {
        await jobTemplateApi.deleteTemplate(record.id)
        message.success('作业模板删除成功')
        await fetchTemplates()
      } catch (error: any) {
        console.error('删除作业模板失败:', error)
        const message = error?.response?.data?.message || '删除作业模板失败'
        message.error(message)
      }
    }
  })
}

const handleViewReferences = async (record: JobTemplate) => {
  let references = { execution_plans: [] as Array<{ id: number; name: string }>, scheduled_jobs: [] as Array<{ id: number; name: string }> }
  try {
    references = await jobTemplateApi.getReferences(record.id)
  } catch (error: any) {
    const message = error?.response?.data?.message || '获取引用关系失败'
    message.error(message)
    console.error('获取引用关系失败:', error)
    return
  }

  const resolveHref = (path: string) => router.resolve({ path }).href

  let modalClose: (() => void) | null = null

  const renderLinks = (
    items: Array<{ id: number; name: string }>,
    type: 'plan' | 'schedule'
  ) => {
    if (!items.length) return '无'
    const sample = items.slice(0, 5)
    const nodes: any[] = []
    sample.forEach((item, index) => {
      const path = type === 'plan'
        ? `/execution-plans/detail/${item.id}`
        : `/scheduled-tasks/detail/${item.id}`
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
    h('div', { style: 'margin-bottom:6px;' }, `模板：${record.name}`),
    h('div', { style: 'font-weight:600;' }, '引用情况'),
    h('div', {}, [
      `执行方案(${references.execution_plans.length}): `,
      renderLinks(references.execution_plans, 'plan')
    ]),
    h('div', {}, [
      `定时任务(${references.scheduled_jobs.length}): `,
      renderLinks(references.scheduled_jobs, 'schedule')
    ])
  ])

  const modal = dialog.info({
    title: '引用关系',
    content: () => content,
    positiveText: '关闭'
  })
  modalClose = modal?.destroy
}

const showNoPermissionMessage = () => {
  message.warning('没有权限执行此操作，请联系管理员开放权限')
}

const handleClickCreatePlan = (record: JobTemplate) => {
  if (!canCreatePlan.value) {
    showNoPermissionMessage()
    return
  }
  handleCreatePlan(record)
}

const handleClickEditTemplate = (record: JobTemplate) => {
  if (!canEditTemplate(record.id)) {
    showNoPermissionMessage()
    return
  }
  handleEdit(record)
}

const handleClickViewPlans = (record: JobTemplate) => {
  if (!canViewPlans.value) {
    showNoPermissionMessage()
    return
  }
  handleViewPlans(record)
}

const handleClickSync = (record: JobTemplate) => {
  if (!canSyncPlans.value) {
    showNoPermissionMessage()
    return
  }
  handleSync(record)
}

const handleClickCopyTemplate = (record: JobTemplate) => {
  if (!canCopyTemplate.value) {
    showNoPermissionMessage()
    return
  }
  handleCopy(record)
}

const handleClickDeleteTemplate = (record: JobTemplate) => {
  if (!canDeleteTemplate(record.id)) {
    showNoPermissionMessage()
    return
  }
  handleDelete(record)
}

// 同步方案
const handleSync = (record: JobTemplate) => {
  syncTemplateId.value = record.id
  syncTemplateName.value = record.name
  syncModalVisible.value = true
}

// 同步成功回调
const handleSyncSuccess = () => {
  syncModalVisible.value = false
  fetchTemplates() // 刷新列表
}

// 工具函数
const getCategoryColor = (category: string) => {
  const colors: Record<string, string> = {
    deployment: 'blue',
    maintenance: 'green',
    monitoring: 'orange',
    backup: 'purple',
    other: 'gray'
  }
  return colors[category] || 'gray'
}

const getCategoryText = (category: string) => {
  const texts: Record<string, string> = {
    deployment: '部署',
    maintenance: '维护',
    monitoring: '监控',
    backup: '备份',
    other: '其他'
  }
  return texts[category] || category
}

const formatDate = (dateString: string) => {
  return new Date(dateString).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

const canCreatePlan = computed(() => {
  if (permissionsStore.isSuperUser) return true
  return permissionsStore.hasPermission('executionplan', 'add')
})

const canViewPlans = computed(() => {
  if (permissionsStore.isSuperUser) return true
  return permissionsStore.hasPermission('executionplan', 'view')
})

const canSyncPlans = computed(() => {
  if (permissionsStore.isSuperUser) return true
  return permissionsStore.hasPermission('executionplan', 'change')
})

const canCopyTemplate = computed(() => {
  if (permissionsStore.isSuperUser) return true
  return permissionsStore.hasPermission('jobtemplate', 'add')
})

const canEditTemplate = (templateId: number): boolean => {
  if (permissionsStore.isSuperUser) return true
  return (
    permissionsStore.hasPermission('jobtemplate', 'change', templateId) ||
    permissionsStore.hasPermission('jobtemplate', 'change')
  )
}

const canDeleteTemplate = (templateId: number): boolean => {
  if (permissionsStore.isSuperUser) return true
  return (
    permissionsStore.hasPermission('jobtemplate', 'delete', templateId) ||
    permissionsStore.hasPermission('jobtemplate', 'delete')
  )
}

// 生命周期
onMounted(() => {
  initFromQuery()
  fetchTemplates()
})

// 机械转换生成的静态下拉选项
const selectOptions1 = [{ label: '部署', value: 'deployment' }, { label: '维护', value: 'maintenance' }, { label: '监控', value: 'monitoring' }, { label: '备份', value: 'backup' }, { label: '其他', value: 'other' }]
</script>

<style scoped>
.job-templates-page {
  padding: 0;
}

.template-filter-grid :deep(.arco-input-wrapper),
.template-filter-grid :deep(.arco-select),
.template-filter-grid :deep(.arco-select-view) {
  min-width: 0;
  width: 100%;
}

.template-table-panel {
  min-width: 0;
  overflow: hidden;
}

/* 搜索按钮定位（与脚本模板保持一致） */
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

/* 模板名称单元格样式 */
.template-name-cell {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  min-width: 0;
}

.template-name-main {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}

.template-link {
  display: block;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.template-description {
  min-width: 0;
  overflow: hidden;
  color: var(--app-meta);
  font-size: 12px;
  line-height: 1.35;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.favorite-btn {
  padding: 0 4px;
  min-width: auto;
  flex-shrink: 0;
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

.text-gray-400 {
  color: #9ca3af;
}

.text-xs {
  font-size: 12px;
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

/* 标签容器样式 */
.tags-container {
  max-width: 100%;
  overflow: hidden;
}

.tag-item {
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  display: inline-block;
}

.tag-more {
  flex-shrink: 0;
}

.disabled-option {
  opacity: 0.5;
  cursor: not-allowed;
}

:deep(.arco-table) {
  width: 100%;
  max-width: 100%;

  .arco-table-container,
  .arco-table-content,
  .arco-table-body,
  .arco-table-element {
    max-width: 100%;
    min-width: 0;
    overflow-x: hidden;
  }

  table {
    width: 100%;
    table-layout: fixed;
  }

  .arco-table-th {
    background-color: #fff;
  }

  .arco-table-td {
    padding: 12px 10px;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .arco-space-item {
    min-width: 0;
  }
}

:deep(.table-row-actions) {
  justify-content: center;
  max-width: 100%;
  overflow: hidden;
}

:deep(.template-primary-action) {
  min-width: 0;
  padding-inline: 6px;
}
</style>
