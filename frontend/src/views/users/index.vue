<template>
  <div class="app-page user-management">
    <PageHeader
      eyebrow="平台管理"
      title="用户管理"
      description="查看平台用户并维护基本资料。账号权限和管理员状态由后端统一控制。"
    >
      <template #actions>
        <n-button :loading="loading" @click="fetchUsers">
          <template #icon><RefreshCw :size="16" /></template>
          刷新
        </n-button>
      </template>
    </PageHeader>

    <DataToolbar
      title="筛选用户"
      description="按用户名、姓名或邮箱搜索。"
      :active-count="search ? 1 : 0"
    >
      <n-input
        v-model:value="search"
        clearable
        placeholder="搜索用户名、姓名或邮箱"
        style="max-width: 360px"
        @keyup.enter="handleSearch"
        @clear="handleSearch"
      />
    </DataToolbar>

    <DetailPanel
      title="用户列表"
      :description="`共 ${pagination.total} 个用户，当前页 ${users.length} 个`"
    >
      <n-data-table
        :data="users"
        :columns="tableColumns"
        :loading="loading"
        :row-key="(row) => row.id"
        :scroll-x="900"
        :pagination="tablePagination"
      />
    </DetailPanel>

    <n-modal v-model:show="editVisible" preset="card" title="编辑用户资料" style="width: 560px; max-width: calc(100vw - 32px)" :mask-closable="false">
      <n-form :model="editForm" label-placement="top">
        <n-form-item label="用户名">
          <n-input :value="editForm.username" disabled />
        </n-form-item>
        <n-form-item label="邮箱">
          <n-input v-model:value="editForm.email" clearable />
        </n-form-item>
        <n-grid :cols="2" :x-gap="12">
          <n-form-item-gi label="名">
            <n-input v-model:value="editForm.first_name" clearable />
          </n-form-item-gi>
          <n-form-item-gi label="姓">
            <n-input v-model:value="editForm.last_name" clearable />
          </n-form-item-gi>
        </n-grid>
        <n-form-item label="手机号">
          <n-input v-model:value="editForm.phone" clearable />
        </n-form-item>
        <n-form-item label="部门">
          <n-input v-model:value="editForm.department" clearable />
        </n-form-item>
        <n-form-item label="职位">
          <n-input v-model:value="editForm.position" clearable />
        </n-form-item>
      </n-form>
      <n-alert type="info">此页面只维护基本资料，不修改密码、角色或管理员状态。</n-alert>
      <template #footer>
        <n-space justify="end">
          <n-button @click="editVisible = false">取消</n-button>
          <n-button type="primary" :loading="saving" @click="saveEdit">保存</n-button>
        </n-space>
      </template>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from 'vue'
import { NAlert, NAvatar, NButton, NDataTable, NForm, NFormItem, NFormItemGi, NGrid, NInput, NModal, NSpace, NTag, type DataTableColumns, useMessage } from 'naive-ui'
import { Edit3, RefreshCw } from 'lucide-vue-next'
import { authApi } from '@/api/auth'
import type { User } from '@/types'
import { DataToolbar, DetailPanel, PageHeader } from '@/components/app'

type UserRecord = User & { profile?: User['profile'] }

const users = ref<UserRecord[]>([])
const loading = ref(false)
const saving = ref(false)
const search = ref('')
const editVisible = ref(false)
const editForm = reactive({
  id: 0,
  username: '',
  email: '',
  first_name: '',
  last_name: '',
  phone: '',
  department: '',
  position: '',
})

const message = useMessage()
const pagination = reactive({ current: 1, pageSize: 20, total: 0, pageSizeOptions: [10, 20, 50, 100] })

const tableColumns: DataTableColumns<UserRecord> = [
  {
    title: '用户',
    key: 'user',
    width: 220,
    render: (record: UserRecord) => h('div', { class: 'user-cell' }, [
      h(NAvatar, { size: 32, round: true }, {
        default: () => (record.first_name || record.username).slice(0, 1).toUpperCase()
      }),
      h('div', {}, [
        h('div', { class: 'user-name' }, displayName(record)),
        h('div', { class: 'user-username' }, `@${record.username}`)
      ])
    ])
  },
  {
    title: '邮箱',
    key: 'email',
    ellipsis: { tooltip: true },
    render: (record: UserRecord) => record.email || '-'
  },
  {
    title: '部门 / 职位',
    key: 'profile',
    width: 180,
    render: (record: UserRecord) => h('span', {}, [
      record.profile?.department || '未填写部门',
      record.profile?.position ? ` · ${record.profile.position}` : ''
    ])
  },
  {
    title: '角色',
    key: 'roles',
    width: 130,
    render: (record: UserRecord) => h(NSpace, { size: 4 }, {
      default: () => [h(NTag, {
        size: 'small',
        type: record.is_superuser ? 'error' : record.is_staff ? 'warning' : 'default'
      }, {
        default: () => record.is_superuser ? '超级管理员' : record.is_staff ? '后台用户' : '普通用户'
      })]
    })
  },
  {
    title: '加入时间',
    key: 'date_joined',
    width: 180
  },
  {
    title: '操作',
    key: 'actions',
    width: 120,
    render: (record: UserRecord) => h(NButton, {
      text: true,
      size: 'small',
      onClick: () => openEdit(record)
    }, {
      icon: () => h(Edit3, { size: 15 }),
      default: () => '编辑资料'
    })
  }
]

const tablePagination = computed(() => ({
  page: pagination.current,
  pageSize: pagination.pageSize,
  itemCount: pagination.total,
  showSizePicker: true,
  pageSizes: pagination.pageSizeOptions,
  onUpdatePage: handlePageChange,
  onUpdatePageSize: handlePageSizeChange
}))

const normalizeUsers = (response: { results?: User[]; total?: number } | User[]) => {
  if (Array.isArray(response)) return { results: response, total: response.length }
  return { results: response.results || [], total: response.total || response.results?.length || 0 }
}

const fetchUsers = async () => {
  loading.value = true
  try {
    const response = await authApi.getUsers({
      page: pagination.current,
      page_size: pagination.pageSize,
      search: search.value || undefined,
    })
    const normalized = normalizeUsers(response)
    users.value = normalized.results as UserRecord[]
    pagination.total = normalized.total
  } catch (error: any) {
    message.error(error?.message || '获取用户列表失败')
    users.value = []
    pagination.total = 0
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  pagination.current = 1
  fetchUsers()
}

const handlePageChange = (page: number) => {
  pagination.current = page
  fetchUsers()
}

const handlePageSizeChange = (pageSize: number) => {
  pagination.pageSize = pageSize
  pagination.current = 1
  fetchUsers()
}

const displayName = (user: UserRecord) => {
  const name = `${user.last_name || ''}${user.first_name || ''}`.trim()
  return name || user.username
}

const openEdit = (user: UserRecord) => {
  Object.assign(editForm, {
    id: user.id,
    username: user.username,
    email: user.email || '',
    first_name: user.first_name || '',
    last_name: user.last_name || '',
    phone: user.profile?.phone || '',
    department: user.profile?.department || '',
    position: user.profile?.position || '',
  })
  editVisible.value = true
}

const saveEdit = async () => {
  saving.value = true
  try {
    await authApi.updateUser(editForm.id, {
      email: editForm.email,
      first_name: editForm.first_name,
      last_name: editForm.last_name,
      phone: editForm.phone,
      department: editForm.department,
      position: editForm.position,
    })
    message.success('用户资料已更新')
    editVisible.value = false
    await fetchUsers()
  } catch (error: any) {
    message.error(error?.message || '更新用户资料失败')
  } finally {
    saving.value = false
  }
}

onMounted(fetchUsers)
</script>

<style scoped>
.user-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}

.user-name {
  font-weight: 600;
  color: var(--color-text-1);
}

.user-username,
.profile-position {
  color: var(--color-text-3);
  font-size: 12px;
}
</style>
