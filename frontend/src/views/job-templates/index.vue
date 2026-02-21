<template>
  <div
    class="job-templates-page"
    v-page-permissions="{
      resourceType: 'jobtemplate',
      permissions: ['view', 'add', 'change', 'delete'],
      resourceIds: templates.map(t => t.id)
    }"
  >
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-content">
        <div class="header-left">
          <h2>作业模板</h2>
          <p class="header-desc">创建和管理可重用的作业模板</p>
        </div>
        <div class="header-right">
          <a-space>
            <a-button @click="fetchTemplates">
              <template #icon>
                <icon-refresh />
              </template>
              刷新
            </a-button>
            <a-button
              type="primary"
              @click="handleCreate"
              v-permission="{ resourceType: 'jobtemplate', permission: 'add' }"
            >
              <template #icon>
                <icon-plus />
              </template>
              新建模板
            </a-button>
          </a-space>
        </div>
      </div>
    </div>

    <!-- 搜索和筛选 -->
    <a-card class="mb-4">
      <a-row :gutter="16">
        <a-col :span="4">
          <a-input
            v-model="searchForm.search"
            placeholder="模板名称"
            allow-clear
            @press-enter="handleSearch"
            @clear="handleSearch"
            style="width: 100%"
          />
        </a-col>
        <a-col :span="2">
          <a-select
            v-model="searchForm.category"
            placeholder="分类"
            allow-clear
            @change="handleSearch"
            @clear="handleSearch"
            style="width: 100%"
          >
            <a-option value="deployment">部署</a-option>
            <a-option value="maintenance">维护</a-option>
            <a-option value="monitoring">监控</a-option>
            <a-option value="backup">备份</a-option>
            <a-option value="other">其他</a-option>
          </a-select>
        </a-col>
        <a-col :span="3">
          <a-select
            v-model="searchForm.tags"
            placeholder="标签"
            allow-clear
            multiple
            @change="handleSearch"
            @clear="handleSearch"
            style="width: 100%"
          >
            <a-option
              v-for="tag in availableTags"
              :key="tag"
              :value="tag"
            >
              {{ tag }}
            </a-option>
          </a-select>
        </a-col>
        <a-col :span="3">
          <a-select
            v-model="searchForm.created_by"
            placeholder="创建者"
            allow-clear
            allow-search
            filter-option="false"
            @search="handleCreatorSearch"
            @change="handleSearch"
            @clear="handleSearch"
            style="width: 100%"
          >
            <a-option
              v-for="user in filteredCreators"
              :key="user.id"
              :value="user.id"
            >
              {{ user.name }}
            </a-option>
          </a-select>
        </a-col>
        <a-col :span="3">
          <a-select
            v-model="searchForm.updated_by"
            placeholder="更新者"
            allow-clear
            allow-search
            filter-option="false"
            @search="handleUpdaterSearch"
            @change="handleSearch"
            @clear="handleSearch"
            style="width: 100%"
          >
            <a-option
              v-for="user in filteredUpdaters"
              :key="user.id"
              :value="user.id"
            >
              {{ user.name }}
            </a-option>
          </a-select>
        </a-col>
        <a-col :span="4">
          <div class="filter-group">
            <div class="filter-switch">
              <span class="filter-label">收藏</span>
              <a-switch v-model="searchForm.favorites_only" @change="handleSearch" />
            </div>
            <div class="filter-switch">
              <span class="filter-label">我的作业</span>
              <a-switch v-model="searchForm.my_templates_only" @change="handleSearch" />
            </div>
          </div>
        </a-col>
        <a-col :span="5">
          <div class="search-actions">
            <a-space>
              <a-button type="primary" @click="handleSearch">
                <template #icon>
                  <icon-search />
                </template>
                搜索
              </a-button>
              <a-button @click="handleReset">
                <template #icon>
                  <icon-refresh />
                </template>
                重置
              </a-button>
            </a-space>
          </div>
        </a-col>
      </a-row>
    </a-card>

    <!-- 模板列表 -->
    <a-card>
      <a-table
        :columns="columns"
        :data="templates"
        :loading="loading"
        :pagination="pagination"
        :scroll="{ x: 1700 }"
        @page-change="handlePageChange"
        @page-size-change="handlePageSizeChange"
      >
        <template #name="{ record }">
          <div class="template-name-cell">
            <a-button
              type="text"
              size="mini"
              class="favorite-btn"
              @click.stop="toggleFavorite(record.id)"
            >
              <icon-star-fill v-if="isFavorite(record.id)" class="favorite-icon active" />
              <icon-star v-else class="favorite-icon" />
            </a-button>
            <a-link @click="handleView(record)" class="template-link">{{ record.name }}</a-link>
          </div>
        </template>
        <template #category="{ record }">
          <a-tag v-if="record.category" :color="getCategoryColor(record.category)">
            {{ getCategoryText(record.category) }}
          </a-tag>
          <span v-else class="text-gray-400">未分类</span>
        </template>

        <template #tags="{ record }">
          <div class="tags-container">
            <a-space v-if="record.tag_list && record.tag_list.length > 0" wrap>
              <a-tag
                v-for="tag in record.tag_list.slice(0, 2)"
                :key="`${tag.key}-${tag.value}`"
                size="small"
                class="tag-item"
              >
                <strong>{{ tag.key }}:</strong> {{ tag.value }}
              </a-tag>
              <a-tag v-if="record.tag_list.length > 2" size="small" class="tag-more">
                +{{ record.tag_list.length - 2 }}
              </a-tag>
            </a-space>
            <span v-else class="text-gray-400">无标签</span>
          </div>
        </template>

        <template #step_count="{ record }">
          <a-badge :count="record.step_count" :max="99" />
        </template>

        <template #plan_count="{ record }">
          <a-space>
            <a-badge :count="record.plan_count" :max="99" />
            <a-tag v-if="record.has_unsync_plans" color="orange" size="small">
              有未同步
            </a-tag>
          </a-space>
        </template>

        <template #references="{ record }">
          <a-link class="reference-link" @click="handleViewReferences(record)">
            <div class="meta-line">方案：{{ record.plan_count || 0 }}</div>
            <div class="meta-line">定时：{{ record.scheduled_job_ref_count || 0 }}</div>
          </a-link>
        </template>

        <template #created_at="{ record }">
          <MetaInfoLines
            :created-text="`创建：${formatDate(record.created_at)} · ${record.created_by_name || '-'}`"
            :updated-text="`更新：${record.updated_at ? formatDate(record.updated_at) : '-'} · ${record.updated_by_name || record.created_by_name || '-'}`"
          />
        </template>

        <template #actions="{ record }">
          <a-space>
            <a-button
              type="text"
              size="small"
              @click="handleView(record)"
              v-permission="{ resourceType: 'jobtemplate', permission: 'view', resourceId: record.id }"
            >
              <template #icon>
                <icon-eye />
              </template>
              查看
            </a-button>
            <a-button
              type="text"
              size="small"
              @click="handleEdit(record)"
              v-permission="{ resourceType: 'jobtemplate', permission: 'change', resourceId: record.id }"
            >
              <template #icon>
                <icon-edit />
              </template>
              编辑
            </a-button>
            <a-dropdown>
              <a-button type="text" size="small">
                <template #icon>
                  <icon-more />
                </template>
              </a-button>
              <template #content>
                <a-doption
                  :class="{ 'disabled-option': !canCreatePlan }"
                  @click="handleClickCreatePlan(record)"
                >
                  <template #icon>
                    <icon-plus />
                  </template>
                  新增执行方案
                </a-doption>
                <a-doption
                  :class="{ 'disabled-option': !canViewPlans }"
                  @click="handleClickViewPlans(record)"
                >
                  <template #icon>
                    <icon-list />
                  </template>
                  查看执行方案
                </a-doption>
                <a-doption
                  :class="{ 'disabled-option': !canSyncPlans }"
                  @click="handleClickSync(record)"
                >
                  <template #icon>
                    <icon-sync />
                  </template>
                  同步方案
                </a-doption>
                <a-doption
                  :class="{ 'disabled-option': !canCopyTemplate }"
                  @click="handleClickCopyTemplate(record)"
                >
                  <template #icon>
                    <icon-copy />
                  </template>
                  复制
                </a-doption>
                <a-doption
                  :class="['text-red-500', { 'disabled-option': !canDeleteTemplate(record.id) }]"
                  @click="handleClickDeleteTemplate(record)"
                >
                  <template #icon>
                    <icon-delete />
                  </template>
                  删除
                </a-doption>
              </template>
            </a-dropdown>
          </a-space>
        </template>
      </a-table>
    </a-card>

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
import { ref, reactive, onMounted, computed, h } from 'vue'
import { useRouter } from 'vue-router'
import { Message, Modal } from '@arco-design/web-vue'
import { jobTemplateApi } from '@/api/ops'
import type { JobTemplate } from '@/types'
import SyncConfirmModal from './components/SyncConfirmModal.vue'
import { usePermissionsStore } from '@/stores/permissions'
import { useFavoritesStore } from '@/stores/favorites'
import MetaInfoLines from '@/components/MetaInfoLines.vue'
import { useAuthStore } from '@/stores/auth'

const permissionsStore = usePermissionsStore()
const favoritesStore = useFavoritesStore()
const authStore = useAuthStore()

const router = useRouter()

// 响应式数据
const loading = ref(false)
const templates = ref<JobTemplate[]>([])

// 同步确认对话框
const syncModalVisible = ref(false)
const syncTemplateId = ref<number>()
const syncTemplateName = ref<string>()

// 搜索表单
const searchForm = reactive({
  search: '',
  category: '',
  tags: [] as string[],
  favorites_only: false,
  my_templates_only: false,
  created_by: undefined as number | undefined,
  updated_by: undefined as number | undefined
})

// 收藏相关方法
const isFavorite = (id: number) => favoritesStore.isFavorite('job_template', id)

const toggleFavorite = async (id: number) => {
  try {
    const isFavorited = await favoritesStore.toggleFavorite('job_template', id, 'personal')
    Message.success(isFavorited ? '已添加到收藏' : '已取消收藏')
  } catch (e) {
    console.error('切换收藏状态失败:', e)
    Message.error('操作失败')
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

// 分页配置
const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  showTotal: true,
  showPageSize: true,
  pageSizeOptions: ['10', '20', '50', '100']
})

// 表格列配置
const columns = [
  {
    title: '模板名称',
    dataIndex: 'name',
    key: 'name',
    slotName: 'name',
    width: 220
  },
  {
    title: '分类',
    dataIndex: 'category',
    key: 'category',
    slotName: 'category',
    width: 110
  },
  {
    title: '标签',
    dataIndex: 'tags',
    key: 'tags',
    slotName: 'tags',
    width: 250
  },
  {
    title: '步骤数',
    dataIndex: 'step_count',
    key: 'step_count',
    slotName: 'step_count',
    width: 80,
    align: 'center'
  },
  {
    title: '执行方案',
    dataIndex: 'plan_count',
    key: 'plan_count',
    slotName: 'plan_count',
    width: 120,
    align: 'center'
  },
  {
    title: '被引用',
    dataIndex: 'references',
    key: 'references',
    slotName: 'references',
    width: 120,
    align: 'center'
  },
  {
    title: '描述',
    dataIndex: 'description',
    key: 'description',
    ellipsis: true,
    tooltip: true,
    width: 250
  },
  {
    title: '创建/更新',
    dataIndex: 'created_at',
    key: 'created_at',
    slotName: 'created_at',
    width: 240
  },
  {
    title: '操作',
    key: 'actions',
    slotName: 'actions',
    fixed: 'right',
    width: 250
  }
]

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
    Message.error('获取作业模板列表失败')
  } finally {
    loading.value = false
  }
}

// 搜索
const handleSearch = () => {
  pagination.current = 1
  fetchTemplates()
}

// 重置搜索
const handleReset = () => {
  searchForm.search = ''
  searchForm.category = ''
  searchForm.tags = []
  searchForm.favorites_only = false
  searchForm.my_templates_only = false
  searchForm.created_by = undefined
  searchForm.updated_by = undefined
  // 重置创建者/更新者过滤
  filteredCreators.value = [...availableUsers.value]
  filteredUpdaters.value = [...availableUsers.value]
  pagination.current = 1
  fetchTemplates()
}

// 分页处理
const handlePageChange = (page: number) => {
  pagination.current = page
  fetchTemplates()
}

const handlePageSizeChange = (pageSize: number) => {
  pagination.pageSize = pageSize
  pagination.current = 1
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
    Message.success('模板数据已复制，请修改模板名称后保存')
  } catch (error) {
    console.error('复制模板失败:', error)
    Message.error('复制模板失败')
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

  Modal.confirm({
    title: hasRefs ? '无法删除' : '确认删除',
    content,
    okButtonProps: { status: 'danger', disabled: hasRefs },
    onOk: async () => {
      if (hasRefs) return
      try {
        await jobTemplateApi.deleteTemplate(record.id)
        Message.success('作业模板删除成功')
        await fetchTemplates()
      } catch (error: any) {
        console.error('删除作业模板失败:', error)
        const message = error?.response?.data?.message || '删除作业模板失败'
        Message.error(message)
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
    Message.error(message)
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

  const modal = Modal.info({
    title: '引用关系',
    content,
    okText: '关闭'
  })
  modalClose = modal?.close
}

const showNoPermissionMessage = () => {
  Message.warning('没有权限执行此操作，请联系管理员开放权限')
}

const handleClickCreatePlan = (record: JobTemplate) => {
  if (!canCreatePlan.value) {
    showNoPermissionMessage()
    return
  }
  handleCreatePlan(record)
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

const canDeleteTemplate = (templateId: number): boolean => {
  if (permissionsStore.isSuperUser) return true
  return (
    permissionsStore.hasPermission('jobtemplate', 'delete', templateId) ||
    permissionsStore.hasPermission('jobtemplate', 'delete')
  )
}

// 生命周期
onMounted(() => {
  fetchTemplates()
})
</script>

<style scoped>
.job-templates-page {
  padding: 0;
}

.page-header {
  background: white;
  border-radius: 6px;
  padding: 20px 24px;
  margin-bottom: 16px;
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.03), 0 1px 6px -1px rgba(0, 0, 0, 0.02), 0 2px 4px 0 rgba(0, 0, 0, 0.02);
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left h2 {
  margin: 0 0 4px 0;
  font-size: 20px;
  font-weight: 600;
  color: #1d2129;
}

.header-desc {
  margin: 0;
  font-size: 14px;
  color: #86909c;
}

.mb-4 {
  margin-bottom: 16px;
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
  color: var(--color-text-3);
  font-size: 12px;
}

/* 模板名称单元格样式 */
.template-name-cell {
  display: flex;
  align-items: center;
  gap: 4px;
}

.template-link {
  overflow: hidden;
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
  color: var(--color-text-3);
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
  color: var(--color-primary-6);
}

.meta-line {
  font-size: 12px;
  line-height: 1.4;
  color: var(--color-text-3);
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

/* 修复表格固定列样式 */
:deep(.arco-table) {
  /* 表头背景色 */
  .arco-table-th {
    background-color: #fff;
  }

  .arco-table-td {
    padding: 12px 16px;
  }
}
</style>
