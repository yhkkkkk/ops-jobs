import type { MockRoute } from './mockAdapter'

const iso = (daysOffset = 0, hour = 9) => {
  const date = new Date()
  date.setDate(date.getDate() + daysOffset)
  date.setHours(hour, 12, 0, 0)
  return date.toISOString()
}

const makeToken = (subject: string) => {
  const header = btoa(JSON.stringify({ alg: 'none', typ: 'JWT' }))
  const payload = btoa(JSON.stringify({
    sub: subject,
    exp: Math.floor(Date.now() / 1000) + 60 * 60 * 8,
  }))
  return `${header}.${payload}.mock`
}

const mockUser = {
  id: 1,
  username: 'demo-admin',
  email: 'demo-admin@example.com',
  first_name: 'Demo',
  last_name: 'Admin',
  is_staff: true,
  is_superuser: true,
  profile: {
    display_name: '演示管理员',
  },
}

const hosts = [
  {
    id: 1,
    name: 'prod-gateway-01',
    ip_address: '10.8.12.21',
    internal_ip: '10.8.12.21',
    port: 22,
    os_type: 'linux',
    os_type_display: 'Linux',
    status: 'online',
    status_display: '在线',
    service_role: 'gateway',
    owner: 'SRE',
    department: '平台工程',
    cpu_cores: 8,
    memory_gb: 32,
    disk_gb: 500,
    tags: [{ key: 'env', value: 'prod' }],
    created_at: iso(-40),
    updated_at: iso(-1),
  },
  {
    id: 2,
    name: 'prod-worker-03',
    ip_address: '10.8.18.33',
    internal_ip: '10.8.18.33',
    port: 22,
    os_type: 'linux',
    os_type_display: 'Linux',
    status: 'offline',
    status_display: '离线',
    service_role: 'worker',
    owner: 'SRE',
    department: '平台工程',
    cpu_cores: 16,
    memory_gb: 64,
    disk_gb: 1000,
    tags: [{ key: 'env', value: 'prod' }],
    created_at: iso(-35),
    updated_at: iso(-2),
  },
  {
    id: 3,
    name: 'staging-runner-02',
    ip_address: '10.9.4.17',
    internal_ip: '10.9.4.17',
    port: 22,
    os_type: 'linux',
    os_type_display: 'Linux',
    status: 'online',
    status_display: '在线',
    service_role: 'runner',
    owner: 'DevOps',
    department: '研发效能',
    cpu_cores: 4,
    memory_gb: 16,
    disk_gb: 200,
    tags: [{ key: 'env', value: 'staging' }],
    created_at: iso(-24),
    updated_at: iso(0),
  },
]

const scriptTemplates = [
  {
    id: 101,
    name: 'Nginx 配置热加载检查',
    description: '检查配置语法并执行 reload。',
    script_type: 'shell',
    category: 'web',
    tag_list: [{ key: 'service', value: 'nginx' }],
    is_active: true,
    usage_count: 48,
    created_by_name: '平台工程',
    created_at: iso(-50),
    updated_at: iso(-2),
  },
  {
    id: 102,
    name: '磁盘水位清理',
    description: '清理临时目录和过期日志。',
    script_type: 'shell',
    category: 'capacity',
    tag_list: [{ key: 'risk', value: 'low' }],
    is_active: true,
    usage_count: 72,
    created_by_name: 'SRE',
    created_at: iso(-44),
    updated_at: iso(-1),
  },
]

const jobTemplates = [
  {
    id: 201,
    name: '发布前主机健康检查',
    description: 'CPU、内存、磁盘、Agent 心跳的发布前检查。',
    category: 'release',
    tags: [{ key: 'env', value: 'prod' }],
    step_count: 4,
    plan_count: 3,
    has_unsync_plans: false,
    created_by: 1,
    created_by_name: '平台工程',
    created_at: iso(-31),
    updated_at: iso(-2),
  },
  {
    id: 202,
    name: '日志归档与压缩',
    description: '按目录策略归档大日志并回写执行摘要。',
    category: 'maintenance',
    tags: [{ key: 'window', value: 'nightly' }],
    step_count: 3,
    plan_count: 2,
    has_unsync_plans: true,
    created_by: 1,
    created_by_name: 'SRE',
    created_at: iso(-29),
    updated_at: iso(-1),
  },
]

const executionPlans = [
  {
    id: 301,
    name: '生产网关发布前检查',
    description: '覆盖生产网关节点。',
    job_template: 201,
    job_template_name: '发布前主机健康检查',
    target_count: 18,
    is_active: true,
    created_by_name: '平台工程',
    updated_at: iso(-1),
  },
  {
    id: 302,
    name: '夜间日志归档',
    description: '每天 01:00 执行。',
    job_template: 202,
    job_template_name: '日志归档与压缩',
    target_count: 42,
    is_active: true,
    created_by_name: 'SRE',
    updated_at: iso(-3),
  },
]

const executionRecords = [
  {
    id: 9001,
    execution_id: 'exec-mock-9001',
    name: '生产网关发布前检查',
    execution_type: 'job_workflow',
    execution_type_display: 'Job工作流',
    job_name: '生产网关发布前检查',
    status: 'success',
    status_display: '成功',
    started_at: iso(0, 10),
    finished_at: iso(0, 10),
    created_at: iso(0, 9),
    start_time: iso(0, 10),
    end_time: iso(0, 10),
    duration: 48,
    executed_by_name: 'demo-admin',
    created_by_name: 'demo-admin',
    total_retry_count: 0,
    has_retries: false,
  },
  {
    id: 9002,
    execution_id: 'exec-mock-9002',
    name: '夜间日志归档',
    execution_type: 'scheduled_job',
    execution_type_display: '定时作业',
    job_name: '夜间日志归档',
    status: 'running',
    status_display: '运行中',
    started_at: iso(0, 9),
    finished_at: null,
    created_at: iso(0, 8),
    start_time: iso(0, 9),
    end_time: null,
    duration: null,
    executed_by_name: 'scheduler',
    created_by_name: 'scheduler',
    total_retry_count: 0,
    has_retries: false,
  },
  {
    id: 9003,
    execution_id: 'exec-mock-9003',
    name: '磁盘水位清理',
    execution_type: 'quick_script',
    execution_type_display: '快速脚本执行',
    job_name: '磁盘水位清理',
    status: 'failed',
    status_display: '失败',
    started_at: iso(-1, 23),
    finished_at: iso(-1, 23),
    created_at: iso(-1, 23),
    start_time: iso(-1, 23),
    end_time: iso(-1, 23),
    duration: 93,
    executed_by_name: 'demo-admin',
    created_by_name: 'demo-admin',
    total_retry_count: 1,
    has_retries: true,
  },
]

const agents = [
  {
    id: 1,
    host: {
      id: 1,
      name: 'prod-gateway-01',
      ip_address: '10.8.12.21',
      status: 'online',
      status_display: '在线',
      os_type: 'linux',
      os_type_display: 'Linux',
      service_role: 'gateway',
    },
    status: 'online',
    status_display: '在线',
    agent_type: 'agent',
    agent_type_display: 'Agent',
    version: '1.4.2',
    endpoint: 'http://10.8.12.21:9100',
    agent_server_id: 1,
    last_heartbeat_at: iso(0, 10),
    last_error_code: '',
    created_at: iso(-20),
    updated_at: iso(0),
  },
  {
    id: 2,
    host: {
      id: 2,
      name: 'prod-worker-03',
      ip_address: '10.8.18.33',
      status: 'offline',
      status_display: '离线',
      os_type: 'linux',
      os_type_display: 'Linux',
      service_role: 'worker',
    },
    status: 'offline',
    status_display: '离线',
    agent_type: 'agent',
    agent_type_display: 'Agent',
    version: '1.3.9',
    endpoint: 'http://10.8.18.33:9100',
    agent_server_id: 1,
    last_heartbeat_at: iso(-1, 18),
    last_error_code: 'heartbeat_timeout',
    created_at: iso(-18),
    updated_at: iso(-1),
  },
]

const scheduledTasks = [
  {
    id: 701,
    name: '夜间日志归档',
    execution_plan: 302,
    execution_plan_name: '夜间日志归档',
    cron_expression: '0 1 * * *',
    is_active: true,
    next_run_time: iso(1, 1),
    created_at: iso(-14),
    updated_at: iso(-1),
  },
  {
    id: 702,
    name: '每日主机健康巡检',
    execution_plan: 301,
    execution_plan_name: '生产网关发布前检查',
    cron_expression: '30 8 * * *',
    is_active: true,
    next_run_time: iso(1, 8),
    created_at: iso(-12),
    updated_at: iso(-1),
  },
]

const agentServers = [
  {
    id: 1,
    name: 'control-plane-a',
    base_url: 'http://127.0.0.1:9001',
    is_active: true,
    description: '主控制面节点',
    has_secret: true,
    require_signature: true,
  },
]

const serverAccounts = [
  {
    id: 1,
    name: '生产只读账号',
    username: 'ops_readonly',
    auth_type: 'key',
    has_password: false,
    has_private_key: true,
    description: '用于生产巡检和只读命令执行',
    created_by_name: '平台工程',
    updated_by_name: '平台工程',
    created_at: iso(-21),
    updated_at: iso(-2),
  },
  {
    id: 2,
    name: '预发维护账号',
    username: 'deploy',
    auth_type: 'both',
    has_password: true,
    has_private_key: true,
    description: '预发环境发布和维护操作',
    created_by_name: 'SRE',
    updated_by_name: 'SRE',
    created_at: iso(-18),
    updated_at: iso(-1),
  },
]

const systemConfigs = [
  {
    id: 1,
    key: 'fabric_max_concurrent_hosts',
    value: 50,
    description: 'Fabric 并发主机数',
    category: 'task',
    category_display: '任务执行',
    is_active: true,
    created_at: iso(-30),
    updated_at: iso(-1),
    updated_by_name: '平台工程',
  },
  {
    id: 2,
    key: 'offline_threshold_seconds',
    value: 90,
    description: 'Agent 离线判定阈值',
    category: 'agent',
    category_display: 'Agent',
    is_active: true,
    created_at: iso(-30),
    updated_at: iso(-1),
    updated_by_name: 'SRE',
  },
]

const agentPackages = [
  {
    id: 1,
    package_type: 'agent',
    package_type_display: 'Agent',
    version: '1.4.2',
    description: '稳定版 Agent 安装包',
    os_type: 'linux',
    os_type_display: 'Linux',
    arch: 'amd64',
    arch_display: 'amd64',
    file: '/mock/packages/agent-linux-amd64.tar.gz',
    file_name: 'agent-linux-amd64.tar.gz',
    file_size: 18_432_000,
    md5_hash: 'mock-md5-agent',
    sha256_hash: 'mock-sha256-agent',
    download_url: '/mock/packages/agent-linux-amd64.tar.gz',
    storage_type: 'local',
    is_default: true,
    is_active: true,
    created_by: 1,
    created_by_name: '平台工程',
    created_at: iso(-10),
    updated_at: iso(-1),
  },
  {
    id: 2,
    package_type: 'agent-server',
    package_type_display: 'Agent Server',
    version: '1.4.2',
    description: '控制面 Agent Server 安装包',
    os_type: 'linux',
    os_type_display: 'Linux',
    arch: 'amd64',
    arch_display: 'amd64',
    file: '/mock/packages/agent-server-linux-amd64.tar.gz',
    file_name: 'agent-server-linux-amd64.tar.gz',
    file_size: 26_214_400,
    md5_hash: 'mock-md5-agent-server',
    sha256_hash: 'mock-sha256-agent-server',
    download_url: '/mock/packages/agent-server-linux-amd64.tar.gz',
    storage_type: 'local',
    is_default: true,
    is_active: true,
    created_by: 1,
    created_by_name: '平台工程',
    created_at: iso(-10),
    updated_at: iso(-1),
  },
]

const installRecords = [
  {
    id: 1,
    install_task_id: 'install-mock-001',
    install_type: 'agent',
    status: 'success',
    status_display: '成功',
    total: 2,
    success_count: 2,
    failed_count: 0,
    created_at: iso(-1, 15),
  },
]

const paginate = <T>(items: T[], query: Record<string, any>) => {
  const page = Number(query.page || 1)
  const pageSize = Number(query.page_size || query.pageSize || 10)
  const search = String(query.search || '').trim().toLowerCase()
  const filtered = search
    ? items.filter((item: any) => JSON.stringify(item).toLowerCase().includes(search))
    : items

  return {
    total: filtered.length,
    page,
    page_size: pageSize,
    results: filtered.slice((page - 1) * pageSize, page * pageSize),
  }
}

const byId = <T extends { id: number }>(items: T[], id: string) => {
  return items.find((item) => item.id === Number(id)) || items[0]
}

const latencyTrend = (range: string) => {
  const length = range === '30d' ? 30 : 7
  return Array.from({ length }, (_, index) => {
    const offset = index - length + 1
    const base = 180 + index * 7
    return {
      ts: iso(offset).slice(0, 10),
      p50: base,
      p95: base + 210 + (index % 3) * 28,
    }
  })
}

const permissionMap = (permissions: string[]) => {
  return permissions.reduce<Record<string, boolean>>((acc, permission) => {
    acc[permission] = true
    return acc
  }, {})
}

export const mockRoutes: MockRoute[] = [
  {
    method: 'get',
    pattern: '/auth/users/auth_config/',
    handler: () => ({ captcha_enabled: false, ldap_enabled: false, two_factor_enabled: false }),
  },
  {
    method: 'get',
    pattern: '/captcha/',
    handler: () => ({ enabled: false }),
  },
  {
    method: 'post',
    pattern: '/auth/check-2fa/',
    handler: () => ({ requires_2fa: false }),
  },
  {
    method: 'get',
    pattern: '/auth/2fa/setup/',
    handler: () => ({
      secret: 'MOCK2FASECRET',
      qr_code: '',
      config_url: 'otpauth://totp/OpsJob:demo-admin?secret=MOCK2FASECRET&issuer=OpsJob',
    }),
  },
  {
    method: 'post',
    pattern: '/auth/2fa/verify/',
    handler: () => ({ backup_tokens: ['mock-backup-1', 'mock-backup-2'] }),
  },
  {
    method: 'get',
    pattern: '/auth/2fa/status/',
    handler: () => ({ enabled: false, device_count: 0 }),
  },
  {
    method: 'post',
    pattern: '/auth/2fa/disable/',
    handler: () => ({ ok: true }),
  },
  {
    method: 'post',
    pattern: '/auth/login/',
    handler: ({ data }) => ({
      access_token: makeToken(data?.username || 'demo-admin'),
      refresh_token: makeToken('refresh'),
      user: {
        ...mockUser,
        username: data?.username || mockUser.username,
      },
    }),
  },
  {
    method: 'post',
    pattern: '/auth/logout/',
    handler: () => ({ ok: true }),
  },
  {
    method: 'post',
    pattern: '/auth/refresh/',
    handler: () => ({ access_token: makeToken('demo-admin'), refresh_token: makeToken('refresh') }),
  },
  {
    method: 'get',
    pattern: '/auth/users/profile/',
    handler: () => mockUser,
  },
  {
    method: 'get',
    pattern: '/auth/users/',
    handler: () => [mockUser],
  },
  {
    method: 'get',
    pattern: '/permissions/user-permissions/',
    handler: () => ({
      user_id: mockUser.id,
      username: mockUser.username,
      is_superuser: true,
      is_staff: true,
      permission_count: 24,
      permissions: ['view', 'add', 'change', 'delete', 'execute'],
    }),
  },
  {
    method: 'get',
    pattern: '/system/configs/',
    handler: ({ query }) => paginate(systemConfigs, query),
  },
  {
    method: 'post',
    pattern: '/system/configs/',
    handler: ({ data }) => ({
      id: 99,
      category_display: data?.category || '系统',
      is_active: true,
      created_at: iso(0),
      updated_at: iso(0),
      updated_by_name: 'demo-admin',
      ...data,
    }),
  },
  {
    method: 'get',
    pattern: '/system/configs/by_category/',
    handler: ({ query }) => ({
      category: query.category || 'task',
      configs: systemConfigs
        .filter((item) => !query.category || item.category === query.category)
        .reduce<Record<string, any>>((acc, item) => {
          acc[item.key] = item.value
          return acc
        }, {}),
    }),
  },
  {
    method: 'post',
    pattern: '/system/configs/batch_update/',
    handler: ({ data }) => data?.configs || [],
  },
  {
    method: 'get',
    pattern: '/system/configs/task_config/',
    handler: () => ({
      fabric_max_concurrent_hosts: 50,
      fabric_connection_timeout: 10,
      fabric_command_timeout: 300,
      fabric_enable_connection_pool: true,
    }),
  },
  {
    method: 'post',
    pattern: '/system/configs/update_task_config/',
    handler: ({ data }) => data,
  },
  {
    method: 'get',
    pattern: '/system/configs/notification_config/',
    handler: () => ({
      dingtalk_enabled: false,
      dingtalk_webhook: '',
      dingtalk_keyword: 'ops-job',
      feishu_enabled: false,
      feishu_webhook: '',
      feishu_keyword: 'ops-job',
      wechatwork_enabled: false,
      wechatwork_webhook: '',
      wechatwork_keyword: 'ops-job',
      levels: ['error', 'warning'],
    }),
  },
  {
    method: 'post',
    pattern: '/system/configs/update_notification_config/',
    handler: ({ data }) => data,
  },
  {
    method: 'get',
    pattern: '/system/configs/agent_config/',
    handler: () => ({
      offline_threshold_seconds: 90,
      offline_threshold_by_env: { prod: 90, staging: 180 },
    }),
  },
  {
    method: 'post',
    pattern: '/system/configs/update_agent_config/',
    handler: ({ data }) => data,
  },
  {
    method: 'get',
    pattern: '/system/configs/:id/',
    handler: ({ params }) => byId(systemConfigs, params.id),
  },
  {
    method: 'put',
    pattern: '/system/configs/:id/',
    handler: ({ params, data }) => ({ ...byId(systemConfigs, params.id), ...data, updated_at: iso(0) }),
  },
  {
    method: 'delete',
    pattern: '/system/configs/:id/',
    handler: () => ({ ok: true }),
  },
  {
    method: 'post',
    pattern: '/permissions/user-permissions/',
    handler: ({ data }) => ({
      user_id: mockUser.id,
      username: mockUser.username,
      permissions: permissionMap(data?.permissions || []),
    }),
  },
  {
    method: 'post',
    pattern: '/permissions/check/',
    handler: ({ data }) => ({
      user_id: mockUser.id,
      username: mockUser.username,
      resource_type: data?.resource_type,
      resource_id: data?.resource_id || null,
      permissions: permissionMap(data?.permissions || ['view']),
    }),
  },
  {
    method: 'post',
    pattern: '/permissions/resource-permissions/',
    handler: ({ data }) => ({
      user_id: mockUser.id,
      username: mockUser.username,
      resource_type: data?.resource_type,
      level: 'object',
      permissions: (data?.resource_ids || []).reduce((acc: Record<string, any>, id: number) => {
        acc[String(id)] = permissionMap(data?.permissions || ['view', 'change', 'delete'])
        return acc
      }, {}),
    }),
  },
  {
    method: 'get',
    pattern: '/dashboard/overview/',
    handler: () => ({
      resources: {
        job_templates: { total: jobTemplates.length },
        execution_plans: { total: executionPlans.length },
        hosts: { total: hosts.length, online: hosts.filter((host) => host.status === 'online').length },
      },
      scheduled_overview: {
        total: scheduledTasks.length,
        active: scheduledTasks.filter((task) => task.is_active).length,
      },
    }),
  },
  {
    method: 'get',
    pattern: '/dashboard/recent_activities/',
    handler: () => ({
      activities: executionRecords.map((record) => ({
        id: record.id,
        type: 'execution',
        description: record.job_name,
        status: record.status,
        created_at: record.start_time,
      })),
    }),
  },
  {
    method: 'get',
    pattern: '/dashboard/execution_plans/',
    handler: () => executionPlans,
  },
  {
    method: 'get',
    pattern: '/dashboard/ops_overview/',
    handler: () => ({
      agents_total: agents.length,
      agents_online: agents.filter((agent) => agent.status === 'online').length,
      agents_offline: agents.filter((agent) => agent.status === 'offline').length,
      agents_pending: 1,
      agents_disabled: 0,
      running_tasks: executionRecords.filter((record) => record.status === 'RUNNING').length,
      fail_rate_24h: 3.8,
      task_p50_ms: 210,
      task_p95_ms: 520,
      task_p99_ms: 930,
      heartbeat_alerts: 1,
      top_failure_hosts: [
        { host_name: 'prod-worker-03', fail_count: 4, last_failed_at: iso(-1, 23) },
        { host_name: 'staging-runner-02', fail_count: 2, last_failed_at: iso(-2, 16) },
      ],
      last_updated: iso(0, 10),
    }),
  },
  {
    method: 'get',
    pattern: '/dashboard/ops_latency_trend/',
    handler: ({ query }) => latencyTrend(query.time_range || '7d'),
  },
  {
    method: 'get',
    pattern: '/hosts/hosts/',
    handler: ({ query }) => paginate(hosts, query),
  },
  {
    method: 'get',
    pattern: '/hosts/hosts/tags/',
    handler: () => ({ tags: ['env:prod', 'env:staging', 'service:gateway'] }),
  },
  {
    method: 'get',
    pattern: '/hosts/accounts/',
    handler: ({ query }) => paginate(serverAccounts, query),
  },
  {
    method: 'post',
    pattern: '/hosts/accounts/',
    handler: ({ data }) => ({ id: 99, ...data, created_at: iso(0), updated_at: iso(0) }),
  },
  {
    method: 'get',
    pattern: '/hosts/accounts/:id/',
    handler: ({ params }) => byId(serverAccounts, params.id),
  },
  {
    method: 'put',
    pattern: '/hosts/accounts/:id/',
    handler: ({ params, data }) => ({ ...byId(serverAccounts, params.id), ...data, updated_at: iso(0) }),
  },
  {
    method: 'delete',
    pattern: '/hosts/accounts/:id/',
    handler: () => ({ ok: true }),
  },
  {
    method: 'get',
    pattern: '/hosts/hosts/:id/',
    handler: ({ params }) => byId(hosts, params.id),
  },
  {
    method: 'get',
    pattern: '/hosts/groups/',
    handler: ({ query }) => paginate([
      { id: 1, name: '生产环境', host_count: 2, online_count: 1, offline_count: 1, created_at: iso(-20), updated_at: iso(-1) },
      { id: 2, name: '预发环境', host_count: 1, online_count: 1, offline_count: 0, created_at: iso(-18), updated_at: iso(-1) },
    ], query),
  },
  {
    method: 'post',
    pattern: '/hosts/groups/',
    handler: ({ data }) => ({ id: 99, host_count: 0, online_count: 0, offline_count: 0, created_at: iso(0), updated_at: iso(0), ...data }),
  },
  {
    method: 'get',
    pattern: '/hosts/groups/simple_list/',
    handler: () => [{ id: 1, name: '生产环境' }, { id: 2, name: '预发环境' }],
  },
  {
    method: 'get',
    pattern: '/hosts/groups/tree/',
    handler: () => [
      {
        id: 1,
        name: '生产环境',
        host_count: 2,
        online_count: 1,
        offline_count: 1,
        children: [
          {
            id: 2,
            name: '预发环境',
            host_count: 1,
            online_count: 1,
            offline_count: 0,
            children: [],
          },
        ],
      },
    ],
  },
  {
    method: 'get',
    pattern: '/hosts/groups/:id/',
    handler: ({ params }) => ({ id: Number(params.id), name: params.id === '1' ? '生产环境' : '预发环境', host_count: 2, online_count: 1, offline_count: 1 }),
  },
  {
    method: 'put',
    pattern: '/hosts/groups/:id/',
    handler: ({ params, data }) => ({ id: Number(params.id), ...data, updated_at: iso(0) }),
  },
  {
    method: 'delete',
    pattern: '/hosts/groups/:id/',
    handler: () => ({ ok: true }),
  },
  {
    method: 'get',
    pattern: '/script-templates/',
    handler: ({ query }) => paginate(scriptTemplates, query),
  },
  {
    method: 'post',
    pattern: '/script-templates/',
    handler: ({ data }) => ({ id: 199, usage_count: 0, is_active: true, created_at: iso(0), updated_at: iso(0), ...data }),
  },
  {
    method: 'get',
    pattern: '/script-templates/for_import/',
    handler: ({ query }) => paginate(scriptTemplates, query),
  },
  {
    method: 'get',
    pattern: '/script-templates/tags/',
    handler: () => ({ tags: ['service:nginx', 'risk:low'] }),
  },
  {
    method: 'get',
    pattern: '/script-templates/:id/',
    handler: ({ params }) => byId(scriptTemplates, params.id),
  },
  {
    method: 'put',
    pattern: '/script-templates/:id/',
    handler: ({ params, data }) => ({ ...byId(scriptTemplates, params.id), ...data, updated_at: iso(0) }),
  },
  {
    method: 'delete',
    pattern: '/script-templates/:id/',
    handler: () => ({ ok: true }),
  },
  {
    method: 'get',
    pattern: '/script-templates/:id/versions/',
    handler: ({ params }) => [{ id: 1, template: Number(params.id), version: 1, created_at: iso(-1), created_by_name: 'demo-admin' }],
  },
  {
    method: 'get',
    pattern: '/script-templates/:id/references/',
    handler: () => ({ job_templates: [], execution_plans: [] }),
  },
  {
    method: 'get',
    pattern: '/script-templates/favorites/',
    handler: ({ query }) => paginate([
      { id: 1, favorite_type: 'job_template', favorite_type_display: '作业模板', object_id: 201, object_name: '发布前主机健康检查' },
      { id: 2, favorite_type: 'execution_plan', favorite_type_display: '执行方案', object_id: 301, object_name: '生产网关发布前检查' },
      { id: 3, favorite_type: 'script_template', favorite_type_display: '脚本模板', object_id: 102, object_name: '磁盘水位清理' },
    ], query),
  },
  {
    method: 'get',
    pattern: '/script-templates/favorites/check/',
    handler: () => ({ is_favorite: true }),
  },
  {
    method: 'get',
    pattern: '/script-templates/favorites/by-category/',
    handler: () => ({ personal: [], team: [], common: [] }),
  },
  {
    method: 'get',
    pattern: '/job-templates/templates/',
    handler: ({ query }) => paginate(jobTemplates, query),
  },
  {
    method: 'post',
    pattern: '/job-templates/templates/',
    handler: ({ data }) => ({ id: 299, step_count: data?.steps?.length || 0, plan_count: 0, has_unsync_plans: false, created_at: iso(0), updated_at: iso(0), ...data }),
  },
  {
    method: 'get',
    pattern: '/job-templates/templates/tags/',
    handler: () => ({ tags: ['env:prod', 'window:nightly'] }),
  },
  {
    method: 'get',
    pattern: '/job-templates/templates/:id/',
    handler: ({ params }) => byId(jobTemplates, params.id),
  },
  {
    method: 'put',
    pattern: '/job-templates/templates/:id/',
    handler: ({ params, data }) => ({ ...byId(jobTemplates, params.id), ...data, updated_at: iso(0) }),
  },
  {
    method: 'delete',
    pattern: '/job-templates/templates/:id/',
    handler: () => ({ ok: true }),
  },
  {
    method: 'get',
    pattern: '/job-templates/templates/:id/references/',
    handler: () => ({ execution_plans: executionPlans }),
  },
  {
    method: 'get',
    pattern: '/job-templates/plans/',
    handler: ({ query }) => paginate(executionPlans, query),
  },
  {
    method: 'post',
    pattern: '/job-templates/plans/',
    handler: ({ data }) => ({ id: 399, target_count: data?.targets?.length || 0, is_active: true, created_at: iso(0), updated_at: iso(0), ...data }),
  },
  {
    method: 'get',
    pattern: '/job-templates/plans/:id/',
    handler: ({ params }) => byId(executionPlans, params.id),
  },
  {
    method: 'put',
    pattern: '/job-templates/plans/:id/',
    handler: ({ params, data }) => ({ ...byId(executionPlans, params.id), ...data, updated_at: iso(0) }),
  },
  {
    method: 'delete',
    pattern: '/job-templates/plans/:id/',
    handler: () => ({ ok: true }),
  },
  {
    method: 'get',
    pattern: '/job-templates/plans/:id/references/',
    handler: () => ({ scheduled_tasks: scheduledTasks, execution_records: executionRecords }),
  },
  {
    method: 'get',
    pattern: '/job-templates/plans/:id/steps/',
    handler: () => [
      { id: 1, name: '检查 Agent 心跳', order: 1, script_template_name: 'Nginx 配置热加载检查' },
      { id: 2, name: '执行健康检查', order: 2, script_template_name: '磁盘水位清理' },
    ],
  },
  {
    method: 'get',
    pattern: '/job-templates/plans/:id/sync_status_detail/',
    handler: () => ({ synced: true, unsynced_steps: [], last_synced_at: iso(-1) }),
  },
  {
    method: 'get',
    pattern: '/scheduled-tasks/',
    handler: ({ query }) => paginate(scheduledTasks, query),
  },
  {
    method: 'post',
    pattern: '/scheduled-tasks/',
    handler: ({ data }) => ({ id: 799, is_active: true, created_at: iso(0), updated_at: iso(0), ...data }),
  },
  {
    method: 'get',
    pattern: '/scheduled-tasks/:id/',
    handler: ({ params }) => byId(scheduledTasks, params.id),
  },
  {
    method: 'put',
    pattern: '/scheduled-tasks/:id/',
    handler: ({ params, data }) => ({ ...byId(scheduledTasks, params.id), ...data, updated_at: iso(0) }),
  },
  {
    method: 'delete',
    pattern: '/scheduled-tasks/:id/',
    handler: () => ({ ok: true }),
  },
  {
    method: 'post',
    pattern: '/scheduled-tasks/:id/enable/',
    handler: ({ params }) => ({ id: Number(params.id), is_active: true }),
  },
  {
    method: 'post',
    pattern: '/scheduled-tasks/:id/disable/',
    handler: ({ params }) => ({ id: Number(params.id), is_active: false }),
  },
  {
    method: 'get',
    pattern: '/scheduler/scheduled-jobs/',
    handler: ({ query }) => paginate(scheduledTasks, query),
  },
  {
    method: 'post',
    pattern: '/scheduler/scheduled-jobs/',
    handler: ({ data }) => ({ id: 899, is_active: true, created_at: iso(0), updated_at: iso(0), ...data }),
  },
  {
    method: 'get',
    pattern: '/scheduler/scheduled-jobs/statistics/',
    handler: () => ({ total: scheduledTasks.length, active: scheduledTasks.length, paused: 0 }),
  },
  {
    method: 'get',
    pattern: '/scheduler/scheduled-jobs/:id/',
    handler: ({ params }) => byId(scheduledTasks, params.id),
  },
  {
    method: 'put',
    pattern: '/scheduler/scheduled-jobs/:id/',
    handler: ({ params, data }) => ({ ...byId(scheduledTasks, params.id), ...data, updated_at: iso(0) }),
  },
  {
    method: 'patch',
    pattern: '/scheduler/scheduled-jobs/:id/',
    handler: ({ params, data }) => ({ ...byId(scheduledTasks, params.id), ...data, updated_at: iso(0) }),
  },
  {
    method: 'delete',
    pattern: '/scheduler/scheduled-jobs/:id/',
    handler: () => ({ ok: true }),
  },
  {
    method: 'post',
    pattern: '/scheduler/scheduled-jobs/:id/execute/',
    handler: ({ params }) => ({ id: Number(params.id), execution_id: 'exec-mock-scheduled', status: 'accepted' }),
  },
  {
    method: 'get',
    pattern: '/executor/execution-records/',
    handler: ({ query }) => paginate(executionRecords, query),
  },
  {
    method: 'get',
    pattern: '/executor/execution-records/:id/',
    handler: ({ params }) => byId(executionRecords, params.id),
  },
  {
    method: 'get',
    pattern: '/executor/execution-records/:id/trace/',
    handler: ({ params }) => ({
      execution_record_id: Number(params.id),
      steps: [
        { id: 1, name: '连接主机', status: 'SUCCESS', duration: 8 },
        { id: 2, name: '执行脚本', status: 'SUCCESS', duration: 32 },
      ],
    }),
  },
  {
    method: 'get',
    pattern: '/executor/execution-records/:id/steps/:stepId/content/',
    handler: ({ params }) => ({
      execution_record_id: Number(params.id),
      step_id: Number(params.stepId),
      content: 'echo "mock execution step"\nuname -a\ndf -h',
    }),
  },
  {
    method: 'get',
    pattern: '/executor/execution-records/:id/steps/:stepId/result/',
    handler: ({ params }) => ({
      execution_record_id: Number(params.id),
      step_id: Number(params.stepId),
      exit_code: 0,
      stdout: 'mock execution completed\nFilesystem      Size  Used Avail Use%\n/dev/vda1        80G   31G   49G  39%',
      stderr: '',
    }),
  },
  {
    method: 'get',
    pattern: '/executor/execution-records/:id/retry_history/',
    handler: () => ({ results: [], total: 0, page: 1, page_size: 10 }),
  },
  {
    method: 'get',
    pattern: '/executor/execution-records/:id/operation_logs/',
    handler: ({ query }) => paginate([
      { id: 1, action: 'view', operator_name: 'demo-admin', created_at: iso(0, 10) },
    ], query),
  },
  {
    method: 'get',
    pattern: '/executor/execution-records/:id/logs/',
    handler: ({ query }) => paginate([
      { id: 1, level: 'info', message: 'mock task accepted', timestamp: iso(0, 10) },
      { id: 2, level: 'info', message: 'mock task completed', timestamp: iso(0, 10) },
    ], query),
  },
  {
    method: 'get',
    pattern: '/realtime/:taskId/status/',
    handler: ({ params }) => ({
      task_id: params.taskId,
      status: 'SUCCESS',
      progress: 100,
      message: 'mock task completed',
    }),
  },
  {
    method: 'get',
    pattern: '/realtime/:taskId/logs/',
    handler: ({ params, query }) => ({
      task_id: params.taskId,
      since: query.since || 0,
      logs: [
        { ts: iso(0, 10), level: 'info', message: 'mock log stream connected' },
        { ts: iso(0, 10), level: 'info', message: 'mock task completed' },
      ],
    }),
  },
  {
    method: 'get',
    pattern: '/agents/',
    handler: ({ query }) => paginate(agents, query),
  },
  {
    method: 'get',
    pattern: '/agents/error_codes/',
    handler: () => ({ items: ['heartbeat_timeout', 'version_outdated'] }),
  },
  {
    method: 'get',
    pattern: '/agents/versions/',
    handler: () => ({ items: ['1.4.2', '1.3.9'] }),
  },
  {
    method: 'post',
    pattern: '/agents/generate_install_script/',
    handler: ({ data }) => ({
      scripts: {
        linux: (data?.host_ids || [1]).map((hostId: number) => ({
          host_id: hostId,
          host_name: byId(hosts, String(hostId)).name,
          host_ip: byId(hosts, String(hostId)).ip_address,
          script: 'curl -fsSL http://mock.local/install-agent.sh | bash',
          token: `mock-token-${hostId}`,
        })),
      },
      install_type: data?.install_type || 'agent',
      agent_server_url: data?.agent_server_url || 'http://127.0.0.1:9001',
    }),
  },
  {
    method: 'post',
    pattern: '/agents/batch_install/',
    handler: ({ data }) => ({
      results: (data?.host_ids || [1]).map((hostId: number) => ({
        host_id: hostId,
        host_name: byId(hosts, String(hostId)).name,
        success: true,
        message: 'mock install accepted',
      })),
      total: (data?.host_ids || [1]).length,
      success_count: (data?.host_ids || [1]).length,
      failed_count: 0,
      install_task_id: 'install-mock-accepted',
    }),
  },
  {
    method: 'get',
    pattern: '/agents/install_records/',
    handler: ({ query }) => paginate(installRecords, query),
  },
  {
    method: 'post',
    pattern: '/agents/retry_install_record/',
    handler: () => ({ install_task_id: 'install-mock-retry', total: 1, status: 'accepted' }),
  },
  {
    method: 'post',
    pattern: '/agents/batch_uninstall/',
    handler: ({ data }) => ({
      results: (data?.agent_ids || [1]).map((agentId: number) => ({
        agent_id: agentId,
        host_id: byId(agents, String(agentId)).host.id,
        host_name: byId(agents, String(agentId)).host.name,
        success: true,
        message: 'mock uninstall accepted',
      })),
      total: (data?.agent_ids || [1]).length,
      success_count: (data?.agent_ids || [1]).length,
      failed_count: 0,
      uninstall_task_id: 'uninstall-mock-accepted',
    }),
  },
  {
    method: 'get',
    pattern: '/agents/uninstall_records/',
    handler: ({ query }) => paginate([], query),
  },
  {
    method: 'get',
    pattern: '/agents/host_agent_status/',
    handler: () => ({
      hosts: hosts.map((host) => {
        const agent = agents.find((item) => item.host.id === host.id)
        return {
          id: host.id,
          name: host.name,
          ip_address: host.ip_address,
          agent_status: agent?.status || null,
          agent_type: agent?.agent_type || null,
          agent_type_display: agent?.agent_type_display || null,
          agent_id: agent?.id || null,
          agent_version: agent?.version || null,
          computed_status: agent?.status || null,
          computed_status_display: agent?.status_display || null,
          can_install: !agent,
        }
      }),
    }),
  },
  {
    method: 'get',
    pattern: '/agents/packages/versions/',
    handler: ({ query }) => agentPackages
      .filter((item) => !query.package_type || item.package_type === query.package_type)
      .map((item) => item.version),
  },
  {
    method: 'get',
    pattern: '/agents/packages/active_packages/',
    handler: ({ query }) => agentPackages.filter((item) => item.is_active && (!query.package_type || item.package_type === query.package_type)),
  },
  {
    method: 'get',
    pattern: '/agents/packages/default_packages/',
    handler: ({ query }) => agentPackages.filter((item) => item.is_default && (!query.package_type || item.package_type === query.package_type)),
  },
  {
    method: 'get',
    pattern: '/agents/packages/',
    handler: ({ query }) => paginate(agentPackages, query),
  },
  {
    method: 'post',
    pattern: '/agents/packages/',
    handler: () => ({ ...agentPackages[0], id: 99, version: 'mock-upload' }),
  },
  {
    method: 'get',
    pattern: '/agents/packages/:id/',
    handler: ({ params }) => byId(agentPackages, params.id),
  },
  {
    method: 'patch',
    pattern: '/agents/packages/:id/',
    handler: ({ params, data }) => ({ ...byId(agentPackages, params.id), ...data, updated_at: iso(0) }),
  },
  {
    method: 'delete',
    pattern: '/agents/packages/:id/',
    handler: () => ({ ok: true }),
  },
  {
    method: 'get',
    pattern: '/agents/:id/',
    handler: ({ params }) => byId(agents, params.id),
  },
  {
    method: 'get',
    pattern: '/agents/agent_servers/',
    handler: ({ query }) => paginate(agentServers, query),
  },
  {
    method: 'get',
    pattern: '/agents/download_urls/',
    handler: () => ({
      download_urls: {
        linux: { amd64: '/mock/agent-linux-amd64.tar.gz' },
        windows: { amd64: '/mock/agent-windows-amd64.zip' },
      },
      version: '1.4.2',
      base_url: '/mock/packages',
    }),
  },
  {
    method: 'get',
    pattern: '/agents/packages/',
    handler: ({ query }) => paginate([], query),
  },
  {
    method: 'get',
    pattern: '/permissions/audit-logs/',
    handler: ({ query }) => paginate([
      {
        id: 1,
        user_id: 1,
        user_name: 'demo-admin',
        user_full_name: '演示管理员',
        action: 'login',
        action_display: '登录',
        resource_name: '运维作业平台',
        resource_type: 'auth',
        resource_type_name: '认证',
        description: '用户登录作业平台',
        ip_address: '127.0.0.1',
        success: true,
        created_at: iso(0, 9),
      },
      {
        id: 2,
        user_id: 1,
        user_name: 'demo-admin',
        user_full_name: '演示管理员',
        action: 'execute',
        action_display: '执行',
        resource_name: '生产网关发布前检查',
        resource_type: 'execution_plan',
        resource_type_name: '执行方案',
        description: '发起执行方案：生产网关发布前检查',
        ip_address: '127.0.0.1',
        success: true,
        created_at: iso(0, 10),
      },
    ], query),
  },
  {
    method: 'post',
    pattern: '/quick/execute_script/',
    handler: () => ({ execution_id: 'exec-mock-new', execution_record_id: 9100, task_id: 'task-mock-9100' }),
  },
  {
    method: 'post',
    pattern: '/quick/transfer_file/',
    handler: () => ({ execution_id: 'exec-mock-file', execution_record_id: 9101, task_id: 'task-mock-9101' }),
  },
  {
    method: 'post',
    pattern: '/agents/artifacts/upload/',
    handler: () => ({ id: 1, name: 'mock-artifact.txt', url: '/mock/artifacts/mock-artifact.txt', size: 128 }),
  },
  {
    method: 'post',
    pattern: '/agents/:id/:action/',
    handler: ({ params }) => ({ id: Number(params.id), status: 'accepted', action: params.action }),
  },
  {
    method: 'post',
    pattern: '/agents/:action/',
    handler: ({ params }) => ({ status: 'accepted', action: params.action, count: 1 }),
  },
  {
    method: 'post',
    pattern: '/script-templates/favorites/toggle/',
    handler: () => ({ is_favorite: true }),
  },
  {
    method: 'any',
    pattern: '/hosts/hosts/:id/:action/',
    handler: ({ params }) => ({ id: Number(params.id), status: 'accepted', action: params.action }),
  },
  {
    method: 'any',
    pattern: '/job-templates/templates/:id/:action/',
    handler: ({ params }) => ({ id: Number(params.id), status: 'accepted', action: params.action }),
  },
  {
    method: 'any',
    pattern: '/job-templates/plans/:id/:action/',
    handler: ({ params }) => ({ id: Number(params.id), status: 'accepted', action: params.action }),
  },
  {
    method: 'any',
    pattern: '/executor/execution-records/:id/:action/',
    handler: ({ params }) => ({ id: Number(params.id), status: 'accepted', action: params.action }),
  },
]
