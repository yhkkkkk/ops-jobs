<template>
  <div class="permissions-page">
    <a-card title="权限管理" class="permissions-card">
      <!-- 用户权限摘要 -->
      <a-row :gutter="16" class="permissions-summary">
        <a-col :span="8">
          <a-statistic
            title="权限总数"
            :value="userPermissions?.permission_count || 0"
            :value-style="{ color: '#3f8600' }"
          >
            <template #suffix>
              <icon-check-circle />
            </template>
          </a-statistic>
        </a-col>
        <a-col :span="8">
          <a-statistic
            title="用户组"
            :value="userPermissions?.groups?.length || 0"
            :value-style="{ color: '#1890ff' }"
          >
            <template #suffix>
              <icon-team />
            </template>
          </a-statistic>
        </a-col>
        <a-col :span="8">
          <a-statistic
            title="用户状态"
            :value="(userPermissions?.is_superuser ? '超级用户' : '普通用户') as any"
            :value-style="{ color: userPermissions?.is_superuser ? '#cf1322' : '#722ed1' }"
          >
            <template #suffix>
              <icon-user />
            </template>
          </a-statistic>
        </a-col>
      </a-row>

      <!-- 权限检查工具 -->
      <a-divider>权限检查工具</a-divider>
      
      <a-form :model="permissionForm" layout="vertical">
        <a-row :gutter="16">
          <a-col :span="8">
            <a-form-item label="资源类型">
              <a-select
                v-model="permissionForm.resourceType"
                placeholder="选择资源类型"
                allow-clear
              >
                <a-option value="host">主机</a-option>
                <a-option value="job">作业</a-option>
                <a-option value="script">脚本</a-option>
                <a-option value="executionplan">执行计划</a-option>
                <a-option value="jobtemplate">作业模板</a-option>
                <a-option value="scripttemplate">脚本模板</a-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="资源ID（可选）">
              <a-input-number
                v-model="permissionForm.resourceId"
                placeholder="输入资源ID"
                :min="1"
                style="width: 100%"
              />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="权限类型">
              <a-select
                v-model="permissionForm.permissions"
                placeholder="选择权限类型"
                mode="multiple"
                allow-clear
              >
                <a-option value="view">查看</a-option>
                <a-option value="add">创建</a-option>
                <a-option value="change">编辑</a-option>
                <a-option value="delete">删除</a-option>
                <a-option value="execute">执行</a-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>
        
        <a-form-item>
          <a-button type="primary" @click="checkPermissions" :loading="checking">
            检查权限
          </a-button>
          <a-button style="margin-left: 8px" @click="clearResults">
            清除结果
          </a-button>
        </a-form-item>
      </a-form>

      <!-- 权限检查结果 -->
      <div v-if="permissionResults" class="permission-results">
        <a-result
          :status="permissionResults.success ? 'success' : 'error'"
          :title="permissionResults.success ? '权限检查完成' : '权限检查失败'"
          :sub-title="permissionResults.message"
        >
          <template #extra>
            <div v-if="permissionResults.content" class="results-content">
              <a-descriptions title="权限详情" bordered>
                <a-descriptions-item label="用户ID">
                  {{ permissionResults.content.user_id }}
                </a-descriptions-item>
                <a-descriptions-item label="用户名">
                  {{ permissionResults.content.username }}
                </a-descriptions-item>
                <a-descriptions-item label="资源类型">
                  {{ permissionResults.content.resource_type }}
                </a-descriptions-item>
                <a-descriptions-item label="资源ID" v-if="permissionResults.content.resource_id">
                  {{ permissionResults.content.resource_id }}
                </a-descriptions-item>
              </a-descriptions>
              
              <a-divider>权限状态</a-divider>
              
              <a-row :gutter="16">
                <a-col 
                  v-for="(hasPermission, permission) in permissionResults.content.permissions" 
                  :key="permission"
                  :span="6"
                >
                  <a-card 
                    :class="['permission-card', hasPermission ? 'has-permission' : 'no-permission']"
                    size="small"
                  >
                    <template #title>
                      <icon-check-circle v-if="hasPermission" style="color: #52c41a" />
                      <icon-close-circle v-else style="color: #ff4d4f" />
                      {{ getPermissionDisplayName(String(permission)) }}
                    </template>
                    <div class="permission-status">
                      {{ hasPermission ? '有权限' : '无权限' }}
                    </div>
                  </a-card>
                </a-col>
              </a-row>
            </div>
          </template>
        </a-result>
      </div>

      <!-- 模型权限列表 -->
      <a-divider>模型权限列表</a-divider>
      
      <a-table
        :data="modelPermissionsData"
        :columns="modelPermissionsColumns"
        :pagination="false"
        size="small"
      >
        <template #permissions="{ record }">
          <a-tag
            v-for="perm in record.permissions"
            :key="perm"
            :color="getPermissionColor(perm)"
            size="small"
          >
            {{ getPermissionDisplayName(perm) }}
          </a-tag>
        </template>
      </a-table>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Message } from '@arco-design/web-vue'
import { usePermissionsStore } from '@/stores/permissions'
import { permissionsApi } from '@/api/permissions'
import type { PermissionLevel, ResourceType } from '@/types'

// 权限表单
const permissionForm = ref({
  resourceType: '' as ResourceType,
  resourceId: undefined as number | undefined,
  permissions: ['view', 'change', 'delete'] as PermissionLevel[]
})

// 权限检查结果
const permissionResults = ref<any>(null)
const checking = ref(false)

// 权限store
const permissionsStore = usePermissionsStore()

// 用户权限信息
const userPermissions = computed(() => permissionsStore.userPermissions)

// 模型权限数据
const modelPermissionsData = computed(() => {
  if (!userPermissions.value?.model_permissions) return []
  
  return Object.entries(userPermissions.value.model_permissions).map(([key, permissions]) => ({
    model: key,
    permissions: permissions as string[]
  }))
})

// 模型权限表格列
const modelPermissionsColumns = [
  {
    title: '模型',
    dataIndex: 'model',
    key: 'model'
  },
  {
    title: '权限',
    dataIndex: 'permissions',
    key: 'permissions',
    slotName: 'permissions'
  }
]

// 组件挂载时获取用户权限
onMounted(async () => {
  await permissionsStore.fetchUserPermissions()
})

/**
 * 检查权限
 */
const checkPermissions = async () => {
  if (!permissionForm.value.resourceType) {
    Message.warning('请选择资源类型')
    return
  }
  
  if (!permissionForm.value.permissions.length) {
    Message.warning('请选择要检查的权限')
    return
  }

  checking.value = true
  
  try {
    const result = await permissionsApi.checkPermission({
      resource_type: permissionForm.value.resourceType as string,
      resource_id: permissionForm.value.resourceId,
      permissions: permissionForm.value.permissions as string[]
    })
    
    // 构建结果对象
    permissionResults.value = {
      success: true,
      message: '权限检查完成',
      content: result
    }
    
    Message.success('权限检查完成')
  } catch (error: any) {
    permissionResults.value = {
      success: false,
      message: error.message || '权限检查失败',
      content: null
    }
    
    Message.error('权限检查失败')
  } finally {
    checking.value = false
  }
}

/**
 * 清除结果
 */
const clearResults = () => {
  permissionResults.value = null
}

/**
 * 获取权限显示名称
 */
const getPermissionDisplayName = (permission: string): string => {
  const permissionMap: Record<string, string> = {
    'view': '查看',
    'add': '创建',
    'change': '编辑',
    'delete': '删除',
    'execute': '执行'
  }
  
  return permissionMap[permission] || permission
}

/**
 * 获取权限标签颜色
 */
const getPermissionColor = (permission: string): string => {
  const colorMap: Record<string, string> = {
    'view': 'blue',
    'add': 'green',
    'change': 'orange',
    'delete': 'red',
    'execute': 'purple'
  }
  
  return colorMap[permission] || 'default'
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
  margin-bottom: 24px;
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

.permission-card {
  text-align: center;
  margin-bottom: 16px;
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

:deep(.arco-descriptions-item-label) {
  font-weight: 600;
}
</style>
