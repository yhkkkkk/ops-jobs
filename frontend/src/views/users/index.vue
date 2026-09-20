<template>
  <div class="app-page user-management">
    <PageHeader
      eyebrow="平台管理"
      title="用户管理"
      description="查看平台用户并维护基本资料。账号权限和管理员状态由后端统一控制。"
    >
      <template #actions>
        <a-button :loading="loading" @click="fetchUsers">
          <template #icon><icon-refresh /></template>
          刷新
        </a-button>
      </template>
    </PageHeader>

    <DataToolbar
      title="筛选用户"
      description="按用户名、姓名或邮箱搜索。"
      :active-count="search ? 1 : 0"
    >
      <a-input-search
        v-model="search"
        allow-clear
        placeholder="搜索用户名、姓名或邮箱"
        style="max-width: 360px"
        @search="handleSearch"
        @clear="handleSearch"
      />
    </DataToolbar>

    <DetailPanel
      title="用户列表"
      :description="`共 ${pagination.total} 个用户，当前页 ${users.length} 个`"
    >
      <a-table
        :data="users"
        :columns="columns"
        :loading="loading"
        :pagination="pagination"
        row-key="id"
        @page-change="handlePageChange"
        @page-size-change="handlePageSizeChange"
      >
        <template #user="{ record }">
          <div class="user-cell">
            <a-avatar :size="32">{{ (record.first_name || record.username).slice(0, 1).toUpperCase() }}</a-avatar>
            <div>
              <div class="user-name">{{ displayName(record) }}</div>
              <div class="user-username">@{{ record.username }}</div>
            </div>
          </div>
        </template>
        <template #roles="{ record }">
          <a-space>
            <a-tag v-if="record.is_superuser" color="red">超级管理员</a-tag>
            <a-tag v-else-if="record.is_staff" color="orange">后台用户</a-tag>
            <a-tag v-else color="gray">普通用户</a-tag>
          </a-space>
        </template>
        <template #profile="{ record }">
          <span>{{ record.profile?.department || '未填写部门' }}</span>
          <span v-if="record.profile?.position" class="profile-position"> · {{ record.profile.position }}</span>
        </template>
        <template #actions="{ record }">
          <a-button type="text" size="small" @click="openEdit(record)">
            <template #icon><icon-edit /></template>
            编辑资料
          </a-button>
        </template>
      </a-table>
    </DetailPanel>

    <a-modal v-model:visible="editVisible" title="编辑用户资料" :ok-loading="saving" @ok="saveEdit">
      <a-form ref="formRef" :model="editForm" layout="vertical">
        <a-form-item label="用户名">
          <a-input :model-value="editForm.username" disabled />
        </a-form-item>
        <a-form-item label="邮箱" field="email">
          <a-input v-model="editForm.email" type="email" allow-clear />
        </a-form-item>
        <a-row :gutter="12">
          <a-col :span="12">
            <a-form-item label="名" field="first_name">
              <a-input v-model="editForm.first_name" allow-clear />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="姓" field="last_name">
              <a-input v-model="editForm.last_name" allow-clear />
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item label="手机号" field="phone">
          <a-input v-model="editForm.phone" allow-clear />
        </a-form-item>
        <a-form-item label="部门" field="department">
          <a-input v-model="editForm.department" allow-clear />
        </a-form-item>
        <a-form-item label="职位" field="position">
          <a-input v-model="editForm.position" allow-clear />
        </a-form-item>
      </a-form>
      <a-alert type="info">此页面只维护基本资料，不修改密码、角色或管理员状态。</a-alert>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { Message } from '@arco-design/web-vue'
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

const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  showTotal: true,
  showPageSize: true,
})

const columns = [
  { title: '用户', slotName: 'user', width: 220 },
  { title: '邮箱', dataIndex: 'email', ellipsis: true, tooltip: true },
  { title: '部门 / 职位', slotName: 'profile', width: 180 },
  { title: '角色', slotName: 'roles', width: 130 },
  { title: '加入时间', dataIndex: 'date_joined', width: 180 },
  { title: '操作', slotName: 'actions', width: 120 },
]

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
    Message.error(error?.message || '获取用户列表失败')
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
    Message.success('用户资料已更新')
    editVisible.value = false
    await fetchUsers()
  } catch (error: any) {
    Message.error(error?.message || '更新用户资料失败')
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
