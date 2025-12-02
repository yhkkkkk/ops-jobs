import type { Directive, DirectiveBinding } from 'vue'
import type { PermissionLevel, ResourceType } from '@/types'

interface PermissionBindingValue {
  resourceType: ResourceType
  permission: PermissionLevel
  resourceId?: number
  fallback?: boolean
}

interface BatchPermissionBindingValue {
  resourceType: ResourceType
  permissions: PermissionLevel[]
  resourceIds?: number[]
  fallback?: boolean
}

/**
 * 权限指令
 * 用法：
 * v-permission="{ resourceType: 'host', permission: 'view', resourceId: 1 }"
 * v-permission="{ resourceType: 'host', permission: 'view' }"
 */
export const permission: Directive = {
  mounted(el: HTMLElement, binding: DirectiveBinding) {
    const { value } = binding
    
    if (!value || typeof value !== 'object') {
      console.warn('v-permission 指令需要传入权限配置对象')
      return
    }

    const { resourceType, permission, resourceId, fallback = false } = value as PermissionBindingValue
    
    if (!resourceType || !permission) {
      console.warn('v-permission 指令缺少必要的 resourceType 或 permission 参数')
      return
    }

    // 先隐藏元素，避免在权限检查完成前显示（除非是fallback模式）
    // 权限检查函数会先检查缓存，如果有缓存会立即显示
    if (!fallback) {
      el.style.display = 'none'
    }

    // 检查权限（异步，但元素已隐藏，不会闪烁）
    checkPermission(el, resourceType, permission, resourceId, fallback)
  },

  updated(el: HTMLElement, binding: DirectiveBinding) {
    const { value } = binding
    
    if (!value || typeof value !== 'object') return

    const { resourceType, permission, resourceId, fallback = false } = value as PermissionBindingValue
    
    if (!resourceType || !permission) return

    // 检查绑定值是否发生变化
    const oldValue = binding.oldValue as PermissionBindingValue | undefined
    if (oldValue && 
        oldValue.resourceType === resourceType &&
        oldValue.permission === permission &&
        oldValue.resourceId === resourceId &&
        oldValue.fallback === fallback) {
      // 绑定值没有变化，且元素已经处理过权限，不需要重新检查
      // 但需要检查缓存，如果缓存中有结果，直接应用
      checkPermissionFromCache(el, resourceType, permission, resourceId, fallback)
      return
    }

    // 重新检查权限
    checkPermission(el, resourceType, permission, resourceId, fallback)
  }
}

/**
 * 从缓存检查权限（同步方法）
 */
function checkPermissionFromCache(
  el: HTMLElement,
  resourceType: ResourceType,
  permission: PermissionLevel,
  resourceId?: number,
  fallback = false
) {
  try {
    // 延迟导入避免循环依赖
    const { usePermissionsStore } = require('@/stores/permissions')
    const permissionsStore = usePermissionsStore()
    
    // 检查是否是超级用户
    if (permissionsStore.isSuperUser) {
      el.style.display = ''
      el.removeAttribute('data-permission-denied')
      return
    }
    
    // 检查缓存中是否有该权限的记录
    const hasPerm = permissionsStore.hasPermission(resourceType, permission, resourceId)
    
    // 如果缓存中没有结果，不处理（等待异步检查完成）
    if (hasPerm === false && !permissionsStore.permissionCache.has(`${resourceType}:${permission}:${resourceId || 'model'}`)) {
      return
    }
    
    // 应用权限结果
    applyPermissionResult(el, hasPerm, fallback)
  } catch (error) {
    console.error('从缓存检查权限失败:', error)
  }
}

/**
 * 应用权限检查结果
 */
function applyPermissionResult(el: HTMLElement, hasPerm: boolean, fallback: boolean) {
    if (hasPerm) {
      // 有权限，显示元素
      el.style.display = ''
      el.style.visibility = 'visible'
      el.style.position = ''
      el.removeAttribute('data-permission-denied')
    } else {
      // 无权限
      if (fallback) {
        // 显示权限不足提示
        el.style.display = ''
        el.style.visibility = 'visible'
        el.style.position = ''
        el.setAttribute('data-permission-denied', 'true')
        el.innerHTML = `
          <div style="padding: 10px; text-align: center; color: #999;">
            <icon-lock style="margin-right: 5px;" />
            权限不足
          </div>
        `
      } else {
        // 隐藏元素
        el.style.display = 'none'
        el.style.visibility = 'hidden'
        el.style.position = ''
      }
  }
}

/**
 * 检查单个权限
 */
async function checkPermission(
  el: HTMLElement,
  resourceType: ResourceType,
  permission: PermissionLevel,
  resourceId?: number,
  fallback = false
) {
  try {
    // 首先检查是否是超级用户 - 从认证存储获取
    try {
      const { useAuthStore } = await import('@/stores/auth')
      const authStore = useAuthStore()
      
      if (authStore.isAdmin) {
        applyPermissionResult(el, true, fallback)
        return
      }
    } catch (authError) {
      console.error('获取认证存储失败:', authError)
    }
    
    // 延迟导入避免循环依赖
    const { usePermissionsStore } = await import('@/stores/permissions')
    const permissionsStore = usePermissionsStore()
    
    // 再次检查超级用户（从权限存储）
    if (permissionsStore.isSuperUser) {
      applyPermissionResult(el, true, fallback)
      return
    }
    
    // 检查缓存中是否有该权限的记录
    const cacheKey = `${resourceType}:${permission}:${resourceId || 'model'}`
    const hasCache = permissionsStore.permissionCache.has(cacheKey)
    
    // 首先尝试使用缓存的权限结果
    let hasPerm: boolean
    if (hasCache) {
      // 有缓存，立即使用
      hasPerm = permissionsStore.hasPermission(resourceType, permission, resourceId)
      applyPermissionResult(el, hasPerm, fallback)
    } else {
      // 如果缓存中没有，调用API检查权限
      // 注意：页面级权限预加载应该已经缓存了大部分权限，这里主要是兜底
      hasPerm = await permissionsStore.checkPermission(resourceType, permission, resourceId)
      applyPermissionResult(el, hasPerm, fallback)
    }
  } catch (error) {
    console.error('权限检查失败:', error)
    // 权限检查失败时，尝试检查用户信息
    try {
      const { useAuthStore } = await import('@/stores/auth')
      const authStore = useAuthStore()
      
      // 如果是超级用户，显示元素
      if (authStore.isAdmin) {
        applyPermissionResult(el, true, fallback)
        return
      }
    } catch (authError) {
      console.error('获取用户信息失败:', authError)
    }
    
    // 权限检查失败时隐藏元素
    applyPermissionResult(el, false, fallback)
  }
}

/**
 * 批量权限指令
 * 用法：
 * v-permissions="{ resourceType: 'host', permissions: ['view', 'change'], resourceId: 1 }"
 */
export const permissions: Directive = {
  mounted(el: HTMLElement, binding: DirectiveBinding) {
    const { value } = binding
    
    if (!value || typeof value !== 'object') {
      console.warn('v-permissions 指令需要传入权限配置对象')
      return
    }

    const { resourceType, permissions, resourceId, fallback = false, requireAll = true } = value as {
      resourceType: ResourceType
      permissions: PermissionLevel[]
      resourceId?: number
      fallback?: boolean
      requireAll?: boolean // 是否需要所有权限
    }
    
    if (!resourceType || !permissions || !Array.isArray(permissions)) {
      console.warn('v-permissions 指令缺少必要的参数')
      return
    }

    // 检查批量权限
    checkBatchPermissions(el, resourceType, permissions, resourceId, fallback, requireAll)
  },

  updated(el: HTMLElement, binding: DirectiveBinding) {
    const { value } = binding
    
    if (!value || typeof value !== 'object') return

    const { resourceType, permissions, resourceId, fallback = false, requireAll = true } = value as {
      resourceType: ResourceType
      permissions: PermissionLevel[]
      resourceId?: number
      fallback?: boolean
      requireAll?: boolean
    }
    
    if (!resourceType || !permissions || !Array.isArray(permissions)) return

    // 重新检查权限
    checkBatchPermissions(el, resourceType, permissions, resourceId, fallback, requireAll)
  }
}

/**
 * 检查批量权限
 */
async function checkBatchPermissions(
  el: HTMLElement,
  resourceType: ResourceType,
  permissions: PermissionLevel[],
  resourceId?: number,
  fallback = false,
  requireAll = true
) {
  try {
    // 延迟导入避免循环依赖
    const { usePermissionsStore } = await import('@/stores/permissions')
    const permissionsStore = usePermissionsStore()
    
    // 首先检查是否是超级用户 - 从认证存储获取
    try {
      const { useAuthStore } = await import('@/stores/auth')
      const authStore = useAuthStore()
      
      if (authStore.isAdmin) {
        el.style.display = ''
        el.removeAttribute('data-permission-denied')
        return
      }
    } catch (authError) {
      console.error('获取认证存储失败:', authError)
      // 如果无法获取认证存储，回退到权限存储
      if (permissionsStore.isSuperUser) {
        el.style.display = ''
        el.removeAttribute('data-permission-denied')
        return
      }
    }
    
    // 首先尝试使用缓存的权限结果
    let result: Record<string, boolean> = {}
    let allCached = true
    
    // 检查缓存中是否有所有需要的权限
    for (const perm of permissions) {
      const cached = permissionsStore.hasPermission(resourceType, perm, resourceId)
      if (cached === null || cached === undefined) {
        allCached = false
        break
      }
      result[perm] = cached
    }
    
    // 如果缓存中没有，才调用API
    if (!allCached) {
      result = await permissionsStore.checkPermissions(resourceType, permissions, resourceId)
    }
    
    // 判断是否满足权限要求
    let hasPermission = false
    
    if (requireAll) {
      // 需要所有权限
      hasPermission = permissions.every(perm => result[perm])
    } else {
      // 只需要其中一个权限
      hasPermission = permissions.some(perm => result[perm])
    }
    
    if (hasPermission) {
      // 有权限，显示元素
      el.style.display = ''
      el.removeAttribute('data-permission-denied')
    } else {
      // 无权限
      if (fallback) {
        // 显示权限不足提示
        el.style.display = ''
        el.setAttribute('data-permission-denied', 'true')
        el.innerHTML = `
          <div style="padding: 10px; text-align: center; color: #999;">
            <icon-lock style="margin-right: 5px;" />
            权限不足
          </div>
        `
      } else {
        // 隐藏元素
        el.style.display = 'none'
      }
    }
  } catch (error) {
    console.error('批量权限检查失败:', error)
    // 权限检查失败时，尝试检查用户信息
    try {
      const { useAuthStore } = await import('@/stores/auth')
      const authStore = useAuthStore()
      
      // 如果是超级用户，显示元素
      if (authStore.isAdmin) {
        el.style.display = ''
        el.removeAttribute('data-permission-denied')
        return
      }
    } catch (authError) {
      console.error('获取用户信息失败:', authError)
    }
    
    // 权限检查失败时隐藏元素
    el.style.display = 'none'
  }
}

/**
 * 页面级批量权限指令 - 用于一次性检查页面中所有元素的权限
 * 用法：
 * v-page-permissions="{ resourceType: 'host', permissions: ['view', 'change', 'delete'] }"
 * 这个指令应该放在页面的根元素上，用于预加载权限
 */
export const pagePermissions: Directive = {
  mounted(_el: HTMLElement, binding: DirectiveBinding) {
    const { value } = binding
    
    if (!value || typeof value !== 'object') {
      console.warn('v-page-permissions 指令需要传入权限配置对象')
      return
    }

    const { resourceType, permissions, resourceIds } = value as BatchPermissionBindingValue
    
    if (!resourceType || !permissions || !Array.isArray(permissions)) {
      console.warn('v-page-permissions 指令缺少必要的参数')
      return
    }

    // 预加载页面权限
    preloadPagePermissions(resourceType, permissions, resourceIds)
  },

  updated(_el: HTMLElement, binding: DirectiveBinding) {
    const { value } = binding
    
    if (!value || typeof value !== 'object') return

    const { resourceType, permissions, resourceIds } = value as BatchPermissionBindingValue
    
    if (!resourceType || !permissions || !Array.isArray(permissions)) return

    // 检查 resourceIds 是否发生变化（使用序列化比较避免数组引用问题）
    const oldValue = binding.oldValue as BatchPermissionBindingValue | undefined
    if (oldValue) {
      const oldIds = oldValue.resourceIds || []
      const newIds = resourceIds || []
      
      // 序列化比较 resourceIds
      const oldIdsStr = JSON.stringify([...oldIds].sort((a, b) => (a || 0) - (b || 0)))
      const newIdsStr = JSON.stringify([...newIds].sort((a, b) => (a || 0) - (b || 0)))
      
      // 如果 resourceIds 没有变化，不需要重新预加载
      if (oldIdsStr === newIdsStr &&
          oldValue.resourceType === resourceType &&
          oldValue.permissions.length === permissions.length &&
          oldValue.permissions.every((p, i) => p === permissions[i])) {
        return
      }
    }

    // resourceIds 发生变化，重新预加载权限
    preloadPagePermissions(resourceType, permissions, resourceIds)
  }
}

// 预加载请求的缓存，用于去重
const preloadRequestCache = new Map<string, Promise<void>>()

/**
 * 预加载页面权限
 */
async function preloadPagePermissions(
  resourceType: ResourceType,
  permissions: PermissionLevel[],
  resourceIds?: number[]
) {
  try {
    // 延迟导入避免循环依赖
    const { usePermissionsStore } = await import('@/stores/permissions')
    const permissionsStore = usePermissionsStore()
    
    // 如果是超级用户，直接返回（无需预加载）
    if (permissionsStore.isSuperUser) {
      return
    }
    
    // 同时预加载模型级权限和对象级权限
    // 1. 先预加载模型级权限（用于没有 resourceId 的 v-permission 指令）
    const modelRequestKey = `preload:${resourceType}:model:${permissions.join(',')}`
    if (!preloadRequestCache.has(modelRequestKey)) {
      const modelRequestPromise = (async () => {
        try {
          await permissionsStore.checkPermissions(resourceType, permissions)
        } finally {
          setTimeout(() => {
            preloadRequestCache.delete(modelRequestKey)
          }, 1000)
        }
      })()
      preloadRequestCache.set(modelRequestKey, modelRequestPromise)
    }
    
    // 2. 如果有 resourceIds，再预加载对象级权限
    if (resourceIds && resourceIds.length > 0) {
      const sortedIds = [...resourceIds].sort((a, b) => a - b).join(',')
      const objectRequestKey = `preload:${resourceType}:${sortedIds}:${permissions.join(',')}`
      
      if (!preloadRequestCache.has(objectRequestKey)) {
        const objectRequestPromise = (async () => {
          try {
      await permissionsStore.batchCheckResourcePermissions(resourceType, resourceIds, permissions)
          } finally {
            setTimeout(() => {
              preloadRequestCache.delete(objectRequestKey)
            }, 1000)
          }
        })()
        preloadRequestCache.set(objectRequestKey, objectRequestPromise)
      }
      
      // 等待两个请求都完成
      await Promise.all([
        preloadRequestCache.get(modelRequestKey),
        preloadRequestCache.get(objectRequestKey)
      ])
    } else {
      // 只等待模型级权限请求完成
      await preloadRequestCache.get(modelRequestKey)
    }
  } catch (error) {
    console.error('页面权限预加载失败:', error)
    // 权限预加载失败时，尝试检查用户信息
    try {
      const { useAuthStore } = await import('@/stores/auth')
      const authStore = useAuthStore()
      
      // 如果是超级用户，记录日志
      if (authStore.isAdmin) {
        return
      }
    } catch (authError) {
      console.error('获取用户信息失败:', authError)
    }
  }
}

/**
 * 注册权限指令
 */
export function setupPermissionDirectives(app: any) {
  app.directive('permission', permission)
  app.directive('permissions', permissions)
  app.directive('page-permissions', pagePermissions)
}
