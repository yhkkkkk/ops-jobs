<template>
  <a-layout class="layout">
    <!-- 侧边栏 -->
    <a-layout-sider
      :width="200"
      :collapsed="collapsed"
      :collapsible="true"
      @collapse="onCollapse"
    >
      <div class="logo">
        <span v-if="!collapsed">Job平台</span>
        <span v-else>OP</span>
      </div>
      
      <a-menu
        :selected-keys="selectedKeys"
        :open-keys="openKeys"
        mode="vertical"
        @menu-item-click="onMenuClick"
        @sub-menu-click="onSubMenuClick"
      >
        <a-menu-item key="/dashboard">
          <template #icon>
            <icon-dashboard />
          </template>
          仪表盘
        </a-menu-item>

        <!-- 资源管理分组 -->
        <a-sub-menu key="resource">
          <template #icon>
            <icon-storage />
          </template>
          <template #title>资源管理</template>

          <a-menu-item key="/hosts">
            <template #icon>
              <icon-computer />
            </template>
            主机管理
          </a-menu-item>

          <a-menu-item key="/accounts">
            <template #icon>
              <icon-user />
            </template>
            服务器账号
          </a-menu-item>
        </a-sub-menu>

        <!-- 作业管理分组 -->
        <a-sub-menu key="job">
          <template #icon>
            <icon-apps />
          </template>
          <template #title>作业管理</template>

          <a-menu-item key="/script-templates">
            <template #icon>
              <icon-code />
            </template>
            脚本模板
          </a-menu-item>

          <a-menu-item key="/job-templates">
            <template #icon>
              <icon-file />
            </template>
            作业模板
          </a-menu-item>

          <a-menu-item key="/execution-plans">
            <template #icon>
              <icon-calendar />
            </template>
            作业执行方案
          </a-menu-item>

          <a-menu-item key="/quick-execute">
            <template #icon>
              <icon-thunderbolt />
            </template>
            快速执行
          </a-menu-item>
        </a-sub-menu>

        <!-- 调度管理分组 -->
        <a-sub-menu key="schedule">
          <template #icon>
            <icon-schedule />
          </template>
          <template #title>调度管理</template>

          <a-menu-item key="/scheduled-tasks">
            <template #icon>
              <icon-clock-circle />
            </template>
            定时任务
          </a-menu-item>
        </a-sub-menu>

        <!-- 监控审计分组 -->
        <a-sub-menu key="monitor">
          <template #icon>
            <icon-eye />
          </template>
          <template #title>监控审计</template>

          <a-menu-item key="/execution-records">
            <template #icon>
              <icon-history />
            </template>
            执行记录
          </a-menu-item>

          <a-menu-item key="/audit-logs" v-if="authStore.user?.is_superuser">
            <template #icon>
              <icon-eye-invisible />
            </template>
            审计日志
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
            <!-- 平台切换（仅超级管理员可见） -->
            <a-button 
              v-if="authStore.user?.is_superuser"
              type="text" 
              @click="switchToOpsPlatform"
            >
              <template #icon>
                <icon-tool />
              </template>
              切换到运维台
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
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const collapsed = ref(false)
const selectedKeys = ref<string[]>([])
const openKeys = ref<string[]>([])

// 菜单配置映射
const menuConfig = {
  '/dashboard': { key: '/dashboard', parent: null },
  '/hosts': { key: '/hosts', parent: 'resource' },
  '/accounts': { key: '/accounts', parent: 'resource' },
  '/script-templates': { key: '/script-templates', parent: 'job' },
  '/job-templates': { key: '/job-templates', parent: 'job' },
  '/execution-plans': { key: '/execution-plans', parent: 'job' },
  '/quick-execute': { key: '/quick-execute', parent: 'job' },
  '/scheduled-tasks': { key: '/scheduled-tasks', parent: 'schedule' },
  '/execution-records': { key: '/execution-records', parent: 'monitor' },
  '/audit-logs': { key: '/audit-logs', parent: 'monitor' },
}

// 查找菜单键和父菜单
const findMenuInfo = (path: string) => {
  // 精确匹配
  for (const [menuPath, config] of Object.entries(menuConfig)) {
    if (path === menuPath || path.startsWith(menuPath + '/')) {
      return config
    }
  }

  return { key: '/dashboard', parent: null }
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

// 切换到运维台
const switchToOpsPlatform = () => {
  // 记住用户选择了运维台
  localStorage.setItem('selected_platform', 'ops')
  sessionStorage.setItem('selected_platform', 'ops')
  
  // 跳转到运维台
  router.push('/ops/dashboard')
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
}

.logo {
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  font-weight: 600;
  color: #1d2129;
  background: #f6f7f9;
  border-bottom: 1px solid #e5e6eb;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  background: white;
  border-bottom: 1px solid #e5e6eb;
}

.header-left {
  flex: 1;
}

.header-right {
  flex-shrink: 0;
}

.content {
  padding: 24px;
  background: #f5f5f5;
  overflow-y: auto;
}

:deep(.arco-layout-sider) {
  background: #f6f7f9;
  border-right: 1px solid #e5e6eb;
}

:deep(.arco-menu-vertical) {
  background: transparent;
  border-right: none;
}

/* 顶级菜单项样式（仪表盘和分组菜单标题） */
:deep(.arco-menu-vertical > .arco-menu-item),
:deep(.arco-menu-vertical > .arco-sub-menu > .arco-menu-sub-title) {
  margin: 2px 8px !important;
  border-radius: 6px !important;
  font-weight: 500 !important;
  height: 40px !important;
  line-height: 40px !important;
  padding: 0 12px !important;
  min-height: 40px !important;
  max-height: 40px !important;
  display: flex !important;
  align-items: center !important;
  color: #4e5969 !important;
  box-sizing: border-box !important;
}

/* 顶级菜单项悬停状态 */
:deep(.arco-menu-vertical > .arco-menu-item:hover),
:deep(.arco-menu-vertical > .arco-sub-menu > .arco-menu-sub-title:hover) {
  background: #e8f4ff !important;
  color: #1890ff !important;
}

/* 顶级菜单项选中状态（仪表盘） */
:deep(.arco-menu-vertical > .arco-menu-item.arco-menu-selected) {
  background: transparent !important;
  color: #1890ff !important;
  font-weight: 600 !important;
}



/* 菜单图标样式 */
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

/* 子菜单容器样式 */
:deep(.arco-menu-sub) {
  background: transparent;
}

/* 子菜单项样式（主机管理、服务器账号等） */
:deep(.arco-menu-sub .arco-menu-item) {
  margin: 1px 16px 1px 32px !important;
  font-weight: 400 !important;
  font-size: 13px !important;
  height: 36px !important;
  line-height: 36px !important;
  padding: 0 12px !important;
  border-radius: 6px !important;
  color: #6b7280 !important;
}

/* 子菜单项悬停状态 */
:deep(.arco-menu-sub .arco-menu-item:hover) {
  background: #e8f4ff !important;
  color: #1890ff !important;
}

/* 子菜单项选中状态 */
:deep(.arco-menu-sub .arco-menu-item.arco-menu-selected),
:deep(.arco-sub-menu .arco-menu-item.arco-menu-selected),
:deep(.arco-menu .arco-sub-menu .arco-menu-item.arco-menu-selected) {
  background: #f0f8ff !important;
  color: #1890ff !important;
  font-weight: 500 !important;
}

/* 更强的选择器确保样式生效 */
:deep(.arco-menu-vertical .arco-sub-menu .arco-menu-item.arco-menu-selected) {
  background: #f0f8ff !important;
  color: #1890ff !important;
  font-weight: 500 !important;
}

/* 通用选中状态重置 */
:deep(.arco-menu .arco-menu-item.arco-menu-selected) {
  background: #f0f8ff !important;
  color: #1890ff !important;
}

/* 确保子菜单选中状态 */
:deep([class*="arco-menu"] [class*="arco-menu-item"][class*="selected"]) {
  background: #f0f8ff !important;
  color: #1890ff !important;
}
</style>
