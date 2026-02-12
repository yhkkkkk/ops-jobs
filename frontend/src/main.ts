import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ArcoVue from '@arco-design/web-vue'
import ArcoVueIcon from '@arco-design/web-vue/es/icon'
import '@arco-design/web-vue/dist/arco.css'
import cronCore from '@vue-js-cron/core'

import App from './App.vue'
import router from './router'
import { useAuthStore } from './stores/auth'
import { setupPermissionDirectives } from './directives/permission'
import { preloadMonaco } from './utils/monacoFactory'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)
app.use(ArcoVue as any)
app.use(ArcoVueIcon as any)
app.use(cronCore)

// 注册权限指令
setupPermissionDirectives(app)

// 初始化认证状态
const authStore = useAuthStore()
authStore.init()

// 添加全局登录状态监听
let authCheckInterval: number | null = null

// 定期检查登录状态
const startAuthCheck = () => {
  if (authCheckInterval) {
    clearInterval(authCheckInterval)
  }
  
  authCheckInterval = window.setInterval(() => {
    // 只在已登录且不在登录页面时检查
    if (authStore.isAuthenticated && router.currentRoute.value.name !== 'Login') {
      if (authStore.isTokenExpired()) {
        console.log('定期检查发现token已过期')
        // token过期会由路由守卫处理，这里只记录日志
      }
    }
  }, 30000) // 每30秒检查一次
}

// 监听页面可见性变化
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible') {
    // 页面重新可见时检查登录状态
    if (authStore.isAuthenticated && authStore.isTokenExpired()) {
      console.log('页面重新激活，检测到token已过期')
      // 强制触发路由检查
      router.push(router.currentRoute.value.fullPath)
    }
  }
})

// 启动认证检查
startAuthCheck()

// 预加载Monaco Editor（在空闲时间）
preloadMonaco()

// 全局错误处理
app.config.errorHandler = (err, _vm, info) => {
  console.error('全局错误:', err, info)
  
  // 如果是认证相关错误，清理状态
  if (err instanceof Error && err.message.includes('401')) {
    authStore.clearState()
    router.push('/login')
  }
}

// 全局警告处理
app.config.warnHandler = (msg, _vm, trace) => {
  console.warn('全局警告:', msg, trace)
}

app.mount('#app')
