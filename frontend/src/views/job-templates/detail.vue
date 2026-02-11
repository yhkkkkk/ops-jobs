<template>
  <div class="template-detail">
    <a-page-header
      :title="template?.name || '模板详情'"
      @back="handleBack"
    >
      <template #subtitle>
        <a-space>
          <a-tag v-if="template?.category" color="blue">{{ template.category }}</a-tag>
          <span class="text-gray-500">创建于 {{ formatDate(template?.created_at) }}</span>
        </a-space>
      </template>

      <template #extra>
        <a-space>
          <a-button type="outline" @click="handleRefresh">
            <template #icon>
              <icon-refresh />
            </template>
            刷新
          </a-button>
          <a-button
            type="outline"
            @click="handleEdit"
            v-permission="{ resourceType: 'jobtemplate', permission: 'change', resourceId: template?.id }"
          >
            <template #icon>
              <icon-edit />
            </template>
            编辑
          </a-button>
          <a-button
            type="outline"
            @click="handleCopy"
            v-permission="{ resourceType: 'jobtemplate', permission: 'add' }"
          >
            <template #icon>
              <icon-copy />
            </template>
            复制
          </a-button>
          <a-button
            type="primary"
            @click="handleDebugExecute"
            v-permission="{ resourceType: 'jobtemplate', permission: 'execute', resourceId: template?.id }"
          >
            <template #icon>
              <icon-play-arrow />
            </template>
            调试执行
          </a-button>
        </a-space>
      </template>
    </a-page-header>

    <div class="detail-content" v-if="template">
      <a-row :gutter="24">
        <!-- 基本信息 -->
        <a-col :span="8">
          <a-card title="基本信息" class="mb-4">
            <a-descriptions :column="1" bordered>
              <a-descriptions-item label="模板名称">
                {{ template.name }}
              </a-descriptions-item>
              <a-descriptions-item label="分类">
                {{ template.category || '未分类' }}
              </a-descriptions-item>
              <a-descriptions-item label="标签">
                <a-space v-if="template.tag_list && template.tag_list.length > 0">
                  <a-tag
                    v-for="tag in template.tag_list"
                    :key="`${tag.key}-${tag.value}`"
                    size="small"
                  >
                    <strong>{{ tag.key }}:</strong> {{ tag.value }}
                  </a-tag>
                </a-space>
                <span v-else class="text-gray-400">无标签</span>
              </a-descriptions-item>
              <a-descriptions-item label="创建人">
                {{ template.created_by_name }}
              </a-descriptions-item>
              <a-descriptions-item label="创建时间">
                {{ formatDate(template.created_at) }}
              </a-descriptions-item>
              <a-descriptions-item label="更新时间">
                {{ formatDate(template.updated_at) }}
              </a-descriptions-item>
              <a-descriptions-item label="步骤数量">
                {{ template.step_count }}
              </a-descriptions-item>
              <a-descriptions-item label="执行方案数量">
                {{ template.plan_count }}
              </a-descriptions-item>
            </a-descriptions>

            <div v-if="template.description" class="mt-4">
              <h4 class="description-title">描述</h4>
              <p class="description-text">{{ template.description }}</p>
            </div>

            <!-- 全局变量 -->
            <GlobalVariablesPanel
              class="global-variables-section"
              :variables="template.global_parameters || {}"
              title="全局变量"
              empty-text="暂无全局变量"
            />
          </a-card>
        </a-col>

        <!-- 作业步骤 -->
        <a-col :span="16">
          <a-card title="作业步骤">
            <div v-if="template.steps && template.steps.length > 0" class="steps-list">
              <StepCard
                v-for="(step, index) in template.steps"
                :key="step.id || index"
                class="step-list-item"
                :step="step"
                :index="index"
                :show-detail="false"
                @click="openStepDrawer(step, index)"
              />
            </div>
            <a-empty v-else description="暂无步骤" />
          </a-card>
        </a-col>
      </a-row>
      <a-drawer
        v-model:visible="drawerVisible"
      :width="960"
        :footer="false"
        unmount-on-close
      >
        <template #title>
          <div class="drawer-title">
            <span>步骤 {{ drawerIndex + 1 }}</span>
            <span class="drawer-title-name">{{ getStepDisplayName(drawerStep) }}</span>
          </div>
        </template>
        <StepCard
          v-if="drawerStep"
          class="step-drawer-card"
          :step="drawerStep"
          :index="drawerIndex"
          :show-detail="true"
          :default-expanded="true"
        />
      </a-drawer>
    </div>

    <div v-else class="loading-container">
      <a-spin size="large" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import { IconEdit, IconCopy, IconPlayArrow, IconRefresh } from '@arco-design/web-vue/es/icon'
import { jobTemplateApi } from '@/api/ops'
import type { JobTemplate } from '@/types'
import StepCard from '@/components/StepCard.vue'
import GlobalVariablesPanel from '@/components/GlobalVariablesPanel.vue'

const router = useRouter()
const route = useRoute()

// 响应式数据
const template = ref<JobTemplate | null>(null)
const loading = ref(false)
const drawerVisible = ref(false)
const drawerStep = ref<any | null>(null)
const drawerIndex = ref(0)

// 获取模板详情
const fetchTemplate = async () => {
  try {
    loading.value = true
    const id = Number(route.params.id)
    const response = await jobTemplateApi.getTemplate(id)
    template.value = response
  } catch (error) {
    console.error('获取模板详情失败:', error)
    Message.error('获取模板详情失败')
  } finally {
    loading.value = false
  }
}

const openStepDrawer = (step: any, index: number) => {
  drawerStep.value = step
  drawerIndex.value = index
  drawerVisible.value = true
}

const getStepDisplayName = (step: any) => {
  if (!step) return '未命名步骤'
  return step.name || step.step_name || '未命名步骤'
}

// 格式化日期
const formatDate = (dateString?: string) => {
  if (!dateString) return '-'
  return new Date(dateString).toLocaleString('zh-CN')
}


// 全局变量展示：对密文参数做掩码处理
// 操作方法
// 无论从哪里进入详情，都统一返回到作业模板列表
const handleBack = () => {
  router.push('/job-templates')
}

const handleEdit = () => {
  router.push(`/job-templates/${template.value?.id}/edit`)
}

const handleCopy = () => {
  if (!template.value) return

  // 创建复制的模板数据
  const copiedTemplate = {
    name: `${template.value.name}_副本`,
    description: template.value.description,
    category: template.value.category,
    tags: template.value.tag_list || [],
    global_parameters: template.value.global_parameters || {},
    steps: template.value.steps || []
  }

  // 将复制数据存储到sessionStorage
  sessionStorage.setItem('copyTemplateData', JSON.stringify(copiedTemplate))

  // 跳转到编辑器页面
  router.push('/job-templates/create?action=copy')
  Message.success('模板数据已复制，请修改模板名称后保存')
}

const handleDebugExecute = async () => {
  if (!template.value) return

  try {

    const result = await jobTemplateApi.debugTemplate(template.value.id, {
      execution_parameters: {},
      execution_mode: 'parallel',
      rolling_batch_size: 1,
      rolling_batch_delay: 0
    })
    Message.success('调试执行已启动！')

    // 跳转到执行记录页面查看结果
    router.push(`/execution-records/${result.execution_id}`)

  } catch (error: any) {
    console.error('调试执行失败:', error)
    Message.error(error.response?.data?.message || '调试执行失败')
  }
}

// 刷新模板详情
const handleRefresh = () => {
  fetchTemplate()
}

// 生命周期
onMounted(() => {
  fetchTemplate()
})
</script>

<style scoped>
.template-detail {
  padding: 0;
}

.detail-content {
  padding: 0 24px 24px;
}

.loading-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 400px;
}

.step-item {
  border: 1px solid #e5e6eb;
  border-radius: 6px;
  margin-bottom: 16px;
  overflow: hidden;
}

.steps-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.step-list-item {
  cursor: pointer;
  transition: border-color 0.2s ease;
}

.step-list-item:hover {
  border-color: var(--color-primary-6);
}

.drawer-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
}

.drawer-title-name {
  color: var(--color-text-2);
  font-weight: 500;
}

.step-drawer-card {
  border: none;
  background: transparent;
  box-shadow: none;
}

.step-drawer-card :deep(.step-card-header) {
  display: none;
}

.step-drawer-card :deep(.step-card-body) {
  padding: 0;
}

.step-header {
  display: flex;
  align-items: flex-start;
  padding: 16px;
  background: #f7f8fa;
  border-bottom: 1px solid #e5e6eb;
}

.step-number {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: #165dff;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  margin-right: 12px;
  flex-shrink: 0;
}

.step-info {
  flex: 1;
}

.step-info h4 {
  margin: 0 0 8px 0;
  font-size: 16px;
  font-weight: 600;
}

.step-content {
  padding: 16px;
}

.script-info {
  margin-bottom: 12px;
  padding: 12px 16px;
  background: #f7f8fa;
  border-radius: 6px;
  border: 1px solid #e5e6eb;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.script-meta {
  flex: 1;
}

.script-lines {
  color: #86909c;
  font-size: 12px;
}

.script-actions {
  flex-shrink: 0;
}

.script-preview {
  position: relative;
  margin-bottom: 12px;
  border: 1px solid #e5e6eb;
  border-radius: 6px;
  background: #fafbfc;
  overflow: hidden;
}

.script-preview-content {
  padding: 12px 16px;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 13px;
  line-height: 1.5;
  color: #4e5969;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 80px;
  overflow: hidden;
}

.script-preview-fade {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 20px;
  background: linear-gradient(transparent, #fafbfc);
  pointer-events: none;
}

.script-code {
  border: 1px solid #e5e6eb;
  border-radius: 6px;
  overflow: hidden;
  background: white;
}

.file-transfer-content {
  background: #f7f8fa;
  border-radius: 4px;
  padding: 12px;
}

/* 全局变量样式 */
.global-variables-section {
  margin-top: 24px;
}

.mt-4 {
  margin-top: 16px;
}

/* 位置参数样式 */
.positional-args-section {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #e5e6eb;
}

.positional-args-section h4 {
  margin: 0 0 12px 0;
  font-size: 14px;
  font-weight: 600;
  color: #1d2129;
}

.positional-args {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.positional-arg-item {
  display: flex;
  align-items: center;
  padding: 8px 12px;
  background: #f7f8fa;
  border-radius: 4px;
  border: 1px solid #e5e6eb;
  transition: all 0.2s ease;
}

.positional-arg-item:hover {
  border-color: #165dff;
  background: #f2f3ff;
}

.arg-index {
  font-weight: 600;
  color: #165dff;
  margin-right: 12px;
  min-width: 40px;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 13px;
  background: #e8f3ff;
  padding: 2px 6px;
  border-radius: 3px;
}

.arg-value {
  color: #1d2129;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 13px;
  flex: 1;
  word-break: break-all;
}

/* 目标主机样式 */
.target-hosts {
  margin-top: 8px;
  padding: 8px 0;
}

.target-hosts-label {
  font-size: 12px;
  color: #86909c;
  margin-bottom: 4px;
}

.description-title {
  margin-bottom: 8px; /* 增加标题和描述文本之间的间距 */
}

.description-text {
  color: #4e5969; /* 设置一个柔和的灰色 */
  line-height: 1.6; /* 增加行高以提高可读性 */
}
</style>
