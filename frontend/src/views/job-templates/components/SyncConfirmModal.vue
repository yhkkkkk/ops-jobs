<template>
  <a-modal
    v-model:visible="modalVisible"
    title="同步执行方案确认"
    width="900px"
    @cancel="handleCancel"
    @ok="handleConfirm"
    :confirm-loading="loading"
    :ok-button-props="{ disabled: !hasPlansToSync }"
    ok-text="确认同步"
    cancel-text="取消"
    :body-style="{ maxHeight: '70vh', overflow: 'auto' }"
  >
    <div v-if="previewLoading" class="text-center py-8">
      <a-spin size="large" />
      <div class="mt-4 text-gray-500">正在获取同步预览...</div>
    </div>

    <div v-else-if="previewData" class="sync-preview">
      <!-- 简化的模板信息 -->
      <div class="mb-4 p-4 border rounded">
        <h3 class="text-lg font-medium mb-2">{{ previewData.template_name || '未知模板' }}</h3>
        <p class="text-sm text-gray-600 mb-2">
          最后更新：{{ previewData.template_updated_at ? formatDateTime(previewData.template_updated_at) : '未知' }}
        </p>
        <p class="text-sm">
          共 {{ previewData.total || 0 }} 个执行方案，
          {{ previewData.plans?.filter(p => p.needs_sync).length || 0 }} 个需要同步
        </p>
      </div>

      <!-- 执行方案列表 -->
      <div class="mb-4">
        <h3 class="text-base font-medium mb-3">执行方案详情</h3>

        <div v-if="!previewData.plans || previewData.plans.length === 0" class="text-center py-8">
          <a-empty description="没有关联的执行方案" />
        </div>

        <div v-else>
          <div
            v-for="plan in previewData.plans"
            :key="plan.plan_id"
            class="mb-3 p-4 border rounded"
          >
            <div class="flex items-center justify-between mb-2">
              <h4 class="font-medium">{{ plan.plan_name }}</h4>
              <span class="text-sm px-2 py-1 rounded" :class="{
                'bg-orange-100 text-orange-800': plan.needs_sync,
                'bg-green-100 text-green-800': !plan.needs_sync
              }">
                {{ plan.needs_sync ? '需要同步' : '已同步' }}
              </span>
            </div>

            <div v-if="plan.plan_description" class="text-sm text-gray-600 mb-2">
              {{ plan.plan_description }}
            </div>

            <div class="text-xs text-gray-500">
              <span v-if="plan.last_sync_at">
                上次同步: {{ formatDateTime(plan.last_sync_at) }}
              </span>
              <span v-else>从未同步</span>
            </div>

            <!-- 变更详情 -->
            <div v-if="plan.changes && plan.changes.has_changes" class="mt-3">
              <!-- 变更摘要 -->
              <div class="p-3 bg-gray-50 rounded text-sm mb-3">
                <div class="font-medium text-gray-700 mb-1">变更摘要</div>
                {{ plan.changes.summary }}
              </div>

              <!-- 全局变量变更 -->
              <div
                v-if="plan.changes.global_parameters_changed"
                class="p-3 bg-blue-50 border border-blue-100 rounded text-sm mb-3"
              >
                <div class="text-blue-800 font-medium mb-3">
                  全局变量已更新 ({{ getGlobalParamChanges(plan).length }})
                </div>
                <div class="space-y-2">
                  <div
                    v-for="item in getGlobalParamChanges(plan)"
                    :key="item.key"
                    class="global-param-item"
                  >
                    <div class="flex items-center gap-2 mb-2">
                      <a-tag color="blue" size="small">{{ item.key }}</a-tag>
                      <a-tag v-if="item.typeOld || item.typeNew" size="small" color="arcoblue">
                        {{ item.typeNew || item.typeOld }}
                      </a-tag>
                      <a-tag v-if="item.status === 'added'" size="small" color="green">新增</a-tag>
                      <a-tag v-else-if="item.status === 'deleted'" size="small" color="red">删除</a-tag>
                    </div>
                    <div class="global-param-values">
                      <div class="param-value old">
                        <span class="label">原值:</span>
                        <span class="value">{{ item.oldDisplay || '(空)' }}</span>
                      </div>
                      <div class="param-value new">
                        <span class="label">新值:</span>
                        <span class="value">{{ item.newDisplay || '(空)' }}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- 新增/删除步骤提示 -->
              <div v-if="plan.changes.added_steps?.length || plan.changes.deleted_steps?.length" class="space-y-2 mb-3">
                <div v-if="plan.changes.added_steps?.length" class="p-3 bg-green-50 border border-green-100 rounded text-sm">
                  <div class="font-medium text-green-800 mb-1">新增步骤 ({{ plan.changes.added_steps.length }})</div>
                  <div class="flex flex-col gap-1">
                    <div v-for="step in plan.changes.added_steps" :key="step.step_id" class="flex items-center justify-between text-sm">
                      <span>步骤 {{ step.order }} · {{ step.name }}</span>
                      <a-tag size="small" color="green">新增</a-tag>
                    </div>
                  </div>
                </div>
                <div v-if="plan.changes.deleted_steps?.length" class="p-3 bg-red-50 border border-red-100 rounded text-sm">
                  <div class="font-medium text-red-800 mb-1">删除步骤 ({{ plan.changes.deleted_steps.length }})</div>
                  <div class="flex flex-col gap-1">
                    <div v-for="step in plan.changes.deleted_steps" :key="step.step_id" class="flex items-center justify-between text-sm">
                      <span>步骤 {{ step.order }} · {{ step.name }}</span>
                      <a-tag size="small" color="red">删除</a-tag>
                    </div>
                  </div>
                </div>
              </div>

              <!-- 详细变更 -->
              <div class="space-y-3">
                <!-- 修改的步骤 -->
                <div v-if="plan.changes.modified_steps && plan.changes.modified_steps.length > 0">
                  <div class="text-sm font-medium text-orange-700 mb-2">
                    <icon-edit class="mr-1" />
                    修改的步骤 ({{ plan.changes.modified_steps.length }})
                  </div>

                  <!-- 使用折叠面板显示详细变更 -->
                  <a-collapse class="detailed-changes-collapse">
                    <a-collapse-item
                      v-for="step in plan.changes.modified_steps"
                      :key="step.step_id"
                      :header="`步骤 ${step.order}: ${step.name}`"
                    >
                      <template #extra>
                        <a-tag color="orange" size="small">
                          {{ step.detailed_changes?.length || step.changes?.length || 0 }} 项变更
                        </a-tag>
                      </template>

                      <!-- 详细变更对比 -->
                      <div v-if="step.detailed_changes?.length" class="space-y-4">
                        <div
                          v-for="(change, index) in step.detailed_changes"
                          :key="index"
                          class="change-item"
                        >
                          <div class="change-header">
                            <a-tag color="blue" size="small">{{ change.field_name }}</a-tag>
                          </div>

                          <!-- 文本类型变更 -->
                          <div v-if="change.change_type === 'text'" class="change-content">
                            <div class="change-row">
                              <span class="change-label old">原值:</span>
                              <span class="change-value old">{{ change.old_value || '(空)' }}</span>
                            </div>
                            <div class="change-row">
                              <span class="change-label new">新值:</span>
                              <span class="change-value new">{{ change.new_value || '(空)' }}</span>
                            </div>
                          </div>

                          <!-- 代码类型变更 -->
                          <div v-else-if="change.change_type === 'code'" class="change-content">
                            <div class="code-diff">
                              <div class="code-section">
                                <div class="code-header old">原脚本内容:</div>
                                <pre class="code-content old">{{ change.old_value || '(空)' }}</pre>
                              </div>
                              <div class="code-section">
                                <div class="code-header new">新脚本内容:</div>
                                <pre class="code-content new">{{ change.new_value || '(空)' }}</pre>
                              </div>
                            </div>
                          </div>

                          <!-- JSON类型变更 -->
                          <div v-else-if="change.change_type === 'json'" class="change-content">
                            <div class="json-diff">
                              <div class="json-section">
                                <div class="json-header old">原参数:</div>
                                <pre class="json-content old">{{ formatJson(change.old_value) }}</pre>
                              </div>
                              <div class="json-section">
                                <div class="json-header new">新参数:</div>
                                <pre class="json-content new">{{ formatJson(change.new_value) }}</pre>
                              </div>
                            </div>
                          </div>

                          <!-- 列表类型变更 -->
                          <div v-else-if="change.change_type === 'list'" class="change-content">
                            <div class="list-diff">
                              <div class="list-section">
                                <div class="list-header old">原{{ change.field_name }}:</div>
                                <div class="list-content old">
                                  <a-tag v-for="item in change.old_value" :key="item" size="small" class="mb-1">
                                    {{ item }}
                                  </a-tag>
                                  <span v-if="!change.old_value?.length" class="text-gray-400">(空)</span>
                                </div>
                              </div>
                              <div class="list-section">
                                <div class="list-header new">新{{ change.field_name }}:</div>
                                <div class="list-content new">
                                  <a-tag v-for="item in change.new_value" :key="item" size="small" class="mb-1">
                                    {{ item }}
                                  </a-tag>
                                  <span v-if="!change.new_value?.length" class="text-gray-400">(空)</span>
                                </div>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>

                      <!-- 简单变更描述（向后兼容） -->
                      <div v-else-if="step.changes?.length" class="space-y-2">
                        <div v-for="(change, index) in step.changes" :key="index" class="simple-change">
                          <a-tag color="orange" size="small">{{ change }}</a-tag>
                        </div>
                      </div>
                    </a-collapse-item>
                  </a-collapse>
                </div>
              </div>
            </div>

            <!-- 无变更状态 -->
            <div v-else-if="plan.changes && !plan.changes.has_changes" class="mt-3 p-3 bg-green-50 border border-green-200 rounded text-sm">
              <div class="text-green-700 flex items-center">
                <icon-check-circle class="mr-2" />
                {{ plan.changes.summary || '执行方案与模板内容一致，无需同步' }}
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 同步说明 -->
      <div v-if="hasPlansToSync" class="p-4 bg-blue-50 border border-blue-200 rounded">
        <div class="text-sm text-blue-800">
          <div class="font-medium mb-2">同步说明:</div>
          <div>
            <p>• 同步将更新执行方案中步骤的脚本内容、参数配置等，使其与模板保持一致</p>
            <p>• 执行方案的步骤选择不会改变，只更新步骤内容</p>
            <p>• 用户自定义的执行参数和超时设置将被模板设置覆盖</p>
            <p>• 同步操作不可撤销，请确认后再执行</p>
          </div>
        </div>
      </div>

      <!-- 无需同步提示 -->
      <div v-else class="p-4 bg-green-50 border border-green-200 rounded">
        <div class="text-sm text-green-800">
          <div class="font-medium mb-2 flex items-center">
            <icon-check-circle class="mr-2" />
            所有执行方案已同步
          </div>
          <p>所有关联的执行方案都与模板内容保持一致，无需进行同步操作。</p>
        </div>
      </div>
    </div>

    <div v-else class="text-center py-8">
      <a-empty description="无法获取同步预览数据" />
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { Message } from '@arco-design/web-vue'
import {
  IconEdit,
  IconCheckCircle
} from '@arco-design/web-vue/es/icon'
import { jobTemplateApi } from '@/api/ops'
import { formatDateTime } from '@/utils/date'

interface Props {
  visible: boolean
  templateId?: number
  templateName?: string
}

interface Emits {
  (e: 'update:visible', visible: boolean): void
  (e: 'sync-success'): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const modalVisible = ref(false)
const loading = ref(false)
const previewLoading = ref(false)
const previewData = ref<any>(null)

// 格式化JSON
const formatJson = (value: any) => {
  if (!value) return '(空)'
  if (typeof value === 'string') return value
  return JSON.stringify(value, null, 2)
}

// 全局变量变更列表
const getGlobalParamChanges = (plan: any) => {
  const oldParams = plan?.changes?.old_global_parameters || {}
  const newParams = plan?.changes?.new_global_parameters || {}
  const keys = Array.from(new Set([...Object.keys(oldParams), ...Object.keys(newParams)]))

  return keys.map((key) => {
    const oldParam = oldParams[key]
    const newParam = newParams[key]
    const oldDisplay = extractParamValue(oldParam)
    const newDisplay = extractParamValue(newParam)
    const typeOld = extractParamType(oldParam)
    const typeNew = extractParamType(newParam)
    let status: 'changed' | 'added' | 'deleted' = 'changed'
    if (oldParam === undefined) status = 'added'
    else if (newParam === undefined) status = 'deleted'

    return { key, oldDisplay, newDisplay, typeOld, typeNew, status }
  })
}

const extractParamValue = (param: any) => {
  if (param === null || param === undefined) return ''
  if (typeof param === 'object' && 'value' in param) return (param as any).value
  return typeof param === 'object' ? JSON.stringify(param) : param
}

const extractParamType = (param: any) => {
  if (param && typeof param === 'object' && 'type' in param) return (param as any).type
  return ''
}

// 计算是否有需要同步的方案
const hasPlansToSync = computed(() => {
  if (!previewData.value?.plans) return false
  return previewData.value.plans.some((plan: any) => plan.needs_sync)
})

// 监听visible变化
watch(
  () => props.visible,
  (visible) => {
    modalVisible.value = visible
    if (visible && props.templateId) {
      fetchSyncPreview()
    }
  },
  { immediate: true }
)

// 监听modalVisible变化
watch(modalVisible, (visible) => {
  emit('update:visible', visible)
})

// 获取同步预览
const fetchSyncPreview = async () => {
  if (!props.templateId) return

  previewLoading.value = true
  try {
    const response = await jobTemplateApi.getSyncPreview(props.templateId)
    console.log('同步预览响应:', response)

    // 响应拦截器已经返回了 data.content，所以直接使用 response
    previewData.value = response
  } catch (error: any) {
    console.error('获取同步预览失败:', error)
    Message.error(error.response?.data?.message || '获取同步预览失败')
  } finally {
    previewLoading.value = false
  }
}

// 确认同步
const handleConfirm = async () => {
  if (!props.templateId) return

  // 检查是否有需要同步的方案
  if (!hasPlansToSync.value) {
    Message.info('所有执行方案已同步，无需进行同步操作')
    return
  }

  loading.value = true
  try {
    await jobTemplateApi.syncPlans(props.templateId)
    Message.success('同步成功')
    modalVisible.value = false
    emit('sync-success')
  } catch (error: any) {
    console.error('同步失败:', error)
    Message.error(error.response?.data?.message || '同步失败')
  } finally {
    loading.value = false
  }
}

// 取消
const handleCancel = () => {
  modalVisible.value = false
  previewData.value = null
}
</script>

<style scoped>
.sync-preview {
  /* 移除固定高度，让模态框自己控制滚动 */
}

/* 变更详情样式 */
.space-y-1 > * + * {
  margin-top: 0.25rem;
}

.space-y-2 > * + * {
  margin-top: 0.5rem;
}

.space-y-3 > * + * {
  margin-top: 0.75rem;
}

.space-y-4 > * + * {
  margin-top: 1rem;
}

/* 详细变更对比样式 */
.detailed-changes-collapse {
  border: 1px solid #e5e7eb;
  border-radius: 6px;
}

.change-item {
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  padding: 16px;
  background-color: #f9fafb;
}

.change-header {
  margin-bottom: 12px;
}

.change-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.change-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.change-label {
  font-weight: 500;
  min-width: 48px;
  font-size: 12px;
}

.change-label.old {
  color: #dc2626;
}

.change-label.new {
  color: #16a34a;
}

.change-value {
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  flex: 1;
}

.change-value.old {
  background-color: #fef2f2;
  color: #991b1b;
  border: 1px solid #fecaca;
}

.change-value.new {
  background-color: #f0fdf4;
  color: #166534;
  border: 1px solid #bbf7d0;
}

/* 代码对比样式 */
.code-diff, .json-diff, .list-diff {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

@media (max-width: 768px) {
  .code-diff, .json-diff, .list-diff {
    grid-template-columns: 1fr;
  }
}

.code-section, .json-section, .list-section {
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  overflow: hidden;
}

.code-header, .json-header, .list-header {
  padding: 8px 12px;
  font-weight: 500;
  font-size: 12px;
  border-bottom: 1px solid #e5e7eb;
}

.code-header.old, .json-header.old, .list-header.old {
  background-color: #fef2f2;
  color: #991b1b;
}

.code-header.new, .json-header.new, .list-header.new {
  background-color: #f0fdf4;
  color: #166534;
}

.code-content, .json-content {
  padding: 12px;
  font-size: 12px;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  white-space: pre-wrap;
  max-height: 240px;
  overflow: auto;
  margin: 0;
}

.code-content.old, .json-content.old {
  background-color: #fef2f2;
}

.code-content.new, .json-content.new {
  background-color: #f0fdf4;
}

.list-content {
  padding: 12px;
}

.list-content.old {
  background-color: #fef2f2;
}

.list-content.new {
  background-color: #f0fdf4;
}

.simple-change {
  padding: 8px;
  background-color: #fef3cd;
  border-radius: 4px;
}

.global-param-item {
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  padding: 12px;
  background: #fff;
}

.global-param-values {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.param-value {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px;
  border-radius: 6px;
  font-size: 12px;
}

.param-value.old {
  background-color: #fef2f2;
  color: #991b1b;
  border: 1px solid #fecaca;
}

.param-value.new {
  background-color: #f0fdf4;
  color: #166534;
  border: 1px solid #bbf7d0;
}

.param-value .label {
  font-weight: 600;
  min-width: 36px;
}

.param-value .value {
  word-break: break-all;
  white-space: pre-wrap;
}
</style>
