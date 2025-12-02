<template>
  <div class="job-template-editor">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-left">
        <a-button type="text" @click="handleBack">
          <template #icon>
            <icon-arrow-left />
          </template>
          返回
        </a-button>
        <h2>{{ isEdit ? '编辑作业模板' : '新建作业模板' }}</h2>
      </div>
      <a-space>
        <a-button @click="handleSave" :loading="saving">
          <template #icon>
            <icon-save />
          </template>
          保存
        </a-button>
        <a-button v-if="isEdit" type="primary" @click="handleDebugExecute">
          <template #icon>
            <icon-play-arrow />
          </template>
          调试执行
        </a-button>
      </a-space>
    </div>

    <!-- 基本信息 -->
    <a-card title="基本信息" class="mb-4">
      <a-form :model="form" layout="vertical" @change="handleFormChange">
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="模板名称" required>
              <a-input
                v-model="form.name"
                placeholder="请输入模板名称"
                :max-length="200"
              />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="分类">
              <a-select
                v-model="form.category"
                placeholder="选择分类"
                allow-clear
              >
                <a-option value="deployment">部署</a-option>
                <a-option value="maintenance">维护</a-option>
                <a-option value="monitoring">监控</a-option>
                <a-option value="backup">备份</a-option>
                <a-option value="other">其他</a-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="标签">
              <TagEditor
                v-model="tagEditorValue"
                placeholder="添加键值对标签"
                :max-tags="10"
              />
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item label="模板描述">
          <a-textarea
            v-model="form.description"
            placeholder="请输入模板描述"
            :rows="3"
            :max-length="1000"
          />
        </a-form-item>
      </a-form>
    </a-card>

    <!-- 全局变量 -->
    <a-card title="全局变量" class="mb-4">
      <template #extra>
        <a-button type="primary" @click="handleAddGlobalParameter">
          <template #icon>
            <icon-plus />
          </template>
          添加变量
        </a-button>
      </template>

      <div v-if="Object.keys(form.global_parameters || {}).length === 0" class="empty-parameters">
        <a-empty description="暂无全局变量，请添加全局变量">
          <a-button type="primary" @click="handleAddGlobalParameter">
            <template #icon>
              <icon-plus />
            </template>
            添加变量
          </a-button>
        </a-empty>
      </div>

      <div v-else class="global-parameters-list">
        <div
          v-for="(_, key) in form.global_parameters"
          :key="key"
          class="parameter-item"
        >
          <div class="parameter-content">
            <div class="parameter-key">
              <a-input
                v-model="parameterKeys[key]"
                placeholder="变量名"
                @blur="handleParameterKeyChange(key, parameterKeys[key])"
                @pressEnter="handleParameterKeyChange(key, parameterKeys[key])"
              />
            </div>
            <div class="parameter-type">
              <a-select
                :model-value="getParameterType(key)"
                placeholder="类型"
                style="width: 80px"
                @change="handleParameterTypeChange(key, $event)"
              >
                <a-option value="text">文本</a-option>
                <a-option value="secret">密文</a-option>
              </a-select>
            </div>
            <div class="parameter-value">
              <a-input
                :model-value="getParameterValue(key)"
                :type="getParameterType(key) === 'secret' && !parameterVisibility[key] ? 'password' : 'text'"
                :placeholder="getParameterType(key) === 'secret' ? '密文变量值' : '变量值'"
                @input="handleParameterValueChange(key, $event)"
              />
              <a-button
                v-if="getParameterType(key) === 'secret'"
                type="text"
                size="small"
                @click="toggleParameterVisibility(key)"
                class="visibility-toggle"
              >
                <template #icon>
                  <icon-eye v-if="parameterVisibility[key]" />
                  <icon-eye-invisible v-else />
                </template>
              </a-button>
            </div>
            <div class="parameter-actions">
              <a-button
                type="text"
                status="danger"
                @click="handleRemoveGlobalParameter(key)"
              >
                <template #icon>
                  <icon-delete />
                </template>
              </a-button>
            </div>
          </div>
        </div>
      </div>
    </a-card>

    <!-- 作业步骤 -->
    <a-card title="作业步骤" class="mb-4">
      <template #extra>
        <a-space>
          <a-button type="primary" @click="handleAddStep">
            <template #icon>
              <icon-plus />
            </template>
            添加步骤
          </a-button>
        </a-space>
      </template>

      <div v-if="form.steps.length === 0" class="empty-steps">
        <a-empty description="暂无步骤，请添加作业步骤">
          <a-button type="primary" @click="handleAddStep">
            <template #icon>
              <icon-plus />
            </template>
            添加步骤
          </a-button>
        </a-empty>
      </div>

      <div v-else class="steps-list">
        <div
          v-for="(step, index) in form.steps"
          :key="step.id || index"
          class="step-item"
        >
          <div class="step-header">
            <div class="step-info">
              <span class="step-number">{{ index + 1 }}</span>
              <span class="step-name">{{ step.name || '未命名步骤' }}</span>
              <a-tag :color="getStepTypeColor(step.step_type)">
                {{ getStepTypeText(step.step_type) }}
              </a-tag>
            </div>
            <a-space>
              <a-button type="text" size="small" @click="handleEditStep(index)">
                <template #icon>
                  <icon-edit />
                </template>
                编辑
              </a-button>
              <a-button type="text" size="small" @click="handleMoveStepUp(index)" :disabled="index === 0">
                <template #icon>
                  <icon-arrow-up />
                </template>
              </a-button>
              <a-button type="text" size="small" @click="handleMoveStepDown(index)" :disabled="index === form.steps.length - 1">
                <template #icon>
                  <icon-arrow-down />
                </template>
              </a-button>
              <a-popconfirm
                content="确定要删除这个步骤吗？"
                @ok="handleDeleteStep(index)"
              >
                <a-button type="text" size="small" status="danger">
                  <template #icon>
                    <icon-delete />
                  </template>
                </a-button>
              </a-popconfirm>
            </a-space>
          </div>
          <div class="step-content">
            <div class="step-description">
              {{ step.description || '无描述' }}
            </div>
            <div class="step-config">
              <a-space>
                <span>超时: {{ step.timeout }}秒</span>
                <span v-if="step.ignore_error">忽略错误</span>
                <span v-if="step.condition">有执行条件</span>
              </a-space>
            </div>
          </div>
        </div>
      </div>
    </a-card>

    <!-- 步骤编辑弹窗 -->
    <StepEditor
      v-model:visible="stepEditorVisible"
      :step="currentStep"
      :is-edit="isEditingStep"
      @save="handleStepSave"
    />

    <!-- 成功提示弹窗 -->
    <SuccessModal
      v-model="showSuccessModal"
      :title="successModal.title"
      :message="successModal.message"
      :description="successModal.description"
      :actions="successModal.actions"
      @action="handleSuccessAction"
    />

    <!-- 同步确认弹窗 -->
    <SyncConfirmModal
      v-model:visible="showSyncConfirmModal"
      :template-id="syncTemplateId"
      :template-name="syncTemplateName"
      @sync-success="handleSyncSuccess"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, h } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Message, Modal } from '@arco-design/web-vue'
import { jobTemplateApi } from '@/api/ops'
import type { JobTemplate, JobStep } from '@/types'
import StepEditor from './components/StepEditor.vue'
import SyncConfirmModal from './components/SyncConfirmModal.vue'
import TagEditor from '@/components/TagEditor.vue'
import SuccessModal from '@/components/SuccessModal.vue'
import { IconEye, IconEyeInvisible, IconPlus, IconPlayArrow, IconList, IconSync, IconDelete, IconEdit, IconArrowUp, IconArrowDown } from '@arco-design/web-vue/es/icon'
import { useUnsavedChanges } from '@/composables/useUnsavedChanges'

const route = useRoute()
const router = useRouter()

// 响应式数据
const loading = ref(false)
const saving = ref(false)
const stepEditorVisible = ref(false)
const currentStep = ref<Partial<JobStep>>({})
const currentStepIndex = ref(-1)
const showSuccessModal = ref(false)
const successModal = ref({
  title: '',
  message: '',
  description: '',
  actions: [] as any[]
})

// 使用未保存更改检测 composable
const {
  setOriginalData,
  checkForChanges,
  markAsSaved,
  canLeave,
  setupLifecycle
} = useUnsavedChanges()

// 同步模态框状态
const showSyncConfirmModal = ref(false)
const syncTemplateId = ref<number>()
const syncTemplateName = ref<string>()

// 表单数据
const form = reactive<Partial<JobTemplate>>({
  name: '',
  description: '',
  category: '',
  tags: [] as string[],
  steps: [],
  global_parameters: {}
})

// 标签转换函数
const convertTagsToStringArray = (tags: { key: string; value: string }[]): string[] => {
  return tags.map(tag => `${tag.key}:${tag.value}`)
}

const convertStringArrayToTags = (tags: string[]): { key: string; value: string }[] => {
  return tags.map(tag => {
    const [key, ...valueParts] = tag.split(':')
    return { key, value: valueParts.join(':') }
  })
}

// 计算属性：用于 TagEditor 的标签数据
const tagEditorValue = computed({
  get: () => convertStringArrayToTags(form.tags || []),
  set: (value: { key: string; value: string }[]) => {
    form.tags = convertTagsToStringArray(value)
    // 检测变更
    checkFormChanges()
  }
})

// 全局变量管理
const parameterKeys = ref<Record<string, string>>({})
const parameterVisibility = ref<Record<string, boolean>>({})

// 计算属性
const isEdit = computed(() => !!route.params.id)
const isEditingStep = computed(() => currentStepIndex.value >= 0)

// 获取模板详情
const fetchTemplate = async () => {
  if (!route.params.id) return

  try {
    loading.value = true
    const template = await jobTemplateApi.getTemplate(Number(route.params.id))

    Object.assign(form, {
      name: template.name,
      description: template.description,
      category: template.category,
      tags: template.tag_list || [],
      steps: template.steps || [],
      global_parameters: template.global_parameters || {}
    })

    // 初始化参数键名映射和可见性状态
    if (template.global_parameters) {
      Object.keys(template.global_parameters).forEach(key => {
        parameterKeys.value[key] = key
        // 密文类型默认隐藏
        const param = template.global_parameters[key]
        const paramType = typeof param === 'string' ? 'text' : param?.type || 'text'
        parameterVisibility.value[key] = paramType !== 'secret'
      })
    }

    // 记录原始数据用于变更检测
    setOriginalData(form)
  } catch (error) {
    console.error('获取模板详情失败:', error)
    Message.error('获取模板详情失败')
  } finally {
    loading.value = false
  }
}

// 保存模板
const handleSave = async () => {
  try {
    // 基本验证
    if (!form.name?.trim()) {
      Message.error('请输入模板名称')
      return
    }

    // 检查主机配置并显示警告
    const hostWarnings = checkHostConfiguration()
    if (hostWarnings.length > 0) {
      const proceed = await showHostWarningModal(hostWarnings)
      if (!proceed) {
        return
      }
    }

    saving.value = true

    const data = {
      name: form.name,
      description: form.description || '',
      category: form.category || '',
      tags: form.tags || [],
      steps: form.steps || [],
      global_parameters: form.global_parameters || {}
    }

    if (isEdit.value) {
      const result = await jobTemplateApi.updateTemplate(Number(route.params.id), data)
      // 标记为已保存
      markAsSaved()
      // 显示编辑成功弹窗
      showEditSuccessModal(result)
    } else {
      const result = await jobTemplateApi.createTemplate(data)
      // 标记为已保存
      markAsSaved()
      // 显示成功弹窗
      showCreateSuccessModal(result)
    }
  } catch (error) {
    console.error('保存模板失败:', error)
    Message.error('保存模板失败')
  } finally {
    saving.value = false
  }
}

// 检查主机配置
const checkHostConfiguration = () => {
  const warnings = []

  if (!form.steps || form.steps.length === 0) {
    return warnings
  }

  // 检查每个步骤的主机配置
  for (let i = 0; i < form.steps.length; i++) {
    const step = form.steps[i]

    // 检查是否没有配置主机
    if (!step.target_hosts || step.target_hosts.length === 0) {
      warnings.push({
        type: 'no-hosts',
        stepIndex: i + 1,
        stepName: step.name || `步骤${i + 1}`,
        message: '未配置目标主机'
      })
    } else {
      // 这里可以添加更多检查，比如主机状态等
      // 但由于我们在步骤编辑器中已经有了实时检查，这里主要检查基本配置
    }
  }

  return warnings
}

// 显示主机警告弹窗
const showHostWarningModal = (warnings: any[]) => {
  return new Promise<boolean>((resolve) => {
    const warningMessages = warnings.map(w => `• ${w.stepName}: ${w.message}`).join('\n')

    Modal.warning({
      title: '主机配置提醒',
      content: h('div', [
        h('p', '检测到以下步骤的主机配置问题：'),
        h('pre', { style: 'margin: 12px 0; padding: 12px; background: #f7f8fa; border-radius: 4px; white-space: pre-wrap;' }, warningMessages),
        h('p', { style: 'margin-top: 12px; color: #86909c;' }, '这些步骤在执行时可能无法正常运行，是否继续保存？')
      ]) as any,
      okText: '继续保存',
      cancelText: '返回修改',
      onOk: () => resolve(true),
      onCancel: () => resolve(false)
    })
  })
}

// 返回列表
const handleBack = () => {
  if (!canLeave.value) {
    Message.warning('您有未保存的更改，请先保存或放弃。')
    return
  }
  router.push('/job-templates')
}

// 调试执行模板
const handleDebugExecute = async () => {
  const templateId = Number(route.params.id)
  if (!templateId) {
    Message.error('模板ID不存在')
    return
  }

  try {
    Message.loading('正在启动调试执行...')

    const result = await jobTemplateApi.debugTemplate(templateId, {
      execution_parameters: {},
      execution_mode: 'parallel',
      rolling_batch_size: 1,
      rolling_batch_delay: 0
    })

    Message.clear()
    Message.success('调试执行已启动！')

    // 跳转到执行记录页面查看结果
    router.push(`/execution-records/${result.execution_id}`)

  } catch (error: any) {
    Message.clear()
    console.error('调试执行失败:', error)
    Message.error(error.response?.data?.message || '调试执行失败')
  }
}

// 成功弹窗相关
const showCreateSuccessModal = (template: JobTemplate) => {
  successModal.value = {
    title: '作业模板创建成功',
    message: `模板「${template.name}」已创建完成`,
    description: '您可以选择以下操作继续使用该模板',
    actions: [
      {
        key: 'view',
        label: '查看模板详情',
        type: 'primary',
        icon: IconEye,
        handler: () => {
          router.replace(`/job-templates/editor/${template.id}`)
        }
      },
      {
        key: 'create-plan',
        label: '新建执行方案',
        type: 'outline',
        icon: IconPlus,
        handler: () => {
          router.push(`/execution-plans/create?template_id=${template.id}`)
        }
      },
      {
        key: 'list',
        label: '返回模板列表',
        type: 'text',
        icon: IconList,
        handler: () => {
          router.push('/job-templates')
        }
      }
    ]
  }
  showSuccessModal.value = true
}

const showEditSuccessModal = (template: JobTemplate) => {
  successModal.value = {
    title: '作业模板更新成功',
    message: `模板「${template.name}」已更新完成`,
    description: '您可以选择以下操作继续使用该模板',
    actions: [
      {
        key: 'view',
        label: '查看模板详情',
        type: 'primary',
        icon: IconEye,
        handler: () => {
          router.push(`/job-templates/detail/${template.id}`)
        }
      },
      {
        key: 'sync',
        label: '同步执行方案',
        type: 'outline',
        icon: IconSync,
        handler: () => {
          showSuccessModal.value = false
          showSyncModal(template)
        }
      },
      {
        key: 'create-plan',
        label: '新建执行方案',
        type: 'outline',
        icon: IconPlus,
        handler: () => {
          router.push(`/execution-plans/create?template_id=${template.id}`)
        }
      },
      {
        key: 'debug-execute',
        label: '调试执行',
        type: 'outline',
        status: 'success',
        icon: IconPlayArrow,
        handler: async () => {
          try {
            Message.loading('正在启动调试执行...')

            const result = await jobTemplateApi.debugTemplate(template.id, {
              execution_parameters: {},
              execution_mode: 'parallel',
              rolling_batch_size: 1,
              rolling_batch_delay: 0
            })

            Message.clear()
            Message.success('调试执行已启动！')

            // 跳转到执行记录页面查看结果
            router.push(`/execution-records/${result.execution_id}`)

          } catch (error: any) {
            Message.clear()
            console.error('调试执行失败:', error)
            Message.error(error.response?.data?.message || '调试执行失败')
          }
        }
      },
      {
        key: 'continue',
        label: '继续编辑',
        type: 'text',
        handler: () => {
          showSuccessModal.value = false
          // 保持在当前页面
        }
      },
      {
        key: 'list',
        label: '返回模板列表',
        type: 'text',
        icon: IconList,
        handler: () => {
          router.push('/job-templates')
        }
      }
    ]
  }
  showSuccessModal.value = true
}

const handleSuccessAction = (action: any) => {
  console.log('Success action:', action.key)
  // 动作处理已在 action.handler 中完成
}

// 显示同步模态框
const showSyncModal = (template: JobTemplate) => {
  syncTemplateId.value = template.id
  syncTemplateName.value = template.name
  showSyncConfirmModal.value = true
}

// 处理同步成功
const handleSyncSuccess = () => {
  Message.success('执行方案同步成功')
}

// 步骤管理
const handleAddStep = () => {
  if (!form.steps) {
    form.steps = []
  }
  
  currentStep.value = {
    name: '',
    description: '',
    step_type: 'script',
    order: form.steps.length + 1,
    step_parameters: [] as string[],
    timeout: 300,
    ignore_error: false,
    condition: '',
    target_hosts: [],
    target_groups: []
  }
  currentStepIndex.value = -1
  stepEditorVisible.value = true
}

const handleEditStep = (index: number) => {
  if (!form.steps) return
  currentStep.value = { ...form.steps[index] }
  currentStepIndex.value = index
  stepEditorVisible.value = true
}

const handleStepSave = (step: JobStep) => {
  if (!form.steps) {
    form.steps = []
  }

  if (isEditingStep.value) {
    // 编辑现有步骤
    form.steps[currentStepIndex.value] = step
  } else {
    // 添加新步骤
    form.steps.push(step)
  }

  // 重新排序
  form.steps.forEach((s, index) => {
    s.order = index + 1
  })

  stepEditorVisible.value = false
  
  // 检测变更
  checkFormChanges()
}

const handleDeleteStep = (index: number) => {
  if (!form.steps) return
  form.steps.splice(index, 1)

  // 重新排序
  form.steps.forEach((s, index) => {
    s.order = index + 1
  })
  
  // 检测变更
  checkFormChanges()
}

const handleMoveStepUp = (index: number) => {
  if (index > 0 && form.steps) {
    const steps = form.steps
    ;[steps[index - 1], steps[index]] = [steps[index], steps[index - 1]]

    // 重新排序
    steps.forEach((s, i) => {
      s.order = i + 1
    })
    
    // 检测变更
    checkFormChanges()
  }
}

const handleMoveStepDown = (index: number) => {
  if (form.steps && index < form.steps.length - 1) {
    const steps = form.steps
    ;[steps[index], steps[index + 1]] = [steps[index + 1], steps[index]]

    // 重新排序
    steps.forEach((s, i) => {
      s.order = i + 1
    })
    
    // 检测变更
    checkFormChanges()
  }
}

// 全局变量管理
const handleAddGlobalParameter = () => {
  const newKey = `param_${Date.now()}`
  if (!form.global_parameters) {
    form.global_parameters = {}
  }
  // 使用新的扩展格式
  form.global_parameters[newKey] = {
    value: '',
    type: 'text',
    description: ''
  }
  parameterKeys.value[newKey] = newKey
  parameterVisibility.value[newKey] = false
  
  // 检测变更
  checkFormChanges()
}

const handleRemoveGlobalParameter = (key: string) => {
  if (form.global_parameters) {
    delete form.global_parameters[key]
  }
  delete parameterKeys.value[key]
  delete parameterVisibility.value[key]
  
  // 检测变更
  checkFormChanges()
}

// 获取参数值（兼容新旧格式）
const getParameterValue = (key: string) => {
  const param = form.global_parameters?.[key]
  if (typeof param === 'string') {
    return param // 旧格式
  }
  return param?.value || '' // 新格式
}

// 获取参数类型
const getParameterType = (key: string) => {
  const param = form.global_parameters?.[key]
  if (typeof param === 'string') {
    return 'text' // 旧格式默认为文本
  }
  return param?.type || 'text' // 新格式
}

// 处理参数值变化（Arco Input 的 @input 直接传字符串值）
const handleParameterValueChange = (key: string, value: string) => {
  if (!form.global_parameters) {
    form.global_parameters = {}
  }

  const param = form.global_parameters[key]
  if (typeof param === 'string') {
    // 升级旧格式到新格式
    form.global_parameters[key] = {
      value: value,
      type: 'text',
      description: ''
    }
  } else {
    // 更新新格式
    form.global_parameters[key] = {
      ...param,
      value: value
    }
  }
  
  // 检测变更
  checkFormChanges()
}

// 处理参数类型变化
const handleParameterTypeChange = (key: string, type: string) => {
  if (!form.global_parameters) {
    form.global_parameters = {}
  }

  const param = form.global_parameters[key]
  const currentValue = typeof param === 'string' ? param : param?.value || ''

  form.global_parameters[key] = {
    value: currentValue,
    type: type,
    description: param?.description || ''
  }
  
  // 检测变更
  checkFormChanges()
}

// 切换参数可见性
const toggleParameterVisibility = (key: string) => {
  parameterVisibility.value[key] = !parameterVisibility.value[key]
}

const handleParameterKeyChange = (oldKey: string, newKey: string) => {
  if (!newKey || newKey === oldKey) return

  // 检查新键名是否已存在
  if (form.global_parameters && newKey in form.global_parameters) {
    Message.warning('变量名已存在')
    parameterKeys.value[oldKey] = oldKey // 恢复原键名
    return
  }

  if (form.global_parameters && oldKey in form.global_parameters) {
    const value = form.global_parameters[oldKey]
    delete form.global_parameters[oldKey]
    form.global_parameters[newKey] = value

    delete parameterKeys.value[oldKey]
    parameterKeys.value[newKey] = newKey
    
    // 检测变更
    checkFormChanges()
  }
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

// 加载复制的数据
const loadCopyData = () => {
  try {
    const copyData = sessionStorage.getItem('copyTemplateData')
    if (copyData) {
      const templateData = JSON.parse(copyData)
      Object.assign(form, templateData)

      // 初始化参数键名映射
      if (templateData.global_parameters) {
        Object.keys(templateData.global_parameters).forEach(key => {
          parameterKeys.value[key] = key
        })
      }

      // 清除sessionStorage中的数据
      sessionStorage.removeItem('copyTemplateData')

      Message.success('已加载复制的模板数据，请修改模板名称后保存')
    }
  } catch (error) {
    console.error('加载复制数据失败:', error)
    Message.error('加载复制数据失败')
  }
}

// 检测表单变更
const checkFormChanges = () => {
  return checkForChanges(form)
}

// 监听表单变更
const handleFormChange = () => {
  checkFormChanges()
}

// 生命周期
onMounted(() => {
  setupLifecycle()
  
  if (isEdit.value) {
    fetchTemplate()
  } else {
    // 检查是否是复制操作
    const action = route.query.action
    if (action === 'copy') {
      loadCopyData()
    } else {
      // 新建时记录初始数据
      setOriginalData(form)
    }
  }
})
</script>

<style scoped>
.job-template-editor {
  padding: 0;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-left h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}

.mb-4 {
  margin-bottom: 16px;
}

.empty-steps {
  padding: 40px 0;
  text-align: center;
}

.steps-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.step-item {
  border: 1px solid var(--color-border-2);
  border-radius: 6px;
  padding: 16px;
  background: var(--color-bg-1);
}

.step-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.step-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.step-number {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  background: var(--color-primary);
  color: white;
  border-radius: 50%;
  font-size: 12px;
  font-weight: 600;
}

.step-name {
  font-weight: 500;
  font-size: 14px;
}

.step-content {
  padding-left: 32px;
}

.step-description {
  color: var(--color-text-2);
  margin-bottom: 8px;
}

.step-config {
  font-size: 12px;
  color: var(--color-text-3);
}

/* 全局变量样式 */
.empty-parameters {
  padding: 40px 0;
  text-align: center;
}

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
  align-items: center;
  gap: 12px;
}

.parameter-key {
  flex: 1;
  min-width: 200px;
}

.parameter-type {
  flex-shrink: 0;
  width: 80px;
}

.parameter-value {
  flex: 2;
  position: relative;
}

.parameter-value .visibility-toggle {
  position: absolute;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
  z-index: 1;
}

.parameter-actions {
  flex-shrink: 0;
}
</style>
