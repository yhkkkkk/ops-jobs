<template>
  <div
    class="app-page script-templates-page"
    v-page-permissions="{ 
      resourceType: 'scripttemplate', 
      permissions: ['view', 'add', 'change', 'delete'],
      resourceIds: templates.map(t => t.id)
    }"
  >
    <PageHeader
      eyebrow="脚本资产"
      title="脚本模板"
      description="创建和管理可复用的脚本模板，维护分类、标签、引用关系和上线状态。"
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
            v-permission="{ resourceType: 'scripttemplate', permission: 'add' }"
            type="primary"
            @click="handleCreate"
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
      title="筛选脚本模板"
      description="按名称、类型、分类、标签和维护人过滤模板资产。"
      :active-count="scriptTemplateActiveFilterCount"
    >
      <div class="app-filter-grid template-filter-grid">
        <div>
          <n-input
            v-model:value="searchForm.name"
            placeholder="模板名称"
            clearable
            @press-enter="handleSearch"
            @clear="handleSearch"
          />
        </div>
        <div>
                    <n-select
            v-model:value="searchForm.script_type"
            placeholder="脚本类型"
            clearable
            @change="handleSearch"
            @clear="handleSearch" :options="selectOptions1" />
        </div>
        <div>
                    <n-select
            v-model:value="searchForm.category"
            placeholder="分类"
            clearable
            @change="handleSearch"
            @clear="handleSearch" :options="selectOptions2" />
        </div>
        <div>
          <n-select
            v-model:value="searchForm.tags"
            placeholder="标签"
            clearable
            multiple
            :options="(availableTags || []).map((t: string) => ({ label: t, value: t }))"
            @update:value="handleSearch"
          />
        </div>
        <div>
          <n-select
            v-model:value="searchForm.created_by"
            placeholder="创建者"
            clearable
            filterable
            remote
            :options="(filteredCreators || []).map((u: any) => ({ label: u.name, value: u.id }))"
            @search="handleCreatorSearch"
            @update:value="handleSearch"
          />
        </div>
        <div>
          <n-select
            v-model:value="searchForm.updated_by"
            placeholder="更新者"
            clearable
            filterable
            remote
            :options="(filteredUpdaters || []).map((u: any) => ({ label: u.name, value: u.id }))"
            @search="handleUpdaterSearch"
            @update:value="handleSearch"
          />
        </div>
        <div>
          <div class="filter-switch">
            <span class="filter-label">收藏</span>
            <n-switch v-model:value="searchForm.favorites_only" @update:value="handleSearch" />
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
      />
    </DetailPanel>
  </div>
</template>

<script setup lang="ts">
import { computed, h, onMounted, reactive, ref, resolveDirective, withDirectives } from 'vue'
import { useRouter } from 'vue-router'
import { scriptTemplateApi } from '@/api/ops'
import type { ScriptTemplate } from '@/types'
import dayjs from 'dayjs'
import { usePermissionsStore } from '@/stores/permissions'
import { useFavoritesStore } from '@/stores/favorites'
import MetaInfoLines from '@/components/MetaInfoLines.vue'
import ActiveFiltersBar from '@/components/ActiveFiltersBar.vue'
import { useFilterQuerySync, parseBooleanQuery, parseNumberQuery, parseStringArrayQuery, toBooleanQuery } from '@/composables/useFilterQuerySync'
import { DataToolbar, DetailPanel, PageHeader, countActiveFilters } from '@/components/app'
import { NButton, NDataTable, NDropdown, NInput, NSelect, NSpace, NSwitch, NTag, type DataTableColumns, useDialog, useMessage } from 'naive-ui'
import { Copy, History, MoreHorizontal, Plus, Power, RefreshCw, Search, Star, Trash2 } from 'lucide-vue-next'

const message = useMessage()
const dialog = useDialog()
const router = useRouter()
const loading = ref(false)
const templates = ref<ScriptTemplate[]>([])
const permissionsStore = usePermissionsStore()
const favoritesStore = useFavoritesStore()

const defaultSearchForm = () => ({
  name: '',
  script_type: '',
  category: '',
  tags: [] as string[],
  favorites_only: false,
  created_by: undefined as number | undefined,
  updated_by: undefined as number | undefined
})

// 搜索表单
const searchForm = reactive(defaultSearchForm())

// 可用标签列表
const availableTags = ref<string[]>([])

// 可用用户列表（创建者）
const availableUsers = ref<Array<{id: number, username: string, name: string}>>([])

// 创建者搜索过滤结果
const filteredCreators = ref<Array<{id: number, username: string, name: string}>>([])

// 更新者搜索过滤结果
const filteredUpdaters = ref<Array<{id: number, username: string, name: string}>>([])

// 收藏相关方法
const isFavorite = (id: number) => favoritesStore.isFavorite('script_template', id)

const toggleFavorite = async (id: number) => {
  try {
    const isFavorited = await favoritesStore.toggleFavorite('script_template', id, 'personal')
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
    { key: 'name' },
    { key: 'script_type' },
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
  { key: 'name', label: '模板名称', display: searchForm.name },
  { key: 'script_type', label: '脚本类型', display: searchForm.script_type ? getScriptTypeText(searchForm.script_type) : '' },
  { key: 'category', label: '分类', display: searchForm.category ? getCategoryText(searchForm.category) : '' },
  { key: 'tags', label: '标签', display: searchForm.tags.length ? searchForm.tags.join('、') : '' },
  { key: 'created_by', label: '创建者', display: resolveUserName(searchForm.created_by) },
  { key: 'updated_by', label: '更新者', display: resolveUserName(searchForm.updated_by) },
  { key: 'favorites_only', label: '收藏', display: searchForm.favorites_only ? '仅收藏' : '' }
])

const scriptTemplateActiveFilterCount = computed(() => countActiveFilters(searchForm as unknown as Record<string, unknown>))

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
const renderTemplateStatus = (record: any) =>
  h(NTag, { type: record.is_active ? 'success' : 'error' }, { default: () => (record.is_active ? '上线' : '下线') })

const rowActionOptions = (record: any) => [
  {
    label: '版本管理',
    key: 'versions',
    disabled: !canManageVersions(record.id),
    icon: () => h(History, { size: 14 }),
  },
  {
    label: record.is_active ? '下线' : '上线',
    key: 'toggle',
    disabled: !canToggleStatus(record.id),
    icon: () => h(Power, { size: 14 }),
  },
  {
    label: '复制',
    key: 'copy',
    disabled: !canCopyTemplate,
    icon: () => h(Copy, { size: 14 }),
  },
  {
    label: '删除',
    key: 'delete',
    disabled: !canDeleteTemplate(record),
    icon: () => h(Trash2, { size: 14 }),
    props: { class: 'danger' },
  },
]

const onRowAction = (key: string, record: any) => {
  if (key === 'versions') handleClickManageVersions(record)
  if (key === 'toggle') handleClickToggleStatus(record)
  if (key === 'copy') handleClickCopy(record)
  if (key === 'delete') handleClickDelete(record)
}

const columns: DataTableColumns<any> = [
  {
    title: '模板名称',
    key: 'name',
    width: 260,
    ellipsis: { tooltip: true },
    render: (record: any) =>
      h('div', { class: 'template-name-cell' }, [
        h(NButton, {
          text: true, size: 'tiny', class: 'favorite-btn',
          onClick: (e: MouseEvent) => { e.stopPropagation(); toggleFavorite(record.id) },
        }, {
          icon: () => h(Star, {
            size: 14,
            fill: isFavorite(record.id) ? '#f59e0b' : 'none',
            stroke: isFavorite(record.id) ? '#f59e0b' : 'currentColor',
          }),
        }),
        h('div', { class: 'template-name-main' }, [
          h(NButton, { text: true, size: 'tiny', class: 'template-link', onClick: () => handleDetail(record) }, { default: () => record.name }),
          h('div', { class: 'template-description' }, record.description || '暂无描述'),
        ]),
      ]),
  },
  {
    title: '脚本类型',
    key: 'script_type',
    width: 92,
    render: (record: any) =>
      h(NTag, { type: getScriptTypeColor(record.script_type) as any }, { default: () => getScriptTypeText(record.script_type) }),
  },
  {
    title: '分类',
    key: 'category',
    width: 92,
    render: (record: any) => record.category
      ? h(NTag, { type: 'info' }, { default: () => getCategoryText(record.category) })
      : h('span', '-',),
  },
  { title: '线上版本', key: 'version', width: 90, render: (record: any) => record.version },
  {
    title: '状态',
    key: 'is_active',
    width: 76,
    render: (record: any) => renderTemplateStatus(record),
  },
  {
    title: '被引用',
    key: 'references',
    render: (record: any) =>
      h(NButton, { text: true, size: 'tiny', class: 'reference-link', onClick: () => handleViewReferences(record) }, {
        default: () => [
          h('div', { class: 'meta-line' }, `作业：${record.job_template_ref_count || 0}`),
          h('div', { class: 'meta-line' }, `方案：${record.execution_plan_ref_count || 0}`),
        ],
      }),
  },
  {
    title: '标签',
    key: 'tags',
    render: (record: any) => {
      if (record.tag_list && record.tag_list.length) {
        return h(NSpace, { wrap: true }, {
          default: () => record.tag_list.map((tag: any) =>
            h(NTag, { size: 'small', class: 'tag-item' }, { default: () => formatTag(tag) })),
        })
      }
      if (record.tags_json && Object.keys(record.tags_json).length) {
        return h(NSpace, { wrap: true }, {
          default: () => Object.entries(record.tags_json).map(([key, value]) =>
            h(NTag, { size: 'small', class: 'tag-item' }, { default: () => `${key}=${value}` })),
        })
      }
      return h('span', { class: 'text-gray' }, '-')
    },
  },
  {
    title: '创建信息',
    key: 'created_at',
    render: (record: any) =>
      h(MetaInfoLines, {
        createdText: `创建：${formatTime(record.created_at)} · ${record.created_by_name || '-'}`,
        updatedText: `更新：${record.updated_at ? formatTime(record.updated_at) : '-'} · ${record.updated_by_name || record.created_by_name || '-'}`,
      }),
  },
  {
    title: '操作',
    key: 'actions',
    width: 170,
    render: (record: any) => {
      const buttons: any[] = []
      if (record.is_active) {
        buttons.push(withPerm(
          h(NButton, {
            text: true, size: 'small', class: 'template-primary-action',
            onClick: () => handleExecute(record),
          }, { default: () => '执行' }),
          { resourceType: 'scripttemplate', permission: 'view', resourceId: record.id },
        ))
      }
      buttons.push(
        h(NDropdown, {
          trigger: 'click',
          options: rowActionOptions(record),
          onSelect: (key: string) => onRowAction(key, record),
        }, {
          default: () => h(NButton, { text: true, size: 'small', 'aria-label': '更多操作' }, {
            icon: () => h(MoreHorizontal, { size: 16 }),
          }),
        }),
      )
      return h(NSpace, { class: 'table-row-actions', wrap: false, wrapItem: false, align: 'center' }, { default: () => buttons })
    },
  },
]

// Naive UI 表格分页对象（远端分页）
const tablePagination = computed(() => ({
  page: pagination.current,
  pageSize: pagination.pageSize,
  itemCount: pagination.total,
  pageSizes: [10, 20, 50, 100],
  showSizePicker: true,
  onChange: (page: number) => handlePageChange(page),
  onUpdatePageSize: (size: number) => handlePageSizeChange(size),
}))

const withPerm = (vnode: any, value: unknown) => {
  const perm = resolveDirective('permission')
  return perm ? withDirectives(vnode, [[perm, value]]) : vnode
}

// 获取可用标签列表
const fetchAvailableTags = async () => {
  try {
    const response = await scriptTemplateApi.getTags()
    const tags = Array.isArray(response?.tags) ? response.tags : Array.isArray(response) ? response : []
    availableTags.value = tags.sort()
  } catch (error) {
    console.error('获取标签列表失败:', error)
  }
}

// 获取可用用户列表（创建者）
const fetchAvailableUsers = async () => {
  try {
    // 从现有模板中提取唯一用户列表
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

// 获取脚本模板列表
const fetchTemplates = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.current,
      page_size: pagination.pageSize,
      ordering: ordering.value || undefined,
      ...searchForm,
    }

    // 处理tags数组参数
    if (params.tags && Array.isArray(params.tags) && params.tags.length > 0) {
      (params as any).tags = params.tags.join(',')
    }

    // 过滤空值
    Object.keys(params).forEach(key => {
      if (params[key] === '' || params[key] === null || params[key] === undefined ||
          (Array.isArray(params[key]) && params[key].length === 0)) {
        delete params[key]
      }
    })

    const response = await scriptTemplateApi.getTemplates(params)
    let resultTemplates = response.results

    // 前端过滤收藏
    if (searchForm.favorites_only) {
      resultTemplates = resultTemplates.filter(t => favoritesStore.isFavorite('script_template', t.id))
    }

    templates.value = resultTemplates
    pagination.total = searchForm.favorites_only ? resultTemplates.length : response.total
    console.log('设置模板列表数据:', templates.value)

    // 拉取可用标签（独立接口，保持选项完整）
    await fetchAvailableTags()

    // 拉取可用用户列表
    await fetchAvailableUsers()

    // 异步加载收藏状态
    await favoritesStore.batchCheckFavorites('script_template', resultTemplates.map(t => t.id))
  } catch (error) {
    message.error('获取脚本模板列表失败')
    console.error('获取脚本模板列表失败:', error)
    templates.value = []
    pagination.total = 0
  } finally {
    loading.value = false
  }
}

// 搜索
const handleSearch = () => {
  console.log('触发搜索，当前搜索条件:', searchForm)
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

// 分页变化
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

// 新建模板
const handleCreate = () => {
  router.push('/script-templates/create')
}

// 查看详情页面
const handleDetail = (record: ScriptTemplate) => {
  router.push(`/script-templates/detail/${record.id}`)
}

// 去执行：跳转到快速执行并携带模板标识
const handleExecute = (record: ScriptTemplate) => {
  if (!record.id) {
    message.warning('模板信息不完整')
    return
  }
  if (!record.is_active) {
    message.warning('模板未上线，无法执行')
    return
  }
  router.push(`/quick-execute?template_id=${record.id}`)
}

// 复制模板
const handleCopy = (record: ScriptTemplate) => {
  // 创建复制的模板数据
  const copiedTemplate = {
    name: `${record.name}_副本`,
    description: record.description,
    script_type: record.script_type,
    script_content: record.script_content || record.content,
    tags_json: record.tags_json || {},
    category: record.category || '',
  }

  // 将复制数据存储到sessionStorage
  sessionStorage.setItem('copyTemplateData', JSON.stringify(copiedTemplate))

  // 跳转到编辑器页面
  router.push('/script-templates/create?action=copy')
}

// 删除模板
const handleDelete = async (record: ScriptTemplate) => {
  let references = { job_templates: [] as Array<{ id: number; name: string }>, execution_plans: [] as Array<{ id: number; name: string }> }
  try {
    references = await scriptTemplateApi.getReferences(record.id!)
  } catch (error) {
    console.error('获取引用关系失败:', error)
  }

  const jobCount = references.job_templates.length
  const planCount = references.execution_plans.length
  const hasRefs = jobCount > 0 || planCount > 0

  const formatNames = (items: Array<{ name: string }>) => {
    if (!items.length) return '无'
    const sample = items.slice(0, 5).map(item => item.name).join('、')
    return items.length > 5 ? `${sample} 等 ${items.length} 个` : sample
  }

  const content = h('div', { style: 'line-height:1.6;' }, [
    h('div', {}, `将删除模板“${record.name}”。`),
    h('div', { style: 'margin-top:8px;font-weight:600;' }, '引用情况'),
    h('div', {}, `作业模板(${jobCount}): ${formatNames(references.job_templates)}`),
    h('div', {}, `执行方案(${planCount}): ${formatNames(references.execution_plans)}`),
    hasRefs ? h('div', { style: 'margin-top:8px;color:#f53f3f;' }, '存在引用，无法删除') : null
  ])

  dialog.warning({
    title: hasRefs ? '无法删除' : '确认删除',
    content: () => content,
    positiveButtonProps: { disabled: hasRefs },
    onPositiveClick: async () => {
      if (hasRefs) return
      try {
        await scriptTemplateApi.deleteTemplate(record.id!)
        message.success('模板删除成功')
        await fetchTemplates()
      } catch (error: any) {
        const message = error?.response?.data?.message || '模板删除失败'
        message.error(message)
        console.error('删除模板失败:', error)
      }
    }
  })
}

const handleViewReferences = async (record: ScriptTemplate) => {
  let references = { job_templates: [] as Array<{ id: number; name: string }>, execution_plans: [] as Array<{ id: number; name: string }> }
  try {
    references = await scriptTemplateApi.getReferences(record.id!)
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
    type: 'job' | 'plan'
  ) => {
    if (!items.length) return '无'
    const sample = items.slice(0, 5)
    const nodes: any[] = []
    sample.forEach((item, index) => {
      const path = type === 'job'
        ? `/job-templates/detail/${item.id}`
        : `/execution-plans/detail/${item.id}`
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
      `作业模板(${references.job_templates.length}): `,
      renderLinks(references.job_templates, 'job')
    ]),
    h('div', {}, [
      `执行方案(${references.execution_plans.length}): `,
      renderLinks(references.execution_plans, 'plan')
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

const handleClickManageVersions = (record: ScriptTemplate) => {
  if (!canManageVersions(record.id!)) {
    showNoPermissionMessage()
    return
  }
  handleVersions(record)
}

const handleClickToggleStatus = (record: ScriptTemplate) => {
  if (!canToggleStatus(record.id!)) {
    showNoPermissionMessage()
    return
  }
  handleToggleStatus(record)
}

const handleClickCopy = (record: ScriptTemplate) => {
  if (!canCopyTemplate.value) {
    showNoPermissionMessage()
    return
  }
  handleCopy(record)
}

const handleClickDelete = (record: ScriptTemplate) => {
  if (!canDeleteTemplate(record)) {
    showNoPermissionMessage()
    return
  }
  handleDelete(record)
}

// 工具函数
const getScriptTypeColor = (type: string) => {
  const colors = {
    shell: 'blue',
    python: 'green',
    powershell: 'purple',
    perl: 'magenta',
  }
  return colors[type] || 'gray'
}

const getScriptTypeText = (type: string) => {
  const texts = {
    shell: 'Shell',
    python: 'Python',
    powershell: 'PowerShell',
    perl: 'Perl',
  }
  return texts[type] || type
}

const getCategoryText = (category: string) => {
  const texts = {
    deployment: '部署',
    monitoring: '监控',
    maintenance: '维护',
    backup: '备份',
    security: '安全',
    other: '其他',
  }
  return texts[category] || category
}

const formatTag = (tag: any) => {
  if (tag && typeof tag === 'object') {
    const key = tag.key ?? ''
    const value = tag.value ?? ''
    return value ? `${key}=${value}` : key
  }
  return String(tag)
}

const formatTime = (timestamp: string) => {
  return dayjs(timestamp).format('YYYY-MM-DD HH:mm')
}

// 版本管理：跳转到独立页面
const handleVersions = (record: ScriptTemplate) => {
  router.push(`/script-templates/${record.id}/versions`)
}

const handleToggleStatus = async (record: ScriptTemplate) => {
  if (!record.id) return

  const action = record.is_active ? '下线' : '上线'
  dialog.warning({
    title: `确认${action}`,
    content: `确定要${action}模板 "${record.name}" 吗？`,
    onPositiveClick: async () => {
      try {
        const result = await scriptTemplateApi.toggleStatus(record.id!)
        record.is_active = result.is_active
        message.success(`模板已${action}`)
      } catch (error) {
        console.error(`${action}失败:`, error)
        message.error(`${action}失败`)
      }
    }
  })
}

const canManageVersions = (templateId: number): boolean => {
  if (permissionsStore.isSuperUser) return true
  return (
    permissionsStore.hasPermission('scripttemplate', 'change', templateId) ||
    permissionsStore.hasPermission('scripttemplate', 'change')
  )
}

const canToggleStatus = (templateId: number): boolean => {
  return canManageVersions(templateId)
}

const canCopyTemplate = computed(() => {
  if (permissionsStore.isSuperUser) return true
  return permissionsStore.hasPermission('scripttemplate', 'add')
})

const canDeleteTemplate = (record: ScriptTemplate): boolean => {
  if (permissionsStore.isSuperUser) return true
  return (
    permissionsStore.hasPermission('scripttemplate', 'delete', record.id!) ||
    permissionsStore.hasPermission('scripttemplate', 'delete')
  )
}

// 生命周期
onMounted(() => {
  initFromQuery()
  fetchTemplates()
})

// 机械转换生成的静态下拉选项
const selectOptions1 = [{ label: 'Shell', value: 'shell' }, { label: 'Python', value: 'python' }, { label: 'PowerShell', value: 'powershell' }, { label: 'Perl', value: 'perl' }, { label: 'JavaScript', value: 'javascript' }, { label: 'Go', value: 'go' }]
const selectOptions2 = [{ label: '部署', value: 'deployment' }, { label: '监控', value: 'monitoring' }, { label: '维护', value: 'maintenance' }, { label: '备份', value: 'backup' }, { label: '安全', value: 'security' }, { label: '其他', value: 'other' }]
</script>

<style scoped>
.script-templates-page {
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

.search-actions {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  width: 100%;
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

.tag-item {
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  display: inline-block;
}

/* 表格样式优化 */
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
    background-color: #fff !important;
    font-weight: 600;
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

/* 标签样式 */
.tags-container {
  display: flex;
  align-items: center;
  justify-content: center;
}

.tags-ellipsis:hover {
  /* 调低悬停时的对比度，避免过于抢眼 */
  background-color: #f3f4f6;
  border-color: #d1d5db;
  color: #4b5563;
  transition: background-color 0.2s ease, border-color 0.2s ease, color 0.2s ease;
}

.disabled-option {
  opacity: 0.5;
  cursor: not-allowed;
}

/* 自定义标签提示气泡样式 */
:global(.script-tags-tooltip) {
  background-color: #f9fafb !important;  /* 浅灰背景 */
  color: #111827 !important;              /* 深色文字 */
  border: 1px solid #e5e7eb !important;   /* 边框 */
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.12);  /* 阴影 */
}

:global(.script-tags-tooltip .arco-tooltip-arrow::before) {
  background-color: #f9fafb !important;  /* 箭头背景色(与主体一致) */
  border: 1px solid #e5e7eb !important;   /* 箭头边框 */
}
</style>
