<template>
  <div
    class="execution-plans-page"
    v-page-permissions="{
      resourceType: 'executionplan',
      permissions: ['view', 'add', 'change', 'delete', 'execute'],
      resourceIds: plans.map(p => p.id)
    }"
  >
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-content">
        <div class="header-left">
          <h2>执行方案管理</h2>
          <p class="header-desc">基于作业模板创建和管理具体的执行方案</p>
        </div>
        <div class="header-right">
          <a-space>
            <a-button @click="handleRefresh">
              <template #icon>
                <icon-refresh />
              </template>
              刷新
            </a-button>
            <a-dropdown @select="handleCreateAction">
              <a-button
                type="primary"
                v-permission="{ resourceType: 'executionplan', permission: 'add' }"
              >
                <template #icon>
                  <icon-plus />
                </template>
                创建方案
                <template #suffix>
                  <icon-down />
                </template>
              </a-button>
              <template #content>
                <a-doption value="select-template">
                  <template #icon>
                    <icon-file />
                  </template>
                  基于作业模板创建
                </a-doption>
                <a-doption value="blank">
                  <template #icon>
                    <icon-plus />
                  </template>
                  空白方案
                </a-doption>
              </template>
            </a-dropdown>
            <a-button
              type="outline"
              :disabled="selectedRowKeys.length === 0"
              @click="handleBatchSync"
              v-permission="{ resourceType: 'executionplan', permission: 'change' }"
            >
              <template #icon>
                <icon-sync />
              </template>
              批量同步
            </a-button>
          </a-space>
        </div>
      </div>
    </div>

    <!-- 搜索和筛选 -->
    <a-card class="mb-4">
      <a-form :model="searchForm" layout="inline" class="compact-filter-form">
        <a-form-item>
          <a-input
            v-model="searchForm.search"
            placeholder="方案名称"
            allow-clear
            @press-enter="handleSearch"
            @clear="handleSearch"
            style="width: 180px"
          />
        </a-form-item>
        <a-form-item>
          <a-select
            v-model="searchForm.template_id"
            placeholder="所属模板"
            allow-clear
            @change="handleSearch"
            @clear="handleSearch"
            style="width: 200px"
            :loading="templateLoading"
          >
            <a-option
              v-for="template in templates"
              :key="template.id"
              :value="template.id"
            >
              {{ template.name }}
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
        <a-form-item label="我的方案">
          <a-switch v-model="searchForm.my_plans_only" @change="handleSearch" />
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

    <!-- 执行方案列表 -->
    <a-card>
      <a-table
        :columns="columns"
        :data="plans"
        :loading="loading"
        :pagination="pagination"
        :row-selection="rowSelection"
        @selection-change="handleSelectionChange"
        @page-change="handlePageChange"
        @page-size-change="handlePageSizeChange"
        row-key="id"
      >
        <template #name="{ record }">
          <div class="plan-name">
            <div class="plan-name-row">
              <a-button
                type="text"
                size="mini"
                class="favorite-btn"
                @click.stop="toggleFavorite(record.id)"
              >
                <icon-star-fill v-if="isFavorite(record.id)" class="favorite-icon active" />
                <icon-star v-else class="favorite-icon" />
              </a-button>
              <a-link @click="handleView(record)">{{ record.name }}</a-link>
            </div>
            <div class="plan-desc">{{ record.description || '无描述' }}</div>
          </div>
        </template>

        <template #template="{ record }">
          <div class="template-info">
            <div class="template-name">{{ record.template_name }}</div>
            <div class="template-category">{{ record.template_category || '未分类' }}</div>
          </div>
        </template>



        <template #stats="{ record }">
          <div class="stats-info">
            <div class="stat-item">
              <span class="stat-label">步骤:</span>
              <span class="stat-value">{{ record.step_count || 0 }}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">执行:</span>
              <span class="stat-value">{{ record.total_executions || 0 }}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">成功率:</span>
              <span class="stat-value">{{ record.success_rate || 0 }}%</span>
            </div>
          </div>
        </template>

        <template #created_info="{ record }">
          <div class="created-info">
            <div class="created-by">{{ record.created_by_name }}</div>
            <div class="created-time">{{ formatDateTime(record.created_at) }}</div>
          </div>
        </template>

        <template #actions="{ record }">
          <a-space>
            <a-button
              type="text"
              size="small"
              @click="handleView(record)"
              v-permission="{ resourceType: 'executionplan', permission: 'view', resourceId: record.id }"
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
              v-permission="{ resourceType: 'executionplan', permission: 'change', resourceId: record.id }"
            >
              <template #icon>
                <icon-edit />
              </template>
              编辑
            </a-button>
            <a-button
              type="text"
              size="small"
              status="success"
              @click="handleExecute(record)"
              v-permission="{ resourceType: 'executionplan', permission: 'execute', resourceId: record.id }"
            >
              <template #icon>
                <icon-play-arrow />
              </template>
              执行
            </a-button>
            <a-button
              type="text"
              size="small"
              @click="handleSchedule(record)"
              v-permission="{ resourceType: 'executionplan', permission: 'execute', resourceId: record.id }"
            >
              <template #icon>
                <icon-schedule />
              </template>
              定时执行
            </a-button>
            <a-dropdown>
              <a-button type="text" size="small">
                <template #icon>
                  <icon-more />
                </template>
              </a-button>
              <template #content>

                <a-doption
                  value="delete"
                  :class="['text-red-500', { 'disabled-option': !canDeletePlan(record.id) }]"
                  @click="handleClickMoreAction('delete', record)"
                >
                  <template #icon>
                    <icon-delete />
                  </template>
                  删除方案
                </a-doption>
              </template>
            </a-dropdown>
          </a-space>
        </template>
      </a-table>
    </a-card>
    <BatchSyncPreviewModal
      v-model="batchSyncModalVisible"
      :plan-ids="batchSyncPlanIds"
      @sync-success="handleBatchSyncSuccess"
    />

    <!-- 模板选择弹窗 -->
    <a-modal
      v-model:visible="templateSelectVisible"
      title="选择作业模板"
      width="800px"
      @ok="handleTemplateSelect"
      @cancel="handleTemplateSelectCancel"
    >
      <div class="template-select-content">
        <a-input
          v-model="templateSearchText"
          placeholder="搜索模板名称"
          allow-clear
          style="margin-bottom: 16px"
        >
          <template #prefix>
            <icon-search />
          </template>
        </a-input>

        <a-table
          :columns="templateColumns"
          :data="filteredTemplatesForSelect"
          :loading="templateLoading"
          :pagination="false"
          row-key="id"
          :row-selection="{ type: 'radio', selectedRowKeys: selectedTemplateKeys, onChange: handleTemplateRowSelect }"
          @row-click="handleTemplateRowClick"
          max-height="400px"
        >
          <template #name="{ record }">
            <div class="template-name">
              <div class="name">{{ record.name }}</div>
              <div class="desc">{{ record.description || '无描述' }}</div>
            </div>
          </template>

          <template #category="{ record }">
            <a-tag v-if="record.category" color="blue">{{ record.category }}</a-tag>
            <span v-else class="text-gray">未分类</span>
          </template>

          <template #stats="{ record }">
            <div class="stats">
              <span>步骤: {{ record.step_count || 0 }}</span>
              <span>方案: {{ record.plan_count || 0 }}</span>
            </div>
          </template>
        </a-table>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Message, Modal } from '@arco-design/web-vue'
import { executionPlanApi, jobTemplateApi } from '@/api/ops'
import type { ExecutionPlan, JobTemplate } from '@/types'
import { usePermissionsStore } from '@/stores/permissions'
import { useFavoritesStore } from '@/stores/favorites'
import { useAuthStore } from '@/stores/auth'
import { defineAsyncComponent } from 'vue'
// @ts-ignore - some editors/tsserver may not immediately include newly added .vue files in project file list
const BatchSyncPreviewModal = defineAsyncComponent(() => import('./components/BatchSyncPreviewModal.vue'))

const permissionsStore = usePermissionsStore()
const favoritesStore = useFavoritesStore()
const authStore = useAuthStore()

const router = useRouter()
const route = useRoute()

// 响应式数据
const loading = ref(false)
const templateLoading = ref(false)
const plans = ref<ExecutionPlan[]>([])
const templates = ref<JobTemplate[]>([])

// 可用用户列表（创建者）
const availableUsers = ref<Array<{id: number, username: string, name: string}>>([])

// 创建者搜索过滤结果
const filteredCreators = ref<Array<{id: number, username: string, name: string}>>([])

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

// 搜索表单
const searchForm = reactive({
  search: '',
  template_id: undefined as number | undefined,
  favorites_only: false,
  my_plans_only: false,
  created_by: undefined as number | undefined
})

// 收藏相关方法
const isFavorite = (id: number) => favoritesStore.isFavorite('execution_plan', id)

const toggleFavorite = async (id: number) => {
  try {
    const isFavorited = await favoritesStore.toggleFavorite('execution_plan', id, 'personal')
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
    title: '方案名称',
    dataIndex: 'name',
    slotName: 'name',
    width: 250
  },
  {
    title: '所属模板',
    dataIndex: 'template_name',
    slotName: 'template',
    width: 200
  },

  {
    title: '统计信息',
    slotName: 'stats',
    width: 180
  },
  {
    title: '创建信息',
    slotName: 'created_info',
    width: 150
  },
  {
    title: '操作',
    slotName: 'actions',
    width: 150,
    fixed: 'right'
  }
]

// 模板选择表格列配置
const templateColumns = [
  {
    title: '模板名称',
    dataIndex: 'name',
    slotName: 'name',
    width: 250
  },
  {
    title: '分类',
    dataIndex: 'category',
    slotName: 'category',
    width: 100
  },
  {
    title: '统计',
    slotName: 'stats',
    width: 120
  },
  {
    title: '创建时间',
    dataIndex: 'created_at',
    width: 150,
    render: ({ record }) => formatDateTime(record.created_at)
  }
]

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
      search: searchForm.search || undefined,
      template: searchForm.template_id || undefined,
      // 如果启用“我的方案”，把创建者传给后端以便服务器端过滤
      created_by: searchForm.my_plans_only ? authStore.user?.id : undefined
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
    fetchAvailableUsers()
  } catch (error) {
    console.error('获取执行方案列表失败:', error)
    Message.error('获取执行方案列表失败')
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
      plans.value.forEach(plan => {
        if (plan.created_by && plan.created_by_name) {
          userMap.set(plan.created_by, {
            id: plan.created_by,
            username: plan.created_by_name,
            name: plan.created_by_name
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
  fetchPlans()
}

// 重置搜索
const handleReset = () => {
  searchForm.search = ''
  searchForm.template_id = undefined
  searchForm.favorites_only = false
  searchForm.my_plans_only = false
  searchForm.created_by = undefined
  // 重置创建者过滤
  filteredCreators.value = [...availableUsers.value]
  pagination.current = 1
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
  fetchPlans()
}

const handlePageSizeChange = (pageSize: number) => {
  pagination.pageSize = pageSize
  pagination.current = 1
  selectedRowKeys.value = [] // 清空选择
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

// 表格行选择（兼容 selection-change 事件）
const handleRowSelect = (selectedKeys: number[] | (string | number)[]) => {
  selectedRowKeys.value = selectedKeys as number[]
}
const handleSelectionChange = (rowKeys: (string | number)[]) => {
  selectedRowKeys.value = rowKeys as number[]
}
// 确认选择模板
const handleTemplateSelect = () => {
  if (selectedTemplateKeys.value.length === 0) {
    Message.warning('请选择一个模板')
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
    Message.warning('请先选择要同步的执行方案')
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

// 执行方案
const handleExecute = (plan: ExecutionPlan) => {
  router.push(`/execution-plans/detail/${plan.id}/execute`)
}

const handleSchedule = (plan: ExecutionPlan) => {
  router.push(`/scheduled-tasks/create?plan_id=${plan.id}`)
}

// 更多操作
const handleMoreAction = async (action: string, plan: ExecutionPlan) => {
  switch (action) {
    case 'delete':
      await handleDelete(plan)
      break
  }
}

const handleClickMoreAction = async (action: string, plan: ExecutionPlan) => {
  if (action === 'delete' && !canDeletePlan(plan.id)) {
    Message.warning('没有权限执行此操作，请联系管理员开放权限')
    return
  }
  await handleMoreAction(action, plan)
}

// 删除方案
const handleDelete = (plan: ExecutionPlan) => {
  Modal.confirm({
    title: '确认删除',
    content: `确定要删除执行方案「${plan.name}」吗？此操作不可恢复。`,
    okText: '确认删除',
    cancelText: '取消',
    okButtonProps: { status: 'danger' },
    onOk: async () => {
      try {
        await executionPlanApi.deletePlan(plan.id)
        Message.success('方案删除成功')
        fetchPlans()
      } catch (error) {
        console.error('删除方案失败:', error)
        Message.error('删除方案失败')
      }
    }
  })
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
  // 检查URL参数，如果有template_id则设置过滤条件
  const templateId = route.query.template_id
  if (templateId) {
    searchForm.template_id = Number(templateId)
  }

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
  color: var(--color-text-1);
}

.header-desc {
  margin: 0;
  color: var(--color-text-3);
  font-size: 14px;
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

/* 搜索按钮定位（与作业模板一致） */
.search-actions {
  margin-left: auto;
  display: flex;
  align-items: center;
  padding-top: 0;
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
  color: var(--color-text-3);
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
  color: var(--color-text-3);
  line-height: 1.4;
}

.template-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.template-name {
  font-weight: 500;
  color: var(--color-text-1);
}

.template-category {
  font-size: 12px;
  color: var(--color-text-3);
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
  color: var(--color-text-3);
  min-width: 32px;
}

.stat-value {
  color: var(--color-text-1);
  font-weight: 500;
}

.created-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.created-by {
  font-weight: 500;
  color: var(--color-text-1);
}

.created-time {
  font-size: 12px;
  color: var(--color-text-3);
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
    border-bottom: 1px solid var(--color-border-2);
  }

  .arco-table-tbody .arco-table-tr:hover .arco-table-td {
    background-color: var(--color-bg-1);
  }


}

/* 模板选择弹窗样式 */
.template-select-content {
  max-height: 500px;
}

.template-name .name {
  font-weight: 500;
  color: var(--color-text-1);
  margin-bottom: 4px;
}

.template-name .desc {
  font-size: 12px;
  color: var(--color-text-3);
}

.stats {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 12px;
  color: var(--color-text-3);
}

.template-select-content ::deep(.arco-table-selection) {
  width: 50px;
}

.text-gray {
  color: var(--color-text-3);
}
</style>
