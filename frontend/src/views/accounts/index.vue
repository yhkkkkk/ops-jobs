<template>
  <div 
    class="account-management"
    v-page-permissions="{ 
      resourceType: 'serveraccount', 
      permissions: ['view', 'add', 'change', 'delete'],
      resourceIds: accounts.map(a => a.id)
    }"
  >
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-content">
        <div class="header-left">
          <h2>服务器账号管理</h2>
          <p class="header-desc">管理服务器登录账号，用于执行命令和文件传输</p>
        </div>
        <div class="header-right">
          <a-space>
            <a-button @click="fetchAccounts">
              <template #icon>
                <icon-refresh />
              </template>
              刷新
            </a-button>
            <a-button 
              v-permission="{ resourceType: 'serveraccount', permission: 'add' }"
              v-if="!isReadOnly"
              type="primary" 
              @click="handleCreate"
            >
              <template #icon>
                <icon-plus />
              </template>
              新建账号
            </a-button>
          </a-space>
        </div>
      </div>
    </div>

    <!-- 搜索栏（与执行记录间距一致） -->
    <a-card class="mb-4">
      <a-row :gutter="16">
        <a-col :span="4">
          <a-input
            v-model="searchForm.search"
            placeholder="账号名称/用户名"
            allow-clear
            @press-enter="handleSearch"
            @clear="handleSearch"
            style="width: 100%"
          />
        </a-col>
        <a-col :span="3">
          <a-select
            v-model="searchForm.auth_type"
            placeholder="认证方式"
            allow-clear
            @change="handleSearch"
            @clear="handleSearch"
            style="width: 100%"
          >
            <a-option value="password">密码认证</a-option>
            <a-option value="key">密钥认证</a-option>
          </a-select>
        </a-col>
        <a-col :span="17">
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
      <ActiveFiltersBar
        :items="activeFilterItems"
        @clear="handleClearFilter"
        @clear-all="handleReset"
      />
    </a-card>

    <!-- 账号列表 -->
    <a-card>
      <a-table
        :columns="columns"
        :data="accounts"
        :loading="loading"
        :pagination="pagination"
        :scroll="{ x: 800 }"
        @page-change="handlePageChange"
        @page-size-change="handlePageSizeChange"
      >
        <template #name="{ record }">
          <div class="account-info">
            <div class="account-name">{{ record.name }}</div>
            <div class="account-username">{{ record.username }}</div>
          </div>
        </template>

        <template #auth_info="{ record }">
          <div class="auth-info">
            <a-tag v-if="record.auth_type === 'password'" color="blue" size="small">密码</a-tag>
            <a-tag v-else-if="record.auth_type === 'key'" color="green" size="small">密钥</a-tag>
            <a-tag v-else-if="record.auth_type === 'both'" color="purple" size="small">密码+密钥</a-tag>
            <a-tag v-else color="red" size="small">未配置</a-tag>
          </div>
        </template>

        <template #description="{ record }">
          <span class="description">{{ record.description || '-' }}</span>
        </template>

        <template #actions="{ record }">
          <a-space>
            <a-button
              v-permission="{ resourceType: 'serveraccount', permission: 'change', resourceId: record.id }"
              v-if="!isReadOnly"
              type="text"
              size="small"
              @click="handleEdit(record)"
            >
              <template #icon>
                <icon-edit />
              </template>
              编辑
            </a-button>
            <a-button
              v-permission="{ resourceType: 'serveraccount', permission: 'delete', resourceId: record.id }"
              v-if="!isReadOnly"
              type="text"
              size="small"
              class="text-red-500"
              @click="handleClickDelete(record)"
            >
              <template #icon>
                <icon-delete />
              </template>
              删除
            </a-button>
          </a-space>
        </template>
      </a-table>
    </a-card>

    <!-- 账号表单弹窗 -->
    <AccountForm
      v-model:visible="formVisible"
      :account="currentAccount"
      @success="handleFormSuccess"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { Message, Modal } from '@arco-design/web-vue'
import { accountApi, type ServerAccount } from '@/api/account'
import AccountForm from './components/AccountForm.vue'
import ActiveFiltersBar from '@/components/ActiveFiltersBar.vue'
import { useFilterQuerySync } from '@/composables/useFilterQuerySync'
import { usePermissionsStore } from '@/stores/permissions'

// 响应式数据
const loading = ref(false)
const accounts = ref<ServerAccount[]>([])
const formVisible = ref(false)
const currentAccount = ref<ServerAccount | null>(null)
const permissionsStore = usePermissionsStore()
const route = useRoute()
const isOpsPlatform = computed(() => {
  return route.matched.some((record) => record.meta?.platform === 'ops')
})
const isReadOnly = computed(() => !isOpsPlatform.value)

const defaultSearchForm = () => ({
  search: '',
  auth_type: ''
})

// 搜索表单
const searchForm = reactive(defaultSearchForm())

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
    { key: 'auth_type' }
  ]
})

const resolveAuthType = (value: string) => {
  if (!value) return ''
  const map: Record<string, string> = {
    password: '密码认证',
    key: '密钥认证'
  }
  return map[value] || value
}

const activeFilterItems = computed(() => [
  { key: 'search', label: '账号名称/用户名', display: searchForm.search },
  { key: 'auth_type', label: '认证方式', display: resolveAuthType(searchForm.auth_type) }
])

const handleClearFilter = (key: string) => {
  const defaults = defaultSearchForm()
  if (key in defaults) {
    ;(searchForm as any)[key] = (defaults as any)[key]
  }
  pagination.current = 1
  syncToQuery()
  fetchAccounts()
}

// 表格列配置
const columns = [
  {
    title: '账号信息',
    dataIndex: 'name',
    slotName: 'name',
    width: 220,
    ellipsis: true,
    tooltip: true
  },
  {
    title: '认证方式',
    dataIndex: 'auth_info',
    slotName: 'auth_info',
    width: 120
  },
  {
    title: '描述',
    dataIndex: 'description',
    slotName: 'description',
    ellipsis: true,
    tooltip: true,
    width: 240
  },
  {
    title: '操作',
    dataIndex: 'actions',
    slotName: 'actions',
    width: 150,
    align: 'center'
  }
]

// 获取账号列表
const fetchAccounts = async () => {
  try {
    loading.value = true
    const params = {
      page: pagination.current,
      page_size: pagination.pageSize,
      ordering: ordering.value || undefined,
      ...searchForm
    }

    // 过滤空值
    Object.keys(params).forEach(key => {
      if (params[key] === '' || params[key] === null || params[key] === undefined) {
        delete params[key]
      }
    })

    const response = await accountApi.getAccounts(params)
    accounts.value = response.results
    pagination.total = response.total
  } catch (error) {
    console.error('获取账号列表失败:', error)
  } finally {
    loading.value = false
  }
}

// 搜索
const handleSearch = () => {
  pagination.current = 1
  syncToQuery()
  fetchAccounts()
}

// 重置
const handleReset = () => {
  Object.assign(searchForm, defaultSearchForm())
  pagination.current = 1
  syncToQuery()
  fetchAccounts()
}

// 分页变化
const handlePageChange = (page: number) => {
  pagination.current = page
  syncToQuery()
  fetchAccounts()
}

const handlePageSizeChange = (pageSize: number) => {
  pagination.pageSize = pageSize
  pagination.current = 1
  syncToQuery()
  fetchAccounts()
}

// 新建账号
const handleCreate = () => {
  currentAccount.value = null
  formVisible.value = true
}

// 编辑账号
const handleEdit = (account: ServerAccount) => {
  currentAccount.value = { ...account }
  formVisible.value = true
}

// 删除账号
const handleDelete = (record: ServerAccount) => {
  Modal.confirm({
    title: '确认删除',
    content: `确定要删除账号"${record.name}"吗？此操作不可恢复。`,
    onOk: async () => {
      try {
        await accountApi.deleteAccount(record.id)
        Message.success('账号删除成功')
        fetchAccounts()
      } catch (error: any) {
        console.error('删除账号失败:', error)

        // 检查是否有具体的错误信息
        const errorMessage = error.message || error.response?.data?.message || error.response?.data?.detail
        if (errorMessage && errorMessage !== '请求失败') {
          Message.error(errorMessage)
        } else {
          Message.error('账号删除失败，请稍后重试')
        }
      }
    }
  })
}

const handleClickDelete = (record: ServerAccount) => {
  handleDelete(record)
}

// 表单提交成功
const handleFormSuccess = () => {
  fetchAccounts()
}

// 页面加载时获取数据
onMounted(() => {
  initFromQuery()
  fetchAccounts()
})
</script>

<style scoped>
.account-management {
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

.search-actions {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  width: 100%;
}


.account-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.account-name {
  font-weight: 500;
  color: var(--color-text-1);
}

.account-username {
  font-size: 12px;
  color: var(--color-text-3);
  font-family: 'Courier New', monospace;
}

.auth-info {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.description {
  color: var(--color-text-2);
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
    padding: 12px 16px;
  }

  /* 操作列按钮间距 */
  .arco-space-item {
    margin-right: 8px;
  }
}
</style>
