<template>
  <div class="execution-plan-editor">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-content">
        <div class="header-left">
          <a-button type="text" @click="handleBack">
            <template #icon>
              <icon-arrow-left />
            </template>
            返回
          </a-button>
          <div class="header-info">
            <h2>{{ isEdit ? '编辑执行方案' : '创建执行方案' }}</h2>
            <p class="header-desc">{{ isEdit ? '修改执行方案配置' : '基于作业模板创建新的执行方案' }}</p>
          </div>
        </div>
        <div class="header-right">
          <a-space>
            <a-button @click="handleBack">取消</a-button>
            <a-button type="primary" :loading="saving" @click="handleSave">
              <template #icon>
                <icon-save />
              </template>
              {{ isEdit ? '保存' : '创建' }}
            </a-button>
          </a-space>
        </div>
      </div>
    </div>

    <div v-if="loading" class="loading-container">
      <a-spin size="large" />
    </div>

    <div v-else class="editor-content">
      <a-row :gutter="24">
        <!-- 左侧：基本信息 -->
        <a-col :span="16">
          <a-card title="基本信息" class="mb-4">
            <a-form :model="form" layout="vertical">
              <a-form-item label="方案名称" required>
                <a-input
                  v-model="form.name"
                  placeholder="请输入方案名称"
                  :max-length="200"
                />
              </a-form-item>

              <a-form-item label="方案描述">
                <a-textarea
                  v-model="form.description"
                  placeholder="请输入方案描述（可选）"
                  :rows="3"
                  :max-length="500"
                />
              </a-form-item>

              <!-- 创建模式：显示模板选择器 -->
              <a-form-item v-if="!isEdit" label="所属模板" required>
                <a-select
                  v-model="form.template_id"
                  placeholder="选择作业模板"
                  :loading="templateLoading"
                  @change="handleTemplateChange"
                >
                  <a-option
                    v-for="template in templates"
                    :key="template.id"
                    :value="template.id"
                  >
                    {{ template.name }}
                  </a-option>
                </a-select>
              </a-form-item>
            <!-- 模板全局变量覆盖（创建模式显示） -->
            <a-card v-if="!isEdit && selectedTemplate && selectedTemplate.global_parameters && Object.keys(selectedTemplate.global_parameters).length > 0" title="模板全局变量（覆盖，仅允许修改值）" class="mb-4">
              <div class="global-parameters-list">
                <div
                  v-for="(val, key) in selectedTemplate.global_parameters"
                  :key="key"
                  class="parameter-item"
                >
                  <div class="parameter-content">
                    <div class="parameter-row">
                      <div class="parameter-key">
                        <!-- 变量名不可修改，仅展示 -->
                        <div style="font-weight:500;">{{ key }}</div>
                      </div>
                      <div class="parameter-value">
                        <a-input
                          v-model:value="form.global_parameter_overrides[key]"
                          :type="(typeof val === 'object' && val.type === 'secret') ? 'password' : 'text'"
                          :placeholder="`模板默认值: ${formatGlobalParameterValue(val) || '(空)'}`"
                        />
                      </div>
                    </div>
                    <div class="parameter-description" v-if="getGlobalParameterDescription(val)">
                      <div style="font-size:12px; color:#86909c;">{{ getGlobalParameterDescription(val) }}</div>
                    </div>
                  </div>
                </div>
              </div>
            </a-card>

            <!-- 模板全局变量覆盖（编辑模式显示 - 可以修改覆盖值） -->
            <a-card v-if="isEdit && selectedTemplate && selectedTemplate.global_parameters && Object.keys(selectedTemplate.global_parameters).length > 0" title="模板全局变量（可覆盖修改值）" class="mb-4">
              <a-alert type="info" style="margin-bottom: 12px;">
                可以修改全局变量的覆盖值。留空则使用模板默认值。
              </a-alert>
              <div class="global-parameters-list">
                <div
                  v-for="(val, key) in selectedTemplate.global_parameters"
                  :key="key"
                  class="parameter-item"
                >
                  <div class="parameter-content">
                    <div class="parameter-row">
                      <div class="parameter-key">
                        <!-- 变量名不可修改，仅展示 -->
                        <div style="font-weight:500;">{{ key }}</div>
                      </div>
                      <div class="parameter-value">
                        <a-input
                          v-model:value="form.global_parameter_overrides[key]"
                          :type="(typeof val === 'object' && val.type === 'secret') ? 'password' : 'text'"
                          :placeholder="`模板默认值: ${formatGlobalParameterValue(val) || '(空)'}`"
                        />
                      </div>
                    </div>
                    <div class="parameter-description" v-if="getGlobalParameterDescription(val)">
                      <div style="font-size:12px; color:#86909c;">{{ getGlobalParameterDescription(val) }}</div>
                    </div>
                  </div>
                </div>
              </div>
            </a-card>

              <!-- 编辑模式：显示模板信息 -->
              <a-form-item v-else label="所属模板">
                <div class="template-display">
                  <div class="template-name">
                    {{ selectedTemplate?.name || '未知模板' }}
                  </div>
                  <div class="template-desc">
                    {{ selectedTemplate?.description || '无描述' }}
                  </div>
                </div>
              </a-form-item>
            </a-form>
          </a-card>

          <!-- 步骤选择 -->
          <a-card title="步骤配置">
            <template #extra>
              <a-space>
                <span class="step-count">已选择 {{ selectedSteps.length }} 个步骤</span>
                <a-button size="small" @click="handleSelectAllSteps">全选</a-button>
                <a-button size="small" @click="handleClearSteps">清空</a-button>
              </a-space>
            </template>

            <div v-if="displaySteps.length === 0" class="empty-steps">
              <a-empty :description="isEdit ? '该执行方案没有步骤' : '请先选择作业模板'" />
            </div>

            <div v-else class="steps-list">
              <div
                v-for="(step, index) in displaySteps"
                :key="step.id"
                class="step-item"
                :class="{ 'step-selected': isStepSelected(step.id) }"
              >
                <div class="step-header">
                  <a-checkbox
                    :model-value="isStepSelected(step.id)"
                    @change="(checked) => handleStepSelect(step.id, checked)"
                  />
                  <div class="step-number">{{ index + 1 }}</div>
                  <div class="step-info">
                    <div class="step-name">{{ step.name }}</div>
                    <div class="step-desc">{{ step.description || '无描述' }}</div>
                  </div>
                  <div class="step-type">
                    <a-tag :color="getStepTypeColor(step.step_type)">
                      {{ getStepTypeText(step.step_type) }}
                    </a-tag>
                  </div>
                </div>

                <!-- 步骤配置（当选中时显示） -->
                <div v-if="isStepSelected(step.id)" class="step-config">
                  <a-form layout="inline" size="small">
                    <a-form-item label="执行顺序">
                      <a-input-number
                        :model-value="getStepOrder(step.id)"
                        @change="(value) => handleStepOrderChange(step.id, value)"
                        :min="1"
                        :max="selectedSteps.length"
                        style="width: 80px"
                      />
                    </a-form-item>
                    <a-form-item label="超时时间(秒)">
                      <a-input-number
                        :model-value="getStepTimeout(step.id)"
                        @change="(value) => handleStepTimeoutChange(step.id, value)"
                        :min="10"
                        :max="3600"
                        style="width: 100px"
                      />
                    </a-form-item>
                  </a-form>
                </div>
              </div>
            </div>
          </a-card>
        </a-col>

        <!-- 右侧：模板信息 -->
        <a-col :span="8">
          <a-card title="模板信息">
            <div v-if="selectedTemplate" class="template-info">
              <a-descriptions :column="1" size="small">
                <a-descriptions-item label="模板名称">
                  {{ selectedTemplate.name }}
                </a-descriptions-item>
                <a-descriptions-item label="模板描述">
                  {{ selectedTemplate.description || '无描述' }}
                </a-descriptions-item>
                <a-descriptions-item label="分类">
                  <a-tag v-if="selectedTemplate.category" color="blue">
                    {{ selectedTemplate.category }}
                  </a-tag>
                  <span v-else>未分类</span>
                </a-descriptions-item>
                <a-descriptions-item label="总步骤数">
                  {{ selectedTemplate.step_count || 0 }} 个
                </a-descriptions-item>
                <a-descriptions-item label="创建人">
                  {{ selectedTemplate.created_by_name }}
                </a-descriptions-item>
              </a-descriptions>
            </div>

            <div v-else class="no-template">
              <a-empty description="请选择作业模板" />
            </div>
          </a-card>
        </a-col>
      </a-row>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import { jobTemplateApi, executionPlanApi } from '@/api/ops'
import type { JobTemplate, JobStep } from '@/types'

const route = useRoute()
const router = useRouter()

// 响应式数据
const loading = ref(false)
const saving = ref(false)
const templateLoading = ref(false)
const templates = ref<JobTemplate[]>([])
const templateSteps = ref<JobStep[]>([])
const selectedTemplate = ref<JobTemplate | null>(null)

// 是否编辑模式
const isEdit = computed(() => !!route.params.id)

// 当前执行方案的步骤数据（用于编辑模式显示）
const currentPlanSteps = ref<any[]>([])

// 显示的步骤列表（编辑模式使用快照数据，创建模式使用模板数据）
const displaySteps = computed(() => {
  if (isEdit.value) {
    // 编辑模式：显示执行方案的快照数据
    return currentPlanSteps.value
  } else {
    // 创建模式：显示模板的实时数据
    return templateSteps.value
  }
})

// 表单数据
const form = reactive({
  name: '',
  description: '',
  template_id: undefined as number | undefined,
  // 覆盖用的全局变量键值（仅模板已有键），默认不覆盖
  global_parameter_overrides: {} as Record<string, any>
})
// 用于提交给后端的全局变量覆盖（只包含被用户修改的键）
form.global_parameter_overrides = {}

// 选中的步骤配置
const selectedSteps = ref<Array<{
  step_id: number
  order: number
  override_timeout?: number
  override_parameters?: Record<string, any>
}>>([])

// 获取模板列表
const fetchTemplates = async () => {
  try {
    templateLoading.value = true
    const response = await jobTemplateApi.getTemplates({ page_size: 20 })
    templates.value = response.results || []
  } catch (error) {
    console.error('获取模板列表失败:', error)
    Message.error('获取模板列表失败')
  } finally {
    templateLoading.value = false
  }
}

// 获取模板步骤
const fetchTemplateSteps = async (templateId: number) => {
  try {
    const template = await jobTemplateApi.getTemplate(templateId)
    templateSteps.value = template.steps || []
    selectedTemplate.value = template
    // 初始化全局变量覆盖对象，仅包含模板已有的键（默认不覆盖）
    form.global_parameter_overrides = {}
    if (template.global_parameters) {
      Object.keys(template.global_parameters).forEach(k => {
        form.global_parameter_overrides[k] = ''
      })
    }
  } catch (error) {
    console.error('获取模板步骤失败:', error)
    Message.error('获取模板步骤失败')
  }
}

// 获取执行方案详情（编辑模式）
const fetchPlanDetail = async () => {
  if (!isEdit.value) return

  try {
    loading.value = true
    const planId = Number(route.params.id)
    const plan = await executionPlanApi.getPlan(planId)

    // 填充表单
    form.name = plan.name
    form.description = plan.description
    form.template_id = plan.template

    // 获取模板步骤
    await fetchTemplateSteps(plan.template)

    // 加载现有的全局变量覆盖（从 global_parameters_snapshot 提取覆盖值）
    if (plan.global_parameters_snapshot && selectedTemplate.value?.global_parameters) {
      form.global_parameter_overrides = {}
      Object.keys(selectedTemplate.value.global_parameters).forEach(key => {
        const snapshotValue = plan.global_parameters_snapshot[key]
        const templateValue = selectedTemplate.value.global_parameters[key]

        // 提取实际值用于比较
        let snapshotActualValue = snapshotValue
        let templateActualValue = templateValue

        if (typeof snapshotValue === 'object' && snapshotValue !== null) {
          snapshotActualValue = snapshotValue.value
        }
        if (typeof templateValue === 'object' && templateValue !== null) {
          templateActualValue = templateValue.value
        }

        // 如果快照值与模板默认值不同，说明有覆盖
        if (snapshotActualValue !== templateActualValue) {
          form.global_parameter_overrides[key] = snapshotActualValue || ''
        } else {
          form.global_parameter_overrides[key] = ''
        }
      })
    }

    // 设置当前方案的步骤数据（用于显示）
    if (plan.plan_steps) {
      currentPlanSteps.value = plan.plan_steps.map(planStep => ({
        id: planStep.template_step_id,
        name: planStep.step_name,
        description: planStep.step_description,
        step_type: planStep.step_type,
        script_content: planStep.step_script_content,
        is_deleted: planStep.is_template_step_deleted
      })).filter(step => step.id && !step.is_deleted) // 过滤掉已删除的步骤

      // 设置选中的步骤
      selectedSteps.value = plan.plan_steps.map(planStep => ({
        step_id: planStep.template_step_id,
        order: planStep.order,
        override_timeout: planStep.override_timeout || undefined,
        override_parameters: planStep.override_parameters || {}
      })).filter(step => step.step_id) // 过滤掉没有step_id的步骤（已删除的步骤）
    }
  } catch (error) {
    console.error('获取方案详情失败:', error)
    Message.error('获取方案详情失败')
  } finally {
    loading.value = false
  }
}

// 模板变化处理
const handleTemplateChange = async (templateId: number) => {
  if (templateId) {
    await fetchTemplateSteps(templateId)
    // 清空已选步骤
    selectedSteps.value = []
  } else {
    templateSteps.value = []
    selectedTemplate.value = null
    selectedSteps.value = []
  }
}

// 步骤选择相关方法
const isStepSelected = (stepId: number) => {
  return selectedSteps.value.some(s => s.step_id === stepId)
}

const handleStepSelect = (stepId: number, checked: boolean) => {
  if (checked) {
    // 添加步骤
    const maxOrder = selectedSteps.value.length > 0
      ? Math.max(...selectedSteps.value.map(s => s.order))
      : 0
    selectedSteps.value.push({
      step_id: stepId,
      order: maxOrder + 1
    })
  } else {
    // 移除步骤
    const index = selectedSteps.value.findIndex(s => s.step_id === stepId)
    if (index > -1) {
      selectedSteps.value.splice(index, 1)
      // 重新排序
      selectedSteps.value.forEach((step, idx) => {
        step.order = idx + 1
      })
    }
  }
}

const handleSelectAllSteps = () => {
  selectedSteps.value = displaySteps.value.map((step, index) => ({
    step_id: step.id,
    order: index + 1
  }))
}

const handleClearSteps = () => {
  selectedSteps.value = []
}

const getStepOrder = (stepId: number) => {
  const step = selectedSteps.value.find(s => s.step_id === stepId)
  return step?.order || 1
}

const getStepTimeout = (stepId: number) => {
  const step = selectedSteps.value.find(s => s.step_id === stepId)
  return step?.override_timeout || 300
}

const handleStepOrderChange = (stepId: number, order: number) => {
  const step = selectedSteps.value.find(s => s.step_id === stepId)
  if (step) {
    step.order = order
  }
}

const handleStepTimeoutChange = (stepId: number, timeout: number) => {
  const step = selectedSteps.value.find(s => s.step_id === stepId)
  if (step) {
    step.override_timeout = timeout
  }
}

// 保存方案
const handleSave = async () => {
  // 验证表单
  if (!form.name?.trim()) {
    Message.error('请输入方案名称')
    return
  }

  if (!isEdit.value && !form.template_id) {
    Message.error('请选择作业模板')
    return
  }

  if (selectedSteps.value.length === 0) {
    Message.error('请至少选择一个步骤')
    return
  }

  try {
    saving.value = true

    const data = {
      name: form.name,
      description: form.description || '',
      step_configs: selectedSteps.value.map(step => ({
        step_id: step.step_id,
        order: step.order,
        override_timeout: step.override_timeout,
        override_parameters: step.override_parameters || {}
      }))
    }

    // 只在创建模式下添加 template_id
    if (!isEdit.value) {
      ;(data as any).template_id = form.template_id
    }

    // 添加全局变量覆盖（创建和编辑模式都支持）
    if (form.global_parameter_overrides) {
      const overrides: Record<string, any> = {}
      Object.keys(form.global_parameter_overrides).forEach(k => {
        const v = form.global_parameter_overrides[k]
        if (v !== undefined && v !== null && String(v).trim() !== '') {
          overrides[k] = v
        }
      })
      if (Object.keys(overrides).length > 0) {
        ;(data as any).global_parameter_overrides = overrides
      }
    }

    if (isEdit.value) {
      // 更新方案
      const planId = Number(route.params.id)
      await executionPlanApi.updatePlan(planId, data)
      Message.success('方案更新成功')
    } else {
      // 创建方案
      await executionPlanApi.createPlan(data)
      Message.success('方案创建成功')
    }

    router.push('/execution-plans')
  } catch (error) {
    console.error('保存方案失败:', error)
    Message.error('保存方案失败')
  } finally {
    saving.value = false
  }
}

// 返回列表
const handleBack = () => {
  router.push('/execution-plans')
}

// 工具函数
const getStepTypeColor = (type: string) => {
  const colors: Record<string, string> = {
    script: 'blue',
    file_transfer: 'green'
  }
  return colors[type] || 'gray'
}

const getStepTypeText = (type: string) => {
  const texts: Record<string, string> = {
    script: '脚本执行',
    file_transfer: '文件传输'
  }
  return texts[type] || type
}

// 格式化全局变量值（处理secret等类型）
const formatGlobalParameterValue = (rawValue: any) => {
  if (rawValue === null || rawValue === undefined) return ''
  if (typeof rawValue !== 'object') {
    return String(rawValue)
  }
  const value = rawValue?.value
  const type = rawValue?.type
  if (type === 'secret') {
    return '******'
  }
  return value !== undefined ? String(value) : ''
}

// 监听URL参数变化
watch(() => route.query.template_id, (templateId) => {
  if (templateId && !isEdit.value) {
    form.template_id = Number(templateId)
    handleTemplateChange(Number(templateId))
  }
}, { immediate: true })

// 辅助：获取模板全局变量描述（用于输入提示）
const getGlobalParameterDescription = (val: any) => {
  if (!val) return ''
  if (typeof val === 'object' && val.description) return String(val.description)
  return ''
}

// 生命周期
onMounted(() => {
  fetchTemplates()
  if (isEdit.value) {
    fetchPlanDetail()
  }
})
</script>

<style scoped>
.execution-plan-editor {
  padding: 0;
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
  color: var(--color-text-1);
}

.header-desc {
  margin: 0;
  color: var(--color-text-3);
  font-size: 14px;
}

.mb-4 {
  margin-bottom: 16px;
}

.loading-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 400px;
}

.form-tip {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 4px;
  font-size: 12px;
  color: var(--color-text-3);
}

.step-count {
  font-size: 12px;
  color: var(--color-text-3);
}

.empty-steps {
  text-align: center;
  padding: 40px 0;
}

.steps-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.step-item {
  border: 1px solid var(--color-border-2);
  border-radius: 6px;
  padding: 16px;
  background: var(--color-bg-1);
  transition: all 0.2s;
}

.step-item:hover {
  border-color: var(--color-primary-6);
}

.step-selected {
  border-color: var(--color-primary-6);
  background: var(--color-primary-1);
}

.step-header {
  display: flex;
  align-items: center;
  gap: 12px;
}

.step-number {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--color-fill-3);
  color: var(--color-text-2);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 12px;
}

.step-selected .step-number {
  background: var(--color-primary-6);
  color: white;
}

.step-info {
  flex: 1;
}

.step-name {
  font-weight: 600;
  color: var(--color-text-1);
  margin-bottom: 4px;
}

.step-desc {
  color: var(--color-text-3);
  font-size: 12px;
}

.step-config {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--color-border-2);
}

.template-info {
  padding: 12px 0;
}

.no-template {
  text-align: center;
  padding: 40px 0;
}

.template-display {
  padding: 8px 12px;
  background-color: var(--color-fill-2);
  border: 1px solid var(--color-border-2);
  border-radius: 6px;
}

.template-name {
  font-weight: 500;
  color: var(--color-text-1);
  margin-bottom: 4px;
}

.template-desc {
  font-size: 12px;
  color: var(--color-text-3);
}

/* 模板全局变量覆盖样式（复用作业模板的样式） */
.global-parameters-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.parameter-item {
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
  flex: 1;
  min-width: 200px;
}

.parameter-value {
  flex: 2;
}

.parameter-description {
  margin-top: 4px;
}
</style>
