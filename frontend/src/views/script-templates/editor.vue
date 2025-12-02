<template>
  <div class="script-template-editor">
    <div class="page-header">
      <a-breadcrumb>
        <a-breadcrumb-item @click="goBack">脚本模板</a-breadcrumb-item>
        <a-breadcrumb-item>{{ getBreadcrumbTitle() }}</a-breadcrumb-item>
      </a-breadcrumb>

      <div class="header-actions">
        <a-space>
          <a-button @click="goBack">
            <template #icon>
              <icon-arrow-left />
            </template>
            返回
          </a-button>
          <a-button @click="handlePreview">
            <template #icon>
              <icon-eye />
            </template>
            预览
          </a-button>
          <a-button type="primary" @click="handleSave" :loading="saving">
            <template #icon>
              <icon-save />
            </template>
            保存
          </a-button>
        </a-space>
      </div>
    </div>

    <template-form
      ref="formRef"
      :template="templateData"
      @submit="handleSubmit"
      @change="handleFormChange"
    />

    <!-- 预览弹窗 -->
    <a-modal
      v-model:visible="previewVisible"
      title="模板预览"
      :width="1000"
      :footer="false"
    >
      <div v-if="previewData">
        <a-descriptions :column="2" bordered class="mb-4">
          <a-descriptions-item label="模板名称">
            {{ previewData.name }}
          </a-descriptions-item>
          <a-descriptions-item label="脚本类型">
            <a-tag :color="getScriptTypeColor(previewData.script_type)">
              {{ getScriptTypeText(previewData.script_type) }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="分类">
            {{ getCategoryText(previewData.category) }}
          </a-descriptions-item>
          <a-descriptions-item label="标签">
            <a-space v-if="previewData.tags_json && Object.keys(previewData.tags_json).length > 0">
              <a-tag v-for="(value, key) in previewData.tags_json" :key="key" size="small">
                {{ key }}:{{ value }}
              </a-tag>
            </a-space>
            <span v-else>-</span>
          </a-descriptions-item>
          <a-descriptions-item label="描述" :span="2">
            {{ previewData.description || '暂无描述' }}
          </a-descriptions-item>
        </a-descriptions>

        <div class="mb-4">
          <h4>脚本内容</h4>
          <monaco-editor
            :model-value="previewData.content"
            :language="previewData.script_type"
            :height="400"
            :readonly="true"
            :theme="currentEditorTheme"
          />
        </div>


      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import { scriptTemplateApi } from '@/api/ops'
import type { ScriptTemplate } from '@/types'
import TemplateForm from './components/TemplateForm.vue'
import MonacoEditor from '@/components/MonacoEditor.vue'
import { useUnsavedChanges } from '@/composables/useUnsavedChanges'

const route = useRoute()
const router = useRouter()

const formRef = ref()
const saving = ref(false)
const loading = ref(false)
const previewVisible = ref(false)
const templateData = ref<ScriptTemplate | null>(null)
const previewData = ref<Partial<ScriptTemplate> | null>(null)
const currentEditorTheme = ref('vs-dark')

// 使用未保存更改检测 composable
const {
  setOriginalData,
  checkForChanges,
  markAsSaved,
  canLeave,
  setupLifecycle
} = useUnsavedChanges()

// 计算属性
const isEdit = computed(() => {
  // 如果是复制操作，视为新建
  if (route.query.action === 'copy') return false
  // 如果参数是 'new'，视为新建
  if (route.params.id === 'new') return false
  // 其他情况视为编辑
  return !!route.params.id && route.params.id !== 'new'
})



// 获取模板数据
const fetchTemplate = async () => {
  // 检查是否是复制操作
  if (route.query.action === 'copy') {
    try {
      const copyData = sessionStorage.getItem('copyTemplateData')
      if (copyData) {
        const copiedTemplate = JSON.parse(copyData)
        templateData.value = copiedTemplate
        // 清除sessionStorage中的数据
        sessionStorage.removeItem('copyTemplateData')
        return
      }
    } catch (error) {
      console.error('解析复制数据失败:', error)
    }
  }

  if (!isEdit.value) {
    // 新建模板时，等待表单初始化完成后记录原始数据
    await nextTick()
    setTimeout(() => {
      recordOriginalData()
    }, 100)
    return
  }

  loading.value = true
  try {
    const templateId = parseInt(route.params.id as string)
    templateData.value = await scriptTemplateApi.getTemplate(templateId)
  } catch (error) {
    console.error('获取模板失败:', error)
    Message.error('获取模板失败')
    router.push('/script-templates')
  } finally {
    loading.value = false

    // 记录原始数据用于变更检测
    await nextTick()
    recordOriginalData()
  }
}

// 预览模板
const handlePreview = async () => {
  try {
    // 使用getCurrentData方法获取当前表单数据，不触发提交
    const currentData = await formRef.value?.getCurrentData()
    if (currentData) {
      console.log('预览数据:', currentData)
      console.log('标签数据 tags_json:', currentData.tags_json)
      console.log('标签数据存在:', !!currentData.tags_json)
      console.log('标签数据键数量:', Object.keys(currentData.tags_json || {}).length)

      previewData.value = currentData
      // 获取当前编辑器主题
      currentEditorTheme.value = formRef.value?.getCurrentTheme() || 'vs-dark'
      previewVisible.value = true
    }
  } catch (error) {
    console.error('预览失败:', error)
    Message.error('表单验证失败，请检查输入内容')
  }
}

// 保存模板
const handleSave = async () => {
  try {
    const result = await formRef.value?.submit()
    if (result) {
      // submit 方法会触发 @submit 事件，在 handleSubmit 中处理实际保存
      console.log('表单验证通过，准备保存')
    }
  } catch (error) {
    console.error('保存失败:', error)
    Message.error('保存失败')
  }
}

// 提交表单
const handleSubmit = async (data: Partial<ScriptTemplate>) => {
  console.log('开始保存模板，数据:', data)
  saving.value = true
  try {
    // 转换字段名以匹配后端API
    const apiData = {
      name: data.name,
      description: data.description || '',
      script_type: data.script_type,
      category: data.category || '', // 分类
      script_content: data.content || '', // 前端的 content 对应后端的 script_content
      tags_json: data.tags_json || {}, // 键值对格式标签
      template_type: templateData.value?.template_type || 'user', // 模板类型，默认为用户模板
      version: data.version || templateData.value?.version || '1.0.0',
      is_active: data.is_active ?? templateData.value?.is_active ?? true,
      is_public: data.is_public ?? templateData.value?.is_public ?? false,
    }

    console.log('转换后的API数据:', apiData)

    if (isEdit.value) {
      console.log('更新模板，ID:', templateData.value!.id)
      await scriptTemplateApi.updateTemplate(templateData.value!.id, apiData)
      Message.success('模板更新成功')
    } else {
      console.log('创建新模板')
      const result = await scriptTemplateApi.createTemplate(apiData)
      console.log('创建结果:', result)
      Message.success('模板创建成功')
    }

    // 重置变更状态
    markAsSaved()

    router.push('/script-templates')
  } catch (error: any) {
    console.error('保存模板失败:', error)

    // 详细的错误信息
    let errorMessage = isEdit.value ? '模板更新失败' : '模板创建失败'
    if (error.response?.data?.message) {
      errorMessage += ': ' + error.response.data.message
    } else if (error.message) {
      errorMessage += ': ' + error.message
    }

    Message.error(errorMessage)
  } finally {
    saving.value = false
  }
}

// 获取面包屑标题
const getBreadcrumbTitle = () => {
  if (route.query.action === 'copy') {
    return '复制模板'
  }
  return isEdit.value ? '编辑模板' : '新建模板'
}

// 返回列表
const goBack = () => {
  if (!canLeave.value) {
    Message.warning('您有未保存的更改，请先保存或放弃。')
    return
  }
  router.push('/script-templates')
}

// 删除旧的 showLeaveConfirm 函数，使用 composable 中的

// 记录原始数据
const recordOriginalData = async () => {
  try {
    // 等待下一个 tick 确保表单完全初始化
    await nextTick()
    const currentData = await formRef.value?.getCurrentData()
    if (currentData) {
      setOriginalData(currentData)
      console.log('已记录原始数据:', currentData)
    }
  } catch (error) {
    console.error('记录原始数据失败:', error)
    // 如果获取当前数据失败，使用模板数据作为原始数据
    if (templateData.value) {
      setOriginalData(templateData.value)
    }
  }
}

// 检测表单变更
const checkFormChanges = async () => {
  try {
    const currentData = await formRef.value?.getCurrentData()
    if (currentData) {
      checkForChanges(currentData)
    }
  } catch (error) {
    // 忽略错误，可能是表单还未完全初始化
  }
}

// 处理表单变更事件
const handleFormChange = (hasChanges: boolean) => {
  if (hasChanges) {
    checkFormChanges()
  }
}

// 删除旧的 beforeunload 处理函数，使用 composable 中的

// 组件挂载时添加事件监听
onMounted(() => {
  fetchTemplate()
  setupLifecycle()
})

// 组件卸载时移除事件监听
onUnmounted(() => {
  // setupLifecycle 已经处理了事件监听
})

// 工具函数
const getScriptTypeColor = (type: string) => {
  const colors = {
    shell: 'blue',
    python: 'green',
    powershell: 'purple',
  }
  return colors[type] || 'gray'
}

const getScriptTypeText = (type: string) => {
  const texts = {
    shell: 'Shell',
    python: 'Python',
    powershell: 'PowerShell',
  }
  return texts[type] || type
}

const getCategoryText = (category: string) => {
  const texts = {
    deployment: '部署',
    monitoring: '监控',
    maintenance: '维护',
    backup: '备份',
    security: '安全',
    other: '其他',
  }
  return texts[category] || category
}

// 生命周期已在上面定义
</script>

<style scoped>
.script-template-editor {
  padding: 0;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.header-actions {
  flex-shrink: 0;
}

.mb-4 {
  margin-bottom: 16px;
}

:deep(.arco-breadcrumb-item) {
  cursor: pointer;
}
</style>
