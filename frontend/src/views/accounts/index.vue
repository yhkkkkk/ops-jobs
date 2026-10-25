<template>
  <div
    class="app-page account-management"
    v-page-permissions="{ 
      resourceType: 'serveraccount', 
      permissions: ['view', 'add', 'change', 'delete'],
      resourceIds: accounts.map(a => a.id)
    }"
  >
    <PageHeader
      eyebrow="账号凭据"
      title="服务器账号管理"
      description="管理服务器登录账号，用于执行命令、文件传输和主机连通性验证。"
    >
      <template #actions>
        <n-space>
          <n-button @click="fetchAccounts">
            <template #icon><RefreshCw :size="16" /></template>
            刷新
          </n-button>
          <n-button
            v-permission="{ resourceType: 'serveraccount', permission: 'add' }"
            v-if="!isReadOnly"
            type="primary"
            @click="handleCreate"
          >
            <template #icon><Plus :size="16" /></template>
            新建账号
          </n-button>
        </n-space>
      </template>
    </PageHeader>

    <DataToolbar
      title="筛选服务器账号"
      description="按账号名称、用户名和认证方式快速定位执行凭据。"
      :active-count="accountActiveFilterCount"
    >
      <div class="app-filter-grid">
        <n-input
          v-model:value="searchForm.search"
          placeholder="账号名称/用户名"
          clearable
          @keyup.enter="handleSearch"
          @clear="handleSearch"
        />
        <n-select
          v-model:value="searchForm.auth_type"
          placeholder="认证方式"
          clearable
          @update:value="handleSearch"
          :options="authTypeOptions"
        />
        <div class="app-filter-grid__actions">
          <n-space>
            <n-button type="primary" @click="handleSearch">
              <template #icon><Search :size="16" /></template>
              搜索
            </n-button>
            <n-button @click="handleReset">
              <template #icon><RefreshCw :size="16" /></template>
              重置
            </n-button>
          </n-space>
        </div>
      </div>
      <ActiveFiltersBar
        :items="activeFilterItems"
        @clear="handleClearFilter"
        @clear-all="handleReset"
      />
    </DataToolbar>

    <DetailPanel
      title="账号列表"
      :description="`共 ${pagination.total} 个账号，当前页 ${accounts.length} 个`"
    >
      <n-data-table
        :columns="tableColumns"
        :data="accounts"
        :loading="loading"
        :pagination="tablePagination"
      />
    </DetailPanel>

    <!-- 账号表单弹窗 -->
    <AccountForm
      v-model:visible="formVisible"
      :account="currentAccount"
      @success="handleFormSuccess"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, h } from 'vue'
import { useRoute } from 'vue-router'
import { NButton, NDataTable, NInput, NSelect, NSpace, NTag, type DataTableColumns, useDialog, useMessage } from 'naive-ui'
import { RefreshCw, Plus, Search, Pencil, Trash2 } from 'lucide-vue-next'
import { accountApi, type ServerAccount } from '@/api/account'
import AccountForm from './components/AccountForm.vue'
import ActiveFiltersBar from '@/components/ActiveFiltersBar.vue'
import { useFilterQuerySync } from '@/composables/useFilterQuerySync'
import { usePermissionsStore } from '@/stores/permissions'
import { DataToolbar, DetailPanel, PageHeader, countActiveFilters } from '@/components/app'

// 响应式数据
const loading = ref(false)
const accounts = ref<ServerAccount[]>([])
const formVisible = ref(false)
const currentAccount = ref<ServerAccount | null>(null)
const permissionsStore = usePermissionsStore()
const message = useMessage()
const dialog = useDialog()
const route = useRoute()
const isOpsPlatform = computed(() => {
  return route.matched.some((record) => record.meta?.platform === 'ops')
})
const isReadOnly = computed(() => !isOpsPlatform.value)

const defaultSearchForm = () => ({
  search: '',
  auth_type: '',
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

const accountActiveFilterCount = computed(() => countActiveFilters(searchForm as unknown as Record<string, unknown>))

const handleClearFilter = (key: string) => {
  const defaults = defaultSearchForm()
  if (key in defaults) {
    ;(searchForm as any)[key] = (defaults as any)[key]
  }
  pagination.current = 1
  syncToQuery()
  fetchAccounts()
}

const canAccountPermission = (permission: 'change' | 'delete', accountId: number) => {
  if (permissionsStore.isSuperUser) return true
  const cacheKey = `serveraccount:${permission}:${accountId}`
  if (!permissionsStore.permissionCache.has(cacheKey)) return false
  return permissionsStore.hasPermission('serveraccount', permission, accountId)
}

const ensureAccountPermission = async (permission: 'change' | 'delete', accountId: number) => {
  if (permissionsStore.isSuperUser) return true
  return permissionsStore.checkPermission('serveraccount', permission, accountId)
}

// 表格列配置
const authTypeOptions = [
  { label: '密码认证', value: 'password' },
  { label: '密钥认证', value: 'key' }
]

const tableColumns = computed<DataTableColumns<ServerAccount>>(() => [
  {
    title: '账号信息',
    key: 'name',
    width: 220,
    ellipsis: { tooltip: true },
    render: (record: ServerAccount) => h('div', { class: 'account-info' }, [
      h('div', { class: 'account-name' }, record.name),
      h('div', { class: 'account-username' }, record.username)
    ])
  },
  {
    title: '认证方式',
    key: 'auth_info',
    width: 120,
    render: (record: ServerAccount) => h(NTag, {
      size: 'small',
      type: record.auth_type === 'password' ? 'info' : record.auth_type === 'key' ? 'success' : record.auth_type === 'both' ? 'warning' : 'error'
    }, { default: () => record.auth_type === 'password' ? '密码' : record.auth_type === 'key' ? '密钥' : record.auth_type === 'both' ? '密码+密钥' : '未配置' })
  },
  {
    title: '描述',
    key: 'description',
    width: 240,
    ellipsis: { tooltip: true },
    render: (record: ServerAccount) => h('span', { class: 'description' }, record.description || '-')
  },
  {
    title: '操作',
    key: 'actions',
    width: 150,
    align: 'center' as const,
    render: (record: ServerAccount) => h(NSpace, { size: 4 }, {
      default: () => [
        !isReadOnly.value && canAccountPermission('change', record.id)
          ? h(NButton, { text: true, size: 'small', onClick: () => handleEdit(record) }, { icon: () => h(Pencil, { size: 15 }), default: () => '编辑' })
          : null,
        !isReadOnly.value && canAccountPermission('delete', record.id)
          ? h(NButton, { text: true, size: 'small', type: 'error', onClick: () => handleClickDelete(record) }, { icon: () => h(Trash2, { size: 15 }), default: () => '删除' })
          : null
      ]
    })
  }
])

const tablePagination = computed(() => ({
  page: pagination.current,
  pageSize: pagination.pageSize,
  itemCount: pagination.total,
  showSizePicker: true,
  pageSizes: pagination.pageSizeOptions.map(Number),
  onUpdatePage: handlePageChange,
  onUpdatePageSize: handlePageSizeChange
}))

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
  void ensureAccountPermission('change', account.id).then((allowed) => {
    if (!allowed) {
      message.error('没有编辑该账号的权限')
      return
    }
    currentAccount.value = { ...account }
    formVisible.value = true
  })
}

// 删除账号
const handleDelete = (record: ServerAccount) => {
  void ensureAccountPermission('delete', record.id).then((allowed) => {
    if (!allowed) {
      message.error('没有删除该账号的权限')
      return
    }
    dialog.warning({
    title: '确认删除',
    content: `确定要删除账号"${record.name}"吗？此操作不可恢复。`,
    positiveText: '确认删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await accountApi.deleteAccount(record.id)
        message.success('账号删除成功')
        fetchAccounts()
      } catch (error: any) {
        console.error('删除账号失败:', error)

        // 检查是否有具体的错误信息
        const errorMessage = error.message || error.response?.data?.message || error.response?.data?.detail
        if (errorMessage && errorMessage !== '请求失败') {
          message.error(errorMessage)
        } else {
          message.error('账号删除失败，请稍后重试')
        }
      }
    }
    })
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


</style>
