import { http } from '@/utils/request'
import type {
  Host,
  ScriptTemplate,
  JobTemplate,
  ExecutionPlan,
  ExecutionRecord,
  ScheduledTask,
  PaginatedResponse,
  BatchTestResult,
  HostGroup,
  HostImportResult
} from '@/types'

// 主机管理API
export const hostApi = {
  // 获取主机列表
  getHosts(params?: any): Promise<PaginatedResponse<Host>> {
    return http.get('/hosts/hosts/', { params })
  },

  // 获取主机详情
  getHost(id: number): Promise<Host> {
    return http.get(`/hosts/hosts/${id}/`)
  },

  // 创建主机
  createHost(data: Partial<Host>): Promise<Host> {
    return http.post('/hosts/hosts/', data)
  },

  // 更新主机
  updateHost(id: number, data: Partial<Host>): Promise<Host> {
    return http.put(`/hosts/hosts/${id}/`, data)
  },

  // 删除主机
  deleteHost(id: number): Promise<void> {
    return http.delete(`/hosts/hosts/${id}/`)
  },

  // 测试连接
  testConnection(id: number): Promise<{ success: boolean; message: string }> {
    return http.post(`/hosts/hosts/${id}/test_connection/`)
  },

  // 收集系统信息
  collectSystemInfo(id: number): Promise<{ success: boolean; message: string; system_info?: any; updated_fields?: string[] }> {
    return http.post(`/hosts/hosts/${id}/collect_system_info/`)
  },

  // 批量测试连接
  batchTestConnection(host_ids: number[]): Promise<BatchTestResult> {
  // batchTestConnection(host_ids: number[]): Promise<{results: Array<{ host_id: number, success: boolean; message: string}> }> {
    return http.post('/hosts/hosts/batch_test/', { host_ids })
  },

  // 从云厂商同步主机
  syncCloudHosts(provider: string, region?: string): Promise<{ success: boolean; message: string; synced_hosts?: number; updated_hosts?: number; total_hosts?: number }> {
    return http.post('/hosts/hosts/sync_cloud_hosts/', { provider, region })
  },

  // 批量移动主机到分组
  batchMoveToGroup(host_ids: number[], group_id?: number | null): Promise<{ success: boolean; message: string; moved_count?: number; target_group_name?: string }> {
    return http.post('/hosts/hosts/batch_move_to_group/', { host_ids, group_id })
  },

  // 导入主机（Excel）
  importHostsFromExcel(formData: FormData): Promise<HostImportResult> {
    return http.post('/hosts/hosts/import_excel/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },

  downloadImportTemplate(): Promise<Blob> {
    return http.get('/hosts/hosts/import_excel_template/', {
      responseType: 'blob'
    })
  },
}

// 主机分组API
export const hostGroupApi = {
  // 获取分组列表
  getGroups(params?: any): Promise<PaginatedResponse<HostGroup>> {
    return http.get('/hosts/groups/', { params })
  },

  // 获取主机分组简单列表（用于下拉选择）
  getSimpleList(): Promise<HostGroup[]> {
    return http.get('/hosts/groups/simple_list/')
  },

  // 获取主机分组树形结构
  getGroupTree(): Promise<HostGroup[]> {
    return http.get('/hosts/groups/tree/')
  },

  // 获取分组详情
  getGroup(id: number): Promise<HostGroup> {
    return http.get(`/hosts/groups/${id}/`)
  },

  // 创建分组
  createGroup(data: Partial<HostGroup>): Promise<HostGroup> {
    return http.post('/hosts/groups/', data)
  },

  // 更新分组
  updateGroup(id: number, data: Partial<HostGroup>): Promise<HostGroup> {
    return http.put(`/hosts/groups/${id}/`, data)
  },

  // 删除分组
  deleteGroup(id: number): Promise<void> {
    return http.delete(`/hosts/groups/${id}/`)
  },

  // 移动分组
  moveGroup(id: number, data: { parent_id?: number; sort_order?: number }): Promise<HostGroup> {
    return http.post(`/hosts/groups/${id}/move/`, data)
  },

  // 批量测试分组内主机连接
  batchTestGroupConnection(id: number): Promise<{ results: Array<{ host_id: number; success: boolean; message: string }> }> {
    return http.post(`/hosts/groups/${id}/batch_test/`)
  },
}

// 脚本模板API
export const scriptTemplateApi = {
  // 获取脚本模板列表
  getTemplates(params?: any): Promise<PaginatedResponse<ScriptTemplate>> {
    return http.get('/script-templates/', { params })
  },
  
  // 获取可用标签
  getTags(): Promise<{ tags: string[] }> {
    return http.get('/script-templates/tags/')
  },

  // 获取脚本模板详情
  getTemplate(id: number): Promise<ScriptTemplate> {
    return http.get(`/script-templates/${id}/`)
  },

  // 创建脚本模板
  createTemplate(data: Partial<ScriptTemplate>): Promise<ScriptTemplate> {
    return http.post('/script-templates/', data)
  },

  // 更新脚本模板
  updateTemplate(id: number, data: Partial<ScriptTemplate>): Promise<ScriptTemplate> {
    return http.put(`/script-templates/${id}/`, data)
  },

  // 删除脚本模板
  deleteTemplate(id: number): Promise<void> {
    return http.delete(`/script-templates/${id}/`)
  },

  // 复制脚本模板
  copyTemplate(id: number): Promise<ScriptTemplate> {
    return http.post(`/script-templates/${id}/copy/`)
  },

  // 版本管理
  getVersions(id: number): Promise<any[]> {
    return http.get(`/script-templates/${id}/versions/`)
  },

  createVersion(id: number, data: { version: string; description?: string }): Promise<any> {
    return http.post(`/script-templates/${id}/create_version/`, data)
  },

  rollbackVersion(id: number, versionId: number): Promise<void> {
    return http.post(`/script-templates/${id}/rollback_version/`, { version_id: versionId })
  },

  toggleStatus(id: number): Promise<{ is_active: boolean }> {
    return http.post(`/script-templates/${id}/toggle_status/`)
  },

  // 获取可用于导入的模板（只返回启用的模板）
  getTemplatesForImport(params?: any): Promise<PaginatedResponse<ScriptTemplate>> {
    return http.get('/script-templates/for_import/', { params })
  },
}

// 作业模板API
export const jobTemplateApi = {
  // 获取作业模板列表
  getTemplates(params?: any): Promise<PaginatedResponse<JobTemplate>> {
    return http.get('/templates/templates/', { params })
  },
  
  // 获取可用标签
  getTags(): Promise<{ tags: string[] }> {
    return http.get('/templates/templates/tags/')
  },

  // 获取作业模板详情
  getTemplate(id: number): Promise<JobTemplate> {
    return http.get(`/templates/templates/${id}/`)
  },

  // 创建作业模板
  createTemplate(data: Partial<JobTemplate>): Promise<JobTemplate> {
    return http.post('/templates/templates/', data)
  },

  // 更新作业模板
  updateTemplate(id: number, data: Partial<JobTemplate>): Promise<JobTemplate> {
    return http.put(`/templates/templates/${id}/`, data)
  },

  // 删除作业模板
  deleteTemplate(id: number): Promise<void> {
    return http.delete(`/templates/templates/${id}/`)
  },

  // 复制作业模板
  copyTemplate(id: number): Promise<JobTemplate> {
    return http.post(`/templates/templates/${id}/copy/`)
  },

  // 调试作业模板
  debugTemplate(id: number, params?: any): Promise<{ execution_id: string; task_id: string; is_debug: boolean }> {
    return http.post(`/templates/templates/${id}/debug/`, params)
  },

  // 获取同步预览
  getSyncPreview(id: number): Promise<any> {
    return http.get(`/templates/templates/${id}/sync_preview/`)
  },

  // 同步执行方案
  syncPlans(id: number): Promise<void> {
    return http.post(`/templates/templates/${id}/sync_plans/`)
  },
}

// 执行计划API
export const executionPlanApi = {
  // 获取执行计划列表
  getPlans(params?: any): Promise<PaginatedResponse<ExecutionPlan>> {
    return http.get('/templates/plans/', { params })
  },

  // 获取执行计划详情
  getPlan(id: number): Promise<ExecutionPlan> {
    return http.get(`/templates/plans/${id}/`)
  },

  // 创建执行计划
  createPlan(data: any): Promise<ExecutionPlan> {
    return http.post('/templates/plans/', data)
  },

  // 更新执行计划
  updatePlan(id: number, data: Partial<ExecutionPlan>): Promise<ExecutionPlan> {
    return http.put(`/templates/plans/${id}/`, data)
  },

  // 删除执行计划
  deletePlan(id: number): Promise<void> {
    return http.delete(`/templates/plans/${id}/`)
  },

  // 获取执行计划步骤
  getPlanSteps(id: number): Promise<any[]> {
    return http.get(`/templates/plans/${id}/steps/`)
  },

  // 执行计划
  executePlan(id: number, params?: any): Promise<{ execution_id: string; execution_record_id: number; task_id: string }> {
    return http.post(`/templates/plans/${id}/execute/`, params)
  },

  // 同步计划
  syncPlan(id: number): Promise<void> {
    return http.post(`/templates/plans/${id}/sync/`)
  },

  // 获取同步状态详情
  getSyncStatusDetail(id: number): Promise<any> {
    return http.get(`/templates/plans/${id}/sync_status_detail/`)
  },
}

// 执行记录API
export const executionRecordApi = {
  // 获取执行记录列表
  getRecords(params?: any): Promise<PaginatedResponse<ExecutionRecord>> {
    return http.get('/executor/execution-records/', { params })
  },

  // 获取执行记录详情
  getRecord(id: number): Promise<ExecutionRecord> {
    return http.get(`/executor/execution-records/${id}/`)
  },

  // 取消执行
  cancelExecution(id: number): Promise<void> {
    return http.post(`/executor/execution-records/${id}/cancel/`)
  },

  // 重试执行
  retryExecution(id: number): Promise<{ execution_id: string; execution_record_id: number; task_id: string; celery_task_id: string; message: string }> {
    return http.post(`/executor/execution-records/${id}/retry/`)
  },

  // 获取重试历史
  getRetryHistory(id: number): Promise<{ content: ExecutionRecord[] }> {
    return http.get(`/executor/execution-records/${id}/retry_history/`)
  },

  // 步骤原地重试
  retryStepInplace(id: number, stepId: string, retryType: 'failed_only' | 'all'): Promise<any> {
    return http.post(`/executor/execution-records/${id}/retry_step_inplace/`, {
      step_id: stepId,
      retry_type: retryType
    })
  },

  // 忽略步骤错误继续执行
  ignoreStepError(id: number, stepId: string): Promise<any> {
    return http.post(`/executor/execution-records/${id}/ignore_step_error/`, {
      step_id: stepId
    })
  },

  // 继续执行流程
  continueExecution(id: number, stepId: string): Promise<any> {
    return http.post(`/executor/execution-records/${id}/continue_execution/`, {
      step_id: stepId
    })
  },
}

// 定时任务API
export const scheduledTaskApi = {
  // 获取定时任务列表
  getTasks(params?: any): Promise<PaginatedResponse<ScheduledTask>> {
    return http.get('/scheduled-tasks/', { params })
  },

  // 获取定时任务详情
  getTask(id: number): Promise<ScheduledTask> {
    return http.get(`/scheduled-tasks/${id}/`)
  },

  // 创建定时任务
  createTask(data: Partial<ScheduledTask>): Promise<ScheduledTask> {
    return http.post('/scheduled-tasks/', data)
  },

  // 更新定时任务
  updateTask(id: number, data: Partial<ScheduledTask>): Promise<ScheduledTask> {
    return http.put(`/scheduled-tasks/${id}/`, data)
  },

  // 删除定时任务
  deleteTask(id: number): Promise<void> {
    return http.delete(`/scheduled-tasks/${id}/`)
  },

  // 启用任务
  enableTask(id: number): Promise<void> {
    return http.post(`/scheduled-tasks/${id}/enable/`)
  },

  // 禁用任务
  disableTask(id: number): Promise<void> {
    return http.post(`/scheduled-tasks/${id}/disable/`)
  }
}

// 快速执行API
export const quickExecuteApi = {
  // 快速执行脚本
  execute(data: {
    target_host_ids: number[]
    script_content: string
    script_type: string
    timeout?: number
    ignore_error?: boolean
    use_fabric?: boolean
    global_variables?: Record<string, any>
    positional_args?: string[]
    execution_mode?: 'parallel' | 'serial' | 'rolling'
    rolling_batch_size?: number
    rolling_batch_delay?: number
  }): Promise<{ execution_id: string; execution_record_id: number; task_id: string }> {
    return http.post('/quick/execute_script/', data)
  },

  // 快速文件传输
  transferFile(data: {
    name?: string
    transfer_type: 'local_upload' | 'server_upload'
    local_path: string
    remote_path: string
    overwrite_policy?: 'overwrite' | 'skip' | 'backup' | 'fail'
    timeout?: number
    bandwidth_limit?: number | null
    execution_mode?: 'parallel' | 'serial' | 'rolling'
    rolling_strategy?: 'fail_pause' | 'ignore_error'
    rolling_batch_size?: number
    rolling_batch_delay?: number
    source_server_host?: string
    source_server_user?: string
    source_server_path?: string
    targets: Array<{ type: 'host' | 'group'; id: number }>
  }): Promise<{ execution_id: string; execution_record_id: number; task_id: string }> {
    return http.post('/quick/transfer_file/', data)
  },
}

// 实时监控API
export const realtimeApi = {
  // 获取任务状态
  getTaskStatus(taskId: string): Promise<any> {
    return http.get(`/realtime/${taskId}/status/`)
  },

  // 获取任务日志
  getTaskLogs(taskId: string, params?: any): Promise<any> {
    return http.get(`/realtime/${taskId}/logs/`, { params })
  },
}

// 审计日志API
export const auditLogApi = {
  // 获取审计日志列表
  getAuditLogs(params?: any): Promise<PaginatedResponse<any>> {
    return http.get('/permissions/audit-logs/', { params })
  },

  // 获取审计日志详情
  getAuditLog(id: number): Promise<any> {
    return http.get(`/permissions/audit-logs/${id}/`)
  },

  // 导出审计日志
  exportAuditLogs(params?: any): Promise<Blob> {
    return http.get('/permissions/audit-logs/export/', { 
      params,
      responseType: 'blob'
    })
  },
}
