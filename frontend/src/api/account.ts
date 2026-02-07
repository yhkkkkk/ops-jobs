/**
 * 服务器账号管理API
 */
import request from '@/utils/request'

export interface ServerAccount {
  id?: number
  name: string
  username: string
  password?: string
  private_key?: string
  description?: string
}

export interface AccountListResponse {
  results: ServerAccount[]
  total: number
  page: number
  page_size: number
}

export const accountApi = {
  /**
   * 获取账号列表
   */
  getAccounts(params?: {
    page?: number
    page_size?: number
    search?: string
    auth_type?: string
  }): Promise<AccountListResponse> {
    return request.get('/hosts/accounts/', { params })
  },

  /**
   * 创建账号
   */
  createAccount(data: ServerAccount): Promise<ServerAccount> {
    return request.post('/hosts/accounts/', data)
  },

  /**
   * 获取账号详情
   */
  getAccount(id: number): Promise<ServerAccount> {
    return request.get(`/hosts/accounts/${id}/`)
  },

  /**
   * 更新账号
   */
  updateAccount(id: number, data: Partial<ServerAccount>): Promise<ServerAccount> {
    return request.put(`/hosts/accounts/${id}/`, data)
  },

  /**
   * 删除账号
   */
  deleteAccount(id: number): Promise<void> {
    return request.delete(`/hosts/accounts/${id}/`)
  }
}
