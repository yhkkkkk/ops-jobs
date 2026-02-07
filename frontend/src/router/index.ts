import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { Message } from '@arco-design/web-vue'
import type { RouteRecordRaw } from 'vue-router'
import NProgress from 'nprogress'
import '@/styles/nprogress.css'

// 配置 NProgress
NProgress.configure({
  showSpinner: false, // 不显示右上角的加载图标
  minimum: 0.2,       // 最小百分比
  speed: 500,         // 递增进度条的速度
  trickleSpeed: 200   // 自动递增间隔
})

// 路由配置
const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: {
      title: '登录',
      requiresAuth: false,
    },
  },
  {
    path: '/',
    name: 'Layout',
    component: () => import('@/views/Layout.vue'),
    redirect: '/dashboard',
    meta: {
      requiresAuth: true,
      platform: 'job', // 标记为作业平台
    },
    children: [
      {
        path: '/dashboard',
        name: 'Dashboard',
        component: () => import('@/views/dashboard/index.vue'),
        meta: {
          title: '仪表盘',
          icon: 'icon-dashboard',
        },
      },
      {
        path: '/hosts',
        name: 'Hosts',
        component: () => import('@/views/hosts/index.vue'),
        meta: {
          title: '主机管理',
          icon: 'icon-computer',
        },
      },
      {
        path: '/hosts/:id',
        name: 'HostDetail',
        component: () => import('@/views/hosts/detail.vue'),
        meta: {
          title: '主机详情',
          hideInMenu: true,
        },
      },
      {
        path: '/accounts',
        name: 'Accounts',
        component: () => import('@/views/accounts/index.vue'),
        meta: {
          title: '服务器账号',
          icon: 'icon-user',
        },
      },
      {
        path: '/script-templates',
        name: 'ScriptTemplates',
        component: () => import('@/views/script-templates/index.vue'),
        meta: {
          title: '脚本模板',
          icon: 'icon-code',
        },
      },
      {
        path: '/script-templates/create',
        name: 'ScriptTemplateCreate',
        component: () => import('@/views/script-templates/editor.vue'),
        meta: {
          title: '创建脚本模板',
          hideInMenu: true,
        },
      },
      {
        path: '/script-templates/:id/edit',
        name: 'ScriptTemplateEdit',
        component: () => import('@/views/script-templates/editor.vue'),
        meta: {
          title: '编辑脚本模板',
          hideInMenu: true,
        },
      },
      {
        path: '/script-templates/detail/:id',
        name: 'ScriptTemplateDetail',
        component: () => import('@/views/script-templates/detail.vue'),
        meta: {
          title: '脚本模板详情',
          hideInMenu: true,
        },
      },
      {
        path: '/script-templates/:id/versions',
        name: 'ScriptTemplateVersions',
        component: () => import('@/views/script-templates/versions.vue'),
        meta: {
          title: '脚本模板版本管理',
          hideInMenu: true,
        },
      },
      {
        path: '/job-templates',
        name: 'JobTemplates',
        component: () => import('@/views/job-templates/index.vue'),
        meta: {
          title: '作业模板',
          icon: 'icon-settings',
        },
      },
      {
        path: '/job-templates/create',
        name: 'JobTemplateCreate',
        component: () => import('@/views/job-templates/editor.vue'),
        meta: {
          title: '创建作业模板',
          hideInMenu: true,
        },
      },
      {
        path: '/job-templates/:id/edit',
        name: 'JobTemplateEdit',
        component: () => import('@/views/job-templates/editor.vue'),
        meta: {
          title: '编辑作业模板',
          hideInMenu: true,
        },
      },
      {
        path: '/job-templates/detail/:id',
        name: 'JobTemplateDetail',
        component: () => import('@/views/job-templates/detail.vue'),
        meta: {
          title: '作业模板详情',
          hideInMenu: true,
        },
      },
      {
        path: '/execution-plans',
        name: 'ExecutionPlans',
        component: () => import('@/views/execution-plans/index.vue'),
        meta: {
          title: '作业执行方案',
          icon: 'icon-calendar',
        },
      },
      {
        path: '/execution-plans/create',
        name: 'ExecutionPlanCreate',
        component: () => import('@/views/execution-plans/editor.vue'),
        meta: {
          title: '创建执行方案',
          hideInMenu: true,
        },
      },
      {
        path: '/execution-plans/detail/:id',
        name: 'ExecutionPlanDetail',
        component: () => import('@/views/execution-plans/detail.vue'),
        meta: {
          title: '执行方案详情',
          hideInMenu: true,
        },
      },
      {
        path: '/execution-plans/:id/edit',
        name: 'ExecutionPlanEdit',
        component: () => import('@/views/execution-plans/editor.vue'),
        meta: {
          title: '编辑执行方案',
          hideInMenu: true,
        },
      },
      {
        path: '/execution-plans/detail/:id/execute',
        name: 'ExecutionPlanExecute',
        component: () => import('@/views/execution-plans/execute.vue'),
        meta: {
          title: '执行方案',
          hideInMenu: true,
        },
      },
      {
        path: '/execution-records',
        name: 'ExecutionRecords',
        component: () => import('@/views/execution-records/index.vue'),
        meta: {
          title: '执行记录',
          icon: 'icon-history',
        },
      },
      {
        path: '/execution-records/:id',
        name: 'ExecutionRecordDetail',
        component: () => import('@/views/execution-records/detail.vue'),
        meta: {
          title: '执行记录详情',
          hideInMenu: true,
        },
      },

      {
        path: '/scheduled-tasks',
        name: 'ScheduledTasks',
        component: () => import('@/views/scheduled-tasks/index.vue'),
        meta: {
          title: '定时任务',
          icon: 'icon-schedule',
        },
      },
      {
        path: '/scheduled-tasks/create',
        name: 'ScheduledTaskCreate',
        component: () => import('@/views/scheduled-tasks/editor.vue'),
        meta: {
          title: '创建定时任务',
          hideInMenu: true,
        },
      },
      {
        path: '/scheduled-tasks/detail/:id',
        name: 'ScheduledTaskDetail',
        component: () => import('@/views/scheduled-tasks/detail.vue'),
        meta: {
          title: '定时任务详情',
          hideInMenu: true,
        },
      },
      {
        path: '/scheduled-tasks/:id/edit',
        name: 'ScheduledTaskEdit',
        component: () => import('@/views/scheduled-tasks/editor.vue'),
        meta: {
          title: '编辑定时任务',
          hideInMenu: true,
        },
      },
      {
        path: '/audit-logs',
        name: 'AuditLogs',
        component: () => import('@/views/audit-logs/index.vue'),
        meta: {
          title: '审计日志',
          icon: 'icon-file-text',
          requiresSuperUser: true,
        },
      },
      {
        path: '/quick-execute',
        name: 'QuickExecute',
        component: () => import('@/views/QuickExecute.vue'),
        meta: {
          title: '快速执行',
          icon: 'icon-thunderbolt',
        },
      },
      {
        path: '/realtime/:taskId',
        name: 'Realtime',
        component: () => import('@/views/Realtime.vue'),
        meta: {
          title: '实时监控',
          hideInMenu: true,
        },
      },
    ],
  },
  {
    path: '/ops',
    name: 'OpsLayout',
    component: () => import('@/views/OpsLayout.vue'),
    redirect: '/ops/dashboard',
    meta: {
      requiresAuth: true,
      requiresSuperUser: true, // 只有超级管理员才能访问运维台
      platform: 'ops', // 标记为运维台
    },
    children: [
      {
        path: 'agents',
        name: 'OpsAgents',
        component: () => import('@/views/ops/agents/index.vue'),
        meta: {
          title: 'Agent 管理',
          icon: 'icon-server',
        },
      },
      {
        path: 'agents/:id',
        name: 'OpsAgentDetail',
        component: () => import('@/views/ops/agents/detail.vue'),
        meta: {
          title: 'Agent 详情',
          hideInMenu: true,
        },
      },
      {
        path: 'agents/install-records',
        name: 'OpsAgentInstallRecords',
        component: () => import('@/views/ops/agents/install-records.vue'),
        meta: {
          title: 'Agent 安装记录',
          icon: 'icon-history',
        },
      },
      {
        path: 'agents/uninstall-records',
        name: 'OpsAgentUninstallRecords',
        component: () => import('@/views/ops/agents/uninstall-records.vue'),
        meta: {
          title: 'Agent 卸载记录',
          icon: 'icon-delete',
        },
      },
      {
        path: 'agents/packages',
        name: 'OpsAgentPackages',
        component: () => import('@/views/ops/agents/packages.vue'),
        meta: {
          title: 'Agent 安装包管理',
          icon: 'icon-archive',
        },
      },
      {
        path: 'hosts',
        name: 'OpsHosts',
        component: () => import('@/views/hosts/index.vue'),
        meta: {
          title: '主机管理',
          icon: 'icon-computer',
        },
      },
      {
        path: 'accounts',
        name: 'OpsAccounts',
        component: () => import('@/views/accounts/index.vue'),
        meta: {
          title: '服务器账号',
          icon: 'icon-user',
        },
      },
      {
        path: 'dashboard',
        name: 'OpsDashboard',
        component: () => import('@/views/ops/dashboard/index.vue'),
        meta: {
          title: '运维台 Dashboard',
          icon: 'icon-dashboard',
        },
      },
      {
        path: 'system-config',
        name: 'OpsSystemConfig',
        component: () => import('@/views/system-config/index.vue'),
        meta: {
          title: '系统配置',
          icon: 'icon-settings',
        },
      },
      {
        path: 'hosts/:id',
        name: 'OpsHostDetail',
        component: () => import('@/views/hosts/detail.vue'),
        meta: {
          title: '主机详情',
          hideInMenu: true,
        },
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/NotFound.vue'),
    meta: {
      title: '页面不存在',
    },
  },
]

// 创建路由实例
const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 全局状态管理，防止重复处理
let isHandlingAuth = false
let authErrorMessages = new Set<string>()

// 清理认证错误消息
const clearAuthErrorMessage = (message: string) => {
  setTimeout(() => {
    authErrorMessages.delete(message)
  }, 3000)
}

// 显示唯一认证错误消息
const showUniqueAuthMessage = async (message: string) => {
  if (!authErrorMessages.has(message)) {
    authErrorMessages.add(message)
    Message.warning(message)
    clearAuthErrorMessage(message)
  }
}

// 路由守卫
router.beforeEach(async (to, from, next) => {
  // 开始进度条
  NProgress.start()

  const authStore = useAuthStore()

  // 设置页面标题
  if (to.meta.title) {
    document.title = `${to.meta.title} - 运维作业平台`
  }
  
  // 检查是否需要认证
  if (to.meta.requiresAuth !== false) {
    // 检查是否已登录
    if (!authStore.isAuthenticated) {
      NProgress.done()
      next({ name: 'Login', query: { redirect: to.fullPath } })
      return
    }

    // 检查token是否过期，防止重复处理
    if (authStore.isTokenExpired() && !isHandlingAuth) {
      isHandlingAuth = true
      
      try {
        console.log('检测到token过期，尝试自动刷新...')
        await authStore.refreshAccessToken()
        console.log('token刷新成功')
        isHandlingAuth = false
      } catch (error: any) {
        console.warn('自动刷新token失败:', error)
        
        // 根据错误类型提供不同的用户提示
        let userMessage = '登录已过期，正在跳转到登录页面...'
        
        if (error.message?.includes('网络连接失败')) {
          userMessage = '网络连接失败，请检查网络后重试'
        } else if (error.message?.includes('服务器内部错误')) {
          userMessage = '服务器暂时不可用，请稍后重试'
        } else if (error.message?.includes('Token已过期或无效')) {
          userMessage = '登录已过期，正在跳转到登录页面...'
        }
        
        // 显示唯一错误消息
        await showUniqueAuthMessage(userMessage)
        
        // 清理认证状态并跳转
        authStore.clearState()
        NProgress.done()
        next({ name: 'Login', query: { redirect: to.fullPath } })
        
        // 重置处理标志
        setTimeout(() => {
          isHandlingAuth = false
        }, 1000)
        
        return
      }
    }

    // 检查是否需要超级用户权限
    if (to.meta.requiresSuperUser && !authStore.user?.is_superuser) {
      NProgress.done()
      Message.warning('您没有权限访问该页面，仅超级管理员可访问')
      next({ name: 'Dashboard' })
      return
    }
  }

  // 已登录用户访问登录页，重定向到首页
  if (to.name === 'Login' && authStore.isAuthenticated && !authStore.isTokenExpired()) {
    NProgress.done()
    next({ name: 'Dashboard' })
    return
  }

  next()
})

// 路由完成后的守卫
router.afterEach(() => {
  // 结束进度条
  NProgress.done()
})

export default router
