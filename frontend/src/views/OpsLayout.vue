<template>
  <a-layout class="layout">
    <!-- 侧边栏 -->
    <a-layout-sider
      :width="200"
      :collapsed="collapsed"
      :collapsible="true"
      :hide-trigger="true"
      @collapse="onCollapse"
    >
      <div class="logo">
        <div class="brand-mark">O</div>
        <div v-if="!collapsed" class="brand-copy">
          <span class="brand-title">运维台</span>
          <span class="brand-subtitle">Ops Console</span>
        </div>
      </div>
      
      <a-menu
        :selected-keys="selectedKeys"
        :open-keys="openKeys"
        mode="vertical"
        @menu-item-click="onMenuClick"
        @sub-menu-click="onSubMenuClick"
      >
        <a-menu-item key="/ops/dashboard">
          <template #icon>
            <icon-dashboard />
          </template>
          仪表盘
        </a-menu-item>
        <!-- 运维管理分组 -->
        <a-sub-menu key="ops">
          <template #icon>
            <icon-tool />
          </template>
          <template #title>运维管理</template>

          <a-menu-item key="/ops/agents">
            <template #icon>
              <icon-desktop />
            </template>
            Agent 管理
          </a-menu-item>

          <a-menu-item key="/ops/agents/packages">
            <template #icon>
              <icon-archive />
            </template>
            安装包管理
          </a-menu-item>
        </a-sub-menu>

        <!-- 资源管理分组（可选，运维台也可以查看主机） -->
        <a-sub-menu key="resource">
          <template #icon>
            <icon-storage />
          </template>
          <template #title>资源管理</template>

          <a-menu-item key="/ops/hosts">
            <template #icon>
              <icon-computer />
            </template>
            主机管理
          </a-menu-item>
          <a-menu-item key="/ops/accounts">
            <template #icon>
              <icon-user />
            </template>
            服务器账号
          </a-menu-item>
        </a-sub-menu>

        <a-sub-menu key="system" v-if="authStore.user?.is_superuser">
          <template #icon>
            <icon-settings />
          </template>
          <template #title>系统管理</template>

          <a-menu-item key="/ops/system-config">
            <template #icon>
              <icon-tool />
            </template>
            系统配置
          </a-menu-item>
        </a-sub-menu>
      </a-menu>
    </a-layout-sider>
    
    <!-- 主内容区 -->
    <a-layout>
      <!-- 顶部导航 -->
      <a-layout-header class="header">
        <div class="header-left">
          <a-breadcrumb>
            <a-breadcrumb-item v-for="item in breadcrumbs" :key="item.path">
              {{ item.title }}
            </a-breadcrumb-item>
          </a-breadcrumb>
        </div>
        
        <div class="header-right">
          <a-space>
            <!-- 平台切换 -->
            <a-button class="platform-switch" type="text" @click="switchToJobPlatform">
              <template #icon>
                <icon-apps />
              </template>
              切换到作业平台
            </a-button>
            
            <!-- 用户信息 -->
            <a-dropdown>
              <a-button type="text">
                <template #icon>
                  <icon-user />
                </template>
                {{ authStore.user?.username }}
              </a-button>
              <template #content>
                <a-doption @click="handleLogout">
                  <template #icon>
                    <icon-export />
                  </template>
                  退出登录
                </a-doption>
              </template>
            </a-dropdown>
          </a-space>
        </div>
      </a-layout-header>
      
      <!-- 内容区域 -->
      <a-layout-content class="content">
        <router-view />
      </a-layout-content>
    </a-layout>
  </a-layout>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick, onBeforeUnmount } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import {
  IconTool,
  IconDesktop,
  IconArchive,
  IconStorage,
  IconComputer,
  IconSettings,
  IconApps,
  IconUser,
  IconExport,
} from '@arco-design/web-vue/es/icon'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const collapsed = ref(false)
const selectedKeys = ref<string[]>([])
const openKeys = ref<string[]>([])

// 菜单配置映射
const menuConfig = {
  '/ops/dashboard': { key: '/ops/dashboard', parent: null },
  '/ops/agents': { key: '/ops/agents', parent: 'ops' },
  '/ops/agents/packages': { key: '/ops/agents/packages', parent: 'ops' },
  '/ops/agents/install-records': { key: '/ops/agents', parent: 'ops' },
  '/ops/agents/uninstall-records': { key: '/ops/agents', parent: 'ops' },
  '/ops/agents/detail': { key: '/ops/agents', parent: 'ops' },
  '/ops/hosts': { key: '/ops/hosts', parent: 'resource' },
  '/ops/accounts': { key: '/ops/accounts', parent: 'resource' },
  '/ops/system-config': { key: '/ops/system-config', parent: 'system' },
}

// 查找菜单键和父菜单
const findMenuInfo = (path: string) => {
  // 按路径长度从长到短排序，优先匹配更具体的路径
  const sortedPaths = Object.entries(menuConfig).sort((a, b) => b[0].length - a[0].length)
  
  for (const [menuPath, config] of sortedPaths) {
    if (path === menuPath || path.startsWith(menuPath + '/')) {
      return config
    }
  }

  return { key: '/ops/agents', parent: 'ops' }
}

// 面包屑导航
const breadcrumbs = computed(() => {
  try {
    const matched = route.matched.filter(item => item.meta?.title)
    return matched.map(item => ({
      title: item.meta?.title,
      path: item.path,
    }))
  } catch (error) {
    console.error('面包屑导航计算失败:', error)
    return []
  }
})

// 监听路由变化，更新菜单选中状态
watch(
  () => route.path,
  (path) => {
    try {
      // 找到匹配的菜单项
      const menuInfo = findMenuInfo(path)
      if (menuInfo.key) {
        selectedKeys.value = [menuInfo.key]

        // 如果有父菜单，确保父菜单展开
        if (menuInfo.parent && !collapsed.value) {
          if (!openKeys.value.includes(menuInfo.parent)) {
            openKeys.value = [...openKeys.value, menuInfo.parent]
          }
        }
      }
    } catch (error) {
      console.error('更新菜单选中状态失败:', error)
    }
  },
  { immediate: true }
)

// 侧边栏折叠
const onCollapse = (collapsedState: boolean) => {
  try {
    // 更新折叠状态
    collapsed.value = collapsedState

    // 折叠时清空展开的菜单
    if (collapsedState) {
      openKeys.value = []
    }
  } catch (error) {
    console.error('侧边栏折叠处理失败:', error)
  }
}

// 菜单点击
const onMenuClick = async (key: string) => {
  try {
    // 避免重复导航到同一路由
    if (route.path !== key) {
      // 等待DOM更新完成
      await nextTick()

      // 执行路由跳转
      await router.push(key).catch(error => {
        // 忽略导航重复错误
        if (error.name !== 'NavigationDuplicated') {
          console.error('路由跳转失败:', error)
        }
      })
    }
  } catch (error) {
    console.error('菜单点击处理失败:', error)
  }
}

// 子菜单点击处理
const onSubMenuClick = (key: string) => {
  try {
    // 切换子菜单展开状态
    if (openKeys.value.includes(key)) {
      openKeys.value = openKeys.value.filter(k => k !== key)
    } else {
      openKeys.value = [...openKeys.value, key]
    }
  } catch (error) {
    console.error('子菜单点击处理失败:', error)
  }
}

// 切换到作业平台
const switchToJobPlatform = () => {
  // 记住用户选择了作业平台
  localStorage.setItem('selected_platform', 'job')
  sessionStorage.setItem('selected_platform', 'job')
  
  // 跳转到作业平台
  router.push('/dashboard')
}

// 退出登录
const handleLogout = async () => {
  try {
    await authStore.logout()
    Message.success('退出登录成功')

    // 清除平台选择
    localStorage.removeItem('selected_platform')
    sessionStorage.removeItem('selected_platform')

    // 使用replace而不是push避免历史记录问题
    await router.replace('/login')
  } catch (error) {
    console.error('退出登录失败:', error)
    // 即使退出失败也要跳转到登录页
    await router.replace('/login')
  }
}

// 组件卸载时清理
onBeforeUnmount(() => {
  try {
    // 清理状态
    selectedKeys.value = []
    openKeys.value = []
  } catch (error) {
    console.error('组件清理失败:', error)
  }
})
</script>

<style scoped>
.layout {
  height: 100vh;
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
  background: var(--app-fg);
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
  flex: 1;
}

.header-right {
  flex-shrink: 0;
}

.content {
  padding: 28px;
  background: var(--app-bg);
  overflow-y: auto;
}

:deep(.arco-layout-sider) {
  background: var(--app-surface);
  border-right: 1px solid var(--app-border);
  box-shadow: 1px 0 0 rgb(15 23 42 / 2%);
}

:deep(.arco-menu-vertical) {
  background: transparent;
  border-right: none;
  padding: 10px 8px;
}

:deep(.arco-menu-vertical > .arco-menu-item),
:deep(.arco-menu-vertical > .arco-sub-menu > .arco-menu-sub-title) {
  margin: 3px 0 !important;
  border-radius: var(--app-radius-sm) !important;
  font-weight: 500 !important;
  height: 40px !important;
  line-height: 40px !important;
  padding: 0 12px !important;
  min-height: 40px !important;
  max-height: 40px !important;
  display: flex !important;
  align-items: center !important;
  color: var(--app-fg-secondary) !important;
  box-sizing: border-box !important;
}

:deep(.arco-menu-vertical > .arco-menu-item:hover),
:deep(.arco-menu-vertical > .arco-sub-menu > .arco-menu-sub-title:hover) {
  background: var(--app-accent-soft) !important;
  color: var(--app-accent) !important;
}

:deep(.arco-menu-vertical > .arco-menu-item.arco-menu-selected) {
  background: var(--app-accent-soft) !important;
  color: var(--app-accent) !important;
  font-weight: 600 !important;
}

:deep(.arco-menu-item .arco-icon) {
  margin-right: 8px;
  font-size: 16px;
  width: 16px;
  height: 16px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

:deep(.arco-menu-sub-title .arco-icon) {
  margin-right: 8px;
  font-size: 16px;
  width: 16px;
  height: 16px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

:deep(.arco-menu-sub) {
  background: transparent;
}

:deep(.arco-menu-sub .arco-menu-item) {
  margin: 2px 0 2px 24px !important;
  font-weight: 400 !important;
  font-size: 13px !important;
  height: 36px !important;
  line-height: 36px !important;
  padding: 0 12px !important;
  border-radius: var(--app-radius-sm) !important;
  color: var(--app-muted) !important;
}

:deep(.arco-menu-sub .arco-menu-item:hover) {
  background: var(--app-accent-soft) !important;
  color: var(--app-accent) !important;
}

:deep(.arco-menu-sub .arco-menu-item.arco-menu-selected),
:deep(.arco-sub-menu .arco-menu-item.arco-menu-selected),
:deep(.arco-menu .arco-sub-menu .arco-menu-item.arco-menu-selected) {
  background: var(--app-accent-soft) !important;
  color: var(--app-accent) !important;
  font-weight: 500 !important;
}

:deep(.arco-menu-vertical .arco-sub-menu .arco-menu-item.arco-menu-selected) {
  background: var(--app-accent-soft) !important;
  color: var(--app-accent) !important;
  font-weight: 500 !important;
}

:deep(.arco-menu .arco-menu-item.arco-menu-selected) {
  background: var(--app-accent-soft) !important;
  color: var(--app-accent) !important;
}

:deep([class*="arco-menu"] [class*="arco-menu-item"][class*="selected"]) {
  background: var(--app-accent-soft) !important;
  color: var(--app-accent) !important;
}

:deep(.arco-layout-sider-collapsed .logo) {
  justify-content: center;
  padding: 0;
}

:deep(.arco-layout-sider-collapsed .arco-menu-vertical) {
  padding: 10px 8px;
}

:deep(.arco-layout-sider-collapsed .arco-menu-vertical > .arco-menu-item),
:deep(.arco-layout-sider-collapsed .arco-menu-vertical > .arco-sub-menu > .arco-menu-sub-title) {
  justify-content: center;
  padding: 0 !important;
}

:deep(.arco-layout-sider-collapsed .arco-menu-item .arco-icon),
:deep(.arco-layout-sider-collapsed .arco-menu-sub-title .arco-icon) {
  margin-right: 0 !important;
}

:deep(.arco-breadcrumb) {
  color: var(--app-muted);
  font-size: 13px;
}

.platform-switch {
  color: var(--app-fg-secondary);
}

@media (max-width: 768px) {
  .content {
    padding: 18px;
  }

  .header {
    padding: 0 18px;
  }
}
</style>

