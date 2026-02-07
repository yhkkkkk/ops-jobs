import { usePermissionsStore } from '@/stores/permissions'
import type { PermissionLevel, ResourceType } from '@/types'

/**
 * 权限检查工具函数
 * 提供便捷的权限检查方法
 */

/**
 * 检查用户是否有特定权限
 * @param resourceType 资源类型
 * @param permission 权限级别
 * @param resourceId 资源ID（可选）
 * @returns Promise<boolean>
 */
export const checkPermission = async (
  resourceType: ResourceType,
  permission: PermissionLevel,
  resourceId?: number
): Promise<boolean> => {
  const permissionsStore = usePermissionsStore()
  return await permissionsStore.checkPermission(resourceType, permission, resourceId)
}

/**
 * 批量检查权限
 * @param resourceType 资源类型
 * @param permissions 权限列表
 * @param resourceId 资源ID（可选）
 * @returns Promise<Record<string, boolean>>
 */
export const checkPermissions = async (
  resourceType: ResourceType,
  permissions: PermissionLevel[],
  resourceId?: number
): Promise<Record<string, boolean>> => {
  const permissionsStore = usePermissionsStore()
  return await permissionsStore.checkPermissions(resourceType, permissions, resourceId)
}

/**
 * 检查资源权限
 * @param resourceType 资源类型
 * @param resourceIds 资源ID列表
 * @param permissions 权限列表
 * @returns Promise<ResourcePermissionsResponse | null>
 */
export const checkResourcePermissions = async (
  resourceType: ResourceType,
  resourceIds: number[],
  permissions: PermissionLevel[] = ['view', 'change', 'delete']
) => {
  const permissionsStore = usePermissionsStore()
  return await permissionsStore.checkResourcePermissions(resourceType, resourceIds, permissions)
}

/**
 * 同步检查权限（基于缓存）
 * @param resourceType 资源类型
 * @param permission 权限级别
 * @param resourceId 资源ID（可选）
 * @returns boolean
 */
export const hasPermission = (
  resourceType: ResourceType,
  permission: PermissionLevel,
  resourceId?: number
): boolean => {
  const permissionsStore = usePermissionsStore()
  return permissionsStore.hasPermission(resourceType, permission, resourceId)
}

/**
 * 检查用户是否是超级用户
 * @returns boolean
 */
export const isSuperUser = (): boolean => {
  const permissionsStore = usePermissionsStore()
  return permissionsStore.isSuperUser
}

/**
 * 检查用户是否是员工
 * @returns boolean
 */
export const isStaff = (): boolean => {
  const permissionsStore = usePermissionsStore()
  return permissionsStore.isStaff
}

/**
 * 权限检查装饰器（用于组件方法）
 * @param resourceType 资源类型
 * @param permission 权限级别
 * @param resourceId 资源ID（可选）
 */
export const requirePermission = (
  resourceType: ResourceType,
  permission: PermissionLevel,
  resourceId?: number
) => {
  return function (target: any, propertyKey: string, descriptor: PropertyDescriptor) {
    const originalMethod = descriptor.value
    
    descriptor.value = async function (...args: any[]) {
      const hasPerm = await checkPermission(resourceType, permission, resourceId)
      if (!hasPerm) {
        throw new Error('权限不足')
      }
      return originalMethod.apply(this, args)
    }
    
    return descriptor
  }
}

/**
 * 权限检查组合函数（用于组合式API）
 * @param resourceType 资源类型
 * @param permission 权限级别
 * @param resourceId 资源ID（可选）
 */
export const usePermission = (
  resourceType: ResourceType,
  permission: PermissionLevel,
  resourceId?: number
) => {
  const permissionsStore = usePermissionsStore()
  
  const check = async () => {
    return await permissionsStore.checkPermission(resourceType, permission, resourceId)
  }
  
  const has = computed(() => {
    return permissionsStore.hasPermission(resourceType, permission, resourceId)
  })
  
  return {
    check,
    has,
    loading: computed(() => permissionsStore.loading),
    error: computed(() => permissionsStore.error)
  }
}

/**
 * 批量权限检查组合函数
 * @param resourceType 资源类型
 * @param permissions 权限列表
 * @param resourceId 资源ID（可选）
 */
export const usePermissions = (
  resourceType: ResourceType,
  permissions: PermissionLevel[],
  resourceId?: number
) => {
  const permissionsStore = usePermissionsStore()
  
  const check = async () => {
    return await permissionsStore.checkPermissions(resourceType, permissions, resourceId)
  }
  
  const has = (permission: PermissionLevel) => {
    return permissionsStore.hasPermission(resourceType, permission, resourceId)
  }
  
  return {
    check,
    has,
    loading: computed(() => permissionsStore.loading),
    error: computed(() => permissionsStore.error)
  }
}
