import { http } from '@/utils/request'
import type { 
  PermissionCheckRequest, 
  PermissionCheckResponse,
  UserPermissionsResponse,
  ResourcePermissionsRequest,
  ResourcePermissionsResponse
} from '@/types'

export const permissionsApi = {
  /**
   * 检查用户对特定资源的权限
   */
  checkPermission(data: PermissionCheckRequest): Promise<PermissionCheckResponse> {
    return http.post('/permissions/check/', data)
  },

  /**
   * 获取当前用户的权限摘要
   */
  getUserPermissions(): Promise<UserPermissionsResponse> {
    return http.get('/permissions/user-permissions/')
  },

  /**
   * 批量检查用户权限
   */
  checkUserPermissions(permissions: string[]): Promise<PermissionCheckResponse> {
    return http.post('/permissions/user-permissions/', { permissions })
  },

  /**
   * 检查用户对资源的权限
   */
  checkResourcePermissions(data: ResourcePermissionsRequest): Promise<ResourcePermissionsResponse> {
    return http.post('/permissions/resource-permissions/', data)
  },

  /**
   * 批量检查多个资源的权限
   */
  batchCheckPermissions(
    resourceType: string, 
    resourceIds: number[], 
    permissions: string[] = ['view', 'change', 'delete']
  ): Promise<ResourcePermissionsResponse> {
    return http.post('/permissions/resource-permissions/', {
      resource_type: resourceType,
      resource_ids: resourceIds,
      permissions
    })
  }
}
