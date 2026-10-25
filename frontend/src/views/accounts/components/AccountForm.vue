<template>
  <n-modal
    v-model:show="modalVisible"
    :title="isEdit ? '编辑账号' : '新建账号'"
    preset="dialog"
    style="width: 600px"
    :positive-text="isEdit ? '保存' : '创建'"
    negative-text="取消"
    :loading="loading"
    @positive-click="handleSubmit"
    @negative-click="handleCancel"
  >
    <n-form ref="formRef" :model="form" :rules="rules" label-placement="top">
      <n-form-item label="账号名称" path="name">
        <n-input
          v-model:value="form.name"
          placeholder="请输入账号名称，如：Root管理员、开发账号等"
          maxlength="100"
          show-count
          clearable
        />
      </n-form-item>
      <n-form-item label="用户名" path="username">
        <n-input
          v-model:value="form.username"
          placeholder="请输入系统用户名，如：root、admin、user01等"
          maxlength="50"
          show-count
          clearable
        />
      </n-form-item>
      <n-form-item label="认证方式" path="auth_type">
        <n-radio-group v-model:value="authType" @update:value="handleAuthTypeChange">
          <n-radio value="password">密码认证</n-radio>
          <n-radio value="key">密钥认证</n-radio>
        </n-radio-group>
      </n-form-item>
      <n-form-item v-if="authType === 'password' || authType === 'both'" label="密码" path="password">
        <n-input
          v-model:value="form.password"
          type="password"
          placeholder="请输入登录密码"
          show-password-on="click"
          clearable
        />
        <div class="form-tip"><Info :size="14" /><span>密码将加密存储，编辑时留空表示不修改</span></div>
      </n-form-item>
      <n-form-item v-if="authType === 'key' || authType === 'both'" label="SSH私钥" path="private_key">
        <n-input
          v-model:value="form.private_key"
          type="textarea"
          placeholder="请粘贴SSH私钥内容，格式如：&#10;-----BEGIN RSA PRIVATE KEY-----&#10;...&#10;-----END RSA PRIVATE KEY-----"
          :autosize="{ minRows: 8, maxRows: 12 }"
          maxlength="10000"
          show-count
        />
        <div class="form-tip"><Info :size="14" /><span>私钥将加密存储，编辑时留空表示不修改</span></div>
      </n-form-item>
      <n-form-item label="描述" path="description">
        <n-input
          v-model:value="form.description"
          type="textarea"
          placeholder="请输入账号描述信息"
          :autosize="{ minRows: 3, maxRows: 6 }"
          maxlength="500"
          show-count
        />
      </n-form-item>
    </n-form>
  </n-modal>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { NForm, NFormItem, NInput, NModal, NRadio, NRadioGroup, type FormInst, useMessage } from 'naive-ui'
import { Info } from 'lucide-vue-next'
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
const message = useMessage()
const loading = ref(false)
const formRef = ref<FormInst | null>(null)
const authType = ref<'password' | 'key' | 'both'>('password')
const modalVisible = computed({
  get: () => props.visible,
  set: (value: boolean) => emit('update:visible', value),
})
const isEdit = computed(() => !!props.account?.id)
const form = reactive({
  name: '',
  username: '',
  password: '',
  private_key: '',
  description: '',
})
const rules = {
  name: [
    { required: true, message: '请输入账号名称', trigger: ['blur', 'input'] },
    { max: 100, message: '账号名称不能超过100个字符', trigger: ['blur', 'input'] },
  ],
  username: [
    { required: true, message: '请输入用户名', trigger: ['blur', 'input'] },
    { max: 50, message: '用户名不能超过50个字符', trigger: ['blur', 'input'] },
    {
      pattern: /^[a-zA-Z0-9_-]+$/,
      message: '用户名只能包含字母、数字、下划线和连字符',
      trigger: ['blur', 'input'],
    },
  ],
}

const resetForm = () => {
  form.name = ''
  form.username = ''
  form.password = ''
  form.private_key = ''
  form.description = ''
  authType.value = 'password'
  formRef.value?.restoreValidation()
}

watch(() => props.account, (account) => {
  if (!account) { resetForm(); return }
  form.name = account.name
  form.username = account.username
  form.password = ''
  form.private_key = ''
  form.description = account.description || ''
  authType.value = account.has_private_key ? 'key' : 'password'
  formRef.value?.restoreValidation()
}, { immediate: true })

const handleAuthTypeChange = () => {
  if (authType.value === 'password') form.private_key = ''
  if (authType.value === 'key') form.password = ''
}

const handleSubmit = async () => {
  if (!formRef.value) { message.error('表单初始化失败'); return false }
  if (!form.name.trim()) { message.error('请输入账号名称'); return false }
  if (!form.username.trim()) { message.error('请输入用户名'); return false }
  if (!isEdit.value && authType.value === 'password' && !form.password) { message.error('请输入密码'); return false }
  if (!isEdit.value && authType.value === 'key' && !form.private_key) { message.error('请输入SSH私钥'); return false }
  if (isEdit.value && form.password && form.private_key) { message.error('密码和私钥只能填写一个'); return false }
  if (isEdit.value && authType.value === 'password') form.private_key = ''
  if (isEdit.value && authType.value === 'key') form.password = ''
  try { await formRef.value.validate() } catch { return false }
  loading.value = true
  try {
    const submitData: Partial<ServerAccount> = { name: form.name, username: form.username, description: form.description }
    if ((authType.value === 'password' || authType.value === 'both') && form.password) submitData.password = form.password
    if ((authType.value === 'key' || authType.value === 'both') && form.private_key) submitData.private_key = form.private_key
    if (isEdit.value) { await accountApi.updateAccount(props.account!.id!, submitData); message.success('账号更新成功') }
    else { await accountApi.createAccount(submitData as ServerAccount); message.success('账号创建成功') }
    emit('success'); modalVisible.value = false; return true
  } catch (error) { console.error('提交失败:', error); message.error(isEdit.value ? '账号更新失败' : '账号创建失败'); return false }
  finally { loading.value = false }
}

const handleCancel = () => { modalVisible.value = false }
</script>

<style scoped>
.form-tip { display: flex; align-items: center; gap: 4px; margin-top: 4px; font-size: 12px; color: var(--color-text-3); }
:deep(.n-input--textarea) { font-family: 'Courier New', monospace; font-size: 12px; }
</style>
