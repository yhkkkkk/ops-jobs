<template>
  <a-modal
    v-model:visible="modalVisible"
    :title="isEdit ? '编辑账号' : '新建账号'"
    width="600px"
    @cancel="handleCancel"
    @ok="handleSubmit"
    :confirm-loading="loading"
  >
    <a-form
      ref="formRef"
      :model="form"
      :rules="rules"
      layout="vertical"
      @submit="handleSubmit"
    >
      <a-form-item label="账号名称" field="name" required>
        <a-input
          v-model="form.name"
          placeholder="请输入账号名称，如：Root管理员、开发账号等"
          :max-length="100"
        />
      </a-form-item>

      <a-form-item label="用户名" field="username" required>
        <a-input
          v-model="form.username"
          placeholder="请输入系统用户名，如：root、admin、user01等"
          :max-length="50"
        />
      </a-form-item>

      <a-form-item label="认证方式" field="auth_type">
        <a-radio-group v-model="authType" @change="handleAuthTypeChange">
          <a-radio value="password">密码认证</a-radio>
          <a-radio value="key">密钥认证</a-radio>
          <a-radio value="both">密码+密钥</a-radio>
        </a-radio-group>
      </a-form-item>

      <a-form-item
        v-if="authType === 'password' || authType === 'both'"
        label="密码"
        field="password"
        :required="authType === 'password'"
      >
        <a-input-password
          v-model="form.password"
          placeholder="请输入登录密码"
          :visibility-toggle="true"
        />
        <div class="form-tip">
          <icon-info-circle />
          密码将加密存储，编辑时留空表示不修改
        </div>
      </a-form-item>

      <a-form-item
        v-if="authType === 'key' || authType === 'both'"
        label="SSH私钥"
        field="private_key"
        :required="authType === 'key'"
      >
        <a-textarea
          v-model="form.private_key"
          placeholder="请粘贴SSH私钥内容，格式如：&#10;-----BEGIN RSA PRIVATE KEY-----&#10;...&#10;-----END RSA PRIVATE KEY-----"
          :rows="8"
          :max-length="10000"
        />
        <div class="form-tip">
          <icon-info-circle />
          私钥将加密存储，编辑时留空表示不修改
        </div>
      </a-form-item>

      <a-form-item label="描述" field="description">
        <a-textarea
          v-model="form.description"
          placeholder="请输入账号描述信息"
          :rows="3"
          :max-length="500"
        />
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { Message } from '@arco-design/web-vue'
import { accountApi, type ServerAccount } from '@/api/account'

interface Props {
  visible: boolean
  account?: ServerAccount | null
}

interface Emits {
  (e: 'update:visible', visible: boolean): void
  (e: 'success'): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

// 响应式数据
const loading = ref(false)
const formRef = ref()
const authType = ref('password')

// 计算属性
const modalVisible = computed({
  get: () => props.visible,
  set: (value) => emit('update:visible', value)
})

const isEdit = computed(() => !!props.account?.id)

// 表单数据
const form = reactive({
  name: '',
  username: '',
  password: '',
  private_key: '',
  description: ''
})

// 表单验证规则
const rules = {
  name: [
    { required: true, message: '请输入账号名称' },
    { max: 100, message: '账号名称不能超过100个字符' }
  ],
  username: [
    { required: true, message: '请输入用户名' },
    { max: 50, message: '用户名不能超过50个字符' },
    {
      pattern: /^[a-zA-Z0-9_-]+$/,
      message: '用户名只能包含字母、数字、下划线和连字符'
    }
  ]
}

// 重置表单
const resetForm = () => {
  form.name = ''
  form.username = ''
  form.password = ''
  form.private_key = ''
  form.description = ''
  authType.value = 'password'
}

// 监听账号数据变化
watch(
  () => props.account,
  (account) => {
    if (account) {
      // 编辑模式，填充表单数据
      form.name = account.name
      form.username = account.username
      form.password = ''  // 编辑时不显示密码
      form.private_key = ''  // 编辑时不显示私钥
      form.description = account.description || ''

      // 根据现有认证信息设置认证方式
      if (account.password && account.private_key) {
        authType.value = 'both'
      } else if (account.private_key) {
        authType.value = 'key'
      } else {
        authType.value = 'password'
      }
    } else {
      // 新建模式，重置表单
      resetForm()
    }
  },
  { immediate: true }
)

// 认证方式变化处理
const handleAuthTypeChange = () => {
  // 清空不需要的认证信息
  if (authType.value === 'password') {
    form.private_key = ''
  } else if (authType.value === 'key') {
    form.password = ''
  }
}

// 提交表单
const handleSubmit = async () => {
  try {
    // 验证表单

    if (!formRef.value) {
      Message.error('表单初始化失败')
      return
    }

    // 手动验证必填字段
    if (!form.name.trim()) {
      Message.error('请输入账号名称')
      return
    }

    if (!form.username.trim()) {
      Message.error('请输入用户名')
      return
    }

    // 验证认证信息
    if (!isEdit.value) {
      if (authType.value === 'password' && !form.password) {
        Message.error('请输入密码')
        return
      }

      if (authType.value === 'key' && !form.private_key) {
        Message.error('请输入SSH私钥')
        return
      }

      if (authType.value === 'both' && !form.password && !form.private_key) {
        Message.error('请至少输入密码或SSH私钥')
        return
      }
    }

    try {
      await formRef.value.validate()
    } catch (error) {
      console.log('表单验证失败:', error)
      return
    }

    loading.value = true

    // 准备提交数据
    const submitData: Partial<ServerAccount> = {
      name: form.name,
      username: form.username,
      description: form.description
    }

    // 根据认证方式添加认证信息
    if (authType.value === 'password' || authType.value === 'both') {
      if (form.password) {
        submitData.password = form.password
      }
    }

    if (authType.value === 'key' || authType.value === 'both') {
      if (form.private_key) {
        submitData.private_key = form.private_key
      }
    }

    // 提交数据
    if (isEdit.value) {
      await accountApi.updateAccount(props.account!.id!, submitData)
      Message.success('账号更新成功')
    } else {
      await accountApi.createAccount(submitData as ServerAccount)
      Message.success('账号创建成功')
    }

    emit('success')
    modalVisible.value = false
  } catch (error) {
    console.error('提交失败:', error)
    Message.error(isEdit.value ? '账号更新失败' : '账号创建失败')
  } finally {
    loading.value = false
  }
}

// 取消操作
const handleCancel = () => {
  modalVisible.value = false
}
</script>

<style scoped>
.form-tip {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 4px;
  font-size: 12px;
  color: var(--color-text-3);
}

:deep(.arco-textarea) {
  font-family: 'Courier New', monospace;
  font-size: 12px;
}
</style>
