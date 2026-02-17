<template>
  <div class="script-template-versions-page">
    <a-page-header
      :title="`脚本模板版本管理 - ${template?.name || ''}`"
      @back="handleBack"
    />

    <a-card class="mb-4">
      <a-descriptions :column="3" bordered size="small" v-if="template">
        <a-descriptions-item label="模板名称">
          {{ template.name }}
        </a-descriptions-item>
        <a-descriptions-item label="脚本类型">
          <a-tag :color="getScriptTypeColor(template.script_type)">
            {{ getScriptTypeText(template.script_type) }}
          </a-tag>
        </a-descriptions-item>
        <a-descriptions-item label="当前版本">
          {{ template.version || '未设置' }}
        </a-descriptions-item>
        <a-descriptions-item label="状态">
          <a-tag :color="template.is_active ? 'green' : 'red'">
            {{ template.is_active ? '上线' : '下线' }}
          </a-tag>
        </a-descriptions-item>
        <a-descriptions-item label="创建者">
          {{ template.created_by_name }}
        </a-descriptions-item>
      </a-descriptions>
    </a-card>

    <a-card>
      <div class="mb-4">
        <a-button type="primary" @click="showCreateVersion = true">
          <template #icon>
            <icon-plus />
          </template>
          创建新版本
        </a-button>
      </div>

      <a-table
        :columns="versionColumns"
        :data="versions"
        :loading="versionLoading"
        :pagination="false"
        row-key="id"
      >
        <template #is_active="{ record }">
          <a-tag :color="record.is_active ? 'green' : 'gray'">
            {{ record.is_active ? '当前版本' : '历史版本' }}
          </a-tag>
        </template>

        <template #created_at="{ record }">
          {{ dayjs(record.created_at).format('YYYY-MM-DD HH:mm:ss') }}
        </template>

        <template #actions="{ record }">
          <a-dropdown>
            <a-button type="text" size="small">
              <template #icon>
                <icon-more />
              </template>
            </a-button>
            <template #content>
              <a-doption
                v-if="!record.is_active"
                class="action-success"
                @click="handleRollback(record)"
              >
                设为当前
              </a-doption>
              <a-doption
                v-if="!record.is_active"
                class="action-info"
                @click="handleCompareWithCurrent(record)"
              >
                对比当前
              </a-doption>
              <a-doption class="action-primary" @click="handleEditVersion(record)">
                编辑
              </a-doption>
              <a-doption class="action-muted" @click="handleViewVersion(record)">
                查看
              </a-doption>
              <a-doption class="action-blue" @click="handleCopyFromVersion(record)">
                复制并新建
              </a-doption>
              <a-doption class="action-success" @click="handleExecuteVersion(record)">
                去执行
              </a-doption>
              <a-doption
                :class="template?.is_active ? 'action-danger' : 'action-success'"
                @click="handleDisableFromVersion"
              >
                {{ template?.is_active ? '禁用模板' : '启用模板' }}
              </a-doption>
            </template>
          </a-dropdown>
        </template>
      </a-table>
    </a-card>

    <!-- 创建版本弹窗 -->
    <a-modal
      v-model:visible="showCreateVersion"
      title="创建新版本"
      @ok="handleCreateVersion"
      @cancel="resetVersionForm"
    >
      <a-form :model="versionForm" layout="vertical">
        <a-form-item label="版本号" required>
          <a-input
            v-model="versionForm.version"
            placeholder="请输入版本号，如：1.1.0"
          />
        </a-form-item>
        <a-form-item label="版本描述">
          <a-textarea
            v-model="versionForm.description"
            placeholder="请输入版本描述"
            :rows="3"
          />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 版本内容查看弹窗 -->
    <a-modal
      v-model:visible="versionContentVisible"
      title="版本内容"
      :width="1000"
      :footer="false"
    >
      <div v-if="currentVersion">
        <a-descriptions :column="2" bordered class="mb-4">
          <a-descriptions-item label="版本号">
            {{ currentVersion.version }}
          </a-descriptions-item>
          <a-descriptions-item label="创建者">
            {{ currentVersion.created_by_name }}
          </a-descriptions-item>
          <a-descriptions-item label="创建时间" :span="2">
            {{ dayjs(currentVersion.created_at).format('YYYY-MM-DD HH:mm:ss') }}
          </a-descriptions-item>
          <a-descriptions-item label="描述" :span="2">
            {{ currentVersion.description || '暂无描述' }}
          </a-descriptions-item>
        </a-descriptions>

        <div>
          <h4>脚本内容</h4>
          <simple-monaco-editor
            :model-value="currentVersion.script_content"
            :language="template?.script_type || 'shell'"
            :height="400"
            :readonly="true"
          />
        </div>
      </div>
    </a-modal>

    <!-- 版本对比弹窗 -->
    <a-modal
      v-model:visible="versionDiffVisible"
      title="版本对比"
      :width="1100"
      :footer="false"
    >
      <div v-if="diffBaseVersion && diffTargetVersion" class="version-diff-container">
        <div class="version-diff-meta">
          <div class="version-diff-meta-column">
            <h4>当前版本 {{ diffBaseVersion.version }}</h4>
            <a-descriptions :column="1" bordered size="small" class="mb-2">
              <a-descriptions-item label="创建者">
                {{ diffBaseVersion.created_by_name }}
              </a-descriptions-item>
              <a-descriptions-item label="创建时间">
                {{ dayjs(diffBaseVersion.created_at).format('YYYY-MM-DD HH:mm:ss') }}
              </a-descriptions-item>
            </a-descriptions>
          </div>
          <div class="version-diff-meta-column">
            <h4>对比版本 {{ diffTargetVersion.version }}</h4>
            <a-descriptions :column="1" bordered size="small" class="mb-2">
              <a-descriptions-item label="创建者">
                {{ diffTargetVersion.created_by_name }}
              </a-descriptions-item>
              <a-descriptions-item label="创建时间">
                {{ dayjs(diffTargetVersion.created_at).format('YYYY-MM-DD HH:mm:ss') }}
              </a-descriptions-item>
            </a-descriptions>
          </div>
        </div>
        <monaco-diff-editor
          :original="diffBaseVersion.script_content"
          :modified="diffTargetVersion.script_content"
          :language="template?.script_type || 'shell'"
          :height="450"
          :readonly="true"
        />
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Message, Modal } from '@arco-design/web-vue'
import { scriptTemplateApi } from '@/api/ops'
import type { ScriptTemplate } from '@/types'
import SimpleMonacoEditor from '@/components/SimpleMonacoEditor.vue'
import MonacoDiffEditor from '@/components/MonacoDiffEditor.vue'
import dayjs from 'dayjs'
import { IconPlus, IconMore } from '@arco-design/web-vue/es/icon'

const route = useRoute()
const router = useRouter()

const template = ref<ScriptTemplate | null>(null)
const versions = ref<any[]>([])
const versionLoading = ref(false)
const showCreateVersion = ref(false)
const versionForm = reactive({
  version: '',
  description: ''
})

const versionContentVisible = ref(false)
const currentVersion = ref<any>(null)

const versionDiffVisible = ref(false)
const diffBaseVersion = ref<any>(null)
const diffTargetVersion = ref<any>(null)

const versionColumns = [
  {
    title: '版本号',
    dataIndex: 'version',
    key: 'version',
    width: 80,
  },
  {
    title: '状态',
    dataIndex: 'is_active',
    key: 'is_active',
    slotName: 'is_active',
    width: 80,
  },
  {
    title: '描述',
    dataIndex: 'description',
    key: 'description',
    ellipsis: true,
    tooltip: true,
    width: 150,
  },
  {
    title: '创建者',
    dataIndex: 'created_by_name',
    key: 'created_by_name',
    width: 100,
  },
  {
    title: '创建时间',
    dataIndex: 'created_at',
    key: 'created_at',
    slotName: 'created_at',
    width: 150,
  },
  {
    title: '操作',
    key: 'actions',
    slotName: 'actions',
    width: 120,
    fixed: 'right',
  },
]

const handleBack = () => {
  router.push('/script-templates')
}

const fetchTemplate = async () => {
  const id = Number(route.params.id)
  if (!id) {
    Message.error('模板ID无效')
    handleBack()
    return
  }

  try {
    template.value = await scriptTemplateApi.getTemplate(id)
  } catch (error) {
    console.error('获取模板详情失败:', error)
    Message.error('获取模板详情失败')
    handleBack()
  }
}

const fetchVersions = async () => {
  if (!template.value?.id) return

  versionLoading.value = true
  try {
    versions.value = await scriptTemplateApi.getVersions(template.value.id)
  } catch (error) {
    console.error('获取版本列表失败:', error)
    Message.error('获取版本列表失败')
  } finally {
    versionLoading.value = false
  }
}

const handleCreateVersion = async () => {
  if (!template.value?.id) return
  if (!versionForm.version.trim()) {
    Message.error('请输入版本号')
    return
  }

  try {
    await scriptTemplateApi.createVersion(template.value.id, {
      version: versionForm.version,
      description: versionForm.description
    })
    Message.success('创建版本成功')
    showCreateVersion.value = false
    resetVersionForm()
    await fetchVersions()
  } catch (error) {
    console.error('创建版本失败:', error)
    Message.error('创建版本失败')
  }
}

const handleRollback = async (version: any) => {
  if (!template.value?.id) return

  Modal.confirm({
    title: '确认设为当前版本',
    content: `将版本 ${version.version} 设为当前后，会同步更新模板内容并保留原当前版本为历史记录，是否继续？`,
    onOk: async () => {
      try {
        await scriptTemplateApi.rollbackVersion(template.value!.id!, version.id)
        Message.success('已设为当前版本')
        await fetchTemplate()
        await fetchVersions()
      } catch (error) {
        console.error('设置当前版本失败:', error)
        Message.error('设置当前版本失败')
      }
    }
  })
}

const handleViewVersion = (version: any) => {
  currentVersion.value = version
  versionContentVisible.value = true
}

const handleEditVersion = (version: any) => {
  if (!template.value) {
    Message.error('当前未选择模板')
    return
  }

  const editData = {
    ...template.value,
    script_content: version.script_content,
    version: version.version,
    description: version.description,
    version_id: version.id,
    is_active: !!version.is_active,
  }

  sessionStorage.setItem('editTemplateData', JSON.stringify(editData))
  router.push(`/script-templates/${template.value.id}/edit?action=editVersion&version_id=${version.id}`)
}

const handleCopyFromVersion = (version: any) => {
  if (!template.value) {
    Message.error('当前未选择模板')
    return
  }

  const copiedTemplate = {
    name: `${template.value.name}_v${version.version}_副本`,
    description: template.value.description,
    script_type: template.value.script_type,
    script_content: version.script_content,
    tags_json: template.value.tags_json || {},
    category: template.value.category || '',
  }

  sessionStorage.setItem('copyTemplateData', JSON.stringify(copiedTemplate))
  router.push('/script-templates/create?action=copy')
}

const handleExecuteVersion = (version: any) => {
  if (!template.value) {
    Message.error('当前未选择模板')
    return
  }

  const data = {
    script_content: version.script_content,
    script_type: template.value.script_type,
    template_name: template.value.name,
    version: version.version,
  }

  sessionStorage.setItem('quickExecuteScriptData', JSON.stringify(data))
  router.push('/quick-execute')
}

const handleDisableFromVersion = async () => {
  if (!template.value?.id) return

  const action = template.value.is_active ? '下线' : '上线'
  Modal.confirm({
    title: `确认${action}`,
    content: `确定要${action}模板 "${template.value.name}" 吗？`,
    onOk: async () => {
      try {
        const result = await scriptTemplateApi.toggleStatus(template.value!.id!)
        template.value!.is_active = result.is_active
        Message.success(`模板已${action}`)
      } catch (error) {
        console.error(`${action}失败:`, error)
        Message.error(`${action}失败`)
      }
    }
  })
}

const handleCompareWithCurrent = (version: any) => {
  const active = versions.value.find(v => v.is_active)
  if (!active) {
    Message.warning('当前没有标记为“当前版本”的版本记录')
    return
  }

  diffBaseVersion.value = active
  diffTargetVersion.value = version
  versionDiffVisible.value = true
}

const resetVersionForm = () => {
  versionForm.version = ''
  versionForm.description = ''
}

const getScriptTypeColor = (type: string) => {
  const colors = {
    shell: 'blue',
    python: 'green',
    powershell: 'purple',
    perl: 'magenta',
    javascript: 'orange',
    go: 'cyan',
  } as Record<string, string>
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
  } as Record<string, string>
  return texts[type] || type
}

onMounted(async () => {
  await fetchTemplate()
  await fetchVersions()
})
</script>

<style scoped>
.script-template-versions-page {
  padding: 0;
}

.mb-4 {
  margin-bottom: 16px;
}

.version-diff-container {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.version-diff-meta {
  display: flex;
  gap: 16px;
}

.version-diff-meta-column {
  flex: 1;
}

:deep(.action-success) {
  color: var(--color-success-6);
}

:deep(.action-danger) {
  color: var(--color-danger-6);
}

:deep(.action-warning) {
  color: var(--color-warning-6);
}

:deep(.action-info) {
  color: var(--color-primary-6);
}

:deep(.action-primary) {
  color: var(--color-primary-6);
}

:deep(.action-blue) {
  color: var(--color-blue-6, #165dff);
}

:deep(.action-muted) {
  color: var(--color-text-3);
}
</style>


