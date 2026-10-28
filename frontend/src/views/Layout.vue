<template>
  <n-layout has-sider class="layout">
    <n-layout-sider
      v-if="!isMobile"
      :width="200"
      :collapsed-width="64"
      :collapsed="collapsed"
      :native-scrollbar="false"
      bordered
      @update:collapsed="onCollapse"
    >
      <div class="logo">
        <div class="brand-mark">J</div>
        <div v-if="!collapsed" class="brand-copy">
          <span class="brand-title">作业平台</span>
          <span class="brand-subtitle">Ops Job</span>
        </div>
      </div>
      <n-menu
        v-model:value="selectedMenuKey"
        :options="menuOptions"
        :collapsed="collapsed"
        :collapsed-width="64"
        :expanded-keys="openKeys"
        :indent="collapsed ? 0 : 12"
        :root-indent="collapsed ? 0 : 12"
        @update:expanded-keys="onExpandedKeysChange"
      />
    </n-layout-sider>

    <n-drawer
      v-if="isMobile"
      v-model:show="mobileMenuOpen"
      placement="left"
      :width="248"
      :show-mask="true"
    >
      <n-drawer-content body-content-style="padding: 0">
        <div class="logo">
          <div class="brand-mark">J</div>
          <div class="brand-copy">
            <span class="brand-title">作业平台</span>
            <span class="brand-subtitle">Ops Job</span>
          </div>
        </div>
        <n-menu
          v-model:value="selectedMenuKey"
          :options="menuOptions"
          :expanded-keys="openKeys"
          :indent="12"
          :root-indent="12"
          @update:expanded-keys="onExpandedKeysChange"
        />
      </n-drawer-content>
    </n-drawer>

    <n-layout>
      <n-layout-header class="header">
        <div class="header-left">
          <n-button
            class="layout-collapse-btn"
            text
            size="small"
            :title="collapseButtonTitle"
            :aria-label="collapseButtonTitle"
            @click="toggleCollapsedOrMobile"
          >
            <component
              :is="collapseButtonIcon"
              :size="17"
              :stroke-width="1.8"
              aria-hidden="true"
            />
          </n-button>
          <n-breadcrumb>
            <n-breadcrumb-item
              v-for="(item, index) in breadcrumbs"
              :key="`${item.path}-${index}`"
              :clickable="Boolean(item.to)"
              @click="item.to && router.push(item.to)"
            >
              {{ item.title }}
            </n-breadcrumb-item>
          </n-breadcrumb>
        </div>
        <div class="header-right">
          <n-space align="center">
            <n-button
              v-if="authStore.user?.is_superuser"
              class="platform-switch"
              text
              title="切换到运维台"
              @click="switchToOpsPlatform"
            >
              <template #icon>
                <Wrench :size="16" :stroke-width="1.8" aria-hidden="true" />
              </template>
              切换到运维台
            </n-button>
            <n-dropdown
              :options="userMenuOptions"
              trigger="click"
              @select="handleUserMenuSelect"
            >
              <n-button
                text
                :aria-label="`用户菜单：${authStore.user?.username || ''}`"
              >
                <template #icon>
                  <UserRound :size="16" :stroke-width="1.8" aria-hidden="true" />
                </template>
                {{ authStore.user?.username }}
              </n-button>
            </n-dropdown>
          </n-space>
        </div>
      </n-layout-header>

      <n-layout-content :class="['content', { 'content--workspace': workspaceMode }]">
        <router-view />
      </n-layout-content>
    </n-layout>
  </n-layout>
</template>

<script setup lang="ts">
import { computed, h, nextTick, onBeforeUnmount, onMounted, ref, watch, type Component } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  NButton,
  NBreadcrumb,
  NBreadcrumbItem,
  NDropdown,
  NDrawer,
  NDrawerContent,
  NLayout,
  NLayoutContent,
  NLayoutHeader,
  NLayoutSider,
  NMenu,
  NSpace,
  useMessage,
  type MenuOption,
} from 'naive-ui'
import {
  AppWindow,
  Calendar,
  CalendarDays,
  Clock3,
  Code2,
  Database,
  Eye,
  FileText,
  GitBranch,
  History,
  LayoutDashboard,
  LogOut,
  Menu,
  Monitor,
  PanelLeftClose,
  PanelLeftOpen,
  Settings2,
  ShieldCheck,
  UserRound,
  Users,
  Wrench,
  X,
  Zap,
} from 'lucide-vue-next'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const message = useMessage()

const MOBILE_BREAKPOINT = 520
const collapsed = ref(false)
const selectedKeys = ref<string[]>([])
const openKeys = ref<string[]>([])
const isMobile = ref(
  typeof window !== 'undefined' && window.innerWidth <= MOBILE_BREAKPOINT,
)
const mobileMenuOpen = ref(false)

const selectedMenuKey = computed({
  get: () => selectedKeys.value[0] || null,
  set: (key: string | null) => {
    if (key) void onMenuClick(key)
  },
})

const workspaceMode = computed(() => route.meta.workspaceMode === true)
let previousCollapsedState: boolean | null = null

const renderIcon = (icon: Component) => () => h(icon, { size: 16, strokeWidth: 1.8 })

const menuConfig: Record<string, { key: string; parent: string | null }> = {
  '/dashboard': { key: '/dashboard', parent: null },
  '/hosts': { key: '/hosts', parent: 'resource' },
  '/accounts': { key: '/accounts', parent: 'resource' },
  '/permissions': { key: '/permissions', parent: 'system' },
  '/users': { key: '/users', parent: 'system' },
  '/script-templates': { key: '/script-templates', parent: 'job' },
  '/job-templates': { key: '/job-templates', parent: 'job' },
  '/execution-plans': { key: '/execution-plans', parent: 'job' },
  '/flows': { key: '/flows', parent: 'job' },
  '/quick-execute': { key: '/quick-execute', parent: 'job' },
  '/scheduled-tasks': { key: '/scheduled-tasks', parent: 'schedule' },
  '/execution-records': { key: '/execution-records', parent: 'monitor' },
  '/audit-logs': { key: '/audit-logs', parent: 'monitor' },
}

const menuOptions = computed<MenuOption[]>(() => [
  {
    label: '仪表盘',
    key: '/dashboard',
    icon: renderIcon(LayoutDashboard),
  },
  {
    label: '资源管理',
    key: 'resource',
    icon: renderIcon(Database),
    children: [
      { label: '主机管理', key: '/hosts', icon: renderIcon(Monitor) },
      { label: '服务器账号', key: '/accounts', icon: renderIcon(UserRound) },
    ],
  },
  {
    label: '作业管理',
    key: 'job',
    icon: renderIcon(AppWindow),
    children: [
      { label: '脚本模板', key: '/script-templates', icon: renderIcon(Code2) },
      { label: '作业模板', key: '/job-templates', icon: renderIcon(FileText) },
      { label: '作业执行方案', key: '/execution-plans', icon: renderIcon(CalendarDays) },
      { label: '运维流水线', key: '/flows', icon: renderIcon(GitBranch) },
      { label: '快速执行', key: '/quick-execute', icon: renderIcon(Zap) },
    ],
  },
  {
    label: '调度管理',
    key: 'schedule',
    icon: renderIcon(Clock3),
    children: [
      { label: '执行方案定时任务', key: '/scheduled-tasks', icon: renderIcon(Calendar) },
    ],
  },
  {
    label: '监控审计',
    key: 'monitor',
    icon: renderIcon(Eye),
    children: [
      { label: '执行记录', key: '/execution-records', icon: renderIcon(History) },
      ...(authStore.user?.is_superuser
        ? [{ label: '审计日志', key: '/audit-logs', icon: renderIcon(ShieldCheck) }]
        : []),
    ],
  },
  {
    label: '平台管理',
    key: 'system',
    icon: renderIcon(Settings2),
    children: [
      { label: '权限管理', key: '/permissions', icon: renderIcon(ShieldCheck) },
      ...(authStore.user?.is_superuser
        ? [{ label: '用户管理', key: '/users', icon: renderIcon(Users) }]
        : []),
    ],
  },
])

const userMenuOptions = [
  { label: '退出登录', key: 'logout', icon: renderIcon(LogOut) },
]

const collapseButtonTitle = computed(() => {
  if (isMobile.value) {
    return mobileMenuOpen.value ? '关闭导航' : '打开导航'
  }
  return '折叠侧边栏'
})

const collapseButtonIcon = computed(() => {
  if (isMobile.value) {
    return mobileMenuOpen.value ? X : Menu
  }
  return collapsed.value ? PanelLeftOpen : PanelLeftClose
})

const findMenuInfo = (path: string) => {
  for (const [menuPath, config] of Object.entries(menuConfig)) {
    if (path === menuPath || path.startsWith(`${menuPath}/`)) {
      return config
    }
  }
  return { key: '/dashboard', parent: null }
}

const breadcrumbs = computed(() => {
  const matched = route.matched.filter((item) => item.meta?.title)
  const leaf = matched[matched.length - 1]
  const parent = leaf?.meta?.breadcrumbParent as { title: string; to: string } | undefined
  const items = matched.map((item) => ({
    title: String(item.meta?.title || ''),
    path: item.path,
    to: undefined as string | undefined,
  }))
  if (parent) {
    return [
      { title: parent.title, path: parent.to, to: parent.to },
      ...items.filter((item) => item.title !== parent.title),
    ]
  }
  return items
})

watch(
  () => route.path,
  (path) => {
    const info = findMenuInfo(path)
    selectedKeys.value = [info.key]
    if (info.parent && !collapsed.value && !openKeys.value.includes(info.parent)) {
      openKeys.value = [...openKeys.value, info.parent]
    }
    if (isMobile.value) {
      mobileMenuOpen.value = false
    }
  },
  { immediate: true },
)

watch(
  workspaceMode,
  (active) => {
    if (active) {
      previousCollapsedState = collapsed.value
      collapsed.value = true
      openKeys.value = []
      return
    }
    if (previousCollapsedState !== null) {
      collapsed.value = previousCollapsedState
      previousCollapsedState = null
    }
  },
  { immediate: true },
)

const onCollapse = (value: boolean) => {
  collapsed.value = value
  if (value) {
    openKeys.value = []
  }
}

const toggleCollapsed = () => onCollapse(!collapsed.value)
const toggleMobileMenu = () => {
  mobileMenuOpen.value = !mobileMenuOpen.value
}
const toggleCollapsedOrMobile = () => {
  if (isMobile.value) {
    toggleMobileMenu()
    return
  }
  toggleCollapsed()
}

const onExpandedKeysChange = (keys: string[]) => {
  openKeys.value = collapsed.value ? [] : keys
}

const onMenuClick = async (key: string) => {
  if (route.path === key) return
  await nextTick()
  await router.push(key).catch((error) => {
    if (error.name !== 'NavigationDuplicated') {
      console.error('路由跳转失败:', error)
    }
  })
}

const switchToOpsPlatform = () => {
  localStorage.setItem('selected_platform', 'ops')
  sessionStorage.setItem('selected_platform', 'ops')
  void router.push('/ops/dashboard')
}

const handleUserMenuSelect = (key: string) => {
  if (key === 'logout') void handleLogout()
}

const handleLogout = async () => {
  try {
    await authStore.logout()
    message.success('退出登录成功')
  } catch (error) {
    console.error('退出登录失败:', error)
  }
  localStorage.removeItem('selected_platform')
  sessionStorage.removeItem('selected_platform')
  await router.replace('/login')
}

const handleViewportChange = () => {
  const nextIsMobile = window.innerWidth <= MOBILE_BREAKPOINT
  if (nextIsMobile !== isMobile.value) {
    isMobile.value = nextIsMobile
    mobileMenuOpen.value = false
  }
}

onMounted(() => {
  handleViewportChange()
  window.addEventListener('resize', handleViewportChange, { passive: true })
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleViewportChange)
  selectedKeys.value = []
  openKeys.value = []
  mobileMenuOpen.value = false
})
</script>

<style scoped>
.layout {
  height: 100vh;
  overflow: hidden;
  background: var(--app-bg);
}

.logo {
  height: 68px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 16px;
  color: var(--app-fg);
  background: var(--app-surface);
  border-bottom: 1px solid var(--app-border);
}

.brand-mark {
  display: inline-flex;
  width: 34px;
  height: 34px;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  color: #fff;
  background: var(--app-accent);
  border-radius: 10px;
  font-family: var(--app-mono);
  font-size: 15px;
  font-weight: 700;
}

.brand-copy {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.brand-title {
  color: var(--app-fg);
  font-size: 15px;
  line-height: 1.2;
  font-weight: 650;
}

.brand-subtitle {
  color: var(--app-meta);
  font-family: var(--app-mono);
  font-size: 11px;
  line-height: 1.2;
  text-transform: uppercase;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 64px;
  padding: 0 28px;
  background: color-mix(in srgb, var(--app-surface) 94%, transparent);
  border-bottom: 1px solid var(--app-border);
  backdrop-filter: blur(10px);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  flex: 1;
}

.layout-collapse-btn {
  flex: 0 0 auto;
  color: var(--app-fg-secondary);
  border-radius: var(--app-radius-sm);
}

.layout-collapse-btn:hover,
.platform-switch:hover {
  color: var(--app-accent);
  background: var(--app-accent-soft);
}

.header-right {
  flex-shrink: 0;
}

.content {
  padding: 28px;
  background: var(--app-bg);
  overflow-y: auto;
}

.content--workspace {
  display: flex !important;
  flex: 1 1 auto;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  padding: 8px 10px;
  overflow: hidden !important;
}

.platform-switch {
  color: var(--app-fg-secondary);
}

:deep(.n-layout-sider) {
  background: var(--app-surface);
  border-right: 1px solid var(--app-border);
  box-shadow: 1px 0 0 rgb(15 23 42 / 2%);
}

:deep(.n-layout-sider .logo) {
  justify-content: flex-start;
}

:deep(.n-layout-sider.n-layout-sider--collapsed) {
  justify-content: flex-start;
  overflow: hidden;
}

:deep(.n-layout-sider.n-layout-sider--collapsed > .n-scrollbar),
:deep(.n-layout-sider.n-layout-sider--collapsed .n-scrollbar-container) {
  width: 100% !important;
  min-width: 0 !important;
  max-width: 100% !important;
}

:deep(.n-layout-sider.n-layout-sider--collapsed .logo) {
  justify-content: center;
  padding: 0;
}

:deep(.n-menu) {
  background: transparent;
  padding: 10px 8px;
}

:deep(.n-menu--collapsed) {
  width: 100% !important;
  min-width: 0 !important;
  padding: 10px 0;
}

:deep(.n-menu-item-content) {
  margin: 3px 0;
  border-radius: var(--app-radius-sm);
  color: var(--app-fg-secondary);
  font-weight: 500;
  min-height: 40px;
}

:deep(.n-menu--collapsed .n-menu-item-content),
:deep(.n-menu--collapsed .n-menu-item-content--selected) {
  padding-left: 0 !important;
  padding-right: 0 !important;
  justify-content: center;
  display: flex !important;
  width: 100%;
}

:deep(.n-menu--collapsed .n-menu-item-content-header),
:deep(.n-menu--collapsed .n-menu-item-content__arrow) {
  display: none !important;
  width: 0 !important;
  max-width: 0 !important;
  margin: 0 !important;
  overflow: hidden;
}

:deep(.n-menu-item-content:hover),
:deep(.n-menu-item-content--selected) {
  background: var(--app-accent-soft);
  color: var(--app-accent);
}

:deep(.n-submenu-children .n-menu-item-content) {
  min-height: 36px;
  color: var(--app-muted);
  font-size: 13px;
}

:deep(.n-menu-item-content__icon) {
  margin-right: 8px;
}

:deep(.n-menu--collapsed .n-menu-item-content__icon) {
  margin-right: 0 !important;
  margin-left: 0 !important;
}

@media (max-width: 520px) {
  .content {
    padding: 18px;
  }

  .header {
    padding: 0 18px;
  }

  :deep(.n-layout-sider) {
    display: none;
  }
}
</style>
