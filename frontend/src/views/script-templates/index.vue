<template>
  <div 
    class="script-templates-page"
    v-page-permissions="{ 
      resourceType: 'scripttemplate', 
      permissions: ['view', 'add', 'change', 'delete'],
      resourceIds: templates.map(t => t.id)
    }"
  >
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-content">
        <div class="header-left">
          <h2>脚本模板</h2>
          <p class="header-desc">创建和管理可重用的脚本模板</p>
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
              v-permission="{ resourceType: 'scripttemplate', permission: 'add' }"
              type="primary" 
              @click="handleCreate"
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

    <!-- 搜索筛选 -->
    <a-card class="mb-4">
      <a-form :model="searchForm" layout="inline" class="compact-filter-form">
        <a-form-item>
          <a-input
            v-model="searchForm.name"
            placeholder="模板名称"
            allow-clear
            @press-enter="handleSearch"
            @clear="handleSearch"
            style="width: 180px"
          />
        </a-form-item>
        <a-form-item>
          <a-select
            v-model="searchForm.script_type"
            placeholder="脚本类型"
            allow-clear
            @change="handleSearch"
            @clear="handleSearch"
            style="width: 120px"
          >
            <a-option value="shell">Shell</a-option>
            <a-option value="python">Python</a-option>
            <a-option value="powershell">PowerShell</a-option>
            <a-option value="perl">Perl</a-option>
            <a-option value="javascript">JavaScript</a-option>
            <a-option value="go">Go</a-option>
          </a-select>
        </a-form-item>
        <a-form-item>
          <a-select
            v-model="searchForm.category"
            placeholder="分类"
            allow-clear
            @change="handleSearch"
            @clear="handleSearch"
            style="width: 120px"
          >
            <a-option value="deployment">部署</a-option>
            <a-option value="monitoring">监控</a-option>
            <a-option value="maintenance">维护</a-option>
            <a-option value="backup">备份</a-option>
            <a-option value="security">安全</a-option>
            <a-option value="other">其他</a-option>
          </a-select>
        </a-form-item>
        <a-form-item>
          <a-select
            v-model="searchForm.tags"
            placeholder="标签"
            allow-clear
            multiple
            @change="handleSearch"
            @clear="handleSearch"
            style="width: 180px"
          >
            <a-option
              v-for="tag in availableTags"
              :key="tag"
              :value="tag"
            >
              {{ tag }}
            </a-option>
          </a-select>
        </a-form-item>
        <a-form-item>
          <a-select
            v-model="searchForm.created_by"
            placeholder="创建者"
            allow-clear
            show-search
            filter-option="false"
            @search="handleCreatorSearch"
            @change="handleSearch"
            @clear="handleSearch"
            style="width: 140px"
          >
            <a-option
              v-for="user in filteredCreators"
              :key="user.id"
              :value="user.id"
            >
              {{ user.name }}
            </a-option>
          </a-select>
        </a-form-item>
        <a-form-item label="收藏">
          <a-switch v-model="searchForm.favorites_only" @change="handleSearch" />
        </a-form-item>
        <a-form-item class="search-actions">
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
        </a-form-item>
      </a-form>
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
            <a-link @click="handleDetail(record)" class="template-link">{{ record.name }}</a-link>
          </div>
        </template>

        <template #script_type="{ record }">
          <a-tag :color="getScriptTypeColor(record.script_type)">
            {{ getScriptTypeText(record.script_type) }}
          </a-tag>
        </template>

        <template #category="{ record }">
          <a-tag v-if="record.category" color="blue">
            {{ getCategoryText(record.category) }}
          </a-tag>
          <span v-else>-</span>
        </template>

        <template #status="{ record }">
          <a-tag :color="record.is_active ? 'green' : 'red'">
            {{ record.is_active ? '上线' : '下线' }}
          </a-tag>
        </template>

        <template #references="{ record }">
          <a-link class="reference-link" @click="handleViewReferences(record)">
            <div class="meta-line">作业：{{ record.job_template_ref_count || 0 }}</div>
            <div class="meta-line">方案：{{ record.execution_plan_ref_count || 0 }}</div>
          </a-link>
        </template>

        <template #tags="{ record }">
          <div v-if="record.tag_list && record.tag_list.length">
            <a-space wrap>
              <a-tag v-for="tag in record.tag_list" :key="tag.key || tag" class="tag-item">
                {{ formatTag(tag) }}
              </a-tag>
            </a-space>
          </div>
          <div v-else-if="record.tags_json && Object.keys(record.tags_json).length">
            <a-space wrap>
              <a-tag v-for="(value, key) in record.tags_json" :key="key" class="tag-item">
                {{ `${key}=${value}` }}
              </a-tag>
            </a-space>
          </div>
          <span v-else class="text-gray">-</span>
        </template>

        <template #created_at="{ record }">
          <MetaInfoLines
            :created-text="`创建：${formatTime(record.created_at)} · ${record.created_by_name || '-'}`"
            :updated-text="`更新：${record.updated_at ? formatTime(record.updated_at) : '-'} · ${record.updated_by_name || record.created_by_name || '-'}`"
          />
        </template>

        <template #actions="{ record }">
          <a-space>
            <a-button
              v-if="record.is_active"
              v-permission="{ resourceType: 'scripttemplate', permission: 'view', resourceId: record.id }"
              type="text"
              size="small"
              @click="handleExecute(record)"
            >
              去执行
            </a-button>
            <a-dropdown>
              <a-button type="text" size="small">
                <template #icon>
                  <icon-more />
                </template>
              </a-button>
              <template #content>
                <a-doption
                  :class="{ 'disabled-option': !canManageVersions(record.id!) }"
                  @click="handleClickManageVersions(record)"
                >
                  <template #icon>
                    <icon-history />
                  </template>
                  版本管理
                </a-doption>
                <a-doption
                  :class="{ 'disabled-option': !canToggleStatus(record.id!) }"
                  @click="handleClickToggleStatus(record)"
                >
                  <template #icon>
                    <icon-poweroff />
                  </template>
                  {{ record.is_active ? '下线' : '上线' }}
                </a-doption>
                <a-doption
                  :class="{ 'disabled-option': !canCopyTemplate }"
                  @click="handleClickCopy(record)"
                >
                  <template #icon>
                    <icon-copy />
                  </template>
                  复制
                </a-doption>
                <a-doption 
                  :class="['text-red-500', { 'disabled-option': !canDeleteTemplate(record) }]"
                  @click="handleClickDelete(record)" 
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
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed, h } from 'vue'
import { useRouter } from 'vue-router'
import { Message, Modal } from '@arco-design/web-vue'
import { scriptTemplateApi } from '@/api/ops'
import type { ScriptTemplate } from '@/types'
import dayjs from 'dayjs'
import { usePermissionsStore } from '@/stores/permissions'
import { useFavoritesStore } from '@/stores/favorites'
import MetaInfoLines from '@/components/MetaInfoLines.vue'

const router = useRouter()
const loading = ref(false)
const templates = ref<ScriptTemplate[]>([])
const permissionsStore = usePermissionsStore()
const favoritesStore = useFavoritesStore()

// 搜索表单
const searchForm = reactive({
  name: '',
  script_type: '',
  category: '',
  tags: [] as string[],
  favorites_only: false,
  created_by: undefined as number | undefined
})

// 可用标签列表
const availableTags = ref<string[]>([])

// 可用用户列表（创建者）
const availableUsers = ref<Array<{id: number, username: string, name: string}>>([])

// 创建者搜索过滤结果
const filteredCreators = ref<Array<{id: number, username: string, name: string}>>([])

// 收藏相关方法
const isFavorite = (id: number) => favoritesStore.isFavorite('script_template', id)

const toggleFavorite = async (id: number) => {
  try {
    const isFavorited = await favoritesStore.toggleFavorite('script_template', id, 'personal')
    Message.success(isFavorited ? '已添加到收藏' : '已取消收藏')
  } catch (e) {
    console.error('切换收藏状态失败:', e)
    Message.error('操作失败')
  }
}

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
    width: 280,
    ellipsis: true,
    tooltip: true
  },
  {
    title: '脚本类型',
    dataIndex: 'script_type',
    key: 'script_type',
    slotName: 'script_type',
    width: 110,
  },
  {
    title: '分类',
    dataIndex: 'category',
    key: 'category',
    slotName: 'category',
    width: 110,
  },
  {
    title: '线上版本',
    dataIndex: 'version',
    key: 'version',
    width: 100,
  },
  {
    title: '状态',
    dataIndex: 'is_active',
    key: 'is_active',
    slotName: 'status',
    width: 100,
  },
  {
    title: '被引用',
    dataIndex: 'references',
    key: 'references',
    slotName: 'references',
    width: 120,
  },
  {
    title: '标签',
    dataIndex: 'tag_list',
    key: 'tag_list',
    slotName: 'tags',
    width: 240,
  },
  {
    title: '描述',
    dataIndex: 'description',
    key: 'description',
    ellipsis: true,
    tooltip: true,
    width: 200,
  },
  {
    title: '创建/更新',
    dataIndex: 'created_at',
    key: 'created_at',
    slotName: 'created_at',
    width: 240,
  },
  {
    title: '操作',
    key: 'actions',
    slotName: 'actions',
    width: 250,
    fixed: 'right',
  },
]

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
      templates.value.forEach(template => {
        if (template.created_by && template.created_by_name) {
          userMap.set(template.created_by, {
            id: template.created_by,
            username: template.created_by_name,
            name: template.created_by_name
          })
        }
      })
      availableUsers.value = Array.from(userMap.values()).sort((a, b) => a.name.localeCompare(b.name))
      // 初始化过滤结果为全部用户
      filteredCreators.value = [...availableUsers.value]
    }
  } catch (error) {
    console.error('获取用户列表失败:', error)
  }
}

// 处理创建者搜索
const handleCreatorSearch = (searchValue: string) => {
  if (!searchValue.trim()) {
    filteredCreators.value = [...availableUsers.value]
    return
  }

  const searchTerm = searchValue.toLowerCase().trim()
  filteredCreators.value = availableUsers.value.filter(user =>
    user.name.toLowerCase().includes(searchTerm) ||
    user.username.toLowerCase().includes(searchTerm)
  )
}

// 获取脚本模板列表
const fetchTemplates = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.current,
      page_size: pagination.pageSize,
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
    Message.error('获取脚本模板列表失败')
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
  fetchTemplates()
}

// 重置搜索
const handleReset = () => {
  Object.assign(searchForm, {
    name: '',
    script_type: '',
    category: '',
    tags: [],
    favorites_only: false,
    created_by: undefined
  })
  // 重置创建者过滤
  filteredCreators.value = [...availableUsers.value]
  pagination.current = 1
  fetchTemplates()
}

// 分页变化
const handlePageChange = (page: number) => {
  pagination.current = page
  fetchTemplates()
}

const handlePageSizeChange = (pageSize: number) => {
  pagination.pageSize = pageSize
  pagination.current = 1
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
    Message.warning('模板信息不完整')
    return
  }
  if (!record.is_active) {
    Message.warning('模板未上线，无法执行')
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

  Modal.confirm({
    title: hasRefs ? '无法删除' : '确认删除',
    content,
    okButtonProps: { disabled: hasRefs },
    onOk: async () => {
      if (hasRefs) return
      try {
        await scriptTemplateApi.deleteTemplate(record.id!)
        Message.success('模板删除成功')
        await fetchTemplates()
      } catch (error: any) {
        const message = error?.response?.data?.message || '模板删除失败'
        Message.error(message)
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
    Message.error(message)
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
  Modal.confirm({
    title: `确认${action}`,
    content: `确定要${action}模板 "${record.name}" 吗？`,
    onOk: async () => {
      try {
        const result = await scriptTemplateApi.toggleStatus(record.id!)
        record.is_active = result.is_active
        Message.success(`模板已${action}`)
      } catch (error) {
        console.error(`${action}失败:`, error)
        Message.error(`${action}失败`)
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
  fetchTemplates()
})
</script>

<style scoped>
.script-templates-page {
  padding: 0;
}

.search-actions {
  margin-left: auto;
  display: flex;
  align-items: center;
  padding-top: 0;
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

:deep(.compact-filter-form .arco-form-item) {
  margin-right: 8px;
  margin-bottom: 0;
}

:deep(.compact-filter-form .arco-form-item:last-child) {
  margin-right: 0;
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

.tag-item {
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  display: inline-block;
}

/* 表格样式优化 */
:deep(.arco-table) {
  .arco-table-th {
    background-color: #fff !important;
    font-weight: 600;
  }

  .arco-table-td {
    padding: 12px 16px;
  }

  /* 操作列按钮间距 */
  .arco-space-item {
    margin-right: 8px;
  }
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
