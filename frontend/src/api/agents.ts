import { http } from '@/utils/request'

export interface Agent {
  id: number
  host: {
    id: number
    name: string
    ip_address: string
    status: string
    status_display: string
    os_type: string
    os_type_display: string
    tags?: { key: string; value: string }[]
    service_role?: string
  }
  status: 'pending' | 'online' | 'offline' | 'disabled'
  status_display: string
  agent_type?: 'agent' | 'agent-server'
  agent_type_display?: string
  version: string
  endpoint: string
  agent_server_id?: number | null
  last_heartbeat_at: string | null
  last_error_code: string
  tags?: string[]
  created_at: string
  updated_at: string
  tokens?: AgentToken[]
  computed_status?: string
  computed_status_display?: string
  is_version_outdated?: boolean
  expected_min_version?: string
}

export interface AgentToken {
  id: number
  token_last4: string
  issued_by: number
  issued_by_name: string
  created_at: string
  expired_at: string | null
  revoked_at: string | null
  note: string
}

export interface AgentTaskStats {
  total?: number
  success?: number
  failed?: number
  cancelled?: number
  avg_duration_ms?: number
  success_rate?: number
  health_status?: string
  last_updated?: string
}

export interface AgentServer {
  id: number
  name: string
  base_url: string
  is_active: boolean
  description?: string
  has_secret?: boolean
  shared_secret_last4?: string
  require_signature?: boolean
  created_at?: string
  updated_at?: string
}

export interface AgentDetail extends Agent {
  host: {
    id: number
    name: string
    ip_address: string
    port: number
    status: string
    status_display: string
    os_type: string
    os_type_display: string
    tags?: { key: string; value: string }[]
    service_role?: string
    groups_info?: any[]
    [key: string]: any
  }
  task_stats?: AgentTaskStats
}

export interface IssueTokenParams {
  expired_at?: string | null
  note?: string
  confirmed: boolean
}

export interface BatchOperationParams {
  agent_ids: number[]
  confirmed: boolean
  agent_server_id?: number
}

export interface PaginatedResponse<T> {
  results: T[]
  total: number
  page: number
  page_size: number
}

export const agentsApi = {
  // 获取 Agent 列表
  getAgents(params?: {
    page?: number
    page_size?: number
    search?: string
    status?: string
    tags?: string
    service_role?: string
    group?: number
    group_id?: number
    agent_server_id?: number
  }): Promise<PaginatedResponse<Agent>> {
    return http.get('/agents/', { params })
  },

  // 获取 Agent 详情
  getAgent(id: number): Promise<AgentDetail> {
    return http.get(`/agents/${id}/`)
  },

  // 签发 Token
  issueToken(id: number, data: IssueTokenParams): Promise<{
    token: string
    expired_at: string | null
    token_last4: string
  }> {
    return http.post(`/agents/${id}/issue_token/`, data)
  },

  // 吊销 Token
  revokeToken(id: number, data: { confirmed: boolean }): Promise<void> {
    return http.post(`/agents/${id}/revoke_token/`, data)
  },

  // 启用 Agent
  enableAgent(id: number): Promise<void> {
    return http.post(`/agents/${id}/enable/`)
  },

  // 禁用 Agent
  disableAgent(id: number, data: { confirmed: boolean }): Promise<void> {
    return http.post(`/agents/${id}/disable/`, data)
  },

  // 更新 Agent 关联的 Agent-Server（仅控制面记录）
  updateAgentServer(id: number, data: { agent_server_id: number | null }): Promise<{ id: number; agent_server_id: number | null }> {
    return http.post(`/agents/${id}/update_agent_server/`, data)
  },

  // 控制 Agent（重启/启动/停止）
  controlAgent(id: number, data: { action: 'start' | 'stop' | 'restart'; reason?: string; agent_server_id?: number }): Promise<{
    message: string
    status: string
  }> {
    return http.post(`/agents/${id}/control/`, data)
  },

  // 升级 Agent
  upgradeAgent(id: number, data: {
    target_version?: string
    package_id?: number
    confirmed: boolean
    agent_server_id?: number
  }): Promise<{
    message: string
  }> {
    return http.post(`/agents/${id}/upgrade/`, data)
  },

  // 批量禁用 Agent
  batchDisable(data: BatchOperationParams): Promise<{ count: number }> {
    return http.post('/agents/batch_disable/', data)
  },

  // 批量启用 Agent
  batchEnable(data: BatchOperationParams): Promise<{ count: number }> {
    return http.post('/agents/batch_enable/', data)
  },

  // 批量重启 Agent（带SSE进度监控）
  batchRestart(data: BatchOperationParams): Promise<{
    batch_task_id: string
    total: number
    status: string
  }> {
    return http.post('/agents/batch_restart/', data)
  },

  // 批量禁用 Agent（带SSE进度监控）
  batchDisableV2(data: BatchOperationParams): Promise<{
    batch_task_id: string
    total: number
    status: string
  }> {
    return http.post('/agents/batch_disable_v2/', data)
  },

  // 批量启用 Agent（带SSE进度监控）
  batchEnableV2(data: BatchOperationParams): Promise<{
    batch_task_id: string
    total: number
    status: string
  }> {
    return http.post('/agents/batch_enable_v2/', data)
  },

  // 重试安装记录中的失败主机
  retryInstallRecord(data: { install_record_id: number; confirmed: boolean }): Promise<{
    install_task_id: string
    total: number
    status: string
  }> {
    return http.post('/agents/retry_install_record/', data)
  },

  // 删除 Agent（仅允许删除 pending 状态）
  deleteAgent(id: number, data: { confirmed: boolean }): Promise<void> {
    return http.delete(`/agents/${id}/`, { data })
  },

  // 批量删除 Agent（仅允许删除 pending 状态）
  batchDelete(data: BatchOperationParams): Promise<{ count: number }> {
    return http.post('/agents/batch_delete/', data)
  },

  // 生成安装脚本
  generateInstallScript(data: {
    host_ids: number[]
    install_type?: 'agent' | 'agent-server'
    agent_server_url?: string
    agent_server_backup_url?: string
    ws_backoff_initial_ms?: number
    ws_backoff_max_ms?: number
    ws_max_retries?: number
    agent_server_listen_addr?: string
    agent_server_base_url?: string
    max_connections?: number
    heartbeat_timeout?: number
    package_id?: number
    package_version?: string
    auth_shared_secret?: string
    auth_require_signature?: boolean
  }): Promise<{
    scripts: Record<string, Array<{
      host_id: number
      host_name: string
      host_ip: string
      script: string
      token: string
    }>>
    install_type: string
    agent_server_url: string
    notice?: string
    errors?: string[]
  }> {
    return http.post('/agents/generate_install_script/', data)
  },

  // 批量安装 Agent
  batchInstall(data: {
    host_ids: number[]
    account_id?: number
    install_type?: 'agent' | 'agent-server'
    agent_server_url?: string
    agent_server_backup_url?: string
    ws_backoff_initial_ms?: number
    ws_backoff_max_ms?: number
    ws_max_retries?: number
    agent_server_listen_addr?: string
    agent_server_base_url?: string
    max_connections?: number
    heartbeat_timeout?: number
    ssh_timeout?: number
    allow_reinstall?: boolean
    package_id?: number
    package_version?: string
    auth_shared_secret?: string
    auth_require_signature?: boolean
    confirmed: boolean
  }): Promise<{
    results: Array<{
      host_id: number
      host_name: string
      success: boolean
      message: string
    }>
    total: number
    success_count: number
    failed_count: number
    install_task_id: string
  }> {
    return http.post('/agents/batch_install/', data)
  },

  // 获取安装记录
  getInstallRecords(params?: {
    page?: number
    page_size?: number
    host_id?: number
    status?: string
    install_type?: string
    search?: string
  }): Promise<PaginatedResponse<any>> {
    return http.get('/agents/install_records/', { params })
  },

  // 为 Agent 重新生成安装脚本（用于 pending 状态的 Agent）
  regenerateScript(agentId: number): Promise<{
    scripts: Record<string, Array<{
      host_id: number
      host_name: string
      host_ip: string
      script: string
      agent_token: string
      agent_id: number
    }>>
    install_type: string
    agent_server_url: string
    notice?: string
    errors?: string[]
  }> {
    return http.post(`/agents/${agentId}/regenerate_script/`)
  },

  // 获取下载地址
  getDownloadUrls(): Promise<{
    download_urls: Record<string, Record<string, string>>
    version: string
    base_url: string
  }> {
    return http.get('/agents/download_urls/')
  },

  // 批量卸载 Agent
  batchUninstall(data: {
    agent_ids: number[]
    account_id?: number
    confirmed: boolean
  }): Promise<{
    results: Array<{
      agent_id: number
      host_id: number
      host_name: string
      success: boolean
      message: string
    }>
    total: number
    success_count: number
    failed_count: number
    uninstall_task_id: string
  }> {
    return http.post('/agents/batch_uninstall/', data)
  },

  // 获取卸载记录
  getUninstallRecords(params?: {
    page?: number
    page_size?: number
    host_id?: number
    status?: string
  }): Promise<PaginatedResponse<any>> {
    return http.get('/agents/uninstall_records/', { params })
  },

  // 获取主机Agent状态
  getHostAgentStatus(): Promise<{
    hosts: Array<{
      id: number
      name: string
      ip_address: string
      agent_status: string | null
      agent_type: string | null
      agent_type_display: string | null
      agent_id: number | null
      agent_version: string | null
      computed_status: string | null
      computed_status_display: string | null
      can_install: boolean
    }>
  }> {
    return http.get('/agents/host_agent_status/')
  },
}

export const agentServerApi = {
  // 获取 Agent-Server 列表
  getAgentServers(params?: {
    page?: number
    page_size?: number
    search?: string
    is_active?: boolean
    require_signature?: boolean
  }): Promise<PaginatedResponse<AgentServer>> {
    return http.get('/agents/agent_servers/', { params })
  },

  // 更新 Agent-Server（仅控制面记录）
  updateAgentServer(id: number, data: {
    name?: string
    base_url?: string
    require_signature?: boolean
    shared_secret?: string
    is_active?: boolean
    description?: string
  }): Promise<AgentServer> {
    return http.patch(`/agents/agent_servers/${id}/`, data)
  }
}

// Agent 安装包管理 API
export interface AgentPackage {
  id: number
  package_type: 'agent' | 'agent-server'
  package_type_display?: string
  version: string
  description: string
  os_type: 'linux' | 'windows' | 'darwin'
  os_type_display: string
  arch: 'amd64' | 'arm64' | '386'
  arch_display: string
  file: string
  file_name: string
  file_size: number
  md5_hash: string
  sha256_hash: string
  download_url: string
  storage_type?: string
  is_default: boolean
  is_active: boolean
  created_by: number
  created_by_name: string
  created_at: string
  updated_at: string
}

export const packageApi = {
  // 获取安装包列表
  getPackages(params?: {
    page?: number
    page_size?: number
    search?: string
    package_type?: string
    os_type?: string
    arch?: string
    is_active?: boolean
    is_default?: boolean
  }): Promise<PaginatedResponse<AgentPackage>> {
    return http.get('/agents/packages/', { params })
  },

  // 获取单个安装包
  getPackage(id: number): Promise<AgentPackage> {
    return http.get(`/agents/packages/${id}/`)
  },

  // 创建安装包
  createPackage(data: FormData): Promise<AgentPackage> {
    return http.post('/agents/packages/', data, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
  },

  // 更新安装包
  updatePackage(id: number, data: FormData): Promise<AgentPackage> {
    return http.patch(`/agents/packages/${id}/`, data, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
  },

  // 删除安装包
  deletePackage(id: number): Promise<void> {
    return http.delete(`/agents/packages/${id}/`)
  },

  // 获取启用的安装包列表（用于安装时选择）
  getActivePackages(params?: { package_type?: string }): Promise<AgentPackage[]> {
    return http.get('/agents/packages/active_packages/', { params })
  },

  // 获取默认版本的安装包
  getDefaultPackages(params?: { package_type?: string }): Promise<AgentPackage[]> {
    return http.get('/agents/packages/default_packages/', { params })
  },
}
