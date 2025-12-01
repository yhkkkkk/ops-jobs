<template>
  <div class="page">
    <div class="page-header">
      <h2>{{ isEdit ? '编辑定时任务' : '创建定时任务' }}</h2>
      <div class="page-actions">
        <a-button @click="handleCancel">取消</a-button>
        <a-button type="primary" :loading="saving" @click="handleSave">
          {{ isEdit ? '更新' : '创建' }}
        </a-button>
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
      <cron-helper v-model="tempCronExpression" />
    </a-modal>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import {
  IconInfoCircle,
  IconExclamationCircle,
  IconClockCircle
} from '@arco-design/web-vue/es/icon'
import { scheduledJobApi, executionPlanApi, cronApi } from '@/api/scheduler'
import CronHelper from './components/CronHelper.vue'

const route = useRoute()
const router = useRouter()

// 响应式数据
const formRef = ref()
const saving = ref(false)
const loadingPlans = ref(false)
const executionPlans = ref([])
const cronDescription = ref('')
const cronError = ref('')
const nextRuns = ref([])
const showCronHelper = ref(false)
const tempCronExpression = ref('')

// 判断是否为编辑模式
const isEdit = computed(() => !!route.params.id)

// 表单数据
const form = reactive({
  name: '',
  description: '',
  execution_plan: undefined,
  cron_expression: '',
  timezone: 'Asia/Shanghai',
  is_active: false
})

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



// 获取执行方案列表
const fetchExecutionPlans = async (search = '') => {
  loadingPlans.value = true
  try {
    const params = { page_size: 20 }
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
    const descResponse = await cronApi.describe(form.cron_expression)
    cronDescription.value = descResponse.data.description

    // 获取下次执行时间
    const nextResponse = await cronApi.getNextRuns(form.cron_expression, 5)
    nextRuns.value = nextResponse.data.next_runs
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

    saving.value = true

    if (isEdit.value) {
      await scheduledJobApi.update(route.params.id, form)
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
    const response = await scheduledJobApi.get(route.params.id)
    const task = response

    Object.assign(form, {
      name: task.name,
      description: task.description,
      execution_plan: task.execution_plan,
      cron_expression: task.cron_expression,
      timezone: task.timezone,
      is_active: task.is_active
    })

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
}, { debounce: 500 })

// 生命周期
onMounted(() => {
  fetchExecutionPlans()
  loadTask()
})
</script>

<style scoped>
.page {
  padding: 16px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.page-header h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}

.page-actions {
  display: flex;
  gap: 12px;
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
</style>
