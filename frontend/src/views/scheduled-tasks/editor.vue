<template>
  <div class="page">
    <div class="page-header">
      <div class="header-content">
        <div class="header-left">
          <a-button type="text" @click="handleCancel">
            <template #icon>
              <icon-arrow-left />
            </template>
            返回
          </a-button>
          <div class="header-info">
            <h2>{{ isEdit ? '编辑定时任务' : '创建定时任务' }}</h2>
            <p class="header-desc">
              {{ isEdit ? '调整触发规则与执行方案' : '配置周期规则并选择执行方案' }}
            </p>
          </div>
        </div>
        <div class="header-right">
          <a-space>
            <a-button @click="handleCancel">取消</a-button>
            <a-button type="primary" :loading="saving" @click="handleSave">
              {{ isEdit ? '更新' : '创建' }}
            </a-button>
          </a-space>
        </div>
      </div>
    </div>

    <a-card>
      <a-form
        ref="formRef"
        :model="form"
        :rules="rules"
        layout="vertical"
        @submit="handleSave"
      >
        <a-row :gutter="24">
          <a-col :span="12">
            <a-form-item label="任务名称" field="name" required>
              <a-input
                v-model="form.name"
                placeholder="请输入任务名称"
                :max-length="200"
                show-word-limit
              />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="状态" field="is_active">
              <a-switch
                v-model="form.is_active"
                checked-text="启用"
                unchecked-text="禁用"
              />
            </a-form-item>
          </a-col>
        </a-row>

        <a-form-item label="描述" field="description">
          <a-textarea
            v-model="form.description"
            placeholder="请输入任务描述"
            :max-length="500"
            show-word-limit
            :auto-size="{ minRows: 3, maxRows: 6 }"
          />
        </a-form-item>

        <a-form-item label="执行方案" field="execution_plan" required>
          <a-select
            v-model="form.execution_plan"
            placeholder="请选择执行方案"
            :loading="loadingPlans"
            allow-search
            @search="handleSearchPlans"
            @change="handleExecutionPlanChange"
          >
            <a-option
              v-for="plan in executionPlans"
              :key="plan.id"
              :value="plan.id"
              :label="`${plan.template_name} - ${plan.name}`"
            >
              <div>
                <div>{{ plan.name }}</div>
                <div style="color: #86909c; font-size: 12px">
                  模板: {{ plan.template_name }}
                </div>
              </div>
            </a-option>
          </a-select>
        </a-form-item>

        <a-form-item label="Agent-Server" required>
          <a-select
            v-model="selectedAgentServerId"
            placeholder="请选择 Agent-Server"
            allow-clear
            allow-search
            :loading="agentServerLoading"
            :filter-option="filterAgentServerOption"
          >
            <a-option
              v-for="server in agentServers"
              :key="server.id"
              :value="server.id"
              :label="`${server.name} (${server.base_url})`"
            >
              {{ server.name }} ({{ server.base_url }})
            </a-option>
          </a-select>
        </a-form-item>

        <!-- 全局变量覆盖 -->
        <a-form-item v-if="form.execution_plan && globalParameters.length > 0" label="全局变量覆盖（可选）">
          <div class="global-parameters-override">
            <div class="form-tip">
              <icon-info-circle />
              可以覆盖执行方案的默认全局变量，不填写则使用执行方案的默认值
            </div>
            <div
              v-for="(param, index) in globalParameters"
              :key="index"
              class="parameter-override-item"
            >
              <div class="parameter-content">
                <div class="parameter-row">
                  <div class="parameter-key">
                    <div class="param-key-label">{{ param.key }}</div>
                    <a-tag v-if="param.type === 'secret'" size="small" color="orange" style="margin-left: 8px">
                      密文
                    </a-tag>
                  </div>
                  <div class="parameter-value">
                    <template v-if="param.type === 'host_list'">
                      <div class="host-override-field">
                        <div class="host-override-summary">
                          <span>已选 {{ getOverrideHostCount(param.overrideValue) }} 台主机</span>
                          <span class="host-override-default">默认 {{ getHostListCount(param.defaultValue) }} 台主机</span>
                        </div>
                        <a-space>
                          <a-button type="outline" size="small" @click="openHostSelector(param.key)">选择主机</a-button>
                          <a-button type="text" size="small" @click="clearHostOverride(param)">清空</a-button>
                        </a-space>
                      </div>
                    </template>
                    <template v-else>
                      <a-input
                        v-model="param.overrideValue"
                        :type="param.type === 'secret' && !parameterVisibility[param.key] ? 'password' : 'text'"
                        :placeholder="param.type === 'secret' ? '密文覆盖值（留空使用默认值）' : `覆盖值（留空使用默认值: ${formatParameterValue(param.defaultValue, param.type)}）`"
                      />
                      <a-button
                        v-if="param.type === 'secret'"
                        type="text"
                        size="small"
                        @click="toggleParameterVisibility(param.key)"
                        class="visibility-toggle"
                      >
                        <template #icon>
                          <icon-eye v-if="parameterVisibility[param.key]" />
                          <icon-eye-invisible v-else />
                        </template>
                      </a-button>
                    </template>
                  </div>
                </div>
                <div class="parameter-description">
                  <div v-if="param.description" class="param-description-text">{{ param.description }}</div>
                  <div class="param-default">
                    <span class="label">默认值:</span>
                    <span class="value">{{ formatParameterValue(param.defaultValue, param.type) }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </a-form-item>

        <HostSelector
          v-model:visible="hostSelectorVisible"
          :hosts="hostSelectorHosts"
          :groups="hostSelectorGroups"
          :selected-hosts="currentSelectedHosts"
          :selected-groups="[]"
          :host-pagination="hostSelectorPagination"
          :enable-host-pagination="false"
          show-preview
          show-copy
          @confirm="handleHostSelectConfirm"
          @host-page-change="handleHostPageChange"
          @host-page-size-change="handleHostPageSizeChange"
        />

        <a-row :gutter="24">
          <a-col :span="16">
            <a-form-item label="Cron表达式" field="cron_expression" required>
              <a-input-group>
                <a-input
                  v-model="form.cron_expression"
                  placeholder="例如: 0 2 * * * (每天凌晨2点)"
                  style="width: calc(100% - 100px)"
                  @blur="handleCronValidation"
                />
                <a-button
                  type="outline"
                  style="width: 100px"
                  @click="showCronHelper = true"
                >
                  辅助工具
                </a-button>
              </a-input-group>
              <div v-if="cronDescription" class="cron-description">
                <icon-info-circle />
                {{ cronDescription }}
              </div>
              <div v-if="cronError" class="cron-error">
                <icon-exclamation-circle />
                {{ cronError }}
              </div>
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="时区" field="timezone">
              <a-select
                v-model="form.timezone"
                placeholder="请选择时区"
                allow-search
              >
                <a-option value="Asia/Shanghai">Asia/Shanghai (北京时间)</a-option>
                <a-option value="UTC">UTC (协调世界时)</a-option>
                <a-option value="America/New_York">America/New_York (纽约时间)</a-option>
                <a-option value="Europe/London">Europe/London (伦敦时间)</a-option>
                <a-option value="Asia/Tokyo">Asia/Tokyo (东京时间)</a-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>

        <!-- 下次执行时间预览 -->
        <a-form-item v-if="nextRuns.length > 0" label="下次执行时间预览">
          <a-card size="small">
            <div class="next-runs">
              <div v-for="(time, index) in nextRuns" :key="index" class="next-run-item">
                <icon-clock-circle />
                {{ formatDateTime(time) }}
              </div>
            </div>
          </a-card>
        </a-form-item>
      </a-form>
    </a-card>

    <!-- Cron表达式辅助工具 -->
    <a-modal
      v-model:visible="showCronHelper"
      title="Cron表达式辅助工具"
      width="800px"
      @ok="handleCronHelperOk"
    >
      <cron-builder v-model="tempCronExpression" />
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import type { FormInstance } from '@arco-design/web-vue'
import {
  IconArrowLeft,
  IconInfoCircle,
  IconExclamationCircle,
  IconClockCircle,
  IconEye,
  IconEyeInvisible
} from '@arco-design/web-vue/es/icon'
import { scheduledJobApi, executionPlanApi, cronApi } from '@/api/scheduler'
import { hostApi, hostGroupApi } from '@/api/ops'
import { agentServerApi } from '@/api/agents'
import HostSelector from '@/components/HostSelector.vue'
import CronBuilder from './components/CronBuilder.vue'

type ExecutionPlanOption = {
  id: number
  name: string
  template_name?: string
}

type GlobalParam = {
  key: string
  defaultValue: any
  description?: string
  type?: 'secret' | 'text' | string
  overrideValue: any
}

const route = useRoute()
const router = useRouter()
const presetPlanId = computed(() => route.query.plan_id ? Number(route.query.plan_id) : undefined)

// 响应式数据
const formRef = ref<FormInstance>()
const saving = ref(false)
const loadingPlans = ref(false)
const executionPlans = ref<ExecutionPlanOption[]>([])
const cronDescription = ref('')
const cronError = ref('')
const nextRuns = ref([])
const showCronHelper = ref(false)
const tempCronExpression = ref('')

const agentServers = ref<any[]>([])
const selectedAgentServerId = ref<number | null>(null)
const agentServerLoading = ref(false)

// 判断是否为编辑模式
const isEdit = computed(() => !!route.params.id)

const currentSelectedHosts = computed(() => {
  const key = currentHostParamKey.value
  if (!key) return []
  const param = globalParameters.value.find(item => item.key === key)
  if (!param) return []
  return Array.isArray(param.overrideValue) ? param.overrideValue : []
})

// 表单数据
const form = reactive<{
  name: string
  description: string
  execution_plan: number | undefined
  cron_expression: string
  timezone: string
  is_active: boolean
  execution_parameters: Record<string, any>
}>({
  name: '',
  description: '',
  execution_plan: undefined,
  cron_expression: '',
  timezone: 'Asia/Shanghai',
  is_active: false,
  execution_parameters: {}
})

// 全局变量覆盖
const globalParameters = ref<GlobalParam[]>([])
const loadingPlanDetail = ref(false)
const parameterVisibility = ref<Record<string, boolean>>({})
const hostSelectorVisible = ref(false)
const hostSelectorHosts = ref<any[]>([])
const hostSelectorGroups = ref<any[]>([])
const hostSelectorPagination = ref({
  current: 1,
  pageSize: 10,
  total: 0,
  pageSizeOptions: ['10']
})
const currentHostParamKey = ref<string | null>(null)
const allHostsLoaded = ref(false)

// 表单验证规则
const rules = {
  name: [
    { required: true, message: '请输入任务名称' },
    { max: 200, message: '任务名称不能超过200个字符' }
  ],
  execution_plan: [
    { required: true, message: '请选择执行方案' }
  ],
  cron_expression: [
    { required: true, message: '请输入Cron表达式' }
  ]
}



const fetchAgentServers = async () => {
  try {
    agentServerLoading.value = true
    const response = await agentServerApi.getAgentServers({ page_size: 200, is_active: true })
    agentServers.value = response?.results || []
  } catch (error) {
    console.error('获取Agent-Server列表失败:', error)
    agentServers.value = []
  } finally {
    agentServerLoading.value = false
  }
}

const filterAgentServerOption = (inputValue: string, option: any) => {
  const label = option?.label || ''
  return label.toLowerCase().includes((inputValue || '').toLowerCase())
}

// 获取执行方案列表
const fetchExecutionPlans = async (search = '') => {
  loadingPlans.value = true
  try {
    const params: any = { page_size: 20 }
    if (search) {
      params.search = search
    }

    const response = await executionPlanApi.list(params)
    executionPlans.value = response.results || []
  } catch (error) {
    console.error('获取执行方案列表失败:', error)
    Message.error('获取执行方案列表失败')
  } finally {
    loadingPlans.value = false
  }
}

// 搜索执行方案
const handleSearchPlans = (search) => {
  fetchExecutionPlans(search)
}

// 处理执行方案变化
const handleExecutionPlanChange = async (planId) => {
  if (!planId) {
    globalParameters.value = []
    return
  }

  loadingPlanDetail.value = true
  try {
    const response = await executionPlanApi.get(planId)
    const plan = response

    // 确保下拉列表包含当前选择的方案（来自外部跳转时可能不在默认列表中）
    if (!executionPlans.value.some(p => p.id === planId)) {
      executionPlans.value.unshift({
        id: plan.id,
        name: plan.name,
        template_name: plan.template_name
      })
    }

    // 获取执行方案的全局变量
    const templateGlobalParams = plan.template_global_parameters || {}
    
    // 构建全局变量列表
    globalParameters.value = Object.keys(templateGlobalParams).map(key => {
      const paramValue = templateGlobalParams[key]
      const defaultValue = typeof paramValue === 'object' && paramValue !== null
        ? paramValue.value
        : paramValue
      const description = typeof paramValue === 'object' && paramValue !== null
        ? paramValue.description
        : ''
      let type = typeof paramValue === 'object' && paramValue !== null
        ? paramValue.type
        : 'text'
      if (!type || type === 'text') {
        if (Array.isArray(defaultValue) && defaultValue.length > 0 && defaultValue.every(item => isNumeric(item))) {
          type = 'host_list'
        }
      }

      // 初始化可见性状态（密文默认隐藏）
      parameterVisibility.value[key] = type !== 'secret'

      return {
        key,
        defaultValue,
        description,
        type,
        overrideValue: (form.execution_parameters && Object.prototype.hasOwnProperty.call(form.execution_parameters, key))
          ? form.execution_parameters[key]
          : (type === 'host_list' ? [] : '')
      }
    })
  } catch (error) {
    console.error('获取执行方案详情失败:', error)
    Message.error('获取执行方案详情失败')
    globalParameters.value = []
  } finally {
    loadingPlanDetail.value = false
  }
}

const getHostListCount = (value: any) => {
  if (Array.isArray(value)) return value.length
  return 0
}

const getOverrideHostCount = (value: any) => {
  if (Array.isArray(value)) return value.length
  return 0
}

const openHostSelector = async (key: string) => {
  currentHostParamKey.value = key
  await ensureHostsLoaded()
  hostSelectorVisible.value = true
}

const clearHostOverride = (param: GlobalParam) => {
  param.overrideValue = []
}

const handleHostSelectConfirm = (payload: { hosts?: any[] }) => {
  if (!currentHostParamKey.value) {
    hostSelectorVisible.value = false
    return
  }
  const param = globalParameters.value.find(item => item.key === currentHostParamKey.value)
  if (!param) {
    hostSelectorVisible.value = false
    return
  }
  const hosts = payload.hosts || []
  param.overrideValue = hosts.map((host: any) => host.id)
  hostSelectorVisible.value = false
}

const handleHostPageChange = (page: number) => {
  hostSelectorPagination.value.current = page
}

const handleHostPageSizeChange = () => {
  hostSelectorPagination.value.pageSize = 10
  hostSelectorPagination.value.current = 1
}

const fetchAllHosts = async (force = false) => {
  if (allHostsLoaded.value && !force) return
  const pageSize = 500
  const all: any[] = []
  let page = 1
  let total = 0

  while (true) {
    const resp = await hostApi.getHosts({ page, page_size: pageSize })
    const results = resp.results || []
    if (page === 1) {
      total = resp.total || 0
    }
    all.push(...results)
    if (all.length >= total || results.length === 0) {
      break
    }
    page += 1
  }

  hostSelectorHosts.value = all
  hostSelectorPagination.value.total = total || all.length
  allHostsLoaded.value = true
}

const ensureHostsLoaded = async (force = false) => {
  if (!allHostsLoaded.value || force) {
    await fetchAllHosts(force)
  }
  if (hostSelectorGroups.value.length === 0) {
    const resp = await hostGroupApi.getGroups({ page_size: 200 })
    hostSelectorGroups.value = resp.results || []
  }
}

// 格式化参数值（对密文做掩码处理）
const formatParameterValue = (value, type?: string) => {
  if (value === null || value === undefined) return ''
  if (type === 'host_list') {
    return `主机列表 (${getHostListCount(value)})`
  }
  if (typeof value === 'object' && value.type === 'secret') {
    return '******'
  }
  if (Array.isArray(value)) {
    return `列表 (${value.length})`
  }
  return String(value)
}

const isNumeric = (value: any) => {
  const str = String(value)
  return /^\\d+$/.test(str)
}

// 切换参数可见性
const toggleParameterVisibility = (key) => {
  if (!(key in parameterVisibility.value)) {
    parameterVisibility.value[key] = false
  }
  parameterVisibility.value[key] = !parameterVisibility.value[key]
}

// Cron表达式验证和描述
const handleCronValidation = async () => {
  if (!form.cron_expression) {
    cronDescription.value = ''
    cronError.value = ''
    nextRuns.value = []
    return
  }

  try {
    // 验证表达式
    await cronApi.validate(form.cron_expression)
    cronError.value = ''

    // 获取描述
    const descResponse: any = await cronApi.describe(form.cron_expression)
    cronDescription.value = descResponse.data?.description || ''

    // 获取下次执行时间
    const nextResponse: any = await cronApi.getNextRuns(form.cron_expression, 5)
    nextRuns.value = nextResponse.data?.next_runs || []
  } catch (error) {
    cronError.value = error.message || 'Cron表达式格式不正确'
    cronDescription.value = ''
    nextRuns.value = []
  }
}

// Cron辅助工具确认
const handleCronHelperOk = () => {
  form.cron_expression = tempCronExpression.value
  showCronHelper.value = false
  handleCronValidation()
}

// 保存
const handleSave = async () => {
  try {
    // ArcoDesign的validate方法：成功时resolve undefined，失败时reject错误
    await formRef.value.validate()

    if (!selectedAgentServerId.value) {
      Message.error('请选择 Agent-Server')
      return
    }

    // 构建执行参数覆盖（只包含有覆盖值的参数）
    const executionParameters: Record<string, any> = {}
    globalParameters.value.forEach(param => {
      const value = param.overrideValue
      if (Array.isArray(value)) {
        if (value.length > 0) {
          executionParameters[param.key] = value
        }
        return
      }
      if (value !== null && value !== undefined && value !== '') {
        executionParameters[param.key] = value
      }
    })
    executionParameters.agent_server_id = selectedAgentServerId.value
    form.execution_parameters = Object.keys(executionParameters).length > 0 ? executionParameters : {}

    saving.value = true

  if (isEdit.value) {
    await scheduledJobApi.update(Number(route.params.id), form)
    Message.success('更新成功')
  } else {
      await scheduledJobApi.create(form)
      Message.success('创建成功')
    }

    router.push('/scheduled-tasks')
  } catch (validationError) {
    // 如果是表单验证错误，不需要特殊处理，ArcoDesign会自动显示错误信息
    if (validationError && typeof validationError === 'object') {
      console.log('表单验证失败:', validationError)
      return
    }

    // 如果是API调用错误
    console.error('保存失败:', validationError)
    Message.error(validationError.response?.data?.message || '保存失败')
  } finally {
    saving.value = false
  }
}

// 取消
const handleCancel = () => {
  router.push('/scheduled-tasks')
}

// 加载任务数据（编辑模式）
const loadTask = async () => {
  if (!isEdit.value) return

  try {
    const response = await scheduledJobApi.get(Number(route.params.id))
    const task = response

    Object.assign(form, {
      name: task.name,
      description: task.description,
      execution_plan: task.execution_plan,
      cron_expression: task.cron_expression,
      timezone: task.timezone,
      is_active: task.is_active,
      execution_parameters: task.execution_parameters || {}
    })

    selectedAgentServerId.value = task.execution_parameters?.agent_server_id ?? null

    // 加载执行方案的全局变量
    if (task.execution_plan) {
      await handleExecutionPlanChange(task.execution_plan)
    }

    // 验证Cron表达式
    handleCronValidation()
  } catch (error) {
    console.error('加载任务数据失败:', error)
    Message.error('加载任务数据失败')
    router.push('/scheduled-tasks')
  }
}

// 工具函数
const formatDateTime = (dateTime) => {
  if (!dateTime) return '-'
  return new Date(dateTime).toLocaleString('zh-CN')
}

// 监听Cron表达式变化
watch(() => form.cron_expression, () => {
  if (form.cron_expression) {
    handleCronValidation()
  }
})

watch(showCronHelper, (visible) => {
  if (visible) {
    tempCronExpression.value = form.cron_expression || '* * * * *'
  }
})

// 生命周期
onMounted(() => {
  fetchAgentServers()
  fetchExecutionPlans().finally(async () => {
    // 新建页支持通过查询参数预填执行方案
    if (!isEdit.value && presetPlanId.value) {
      form.execution_plan = presetPlanId.value
      await handleExecutionPlanChange(presetPlanId.value)
      if (!form.name) {
        const matched = executionPlans.value.find(p => p.id === presetPlanId.value)
        form.name = matched ? `${matched.name}-定时任务` : '定时任务'
      }
    }
  })
  loadTask()
})
</script>

<style scoped>
.page {
  padding: 16px;
}

.page-header {
  background: white;
  border-radius: 6px;
  margin-bottom: 16px;
  padding: 20px 24px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.header-left {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.header-info h2 {
  margin: 0 0 4px 0;
  font-size: 20px;
  font-weight: 600;
}

.header-desc {
  margin: 0;
  color: var(--color-text-3);
  font-size: 14px;
}

.header-right {
  flex-shrink: 0;
}

.cron-description {
  margin-top: 8px;
  padding: 8px 12px;
  background-color: #f0f9ff;
  border: 1px solid #bae7ff;
  border-radius: 4px;
  color: #1890ff;
  font-size: 12px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.cron-error {
  margin-top: 8px;
  padding: 8px 12px;
  background-color: #fff2f0;
  border: 1px solid #ffccc7;
  border-radius: 4px;
  color: #f5222d;
  font-size: 12px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.next-runs {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.next-run-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: #666;
}

.next-run-item svg {
  color: #1890ff;
}

.global-parameters-override {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.global-parameters-override .form-tip {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-bottom: 0;
  font-size: 12px;
  color: var(--color-text-3);
}

.global-parameters-override .form-tip .arco-icon {
  color: var(--color-primary-6);
  font-size: 14px;
  flex-shrink: 0;
}

.parameter-override-item {
  border: 1px solid var(--color-border-2);
  border-radius: 6px;
  padding: 12px;
  background: var(--color-bg-1);
}

.parameter-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.parameter-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.parameter-key {
  flex: 0 0 300px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.param-key-label {
  font-weight: 600;
  color: var(--color-text-1);
  font-size: 14px;
}

.parameter-value {
  flex: 1;
  position: relative;
}

.parameter-value .visibility-toggle {
  position: absolute;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
  z-index: 1;
}

.parameter-description {
  margin-top: 4px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.host-override-field {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.host-override-summary {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--color-text-2);
}

.host-override-default {
  color: var(--color-text-3);
}

.param-description-text {
  font-size: 12px;
  color: var(--color-text-3);
  line-height: 1.4;
}

.param-default {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
}

.param-default .label {
  color: var(--color-text-3);
}

.param-default .value {
  color: var(--color-text-2);
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  background: var(--color-bg-2);
  padding: 2px 6px;
  border-radius: 3px;
}
</style>
