<template>
  <a-modal
    v-model:visible="visible"
    title="批量同步预览与确认"
    width="800px"
    @ok="handleConfirm"
    @cancel="handleCancel"
    :confirm-loading="loading"
    :ok-button-props="{ disabled: !hasPlansToSync }"
    ok-text="确认同步"
    cancel-text="取消"
  >
    <div v-if="loadingPreview" class="text-center py-8">
      <a-spin size="large" />
      <div class="mt-4 text-gray-500">正在获取执行方案信息...</div>
    </div>

  <div v-else>
    <div v-if="plans.length === 0" class="text-center py-8">
      <a-empty description="未选择任何执行方案或无法获取信息" />
    </div>

    <div v-else>
      <p class="mb-3">将要同步以下执行方案，共 {{ plans.length }} 个：</p>

      <div v-for="plan in plans" :key="plan.plan_id || plan.plan_id || plan.id" class="mb-4 p-4 border rounded">
        <div class="flex items-center justify-between mb-2">
          <h4 class="font-medium">{{ plan.plan_name || plan.name || `方案 ${plan.plan_id || plan.id}` }}</h4>
          <span class="text-sm px-2 py-1 rounded" :class="{
            'bg-orange-100 text-orange-800': plan.needs_sync,
            'bg-green-100 text-green-800': !plan.needs_sync
          }">
            {{ plan.needs_sync ? '需要同步' : '已同步' }}
          </span>
        </div>

        <div v-if="plan.changes && plan.changes.has_changes" class="mt-2">
          <div class="mb-2 font-medium text-gray-700">变更摘要</div>
          <div class="p-3 bg-gray-50 rounded text-sm mb-2">
            {{ plan.changes.summary || '存在变更项，详情见下方' }}
          </div>

          <div
            v-if="plan.changes.global_parameters_changed"
            class="p-3 bg-blue-50 border border-blue-100 rounded text-sm mb-2"
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

          <div v-if="plan.changes.added_steps?.length || plan.changes.deleted_steps?.length" class="space-y-2 mb-2">
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

          <div v-if="plan.changes.modified_steps && plan.changes.modified_steps.length > 0">
            <div class="text-sm font-medium text-orange-700 mb-2">
              <icon-edit class="mr-1" />
              修改的步骤 ({{ plan.changes.modified_steps.length }})
            </div>
            <a-collapse class="detailed-changes-collapse">
              <a-collapse-item
                v-for="step in plan.changes.modified_steps"
                :key="step.step_id"
                :header="`步骤 ${step.order}: ${step.name}`"
              >
                <div v-if="step.detailed_changes?.length" class="space-y-4">
                  <div v-for="(change, idx) in step.detailed_changes" :key="idx" class="change-item">
                    <div class="change-header mb-2">
                      <a-tag color="blue" size="small">{{ change.field_name }}</a-tag>
                    </div>
                    <div v-if="change.change_type === 'text'">
                      <div class="change-row"><span class="change-label old">原值:</span><span class="change-value old">{{ change.old_value || '(空)' }}</span></div>
                      <div class="change-row"><span class="change-label new">新值:</span><span class="change-value new">{{ change.new_value || '(空)' }}</span></div>
                    </div>
                    <div v-else-if="change.change_type === 'code'">
                      <div class="code-diff">
                        <div class="code-section"><div class="code-header old">原脚本内容:</div><pre class="code-content old">{{ change.old_value || '(空)' }}</pre></div>
                        <div class="code-section"><div class="code-header new">新脚本内容:</div><pre class="code-content new">{{ change.new_value || '(空)' }}</pre></div>
                      </div>
                    </div>
                  </div>
                </div>
                <div v-else-if="step.changes?.length">
                  <div v-for="(chg, i) in step.changes" :key="i"><a-tag color="orange" size="small">{{ chg }}</a-tag></div>
                </div>
              </a-collapse-item>
            </a-collapse>
          </div>
        </div>

        <div v-else-if="plan.changes && !plan.changes.has_changes" class="mt-2 p-3 bg-green-50 border border-green-200 rounded text-sm">
          <div class="text-green-700 flex items-center">
            <icon-check-circle class="mr-2" />
            {{ plan.changes.summary || '执行方案与模板内容一致，无需同步' }}
          </div>
        </div>
      </div>

      <div class="mt-4 text-sm text-gray-600">
        批量同步会对每个方案执行后端同步操作，确认后会并发发起同步请求。
      </div>
    </div>
  </div>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, computed } from 'vue'
import { executionPlanApi, jobTemplateApi } from '@/api/ops'
import type { ExecutionPlan } from '@/types'
import { formatDateTime } from '@/utils/date'

const emit = defineEmits(['update:modelValue', 'sync-success'])
const props = defineProps<{ modelValue: boolean; planIds: number[] }>()
const visible = ref(!!props.modelValue)
const loading = ref(false)
const loadingPreview = ref(false)
// plans 保存合并后的 preview 结构（来自 jobTemplateApi.getSyncPreview 的 preview.plans 条目或回退信息）
const plans = ref<any[]>([])

// 只有当至少有一个方案需要同步时才允许确认同步
const hasPlansToSync = computed(() => {
  if (!plans.value || plans.value.length === 0) return false
  return plans.value.some((p: any) => p.needs_sync)
})

watch(() => props.modelValue, v => { visible.value = v })
watch(visible, v => {
  emit('update:modelValue', v)
  if (v) {
    // 当模态打开时确保拉取 preview（兼容 props.planIds 在组件加载前已设置的情况）
    fetchPreview()
  }
})
watch(() => props.planIds, () => {
  if (visible.value) fetchPreview()
})

const formatJson = (value: any) => {
  if (!value) return '(空)'
  if (typeof value === 'string') return value
  try {
    return JSON.stringify(value, null, 2)
  } catch (e) {
    return String(value)
  }
}

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

const fetchPreview = async () => {
  loadingPreview.value = true
  plans.value = []
  try {
    const ids = props.planIds || []
    if (!ids || ids.length === 0) {
      loadingPreview.value = false
      return
    }

    // 获取每个 plan 的基本信息（以获得 template id）
    const planRequests = ids.map(id => executionPlanApi.getPlan(id).catch(() => null))
    const planResponses = await Promise.all(planRequests)
    const planInfos = planResponses.filter(Boolean) as ExecutionPlan[]

    // 根据 template id 分组调用模板的 sync preview 接口（避免重复请求）
    const templateIdToPlanIds = new Map<number, number[]>()
    planInfos.forEach(p => {
      const tid = (p as any).template || (p as any).template_id
      if (tid) {
        if (!templateIdToPlanIds.has(tid)) templateIdToPlanIds.set(tid, [])
        templateIdToPlanIds.get(tid)!.push((p as any).id)
      }
    })

    const previewResults: any[] = []

    for (const [templateId, planIdList] of templateIdToPlanIds.entries()) {
      try {
        const preview = await jobTemplateApi.getSyncPreview(templateId)
        if (preview && preview.plans) {
          planIdList.forEach(pid => {
            const planPreview = preview.plans.find((pp: any) => Number(pp.plan_id) === Number(pid))
            if (planPreview) {
              planPreview.template_id = templateId
              planPreview.template_name = preview.template_name || ''
              previewResults.push(planPreview)
            } else {
              const info = planInfos.find(p => (p as any).id === pid)
              previewResults.push({
                plan_id: pid,
                plan_name: info?.name || `方案 ${pid}`,
                needs_sync: false,
                changes: null,
                template_id: templateId,
                template_name: preview.template_name || ''
              })
            }
          })
        } else {
          planIdList.forEach(pid => {
            const info = planInfos.find(p => (p as any).id === pid)
            previewResults.push({
              plan_id: pid,
              plan_name: info?.name || `方案 ${pid}`,
              needs_sync: false,
              changes: null,
              template_id: templateId,
              template_name: preview?.template_name || ''
            })
          })
        }
      } catch (e) {
        console.error('获取模板同步预览失败:', e)
        planIdList.forEach(pid => {
          const info = planInfos.find(p => (p as any).id === pid)
          previewResults.push({
            plan_id: pid,
            plan_name: info?.name || `方案 ${pid}`,
            needs_sync: false,
            changes: null,
            template_id: templateId,
            template_name: ''
          })
        })
      }
    }

    // 补上没有 template id 的 plan
    const coveredPlanIds = new Set(previewResults.map(r => Number(r.plan_id)))
    planInfos.forEach(p => {
      if (!coveredPlanIds.has(Number((p as any).id))) {
        previewResults.push({
          plan_id: (p as any).id,
          plan_name: p.name,
          needs_sync: false,
          changes: null,
          template_id: (p as any).template || (p as any).template_id,
          template_name: ''
        })
      }
    })

    plans.value = previewResults
  } catch (e) {
    console.error('获取执行方案信息失败:', e)
  } finally {
    loadingPreview.value = false
  }
}

onMounted(() => {
  if (visible.value) fetchPreview()
})

const handleConfirm = async () => {
  if (!props.planIds || props.planIds.length === 0) {
    visible.value = false
    return
  }
  loading.value = true
  try {
    const ids = props.planIds
    const promises = ids.map(id => executionPlanApi.syncPlan(id).catch(err => ({ id, error: err })))
    const results = await Promise.allSettled(promises)
    let success = 0
    let fail = 0
    results.forEach(r => {
      if (r.status === 'fulfilled') success++
      else fail++
    })
    emit('sync-success', { success, fail })
    visible.value = false
  } catch (e) {
    console.error('批量同步失败:', e)
  } finally {
    loading.value = false
  }
}

const handleCancel = () => {
  visible.value = false
}
</script>

<style scoped>
.preview-item {
  display: flex;
  flex-direction: column;
}
.preview-title {
  font-weight: 500;
}
.preview-meta {
  font-size: 12px;
}

/* 详细变更对比样式 - 与模板同步弹窗保持一致 */
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

.simple-change {
  padding: 8px;
  background-color: #fef3cd;
  border-radius: 4px;
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
</style>
