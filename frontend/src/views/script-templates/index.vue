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
      <a-form :model="searchForm" layout="inline">
        <a-form-item label="模板名称">
          <a-input
            v-model="searchForm.name"
            placeholder="请输入模板名称"
            allow-clear
            @press-enter="handleSearch"
            @clear="handleSearch"
            style="width: 200px"
          />
        </a-form-item>
        <a-form-item label="脚本类型">
          <a-select
            v-model="searchForm.script_type"
            placeholder="请选择脚本类型"
            allow-clear
            @change="handleSearch"
            @clear="handleSearch"
            style="width: 120px"
          >
            <a-option value="shell">Shell</a-option>
            <a-option value="python">Python</a-option>
            <a-option value="powershell">PowerShell</a-option>
          </a-select>
        </a-form-item>
        <a-form-item label="分类">
          <a-select
            v-model="searchForm.category"
            placeholder="请选择分类"
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
        <a-form-item label="标签">
          <a-select
            v-model="searchForm.tags"
            placeholder="请选择标签"
            allow-clear
            multiple
            @change="handleSearch"
            @clear="handleSearch"
            style="width: 200px"
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
        :scroll="{ x: 1200 }"
        @page-change="handlePageChange"
        @page-size-change="handlePageSizeChange"
      >
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

        <template #tags="{ record }">
          <div v-if="record.tag_list && record.tag_list.length > 0" class="tags-container">
            <a-tooltip content-class="script-tags-tooltip">
              <template #content>
                <a-space>
                  <a-tag v-for="tag in record.tag_list" :key="tag" size="small">
                    {{ tag }}
                  </a-tag>
                </a-space>
              </template>
              <span class="tags-ellipsis">...</span>
            </a-tooltip>
          </div>
          <div v-else-if="record.tags_json && Object.keys(record.tags_json).length > 0" class="tags-container">
            <a-tooltip content-class="script-tags-tooltip">
              <template #content>
                <a-space>
                  <a-tag v-for="(value, key) in record.tags_json" :key="key" size="small">
                    {{ key }}:{{ value }}
                  </a-tag>
                </a-space>
              </template>
              <span class="tags-ellipsis">...</span>
            </a-tooltip>
          </div>
          <span v-else>-</span>
        </template>

        <template #created_at="{ record }">
          {{ formatTime(record.created_at) }}
        </template>

        <template #actions="{ record }">
          <a-space>
            <a-button 
              v-permission="{ resourceType: 'scripttemplate', permission: 'view', resourceId: record.id }"
              type="text" 
              size="small" 
              @click="handleView(record)"
            >
              <template #icon>
                <icon-eye />
              </template>
              查看
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
                  :class="['text-red-500', { 'disabled-option': !canDeleteTemplate(record.id!) }]"
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

    <!-- 预览弹窗 -->
    <a-modal
      v-model:visible="previewVisible"
      title="脚本预览"
      :width="800"
      :footer="false"
    >
      <div v-if="currentTemplate">
        <a-descriptions :column="2" bordered class="mb-4">
          <a-descriptions-item label="模板名称">
            {{ currentTemplate.name }}
          </a-descriptions-item>
          <a-descriptions-item label="脚本类型">
            <a-tag :color="getScriptTypeColor(currentTemplate.script_type)">
              {{ getScriptTypeText(currentTemplate.script_type) }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="分类">
            {{ getCategoryText(currentTemplate.category) }}
          </a-descriptions-item>
          <a-descriptions-item label="版本">
            {{ currentTemplate.version || '1.0.0' }}
          </a-descriptions-item>
          <a-descriptions-item label="状态">
            <a-tag :color="currentTemplate.is_active ? 'green' : 'red'">
              {{ currentTemplate.is_active ? '上线' : '下线' }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="可见性">
            <a-tag :color="currentTemplate.is_public ? 'blue' : 'gray'">
              {{ currentTemplate.is_public ? '公开' : '私有' }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="创建者">
            {{ currentTemplate.created_by_name }}
          </a-descriptions-item>
          <a-descriptions-item label="标签">
            <a-space v-if="currentTemplate.tags_json && Object.keys(currentTemplate.tags_json).length > 0">
              <a-tag v-for="(value, key) in currentTemplate.tags_json" :key="key" size="small">
                {{ key }}:{{ value }}
              </a-tag>
            </a-space>
            <a-space v-else-if="currentTemplate.tag_list && currentTemplate.tag_list.length > 0">
              <a-tag v-for="tag in currentTemplate.tag_list" :key="tag" size="small">
                {{ tag }}
              </a-tag>
            </a-space>
            <span v-else>-</span>
          </a-descriptions-item>
          <a-descriptions-item label="描述" :span="2">
            {{ currentTemplate.description || '暂无描述' }}
          </a-descriptions-item>
        </a-descriptions>

        <div class="mb-4">
          <div class="preview-header">
            <h4>脚本内容</h4>
          </div>
          <simple-monaco-editor
            :model-value="currentTemplate.script_content || currentTemplate.content"
            :language="currentTemplate.script_type"
            :height="400"
            :readonly="true"
          />
        </div>
      </div>
    </a-modal>

    <!-- 版本管理相关 UI 已迁移到独立页面 /script-templates/:id/versions -->
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { Message, Modal } from '@arco-design/web-vue'
import { scriptTemplateApi } from '@/api/ops'
import type { ScriptTemplate } from '@/types'
import SimpleMonacoEditor from '@/components/SimpleMonacoEditor.vue'
import dayjs from 'dayjs'
import { usePermissionsStore } from '@/stores/permissions'

const router = useRouter()
const loading = ref(false)
const templates = ref<ScriptTemplate[]>([])
const previewVisible = ref(false)
const currentTemplate = ref<ScriptTemplate | null>(null)
const permissionsStore = usePermissionsStore()

// 搜索表单
const searchForm = reactive({
  name: '',
  script_type: '',
  category: '',
  tags: [] as string[],
})

// 可用标签列表
const availableTags = ref<string[]>([])

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
    width: 120,
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
    title: '版本',
    dataIndex: 'version',
    key: 'version',
    width: 90,
  },
  {
    title: '状态',
    dataIndex: 'is_active',
    key: 'is_active',
    slotName: 'status',
    width: 100,
  },
  {
    title: '标签',
    dataIndex: 'tag_list',
    key: 'tag_list',
    slotName: 'tags',
    width: 110,
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
    title: '创建者',
    dataIndex: 'created_by_name',
    key: 'created_by_name',
    width: 110,
  },
  {
    title: '创建时间',
    dataIndex: 'created_at',
    key: 'created_at',
    slotName: 'created_at',
    width: 140,
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

// 获取模板列表
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

    console.log('调用模板列表API，参数:', params)
    const response = await scriptTemplateApi.getTemplates(params)
    console.log('获取到的模板列表响应:', response)
    templates.value = response.results
    pagination.total = response.total
    console.log('设置模板列表数据:', templates.value)

    // 拉取可用标签（独立接口，保持选项完整）
    fetchAvailableTags()
  } catch (error) {
    console.error('获取模板列表失败:', error)
    Message.error('获取模板列表失败')
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
  })
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

// 查看模板
const handleView = async (record: ScriptTemplate) => {
  console.log('查看模板，record数据:', record)
  console.log('record标签数据 tags_json:', record.tags_json)
  console.log('record标签数据 tag_list:', record.tag_list)

  // 如果列表数据中已经有完整的脚本内容，直接使用
  if (record.script_content || record.content) {
    console.log('使用列表数据，包含脚本内容')
    currentTemplate.value = record
    previewVisible.value = true
    return
  }

  try {
    // 调用详情API获取完整的模板数据
    console.log('调用详情API，模板ID:', record.id)
    const templateDetail = await scriptTemplateApi.getTemplate(record.id!)
    console.log('获取到的模板详情:', templateDetail)
    console.log('详情标签数据 tags_json:', templateDetail.tags_json)
    console.log('详情标签数据 tag_list:', templateDetail.tag_list)
    currentTemplate.value = templateDetail
    previewVisible.value = true
  } catch (error) {
    console.error('获取模板详情失败:', error)
    console.log('使用列表数据作为后备:', record)
    currentTemplate.value = record
    previewVisible.value = true
    Message.warning('获取模板详情失败，显示基本信息')
  }
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
const handleDelete = (record: ScriptTemplate) => {
  Modal.confirm({
    title: '确认删除',
    content: `确定要删除任务"${record.name}"吗？此操作不可恢复。`,
    onOk: async () => {
      try {
        await scriptTemplateApi.deleteTemplate(record.id)
        Message.success('模板删除成功')
        fetchTemplates()
      } catch (error) {
        Message.error('模板删除失败')
        console.error('删除模板失败:', error)
      }
    }
  })
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
  if (!canDeleteTemplate(record.id!)) {
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
  }
  return colors[type] || 'gray'
}

const getScriptTypeText = (type: string) => {
  const texts = {
    shell: 'Shell',
    python: 'Python',
    powershell: 'PowerShell',
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

const canDeleteTemplate = (templateId: number): boolean => {
  if (permissionsStore.isSuperUser) return true
  return (
    permissionsStore.hasPermission('scripttemplate', 'delete', templateId) ||
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
