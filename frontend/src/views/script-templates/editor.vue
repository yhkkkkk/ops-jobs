<template>
  <div class="script-template-editor">
    <div class="page-header">
      <div class="header-content">
        <div class="header-left">
          <a-button type="text" @click="goBack">
            <template #icon>
              <icon-arrow-left />
            </template>
            返回
          </a-button>
          <div class="header-info">
            <h2>{{ headerTitle }}</h2>
            <p class="header-desc">
              {{ headerDesc }}
            </p>
          </div>
        </div>
        <div class="header-right">
          <a-space>
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
    </div>

    <template-form
      ref="formRef"
      :template="templateData"
      :mode="isEditVersion ? 'version' : 'template'"
      @submit="handleSubmit"
      @change="handleFormChange"
    />

    <!-- 未保存更改提示 -->
    <a-modal
      v-model:visible="leaveConfirmVisible"
      title="未保存更改"
      :width="480"
      :footer="false"
    >
      <div class="leave-confirm-content">
        您有未保存的更改，是否保存并离开？
      </div>
      <div class="leave-confirm-actions">
        <a-button type="primary" :loading="saving" @click="handleLeaveSave">保存并离开</a-button>
        <a-button status="danger" @click="handleLeaveDiscard">放弃更改</a-button>
        <a-button @click="handleLeaveCancel">取消</a-button>
      </div>
    </a-modal>

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
          <a-descriptions-item label="版本号">
            {{ previewData.version || '未设置' }}
          </a-descriptions-item>
          <a-descriptions-item label="状态">
            <a-tag v-if="previewData.is_active" color="green">上线</a-tag>
            <a-tag v-else color="red">下线</a-tag>
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
const editingVersionId = ref<number | null>(null)
const previewVisible = ref(false)
const templateData = ref<ScriptTemplate | null>(null)
const previewData = ref<Partial<ScriptTemplate> | null>(null)
const currentEditorTheme = ref('vs-dark')
const leaveConfirmVisible = ref(false)
const leaveAfterSave = ref(false)

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

const isEditVersion = computed(() => route.query.action === 'editVersion')

const headerTitle = computed(() => {
  if (route.query.action === 'copy') return '复制脚本模板'
  if (isEditVersion.value) return '编辑脚本版本'
  return isEdit.value ? '编辑脚本模板' : '新建脚本模板'
})

const headerDesc = computed(() => {
  if (route.query.action === 'copy') return '基于现有模板复制并调整脚本与元数据'
  if (isEditVersion.value) return '修改版本脚本内容与版本信息'
  return isEdit.value ? '调整脚本内容、元数据和标签' : '创建可复用的脚本模板'
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

    // 如果是从版本管理入口编辑指定版本，优先使用版本中的脚本内容等信息
    try {
      const stored = sessionStorage.getItem('editTemplateData')
      if (stored) {
        const data = JSON.parse(stored)
        // 只覆盖脚本相关和版本展示相关字段，保留后端返回的其他元数据
        templateData.value = {
          ...templateData.value,
          script_type: data.script_type || templateData.value.script_type,
          description: data.description ?? templateData.value.description,
          script_content: data.script_content || templateData.value.script_content,
          version: data.version || templateData.value.version,
        }
        editingVersionId.value = data.version_id ?? null
        sessionStorage.removeItem('editTemplateData')
      }
    } catch (e) {
      console.error('解析版本编辑数据失败:', e)
    }

    if (isEditVersion.value && !editingVersionId.value) {
      const versionIdParam = Number(route.query.version_id)
      if (versionIdParam) {
        try {
          const versionList = await scriptTemplateApi.getVersions(templateId)
          const targetVersion = versionList.find((v: any) => v.id === versionIdParam)
          if (targetVersion) {
            templateData.value = {
              ...templateData.value,
              description: targetVersion.description ?? templateData.value.description,
              script_content: targetVersion.script_content || templateData.value.script_content,
              version: targetVersion.version || templateData.value.version,
            }
            editingVersionId.value = targetVersion.id
          } else {
            Message.error('未找到指定版本')
          }
        } catch (e) {
          console.error('获取版本内容失败:', e)
          Message.error('获取版本内容失败')
        }
      }
    }
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
const handleSave = async (): Promise<boolean> => {
  try {
    const result = await formRef.value?.submit()
    if (result) {
      // submit 方法会触发 @submit 事件，在 handleSubmit 中处理实际保存
      console.log('表单验证通过，准备保存')
      return true
    }
    return false
  } catch (error) {
    console.error('保存失败:', error)
    Message.error('保存失败')
    return false
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
    }

    console.log('转换后的API数据:', apiData)

    if (isEditVersion.value) {
      if (!templateData.value?.id || !editingVersionId.value) {
        Message.error('版本信息不完整，无法保存')
        return
      }

      const versionData = {
        script_content: data.content || '',
        version: data.version || templateData.value.version || '1.0.0',
        description: data.description || '',
      }

      console.log('更新版本，模板ID:', templateData.value.id, '版本ID:', editingVersionId.value)
      await scriptTemplateApi.updateVersion(templateData.value.id, editingVersionId.value, versionData)
      Message.success('版本更新成功')
    } else if (isEdit.value) {
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

    if (leaveAfterSave.value) {
      leaveAfterSave.value = false
      leaveConfirmVisible.value = false
    }

    if (isEditVersion.value && templateData.value?.id) {
      router.push(`/script-templates/${templateData.value.id}/versions`)
    } else {
      router.push('/script-templates')
    }
  } catch (error: any) {
    console.error('保存模板失败:', error)

    // 详细的错误信息
    let errorMessage = isEditVersion.value
      ? '版本更新失败'
      : isEdit.value ? '模板更新失败' : '模板创建失败'
    if (error.response?.data?.message) {
      errorMessage += ': ' + error.response.data.message
    } else if (error.message) {
      errorMessage += ': ' + error.message
    }

    Message.error(errorMessage)
    leaveAfterSave.value = false
  } finally {
    saving.value = false
  }
}

// 返回列表
const goBack = () => {
  if (!canLeave.value) {
    leaveConfirmVisible.value = true
    return
  }
  router.push('/script-templates')
}

const handleLeaveSave = async () => {
  leaveAfterSave.value = true
  await handleSave()
}

const handleLeaveDiscard = () => {
  leaveConfirmVisible.value = false
  router.push('/script-templates')
}

const handleLeaveCancel = () => {
  leaveConfirmVisible.value = false
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
    perl: 'magenta',
    javascript: 'orange',
    go: 'cyan',
  }
  return colors[type] || 'gray'
}

const getScriptTypeText = (type: string) => {
  const texts = {
    shell: 'Shell',
    python: 'Python',
    powershell: 'PowerShell',
    perl: 'Perl',
    javascript: 'JavaScript',
    go: 'Go',
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

.mb-4 {
  margin-bottom: 16px;
}

.leave-confirm-content {
  margin-bottom: 16px;
  color: var(--color-text-2);
}

.leave-confirm-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
