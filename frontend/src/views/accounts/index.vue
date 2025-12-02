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

    <!-- 搜索栏 -->
    <a-card class="mb-4">
      <a-form :model="searchForm" layout="inline">
        <a-form-item label="账号名称">
          <a-input
            v-model="searchForm.search"
            placeholder="请输入账号名称或用户名"
            allow-clear
            @press-enter="handleSearch"
            style="width: 200px"
          />
        </a-form-item>
        <a-form-item label="认证方式">
          <a-select
            v-model="searchForm.auth_type"
            placeholder="请选择认证方式"
            allow-clear
            style="width: 150px"
          >
            <a-option value="password">密码认证</a-option>
            <a-option value="key">密钥认证</a-option>
            <a-option value="both">密码+密钥</a-option>
            <a-option value="none">未配置</a-option>
          </a-select>
        </a-form-item>
        <a-form-item>
          <a-button type="primary" @click="handleSearch">
            <template #icon>
              <icon-search />
            </template>
            搜索
          </a-button>
          <a-button @click="handleReset" style="margin-left: 8px">
            <template #icon>
              <icon-refresh />
            </template>
            重置
          </a-button>
        </a-form-item>
      </a-form>
    </a-card>

    <!-- 账号列表 -->
    <div class="table-container">
      <a-table
        :columns="columns"
        :data="accounts"
        :loading="loading"
        :pagination="pagination"
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
          <a-button 
            v-permission="{ resourceType: 'serveraccount', permission: 'change', resourceId: record.id }"
            type="text" 
            size="small" 
            @click="handleEdit(record)"
          >
            <template #icon>
              <icon-edit />
            </template>
            编辑
          </a-button>
          <a-popconfirm
            content="确定要删除这个账号吗？"
            @ok="handleDelete(record.id)"
          >
            <a-button 
              v-permission="{ resourceType: 'serveraccount', permission: 'delete', resourceId: record.id }"
              type="text" 
              status="danger" 
              size="small"
            >
              <template #icon>
                <icon-delete />
              </template>
              删除
            </a-button>
          </a-popconfirm>
        </template>
      </a-table>
    </div>

    <!-- 账号表单弹窗 -->
    <AccountForm
      v-model:visible="formVisible"
      :account="currentAccount"
      @success="handleFormSuccess"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { Message } from '@arco-design/web-vue'
import { accountApi, type ServerAccount } from '@/api/account'
import AccountForm from './components/AccountForm.vue'

// 响应式数据
const loading = ref(false)
const accounts = ref<ServerAccount[]>([])
const formVisible = ref(false)
const currentAccount = ref<ServerAccount | null>(null)

// 搜索表单
const searchForm = reactive({
  search: '',
  auth_type: ''
})

// 分页配置
const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  showTotal: true,
  showPageSize: true
})

// 表格列配置
const columns = [
  {
    title: '账号信息',
    dataIndex: 'name',
    slotName: 'name',
    width: 200
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
    slotName: 'description'
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
  fetchAccounts()
}

// 重置
const handleReset = () => {
  searchForm.search = ''
  searchForm.auth_type = ''
  pagination.current = 1
  fetchAccounts()
}

// 分页变化
const handlePageChange = (page: number) => {
  pagination.current = page
  fetchAccounts()
}

const handlePageSizeChange = (pageSize: number) => {
  pagination.pageSize = pageSize
  pagination.current = 1
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
const handleDelete = async (id: number) => {
  try {
    await accountApi.deleteAccount(id)
    Message.success('账号删除成功')
    fetchAccounts()
  } catch (error) {
    console.error('删除账号失败:', error)
  }
}

// 表单提交成功
const handleFormSuccess = () => {
  fetchAccounts()
}

// 页面加载时获取数据
onMounted(() => {
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

.search-bar {
  background: var(--color-bg-2);
  padding: 16px;
  border-radius: 6px;
  margin-bottom: 16px;
}

.table-container {
  background: white;
  border-radius: 6px;
  overflow: hidden;
}

.account-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
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

/* 表格样式优化 */
:deep(.arco-table) {
  .arco-table-th {
    background-color: #fff !important;
    font-weight: 600;
  }

  /* 固定列样式 */
  .arco-table-col-fixed-right {
    background-color: transparent !important;
  }

  .arco-table-col-fixed-right .arco-table-td {
    background-color: inherit !important;
  }

  .arco-table-col-fixed-right .arco-table-cell {
    background-color: inherit !important;
  }

  .arco-table-col-fixed-right::before {
    background-color: transparent !important;
    box-shadow: none !important;
  }
}
</style>
