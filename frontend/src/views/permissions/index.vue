<template>
  <div class="permissions-page">
    <n-card title="权限管理" class="permissions-card">
      <div class="permissions-summary">
        <n-statistic
          label="权限总数"
          :value="userPermissions?.permission_count || 0"
          :value-style="{ color: '#3f8600' }"
        >
          <template #suffix>
            <CheckCircle2 :size="18" />
          </template>
        </n-statistic>
        <n-statistic
          label="用户组"
          :value="userPermissions?.groups?.length || 0"
          :value-style="{ color: '#1890ff' }"
        >
          <template #suffix>
            <Users :size="18" />
          </template>
        </n-statistic>
        <n-statistic
          label="用户状态"
          :value="userPermissions?.is_superuser ? '超级用户' : '普通用户'"
          :value-style="{ color: userPermissions?.is_superuser ? '#cf1322' : '#722ed1' }"
        >
          <template #suffix>
            <User :size="18" />
          </template>
        </n-statistic>
      </div>

      <n-divider>权限检查工具</n-divider>

      <n-form :model="permissionForm" label-placement="top">
        <div class="permission-form-grid">
          <n-form-item label="资源类型">
            <n-select
              v-model:value="permissionForm.resourceType"
              placeholder="选择资源类型"
              clearable
              :options="resourceTypeOptions"
            />
          </n-form-item>
          <n-form-item label="资源ID（可选）">
            <n-input-number
              v-model:value="permissionForm.resourceId"
              placeholder="输入资源ID"
              :min="1"
              style="width: 100%"
            />
          </n-form-item>
          <n-form-item label="权限类型">
            <n-select
              v-model:value="permissionForm.permissions"
              placeholder="选择权限类型"
              multiple
              clearable
              :options="permissionOptions"
            />
          </n-form-item>
        </div>

        <n-form-item>
          <n-space>
            <n-button type="primary" :loading="checking" @click="checkPermissions">
              检查权限
            </n-button>
            <n-button @click="clearResults">
              清除结果
            </n-button>
          </n-space>
        </n-form-item>
      </n-form>

      <div v-if="permissionResults" class="permission-results">
        <n-result
          :status="permissionResults.success ? 'success' : 'error'"
          :title="permissionResults.success ? '权限检查完成' : '权限检查失败'"
          :description="permissionResults.message"
        >
          <template #footer>
            <div v-if="permissionResults.content" class="results-content">
              <n-descriptions title="权限详情" bordered :column="2">
                <n-descriptions-item label="用户ID">
                  {{ permissionResults.content.user_id }}
                </n-descriptions-item>
                <n-descriptions-item label="用户名">
                  {{ permissionResults.content.username }}
                </n-descriptions-item>
                <n-descriptions-item label="资源类型">
                  {{ permissionResults.content.resource_type }}
                </n-descriptions-item>
                <n-descriptions-item v-if="permissionResults.content.resource_id" label="资源ID">
                  {{ permissionResults.content.resource_id }}
                </n-descriptions-item>
              </n-descriptions>

              <n-divider>权限状态</n-divider>

              <div class="permission-status-grid">
                <n-card
                  v-for="(hasPermission, permission) in permissionResults.content.permissions"
                  :key="permission"
                  size="small"
                  :class="['permission-card', hasPermission ? 'has-permission' : 'no-permission']"
                >
                  <template #header>
                    <n-space align="center" :size="6">
                      <CheckCircle2 v-if="hasPermission" :size="16" color="#52c41a" />
                      <XCircle v-else :size="16" color="#ff4d4f" />
                      {{ getPermissionDisplayName(String(permission)) }}
                    </n-space>
                  </template>
                  <div class="permission-status">
                    {{ hasPermission ? '有权限' : '无权限' }}
                  </div>
                </n-card>
              </div>
            </div>
          </template>
        </n-result>
      </div>

      <n-divider>模型权限列表</n-divider>

      <n-data-table
        :data="modelPermissionsData"
        :columns="modelPermissionsColumns"
        :pagination="false"
        size="small"
      />
    </n-card>
  </div>
</template>

<script setup lang="ts">
import { computed, h, onMounted, ref } from 'vue'
import { NButton, NCard, NDataTable, NDescriptions, NDescriptionsItem, NDivider, NForm, NFormItem, NInputNumber, NResult, NSelect, NSpace, NStatistic, NTag, useMessage } from 'naive-ui'
import { CheckCircle2, User, Users, XCircle } from 'lucide-vue-next'
import { usePermissionsStore } from '@/stores/permissions'
import { permissionsApi } from '@/api/permissions'
import type { PermissionLevel, ResourceType } from '@/types'

const message = useMessage()

const permissionForm = ref({
  resourceType: '' as ResourceType,
  resourceId: undefined as number | undefined,
  permissions: ['view', 'change', 'delete'] as PermissionLevel[]
})

const permissionResults = ref<any>(null)
const checking = ref(false)
const permissionsStore = usePermissionsStore()
const userPermissions = computed(() => permissionsStore.userPermissions)

const resourceTypeOptions = [
  { label: '主机', value: 'host' },
  { label: '作业', value: 'job' },
  { label: '脚本', value: 'script' },
  { label: '执行计划', value: 'executionplan' },
  { label: '作业模板', value: 'jobtemplate' },
  { label: '脚本模板', value: 'scripttemplate' }
]

const permissionOptions = [
  { label: '查看', value: 'view' },
  { label: '创建', value: 'add' },
  { label: '编辑', value: 'change' },
  { label: '删除', value: 'delete' },
  { label: '执行', value: 'execute' }
]

const modelPermissionsData = computed(() => {
  if (!userPermissions.value?.model_permissions) return []

  return Object.entries(userPermissions.value.model_permissions).map(([model, permissions]) => ({
    model,
    permissions: permissions as string[]
  }))
})

const modelPermissionsColumns = [
  {
    title: '模型',
    key: 'model'
  },
  {
    title: '权限',
    key: 'permissions',
    render: (record: { permissions: string[] }) => h(
      'div',
      { class: 'permission-tags' },
      record.permissions.map((permission) => h(
        NTag,
        { key: permission, size: 'small', type: getPermissionTagType(permission) },
        { default: () => getPermissionDisplayName(permission) }
      ))
    )
  }
]

const getPermissionTagType = (permission: string): 'default' | 'info' | 'success' | 'warning' | 'error' => {
  const typeMap: Record<string, 'default' | 'info' | 'success' | 'warning' | 'error'> = {
    view: 'info',
    add: 'success',
    change: 'warning',
    delete: 'error',
    execute: 'default'
  }

  return typeMap[permission] || 'default'
}

onMounted(async () => {
  await permissionsStore.fetchUserPermissions()
})

const checkPermissions = async () => {
  if (!permissionForm.value.resourceType) {
    message.warning('请选择资源类型')
    return
  }

  if (!permissionForm.value.permissions.length) {
    message.warning('请选择要检查的权限')
    return
  }

  checking.value = true

  try {
    const result = await permissionsApi.checkPermission({
      resource_type: permissionForm.value.resourceType as string,
      resource_id: permissionForm.value.resourceId,
      permissions: permissionForm.value.permissions as string[]
    })

    permissionResults.value = {
      success: true,
      message: '权限检查完成',
      content: result
    }

    message.success('权限检查完成')
  } catch (error: any) {
    permissionResults.value = {
      success: false,
      message: error.message || '权限检查失败',
      content: null
    }

    message.error('权限检查失败')
  } finally {
    checking.value = false
  }
}

const clearResults = () => {
  permissionResults.value = null
}

const getPermissionDisplayName = (permission: string): string => {
  const permissionMap: Record<string, string> = {
    view: '查看',
    add: '创建',
    change: '编辑',
    delete: '删除',
    execute: '执行'
  }

  return permissionMap[permission] || permission
}
</script>

<style scoped>
.permissions-page {
  padding: 20px;
}

.permissions-card {
  margin-bottom: 20px;
}

.permissions-summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}

.permission-form-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.permission-results {
  margin-top: 24px;
  padding: 20px;
  background-color: #fafafa;
  border-radius: 6px;
}

.results-content {
  text-align: left;
}

.permission-status-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.permission-card {
  text-align: center;
}

.permission-card.has-permission {
  border-color: #52c41a;
}

.permission-card.no-permission {
  border-color: #ff4d4f;
}

.permission-status {
  font-size: 12px;
  color: #666;
}

.permission-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

@media (max-width: 768px) {
  .permissions-summary,
  .permission-form-grid,
  .permission-status-grid {
    grid-template-columns: 1fr;
  }
}
</style>
