// 通用响应类型
export interface ApiResponse<T = any> {
  code: number
  message: string
  success: boolean
  content: T
}

// 分页响应类型
export interface PaginatedResponse<T> {
  total: number
  page_size: number
  page: number
  results: T[]
}

// 用户类型
export interface User {
  id: number
  username: string
  email: string
  first_name: string
  last_name: string
  is_staff: boolean
  is_superuser: boolean
  profile: any
}

// 登录相关类型
export interface LoginParams {
  username: string
  password: string
}

export interface LoginResult {
  access_token: string
  refresh_token: string
  user: User
}

// 主机类型
export interface Host {
  id: number
  name: string
  ip_address: string
  port: number
  username: string
  os_type: 'linux' | 'windows' | 'aix' | 'solaris'
  os_type_display?: string
  auth_type: 'password' | 'key'
  auth_type_display?: string
  password?: string
  private_key?: string
  description?: string
  status: 'online' | 'offline' | 'unknown'
  status_display?: string
  last_connected_at?: string
  last_check_time?: string
  connection_count?: number
  groups?: HostGroup[]
  groups_info?: HostGroup[]
  created_by?: number
  created_by_name?: string
  created_at: string
  updated_at: string
  testing?: boolean // 前端用于显示测试状态

  // === 网络信息 ===
  public_ip?: string
  internal_ip?: string
  internal_mac?: string
  external_mac?: string
  gateway?: string
  dns_servers?: string

  // === 云厂商信息 ===
  cloud_provider?: 'aliyun' | 'tencent' | 'aws' | 'azure' | 'huawei' | 'baidu' | 'ucloud' | 'qiniu' | 'idc' | 'other'
  cloud_provider_display?: string
  instance_id?: string
  region?: string
  zone?: string
  instance_type?: string
  network_type?: string

  // === 硬件信息 ===
  device_type?: 'vm' | 'container' | 'physical' | 'k8s_node'
  device_type_display?: string
  cpu_cores?: number
  memory_gb?: number
  disk_gb?: number

  // === 系统详细信息 ===
  os_version?: string
  kernel_version?: string
  hostname?: string
  cpu_model?: string
  os_arch?: string
  cpu_arch?: string
  boot_time?: string

  // === 业务信息 ===
  environment?: 'dev' | 'test' | 'staging' | 'prod'
  environment_display?: string
  business_system?: string
  service_role?: string
  remarks?: string

  // === 管理信息 ===
  owner?: string
  department?: string
}

export interface HostImportSummary {
  total: number
  created: number
  updated: number
  skipped: number
  failed: number
}

export type HostImportStatus = 'created' | 'updated' | 'skipped' | 'failed'

export interface HostImportDetail {
  row: number
  name?: string | null
  ip_address?: string | null
  status: HostImportStatus
  message?: string
  missing_groups?: string[]
}

export interface HostImportResult {
  summary: HostImportSummary
  details: HostImportDetail[]
  message?: string
  limit_note?: string
  success?: boolean
  missing_columns?: string[]
}

// 主机分组类型
export interface HostGroup {
  id: number
  name: string
  description?: string
  parent?: number | null
  parent_name?: string
  sort_order?: number
  full_path?: string
  level?: number
  host_count?: number
  online_count?: number
  offline_count?: number
  children_count?: number
  has_children?: boolean
  children?: HostGroup[]
  total_host_count?: number
  total_online_count?: number
  created_by?: number
  created_by_name?: string
  created_at: string
  updated_at: string
}

// 服务器账号类型
export interface ServerAccount {
  id?: number
  name: string
  username: string
  password?: string
  private_key?: string
  description?: string
  auth_type?: 'password' | 'key' | 'both' | 'none'
  has_password?: boolean
  has_private_key?: boolean
}

// 脚本模板类型
export interface ScriptTemplate {
  id?: number
  name: string
  description?: string
  script_type: 'shell' | 'python' | 'powershell'
  category?: string
  tags_json?: Record<string, string>  // 键值对格式的标签
  tag_list?: string[]  // 后端返回的标签列表（用于显示）
  content?: string     // 前端使用的字段
  script_content?: string  // 后端返回的字段
  template_type?: string
  version?: string
  is_active?: boolean
  is_public?: boolean
  usage_count?: number
  created_by?: number
  created_by_name?: string
  created_at?: string
  updated_at?: string
}

export interface ScriptParameter {
  name: string
  type: 'string' | 'number' | 'boolean' | 'array'
  default: string
  description: string
  required: boolean
}

// 作业模板类型
export interface JobTemplate {
  id: number
  name: string
  description: string
  category: string
  // 用于创建/编辑时的标签结构
  tags: { key: string; value: string }[]
  global_parameters: Record<string, any>
  steps: JobStep[]
  step_count: number
  plan_count: number
  has_unsync_plans: boolean
  created_by_name: string
  created_at: string
  updated_at: string
}


export interface JobStep {
  id: number
  name: string
  description: string
  step_type: 'script' | 'file_transfer'
  step_type_display: string
  order: number
  step_parameters: string[]  // 位置参数数组
  timeout: number
  ignore_error: boolean
  condition: string
  target_hosts: number[]
  target_groups: number[]

  // 脚本相关字段
  script_type?: string
  script_content?: string
  account_id?: number

  account_name?: string | null
  // 文件传输相关字段
  transfer_type?: string
  local_path?: string
  remote_path?: string
  overwrite_policy?: string
}

// 执行计划类型
export interface ExecutionPlan {
  id: number
  template: number
  template_name: string
  template_global_parameters: Record<string, any>
  name: string
  description: string
  is_synced: boolean
  needs_sync: boolean
  last_sync_at: string | null
  step_count: number
  total_executions: number
  success_executions: number
  failed_executions: number
  success_rate: number
  last_executed_at: string | null
  created_by: number
  created_by_name: string
  created_at: string
  updated_at: string
  plan_steps?: PlanStep[]
}

// 方案步骤类型
export interface PlanStep {
  id: number
  order: number
  template_step_id: number | null
  is_template_step_deleted: boolean
  // 快照数据（执行方案创建时的模板状态）
  step_name: string
  step_description: string
  step_type: string
  step_script_content: string
  step_script_type: string
  step_parameters: string[]
  step_timeout: number
  step_ignore_error: boolean
  step_condition: string
  step_target_host_ids: number[]
  step_target_group_ids: number[]
  step_account_id?: number | null
  step_account_name?: string | null
  step_transfer_type?: string
  step_local_path?: string
  step_remote_path?: string
  // 覆盖配置
  override_parameters: Record<string, any>
  override_timeout: number | null
  // 有效值（仅在有覆盖时存在）
  effective_parameters?: string[]
  effective_timeout?: number
}


// 批量连接测试结果
export interface BatchTestResult {
  total: number
  success: number
  failed: number
  details: Array<{
    host_id: number
    host_name: string
    ip_address: string
    result: {
      success: boolean
      message: string
      latency: number
      system_info?: {
        os: string
        cpu: string
        memory: string
      }
    }
  }>
}

// 执行记录类型
export interface ExecutionRecord {
  id: number
  execution_id: string  // 改为string类型，避免JavaScript精度问题
  execution_type: 'quick_script' | 'quick_file_transfer' | 'job_workflow' | 'scheduled_job'
  execution_type_display: string
  name: string
  description: string
  status: 'pending' | 'running' | 'success' | 'failed' | 'cancelled'
  status_display: string
  trigger_type: 'manual' | 'scheduled' | 'api' | 'webhook'
  trigger_type_display: string
  executed_by: number
  executed_by_name: string
  celery_task_id?: string
  execution_parameters: any
  execution_results: any
  error_message: string
  created_at: string
  started_at?: string
  finished_at?: string
  duration?: number
  retry_count: number
  max_retries: number
  client_ip: string
  user_agent: string
  is_completed: boolean
  is_running: boolean
  related_object_info?: {
    type: string
    id: number
    name: string
  }
}

// 定时任务类型
export interface ScheduledTask {
  id: number
  name: string
  description: string
  plan_id: number
  plan_name: string
  cron_expression: string
  enabled: boolean
  next_run_time?: string
  last_run_time?: string
  last_run_status?: 'success' | 'failed' | 'running'
  run_count: number
  success_count: number
  created_by_name: string
  created_at: string
  updated_at: string
}

// 审计日志类型
export interface AuditLog {
  id: number
  user: number
  user_name: string
  user_full_name: string
  action: string
  action_display: string
  resource_type: number | null
  resource_type_name: string | null
  resource_id: number | null
  resource_name: string
  description: string
  ip_address: string
  user_agent: string
  success: boolean
  error_message: string
  extra_data: Record<string, any>
  created_at: string
}

// 审计日志查询参数
export interface AuditLogQueryParams {
  page?: number
  page_size?: number
  user_id?: number
  action?: string
  success?: boolean
  resource_type?: string
  start_date?: string
  end_date?: string
  ip_address?: string
  search?: string
}

// 权限相关类型
export interface PermissionCheckRequest {
  resource_type: string
  resource_id?: number
  permissions?: string[]
}

export interface PermissionCheckResponse {
  user_id: number
  username: string
  resource_type: string
  resource_id?: number
  permissions: Record<string, boolean>
}

export interface UserPermissionsResponse {
  user_id: number
  username: string
  is_superuser: boolean
  is_staff: boolean
  groups: string[]
  model_permissions: Record<string, string[]>
  object_permissions: Record<string, any>
  permission_count: number
}

export interface ResourcePermissionsRequest {
  resource_type: string
  resource_ids?: number[]
  permissions?: string[]
}

export interface ResourcePermissionsResponse {
  user_id: number
  username: string
  resource_type: string
  permissions: Record<string, any>
  level: 'model' | 'object'
}

// 权限检查结果类型
export interface PermissionResult {
  hasPermission: boolean
  loading: boolean
  error: string | null
}

// 权限级别
export type PermissionLevel = 'view' | 'add' | 'change' | 'delete' | 'execute'

// 资源类型
export type ResourceType = 'host' | 'job' | 'script' | 'executionplan' | 'jobtemplate' | 'scripttemplate' | 'serveraccount' | 'executionrecord'
