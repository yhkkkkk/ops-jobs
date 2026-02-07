<template>
  <div class="script-template-detail">
    <!-- 页面头部 -->
    <a-page-header
      :title="template?.name || '脚本模板详情'"
      @back="handleBack"
    >
      <template #subtitle>
        <a-space>
          <a-tag v-if="template?.category" color="blue">{{ getCategoryText(template.category) }}</a-tag>
        </a-space>
      </template>

      <template #extra>
        <a-space>
          <span class="text-gray-500">创建于 {{ formatTime(template?.created_at) }}</span>
          <a-button type="outline" @click="handleRefresh">
            <template #icon>
              <icon-refresh />
            </template>
            刷新
          </a-button>
          <a-button
            type="outline"
            @click="handleEdit"
            v-permission="{ resourceType: 'scripttemplate', permission: 'change', resourceId: template?.id }"
          >
            <template #icon>
              <icon-edit />
            </template>
            编辑
          </a-button>
          <a-button
            type="outline"
            @click="handleCopy"
            v-permission="{ resourceType: 'scripttemplate', permission: 'add' }"
          >
            <template #icon>
              <icon-copy />
            </template>
            复制
          </a-button>
          <a-dropdown>
            <a-button type="outline">
              <template #icon>
                <icon-more />
              </template>
            </a-button>
            <template #content>
              <a-doption
                :class="{ 'disabled-option': !canManageVersions }"
                @click="handleVersions"
              >
                <template #icon>
                  <icon-history />
                </template>
                版本管理
              </a-doption>
              <a-doption
                :class="{ 'disabled-option': !canToggleStatus }"
                @click="handleToggleStatus"
              >
                <template #icon>
                  <icon-poweroff />
                </template>
                {{ template?.is_active ? '下线' : '上线' }}
              </a-doption>
              <a-doption
                :class="['text-red-500', { 'disabled-option': !canDeleteTemplate }]"
                @click="handleDelete"
              >
                <template #icon>
                  <icon-delete />
                </template>
                删除
              </a-doption>
            </template>
          </a-dropdown>
        </a-space>
      </template>
    </a-page-header>

    <div class="detail-content" v-if="template">
      <a-row :gutter="24">
        <a-col :span="8">
          <!-- 基本信息 -->
          <a-card title="基本信息" class="mb-4">
            <a-descriptions :column="1" bordered>
              <a-descriptions-item label="模板名称">
                {{ template.name }}
              </a-descriptions-item>
              <a-descriptions-item label="脚本类型">
                <a-tag :color="getScriptTypeColor(template.script_type)">
                  {{ getScriptTypeText(template.script_type) }}
                </a-tag>
              </a-descriptions-item>
              <a-descriptions-item label="分类">
                {{ template.category || '未分类' }}
              </a-descriptions-item>
              <a-descriptions-item label="版本">
                {{ template.version || '1.0.0' }}
              </a-descriptions-item>
              <a-descriptions-item label="状态">
                <a-tag :color="template.is_active ? 'green' : 'red'">
                  {{ template.is_active ? '上线' : '下线' }}
                </a-tag>
              </a-descriptions-item>
              <a-descriptions-item label="创建人">
                {{ template.created_by_name }}
              </a-descriptions-item>
              <a-descriptions-item label="创建时间">
                {{ formatTime(template.created_at) }}
              </a-descriptions-item>
              <a-descriptions-item label="更新时间">
                {{ formatTime(template.updated_at) }}
              </a-descriptions-item>
            </a-descriptions>

            <div v-if="template?.description" class="mt-4">
              <h4 class="description-title">描述</h4>
              <p class="description-text">{{ template?.description }}</p>
            </div>

            <!-- 标签信息 -->
            <div class="mt-4">
              <h4 class="description-title">标签</h4>
              <div v-if="template?.tag_list && template.tag_list.length > 0">
                <a-space wrap>
                  <a-tag
                    v-for="tag in template.tag_list"
                    :key="`${tag.key}-${tag.value}`"
                    size="small"
                  >
                    <strong>{{ tag.key }}:</strong> {{ tag.value }}
                  </a-tag>
                </a-space>
              </div>
              <span v-else class="text-gray-400">无标签</span>
            </div>
          </a-card>
        </a-col>

        <a-col :span="16">
          <!-- 脚本内容 -->
          <a-card title="脚本内容">
            <simple-monaco-editor
              :model-value="template?.script_content || template?.content || ''"
              :language="template?.script_type || 'shell'"
              :height="500"
              :readonly="true"
            />
          </a-card>
        </a-col>
      </a-row>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Message, Modal } from '@arco-design/web-vue'
import {
  IconRefresh,
  IconEdit,
  IconCopy,
  IconMore,
  IconHistory,
  IconPoweroff,
  IconDelete,
  IconArrowLeft
} from '@arco-design/web-vue/es/icon'
import { scriptTemplateApi } from '@/api/ops'
import type { ScriptTemplate } from '@/types'
import SimpleMonacoEditor from '@/components/SimpleMonacoEditor.vue'
import { usePermissionsStore } from '@/stores/permissions'

const router = useRouter()
const route = useRoute()
const permissionsStore = usePermissionsStore()

const loading = ref(false)
const template = ref<ScriptTemplate | null>(null)

const templateId = Number(route.params.id)

// 获取模板详情
const fetchTemplate = async () => {
  loading.value = true
  try {
    const data = await scriptTemplateApi.getTemplate(templateId)
    template.value = data
  } catch (error) {
    console.error('获取脚本模板详情失败:', error)
    Message.error('获取模板详情失败')
    router.back()
  } finally {
    loading.value = false
  }
}

// 返回上一页
const handleBack = () => {
  router.back()
}

// 刷新
const handleRefresh = () => {
  fetchTemplate()
}

// 编辑
const handleEdit = () => {
  router.push(`/script-templates/${templateId}/edit`)
}

// 复制
const handleCopy = () => {
  const copiedTemplate = {
    name: `${template.value?.name}_副本`,
    description: template.value?.description,
    script_type: template.value?.script_type,
    script_content: template.value?.script_content || template.value?.content,
    tags_json: template.value?.tags_json || {},
    category: template.value?.category || '',
  }

  sessionStorage.setItem('copyTemplateData', JSON.stringify(copiedTemplate))
  router.push('/script-templates/create?action=copy')
}

// 版本管理
const handleVersions = () => {
  router.push(`/script-templates/${templateId}/versions`)
}

// 切换状态
const handleToggleStatus = async () => {
  if (!template.value) return

  const action = template.value.is_active ? '下线' : '上线'
  Modal.confirm({
    title: `确认${action}`,
    content: `确定要${action}模板 "${template.value.name}" 吗？`,
    onOk: async () => {
      try {
        const result = await scriptTemplateApi.toggleStatus(templateId)
        template.value!.is_active = result.is_active
        Message.success(`模板已${action}`)
      } catch (error) {
        console.error(`${action}失败:`, error)
        Message.error(`${action}失败`)
      }
    }
  })
}

// 删除
const handleDelete = async () => {
  if (!template.value) return

  Modal.confirm({
    title: '确认删除',
    content: `确定要删除模板"${template.value.name}"吗？此操作不可恢复。`,
    onOk: async () => {
      try {
        await scriptTemplateApi.deleteTemplate(templateId)
        Message.success('模板删除成功')
        router.push('/script-templates')
      } catch (error) {
        Message.error('模板删除失败')
        console.error('删除模板失败:', error)
      }
    }
  })
}

// 工具函数
const getScriptTypeColor = (type: string) => {
  const colors = {
    shell: 'blue',
    python: 'green',
    powershell: 'purple',
    javascript: 'yellow',
    go: 'cyan',
  }
  return colors[type] || 'gray'
}

const getScriptTypeText = (type: string) => {
  const texts = {
    shell: 'Shell',
    python: 'Python',
    powershell: 'PowerShell',
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

const formatTag = (tag: any) => {
  if (tag && typeof tag === 'object') {
    const key = tag.key ?? ''
    const value = tag.value ?? ''
    return value ? `${key}=${value}` : key
  }
  return String(tag)
}

const formatTime = (timestamp: string) => {
  if (!timestamp) return '-'
  return new Date(timestamp).toLocaleString('zh-CN')
}

// 权限检查
const canManageVersions = computed(() => {
  if (permissionsStore.isSuperUser) return true
  return (
    permissionsStore.hasPermission('scripttemplate', 'change', templateId) ||
    permissionsStore.hasPermission('scripttemplate', 'change')
  )
})

const canToggleStatus = computed(() => {
  return canManageVersions.value
})

const canDeleteTemplate = computed(() => {
  if (permissionsStore.isSuperUser) return true
  return (
    permissionsStore.hasPermission('scripttemplate', 'delete', templateId) ||
    permissionsStore.hasPermission('scripttemplate', 'delete')
  )
})

// 生命周期
onMounted(() => {
  fetchTemplate()
})
</script>

<style scoped>
.script-template-detail {
  padding: 0;
}

.detail-content {
  padding: 0 24px 24px;
}

.mb-6 {
  margin-bottom: 24px;
}

.mt-6 {
  margin-top: 24px;
}

.text-gray-400 {
  color: #86909c;
}

.text-gray-500 {
  color: #86909c;
}

.disabled-option {
  opacity: 0.5;
  cursor: not-allowed;
}

/* 页面头部样式 */
.page-header {
  background: white;
  border-radius: 6px;
  padding: 20px 24px;
  margin-bottom: 16px;
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.03), 0 1px 6px -1px rgba(0, 0, 0, 0.02), 0 2px 4px 0 rgba(0, 0, 0, 0.02);
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left {
  flex: 1;
  min-width: 0;
}

.header-title-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 4px;
}

.back-button {
  padding: 4px;
  color: var(--color-text-3);
}

.back-button:hover {
  color: var(--color-text-1);
  background-color: var(--color-fill-2);
}

.header-left h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: #1d2129;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.header-subtitle {
  margin-top: 4px;
}

.header-right {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 16px;
}

.header-info {
  flex-shrink: 0;
}

:deep(.arco-descriptions-item-label) {
  font-weight: 500;
}

:deep(.arco-card .arco-card-header) {
  border-bottom: 1px solid var(--color-border-2);
}

.mt-4 {
  margin-top: 16px;
}

.description-title {
  margin: 0 0 8px 0;
  font-size: 14px;
  font-weight: 600;
  color: #1d2129;
}

.description-text {
  color: #4e5969;
  line-height: 1.6;
}
</style>
