import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { 
  PermissionCheckResponse, 
  UserPermissionsResponse,
  ResourcePermissionsResponse,
  PermissionLevel,
  ResourceType
} from '@/types'
import { permissionsApi } from '@/api/permissions'

export const usePermissionsStore = defineStore('permissions', () => {
  // 状态
  const userPermissions = ref<UserPermissionsResponse | null>(null)
  const permissionCache = ref<Map<string, PermissionCheckResponse>>(new Map())
  const resourcePermissionsCache = ref<Map<string, ResourcePermissionsResponse>>(new Map())
  const loading = ref(false)
  const error = ref<string | null>(null)

  // 计算属性 - 从认证存储获取超级用户状态
  const isSuperUser = computed(() => {
    try {
      // 延迟导入避免循环依赖
      const { useAuthStore } = require('@/stores/auth')
      const authStore = useAuthStore()
      return authStore.isAdmin
    } catch (error) {
      // 如果无法获取认证存储，回退到权限存储
      return userPermissions.value?.is_superuser || false
    }
  })
  
  const isStaff = computed(() => userPermissions.value?.is_staff || false)
  const hasAnyPermissions = computed(() => (userPermissions.value?.permission_count || 0) > 0)

  /**
   * 获取用户权限摘要
   */
  const fetchUserPermissions = async (): Promise<void> => {
    if (userPermissions.value) return // 已缓存

    loading.value = true
    error.value = null
    
    try {
      const result = await permissionsApi.getUserPermissions()
      userPermissions.value = result
    } catch (err: any) {
      error.value = err.message || '获取用户权限失败'
      console.error('获取用户权限失败:', err)
    } finally {
      loading.value = false
    }
  }

  /**
   * 检查单个权限
   */
  const checkPermission = async (
    resourceType: ResourceType,
    permission: PermissionLevel,
    resourceId?: number
  ): Promise<boolean> => {
    // 超级用户拥有所有权限
    if (isSuperUser.value) return true

    const cacheKey = `${resourceType}:${permission}:${resourceId || 'model'}`
    
    // 检查缓存
    if (permissionCache.value.has(cacheKey)) {
      const cached = permissionCache.value.get(cacheKey)!
      return cached.permissions[permission] || false
    }

    try {
      const result = await permissionsApi.checkPermission({
        resource_type: resourceType,
        resource_id: resourceId,
        permissions: [permission]
      })

      // 缓存结果
      permissionCache.value.set(cacheKey, result)
      
      return result.permissions[permission] || false
    } catch (err: any) {
      console.error('权限检查失败:', err)
      return false
    }
  }

  /**
   * 批量检查权限
   */
  const checkPermissions = async (
    resourceType: ResourceType,
    permissions: PermissionLevel[],
    resourceId?: number
  ): Promise<Record<string, boolean>> => {
    // 超级用户拥有所有权限
    if (isSuperUser.value) {
      const result: Record<string, boolean> = {}
      permissions.forEach(perm => result[perm] = true)
      return result
    }

    const cacheKey = `${resourceType}:${permissions.join(',')}:${resourceId || 'model'}`
    
    // 检查缓存
    if (permissionCache.value.has(cacheKey)) {
      const cached = permissionCache.value.get(cacheKey)!
      return cached.permissions
    }

    try {
      const result = await permissionsApi.checkPermission({
        resource_type: resourceType,
        resource_id: resourceId,
        permissions
      })

      // 缓存结果
      permissionCache.value.set(cacheKey, result)
      
      return result.permissions
    } catch (err: any) {
      console.error('批量权限检查失败:', err)
      const result: Record<string, boolean> = {}
      permissions.forEach(perm => result[perm] = false)
      return result
    }
  }

  /**
   * 检查资源权限
   */
  const checkResourcePermissions = async (
    resourceType: ResourceType,
    resourceIds: number[],
    permissions: PermissionLevel[] = ['view', 'change', 'delete']
  ): Promise<ResourcePermissionsResponse | null> => {
    // 超级用户拥有所有权限
    if (isSuperUser.value) {
      const result: ResourcePermissionsResponse = {
        user_id: 0,
        username: 'superuser',
        resource_type: resourceType,
        permissions: {},
        level: 'object'
      }

      // 为每个资源ID创建权限结果
      resourceIds.forEach(id => {
        result.permissions[id.toString()] = {}
        permissions.forEach(perm => {
          result.permissions[id.toString()][perm] = true
        })
      })

      return result
    }

    const cacheKey = `${resourceType}:${resourceIds.join(',')}:${permissions.join(',')}`
    
    // 检查缓存
    if (resourcePermissionsCache.value.has(cacheKey)) {
      return resourcePermissionsCache.value.get(cacheKey)!
    }

    try {
      const result = await permissionsApi.batchCheckPermissions(
        resourceType,
        resourceIds,
        permissions
      )

      // 缓存结果
      resourcePermissionsCache.value.set(cacheKey, result)
      
      return result
    } catch (err: any) {
      console.error('资源权限检查失败:', err)
      return null
    }
  }

  /**
   * 清除权限缓存
   */
  const clearCache = (): void => {
    permissionCache.value.clear()
    resourcePermissionsCache.value.clear()
  }

  /**
   * 清除特定资源的权限缓存
   */
  const clearResourceCache = (resourceType: ResourceType): void => {
    // 清除相关缓存
    for (const key of permissionCache.value.keys()) {
      if (key.startsWith(`${resourceType}:`)) {
        permissionCache.value.delete(key)
      }
    }
    
    for (const key of resourcePermissionsCache.value.keys()) {
      if (key.startsWith(`${resourceType}:`)) {
        resourcePermissionsCache.value.delete(key)
      }
    }
  }

  /**
   * 检查用户是否有特定权限（同步方法，基于缓存）
   */
  const hasPermission = (
    resourceType: ResourceType,
    permission: PermissionLevel,
    resourceId?: number
  ): boolean => {
    // 超级用户拥有所有权限
    if (isSuperUser.value) return true

    const cacheKey = `${resourceType}:${permission}:${resourceId || 'model'}`
    const cached = permissionCache.value.get(cacheKey)
    
    if (cached) {
      return cached.permissions[permission] || false
    }
    
    // 如果没有缓存，返回false（需要先调用checkPermission）
    return false
  }

  /**
   * 批量检查多个资源的权限（优化版本）
   */
  const batchCheckResourcePermissions = async (
    resourceType: ResourceType,
    resourceIds: number[],
    permissions: PermissionLevel[] = ['view', 'change', 'delete']
  ): Promise<Record<string, Record<string, boolean>>> => {
    // 超级用户拥有所有权限
    if (isSuperUser.value) {
      const result: Record<string, Record<string, boolean>> = {}
      resourceIds.forEach(id => {
        result[id.toString()] = {}
        permissions.forEach(perm => {
          result[id.toString()][perm] = true
        })
      })
      return result
    }

    try {
      const result = await permissionsApi.batchCheckPermissions(resourceType, resourceIds, permissions)
      return result.permissions
    } catch (err: any) {
      console.error('批量资源权限检查失败:', err)
      // 返回默认权限（无权限）
      const result: Record<string, Record<string, boolean>> = {}
      resourceIds.forEach(id => {
        result[id.toString()] = {}
        permissions.forEach(perm => {
          result[id.toString()][perm] = false
        })
      })
      return result
    }
  }

  return {
    // 状态
    userPermissions,
    permissionCache,
    resourcePermissionsCache,
    loading,
    error,
    
    // 计算属性
    isSuperUser,
    isStaff,
    hasAnyPermissions,
    
    // 方法
    fetchUserPermissions,
    checkPermission,
    checkPermissions,
    checkResourcePermissions,
    batchCheckResourcePermissions,
    clearCache,
    clearResourceCache,
    hasPermission,
  }
})
