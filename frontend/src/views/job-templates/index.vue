<template>
  <div class="job-templates-page">
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
            <a-button type="primary" @click="handleCreate">
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
      <a-form :model="searchForm" layout="inline">
        <a-form-item label="模板名称">
          <a-input
            v-model="searchForm.search"
            placeholder="请输入模板名称"
            allow-clear
            @press-enter="handleSearch"
            @clear="handleSearch"
            style="width: 200px"
          />
        </a-form-item>
        <a-form-item label="分类">
          <a-select
            v-model="searchForm.category"
            placeholder="选择分类"
            allow-clear
            @change="handleSearch"
            style="width: 150px"
          >
            <a-option value="deployment">部署</a-option>
            <a-option value="maintenance">维护</a-option>
            <a-option value="monitoring">监控</a-option>
            <a-option value="backup">备份</a-option>
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
        :scroll="{ x: 1150 }"
        @page-change="handlePageChange"
        @page-size-change="handlePageSizeChange"
      >
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

        <template #created_at="{ record }">
          <div>
            <div>{{ formatDate(record.created_at) }}</div>
            <div class="text-gray-400 text-xs">{{ record.created_by_name }}</div>
          </div>
        </template>

        <template #actions="{ record }">
          <a-space>
            <a-button type="text" size="small" @click="handleView(record)">
              <template #icon>
                <icon-eye />
              </template>
              查看
            </a-button>
            <a-button type="text" size="small" @click="handleEdit(record)">
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
                <a-doption @click="handleCreatePlan(record)">
                  <template #icon>
                    <icon-plus />
                  </template>
                  新增执行方案
                </a-doption>
                <a-doption @click="handleViewPlans(record)">
                  <template #icon>
                    <icon-list />
                  </template>
                  查看执行方案
                </a-doption>
                <a-doption @click="handleSync(record)">
                  <template #icon>
                    <icon-sync />
                  </template>
                  同步方案
                </a-doption>
                <a-doption @click="handleCopy(record)">
                  <template #icon>
                    <icon-copy />
                  </template>
                  复制
                </a-doption>
                <a-doption @click="handleDelete(record)" class="text-red-500">
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
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import { jobTemplateApi } from '@/api/ops'
import type { JobTemplate } from '@/types'
import SyncConfirmModal from './components/SyncConfirmModal.vue'

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
    width: 200,
    ellipsis: true,
    tooltip: true
  },
  {
    title: '分类',
    dataIndex: 'category',
    key: 'category',
    slotName: 'category',
    width: 100
  },
  {
    title: '标签',
    dataIndex: 'tags',
    key: 'tags',
    slotName: 'tags',
    width: 200
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
    title: '描述',
    dataIndex: 'description',
    key: 'description',
    ellipsis: true,
    tooltip: true,
    width: 250
  },
  {
    title: '创建信息',
    dataIndex: 'created_at',
    key: 'created_at',
    slotName: 'created_at',
    width: 150
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
    // 从所有模板中提取标签
    const allTags = new Set<string>()
    templates.value.forEach(template => {
      if (template.tag_list && template.tag_list.length > 0) {
        template.tag_list.forEach(tagObj => {
          // 将键值对转换为 "key:value" 格式
          allTags.add(`${tagObj.key}:${tagObj.value}`)
        })
      }
    })
    availableTags.value = Array.from(allTags).sort()
  } catch (error) {
    console.error('获取标签列表失败:', error)
  }
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
    }

    // 过滤空值
    Object.keys(params).forEach(key => {
      if (params[key] === undefined ||
          (Array.isArray(params[key]) && params[key].length === 0)) {
        delete params[key]
      }
    })

    const response = await jobTemplateApi.getTemplates(params)
    templates.value = response.results || []
    pagination.total = response.total || 0

    // 获取可用标签
    await fetchAvailableTags()
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
  router.push('/job-templates/editor')
}

const handleView = (record: JobTemplate) => {
  router.push(`/job-templates/detail/${record.id}`)
}

const handleEdit = (record: JobTemplate) => {
  router.push(`/job-templates/editor/${record.id}`)
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
    router.push('/job-templates/editor?action=copy')
    Message.success('模板数据已复制，请修改模板名称后保存')
  } catch (error) {
    console.error('复制模板失败:', error)
    Message.error('复制模板失败')
  }
}

const handleDelete = async (record: JobTemplate) => {
  try {
    await jobTemplateApi.deleteTemplate(record.id)
    Message.success('模板删除成功')
    fetchTemplates()
  } catch (error) {
    console.error('删除模板失败:', error)
    Message.error('删除模板失败')
  }
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

.text-gray-400 {
  color: #9ca3af;
}

.text-xs {
  font-size: 12px;
}

/* 标签容器样式 */
.tags-container {
  max-width: 100%;
  overflow: hidden;
}

.tag-item {
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  display: inline-block;
}

.tag-more {
  flex-shrink: 0;
}

/* 修复表格固定列样式 */
:deep(.arco-table) {
  /* 表头背景色 */
  .arco-table-th {
    background-color: #fff;
  }
}
</style>
