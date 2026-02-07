<template>
  <div class="login-container">
    <div class="login-box">
      <div class="login-header">
        <h1>运维作业平台</h1>
      </div>
      
      <!-- 登录方式选择标签页 -->
      <a-tabs 
        v-model:active-key="loginType" 
        type="line"
        class="login-tabs"
        v-if="authConfig.ldap_enabled"
      >
        <a-tab-pane key="normal" title="普通登录" />
        <a-tab-pane key="ldap" title="LDAP登录" />
      </a-tabs>
      
      <a-form
        ref="formRef"
        :model="form"
        :rules="rules"
        layout="vertical"
        @submit="handleSubmit"
      >
        <a-form-item field="username" label="用户名">
          <a-input
            v-model="form.username"
            placeholder="请输入用户名"
            size="large"
            allow-clear
          >
            <template #prefix>
              <IconUser />
            </template>
          </a-input>
        </a-form-item>
        
        <a-form-item field="password" label="密码">
          <a-input-password
            v-model="form.password"
            placeholder="请输入密码"
            size="large"
            allow-clear
          >
            <template #prefix>
              <IconLock />
            </template>
          </a-input-password>
        </a-form-item>

        <!-- 验证码（与2FA互斥，如果启用了2FA则不显示验证码） -->
        <a-form-item 
          v-if="authConfig.captcha_enabled && !authConfig.two_factor_enabled" 
          field="captcha_value" 
          label="验证码"
        >
          <div class="captcha-container">
            <a-input
              v-model="form.captcha_value"
              placeholder="请输入验证码"
              size="large"
              style="flex: 1"
            >
              <template #prefix>
                <IconSafe />
              </template>
            </a-input>
            <div class="captcha-image" @click="refreshCaptcha">
              <img 
                v-if="captchaImage" 
                :src="captchaImage" 
                alt="验证码"
                style="width: 100%; height: 100%; cursor: pointer;"
              />
              <div v-else class="captcha-placeholder">
                <IconRefresh :size="20" />
              </div>
            </div>
          </div>
          <input v-model="form.captcha_key" type="hidden" />
        </a-form-item>

        <!-- 2FA验证码 -->
        <a-form-item 
          v-if="showOtpInput" 
          field="otp_token" 
          label="双因子验证码"
        >
          <a-input
            v-model="form.otp_token"
            placeholder="请输入6位验证码"
            size="large"
            :max-length="6"
          >
            <template #prefix>
              <IconLock />
            </template>
          </a-input>
          <template #extra>
            <a-link @click="showOtpHelp = true">如何使用？</a-link>
          </template>
        </a-form-item>

        <a-form-item>
          <div class="login-options">
            <a-checkbox v-model="form.remember">
              记住登录状态
            </a-checkbox>
            <div class="platform-selector-inline">
              <a-radio-group v-model="selectedPlatform" type="button" size="small">
                <a-radio value="job" class="platform-radio">
                  <span class="platform-radio-content">
                    <IconApps :size="14" />
                    <span>作业平台</span>
                  </span>
                </a-radio>
                <a-radio value="ops" class="platform-radio">
                  <span class="platform-radio-content">
                    <IconTool :size="14" />
                    <span>运维台</span>
                  </span>
                </a-radio>
              </a-radio-group>
            </div>
          </div>
        </a-form-item>

        <a-form-item>
          <a-button
            type="primary"
            html-type="submit"
            size="large"
            long
            :loading="loading"
          >
            登录
          </a-button>
        </a-form-item>
      </a-form>
    </div>

    <!-- 2FA帮助对话框 -->
    <a-modal
      v-model:visible="showOtpHelp"
      title="双因子认证使用说明"
      :footer="false"
      width="500px"
    >
      <div class="otp-help">
        <p>1. 如果您已启用双因子认证，请在登录时输入6位验证码</p>
        <p>2. 验证码来自您的认证器应用（如 Google Authenticator、Microsoft Authenticator 等）</p>
        <p>3. 验证码每30秒自动更新</p>
        <p>4. 如果丢失了认证器，可以使用备份码登录</p>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, onMounted, computed, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import { IconApps, IconTool, IconUser, IconLock, IconSafe, IconRefresh } from '@arco-design/web-vue/es/icon'
import { useAuthStore } from '@/stores/auth'
import { authApi, captchaApi } from '@/api/auth'
import type { LoginParams, AuthConfig } from '@/types'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const formRef = ref()
const loading = ref(false)
const authConfig = ref<AuthConfig>({
  captcha_enabled: false,
  ldap_enabled: false,
  two_factor_enabled: false,
})
const captchaImage = ref<string>('')
const showOtpInput = ref(false)
const showOtpHelp = ref(false)
const loginType = ref<'normal' | 'ldap'>('normal')
const selectedPlatform = ref<'job' | 'ops'>('job')

// 表单数据
const form = reactive<LoginParams & { remember: boolean }>({
  username: '',
  password: '',
  captcha_key: '',
  captcha_value: '',
  otp_token: '',
  remember: false,
})

// 表单验证规则
const rules = computed(() => {
  const baseRules: any = {
    username: [
      { required: true, message: '请输入用户名' },
      { minLength: 2, message: '用户名至少2个字符' },
    ],
    password: [
      { required: true, message: '请输入密码' },
      { minLength: 6, message: '密码至少6个字符' },
    ],
  }

  if (authConfig.value.captcha_enabled) {
    baseRules.captcha_value = [
      { required: true, message: '请输入验证码' },
    ]
  }

  if (showOtpInput.value) {
    baseRules.otp_token = [
      { required: true, message: '请输入双因子验证码' },
      { length: 6, message: '验证码为6位数字' },
    ]
  }

  return baseRules
})

// 获取认证配置
const fetchAuthConfig = async () => {
  try {
    const config = await authApi.getAuthConfig()
    authConfig.value = config
    
    // 如果启用验证码，自动获取验证码
    if (config.captcha_enabled) {
      await refreshCaptcha()
    }
  } catch (error: any) {
    console.error('获取认证配置失败:', error)
    // 如果获取配置失败，使用默认配置（所有功能禁用）
    // 这样至少可以让用户尝试登录
    authConfig.value = {
      captcha_enabled: false,
      ldap_enabled: false,
      two_factor_enabled: false,
    }
  }
}

// 刷新验证码
const refreshCaptcha = async () => {
  try {
    const result = await captchaApi.getCaptcha()
    if (result.enabled && result.captcha_key && result.captcha_image) {
      form.captcha_key = result.captcha_key
      // 如果是相对路径，转换为绝对路径
      if (result.captcha_image.startsWith('/')) {
        captchaImage.value = `${window.location.origin}${result.captcha_image}`
      } else {
        captchaImage.value = result.captcha_image
      }
      form.captcha_value = ''
    }
  } catch (error) {
    console.error('获取验证码失败:', error)
    Message.error('获取验证码失败')
  }
}

// 提交登录
const handleSubmit = async (data: { values: LoginParams; errors: any }) => {
  if (data.errors) return
  
  loading.value = true
  try {
    // 如果还没有显示OTP输入框，且启用了2FA，先检查用户是否需要2FA
    if (!showOtpInput.value && authConfig.value.two_factor_enabled) {
      try {
        const checkResult = await authApi.check2FARequired({
          username: form.username,
          password: form.password,
        })
        
        if (checkResult.requires_2fa) {
          // 用户启用了2FA，显示OTP输入框
          showOtpInput.value = true
          Message.warning('该账户已启用双因子认证，请输入验证码')
          loading.value = false
          return
        }
      } catch (error: any) {
        // 如果检查失败（可能是用户名或密码错误），继续尝试登录
        // 让登录接口返回具体错误信息
        console.warn('检查2FA状态失败:', error)
      }
    }

    // 构建登录数据
    const loginData: LoginParams = {
      username: form.username,
      password: form.password,
      remember: form.remember,
    }

    // 验证码和2FA互斥：如果启用了2FA，就不使用验证码
    if (authConfig.value.captcha_enabled && !authConfig.value.two_factor_enabled) {
      loginData.captcha_key = form.captcha_key
      loginData.captcha_value = form.captcha_value
    }

    // 如果显示OTP输入框，添加OTP字段
    if (showOtpInput.value && authConfig.value.two_factor_enabled) {
      loginData.otp_token = form.otp_token
    }

    try {
      await authStore.login(loginData)
      // 等待 Vue 微任务队列让 authStore 更新用户信息，避免随后读取 user 时发生竞态
      await nextTick()
      Message.success('登录成功')
      
      // 记住用户选择的平台
      // 检查用户权限
      const user = authStore.user
      if (selectedPlatform.value === 'ops' && !user?.is_superuser) {
        // 非超级管理员不能访问运维台
        Message.warning('您没有权限访问运维台，仅超级管理员可访问')
        selectedPlatform.value = 'job'
      }
      
      localStorage.setItem('selected_platform', selectedPlatform.value)
      sessionStorage.setItem('selected_platform', selectedPlatform.value)
      
      // 根据选择的平台跳转
      const redirect = route.query.redirect as string | undefined
      let target = redirect
      if (selectedPlatform.value === 'ops') {
        // 运维台强制落在运维台首页，避免带着作业平台的 redirect 误跳转
        target = '/ops/dashboard'
      } else {
        target = target || '/dashboard'
      }
      router.push(target)
    } catch (error: any) {
      // 检查是否是2FA错误
      if (error.response?.data?.errors?.otp_token || 
          error.message?.includes('双因子') || 
          error.message?.includes('验证码')) {
        // 需要2FA验证
        if (authConfig.value.two_factor_enabled) {
          showOtpInput.value = true
          Message.warning('请输入双因子验证码')
          loading.value = false
          return
        }
      }
      
      // 其他错误，刷新验证码（仅当启用验证码且未启用2FA时）
      if (authConfig.value.captcha_enabled && !authConfig.value.two_factor_enabled) {
        await refreshCaptcha()
      }
      throw error
    }
  } catch (error: any) {
    console.error('登录失败:', error)
    const errorMessage = error.response?.data?.message || error.message || '登录失败，请检查用户名和密码'
    Message.error(errorMessage)
  } finally {
    loading.value = false
  }
}

// 初始化
onMounted(() => {
  fetchAuthConfig()
  
  // 恢复上次选择的平台
  const savedPlatform = localStorage.getItem('selected_platform') || sessionStorage.getItem('selected_platform')
  if (savedPlatform === 'ops' || savedPlatform === 'job') {
    selectedPlatform.value = savedPlatform
  }
})
</script>

<style scoped>
.login-container {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.login-box {
  width: 400px;
  padding: 40px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
}

.login-header {
  text-align: center;
  margin-bottom: 32px;
}

.login-header h1 {
  font-size: 24px;
  font-weight: 600;
  color: #1d2129;
  margin-bottom: 8px;
}

.login-header p {
  font-size: 14px;
  color: #86909c;
}

.login-options {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  margin-bottom: 16px;
  gap: 16px;
}

.login-options :deep(.arco-checkbox) {
  flex-shrink: 0;
  white-space: nowrap;
}

.platform-selector-inline {
  display: flex;
  align-items: center;
  flex-shrink: 0;
  min-width: 0;
}

.platform-selector-inline :deep(.arco-radio-group) {
  display: inline-flex;
  white-space: nowrap;
  min-width: 0;
}

.platform-selector-inline :deep(.arco-radio-button) {
  display: inline-flex;
  align-items: center;
  font-size: 12px;
  padding: 2px 8px;
  height: 24px;
  line-height: 20px;
  white-space: nowrap;
  flex-shrink: 0;
}

.platform-selector-inline :deep(.arco-radio-button-content) {
  display: inline-flex;
  align-items: center;
  white-space: nowrap;
}

.platform-radio-content {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  white-space: nowrap;
}

.login-tabs {
  margin-bottom: 24px;
}

.login-tabs :deep(.arco-tabs-nav) {
  margin-bottom: 0;
}

.captcha-container {
  display: flex;
  gap: 8px;
  align-items: center;
}

.captcha-image {
  width: 120px;
  height: 40px;
  border: 1px solid #d9d9d9;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f7f8fa;
  cursor: pointer;
  transition: all 0.3s;
}

.captcha-image:hover {
  border-color: #165dff;
  background: #f2f3ff;
}

.captcha-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  color: #86909c;
}

.otp-help {
  line-height: 1.8;
  color: #4e5969;
}

.otp-help p {
  margin: 8px 0;
}
</style>
