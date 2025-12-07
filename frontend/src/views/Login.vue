<template>
  <div class="login-container">
    <div class="login-box">
      <div class="login-header">
        <h1>运维作业平台</h1>
      </div>
      
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
              <icon-user />
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
              <icon-lock />
            </template>
          </a-input-password>
        </a-form-item>

        <!-- 验证码 -->
        <a-form-item
          v-if="authConfig.captcha_enabled"
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
                <icon-safe />
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
                <icon-refresh :size="20" />
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
              <icon-lock />
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
import { reactive, ref, onMounted, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Message } from '@arco-design/web-vue'
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
    // 第一次尝试登录（不包含OTP）
    const loginData: LoginParams = {
      username: form.username,
      password: form.password,
      remember: form.remember,
    }

    // 如果启用验证码，添加验证码字段
    if (authConfig.value.captcha_enabled) {
      loginData.captcha_key = form.captcha_key
      loginData.captcha_value = form.captcha_value
    }

    // 如果显示OTP输入框，添加OTP字段
    if (showOtpInput.value) {
      loginData.otp_token = form.otp_token
    }

    try {
      await authStore.login(loginData)
      Message.success('登录成功')

      // 跳转到目标页面或首页
      const redirect = route.query.redirect as string
      router.push(redirect || '/dashboard')
    } catch (error: any) {
      // 检查是否是2FA错误
      if (error.response?.data?.errors?.otp_token ||
          error.message?.includes('双因子') ||
          error.message?.includes('验证码')) {
        // 需要2FA验证
        if (authConfig.value.two_factor_enabled) {
          showOtpInput.value = true
          Message.warning('请输入双因子验证码')
          // 刷新验证码（如果启用）
          if (authConfig.value.captcha_enabled) {
            await refreshCaptcha()
          }
          return
        }
      }

      // 其他错误，刷新验证码
      if (authConfig.value.captcha_enabled) {
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
  margin-bottom: 16px;
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
