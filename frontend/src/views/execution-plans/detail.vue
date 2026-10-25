<template>
  <div class="execution-plan-detail">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-content">
        <div class="header-left">
          <n-button text @click="handleBack">
            <template #icon>
              <ChevronLeft />
            </template>
            返回
          </n-button>
          <div class="header-info">
            <h2>{{ plan?.name || '执行方案详情' }}</h2>
            <p class="header-desc">{{ plan?.description || '暂无描述' }}</p>
          </div>
        </div>
        <div class="header-right">
          <n-space>
            <n-button @click="handleRefresh">
              <template #icon>
                <RefreshCw  />
              </template>
              刷新
            </n-button>
            <n-button
              @click="handleEdit"
              v-permission="{ resourceType: 'executionplan', permission: 'change', resourceId: plan?.id }"
            >
              <template #icon>
                <Pencil  />
              </template>
              编辑方案
            </n-button>
            <n-button
              type="primary"
              @click="handleExecute"
              v-permission="{ resourceType: 'executionplan', permission: 'execute', resourceId: plan?.id }"
            >
              <template #icon>
                <Play />
              </template>
              执行方案
            </n-button>
          </n-space>
        </div>
      </div>
    </div>

    <div v-if="loading" class="loading-container">
      <n-spin size="large" />
    </div>

    <div v-else-if="plan" class="detail-content">
      <div class="form-grid-row">
        <!-- 基本信息 -->
        <div class="form-grid-col" style="grid-column: span 8">
          <n-card title="基本信息" class="mb-4">
            <n-descriptions :column="1" bordered label-placement="left" :label-style="{ width: '96px' }">
              <n-descriptions-item label="方案名称">
                {{ plan.name }}
              </n-descriptions-item>
              <n-descriptions-item label="所属模板">
                <n-button text size="small" @click="handleViewTemplate">{{ plan.template_name }}</n-button>
              </n-descriptions-item>
              <n-descriptions-item label="方案描述">
                {{ plan.description || '暂无描述' }}
              </n-descriptions-item>
              <n-descriptions-item label="同步状态">
                <n-tag v-if="plan.needs_sync" type="warning">
                  <template #icon>
                    <CircleAlert  />
                  </template>
                  需要同步
                </n-tag>
                <n-tag v-else type="success">>
                  <template #icon>
                    <CircleCheck  />
                  </template>
                  已同步
                </n-tag>
              </n-descriptions-item>
              <n-descriptions-item label="创建人">
                {{ plan.created_by_name }}
              </n-descriptions-item>
              <n-descriptions-item label="创建时间">
                {{ formatDateTime(plan.created_at) }}
              </n-descriptions-item>
              <n-descriptions-item label="更新时间">
                {{ formatDateTime(plan.updated_at) }}
              </n-descriptions-item>
              <n-descriptions-item label="执行统计">
                <div class="stats-info">
                  <span>总执行: {{ plan.total_executions || 0 }} 次</span>
                  <span>成功率: {{ plan.success_rate || 0 }}%</span>
                </div>
              </n-descriptions-item>
            </n-descriptions>
          </n-card>

          <!-- 执行变量 -->
          <n-card title="执行变量" class="mb-4">
            <ExecutionVariablesPanel
              :variables="plan.global_parameters_snapshot || plan.template_global_parameters || {}"
            />
          </n-card>
        </div>

        <!-- 执行步骤 -->
        <div class="form-grid-col" style="grid-column: span 16">
          <n-card title="执行步骤" class="mb-4">
        <template #footer>
          <n-space>
            <n-tag>共 {{ steps.length }} 个步骤</n-tag>
            <n-button v-if="plan.needs_sync" secondary size="small" @click="handleViewTemplate">
              <template #icon>
                <RefreshCw  />
              </template>
              去模板同步
            </n-button>
            <n-button
              v-if="plan.needs_sync"
              type="primary"
              size="small"
              @click="handleSync"
              v-permission="{ resourceType: 'executionplan', permission: 'change', resourceId: plan?.id }"
            >
              <template #icon>
                <RefreshCw  />
              </template>
              同步方案
            </n-button>
          </n-space>
        </template>



        <div v-if="steps.length === 0" class="empty-steps">
          <n-empty description="暂无执行步骤" />
        </div>

        <div v-else class="steps-list">
          <StepCard
            v-for="(step, index) in steps"
            :key="step.id || step.template_step_id || index"
            class="step-list-item"
            :step="step"
            :index="index"
            :show-detail="false"
            @click="openStepDrawer(step, index)"
          />
        </div>
          </n-card>

        </div>
      </div>
      <n-drawer
        v-model:show="drawerVisible"
        :width="960"
       
       
      ><n-drawer-content>
        <template #header>
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
      </n-drawer-content></n-drawer>
    </div>

    <div v-else class="error-container">
      <n-result
        status="404"
        title="执行方案不存在"
        subtitle="请检查方案ID是否正确"
      >
        <template #footer>
          <n-button type="primary" @click="handleBack">
            返回
          </n-button>
        </template>
      </n-result>
    </div>
  </div>


</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { executionPlanApi } from '@/api/ops'
import type { ExecutionPlan } from '@/types'
import StepCard from '@/components/StepCard.vue'
import ExecutionVariablesPanel from '@/components/ExecutionVariablesPanel.vue'
import { NButton, NCard, NDescriptions, NDescriptionsItem, NDrawer, NDrawerContent, NEmpty, NResult, NSpace, NSpin, NTag, useMessage } from 'naive-ui'
import { ChevronLeft, CircleAlert, CircleCheck, Pencil, Play, RefreshCw } from 'lucide-vue-next'


const message = useMessage()
const route = useRoute()
const router = useRouter()

// 响应式数据
const loading = ref(false)
const plan = ref<ExecutionPlan | null>(null)
const steps = ref<any[]>([])
const drawerVisible = ref(false)
const drawerStep = ref<any | null>(null)
const drawerIndex = ref(0)


// 获取方案详情
const fetchPlanDetail = async () => {
  try {
    loading.value = true;
    const planId = Number(route.params.id);
    const response = await executionPlanApi.getPlan(planId);
    plan.value = response;
    // Ensure steps are updated from the detailed API response
    if (response && response.plan_steps) {
      steps.value = response.plan_steps;
    } else {
      steps.value = [];
    }
  } catch (error) {
    console.error('获取方案详情失败:', error);
    message.error('获取方案详情失败');
  } finally {
    loading.value = false;
  }
};

const openStepDrawer = (step: any, index: number) => {
  drawerStep.value = step
  drawerIndex.value = index
  drawerVisible.value = true
}

const getStepDisplayName = (step: any) => {
  if (!step) return '未命名步骤'
  return step.step_name || step.name || '未命名步骤'
}

// 获取方案步骤


// 返回列表
const handleBack = () => {
  router.push('/execution-plans')
}

// 刷新
const handleRefresh = () => {
  fetchPlanDetail()

}

// 编辑方案
const handleEdit = () => {
  router.push(`/execution-plans/${route.params.id}/edit`)
}

// 执行方案
const handleExecute = () => {
  router.push(`/execution-plans/detail/${route.params.id}/execute`)
}

// 查看所属模板详情
const handleViewTemplate = () => {
  if (plan.value?.template) {
    const routeUrl = router.resolve({
      path: `/job-templates/detail/${plan.value.template}`
    })
    window.open(routeUrl.href, '_blank')
  }
}

// 同步方案
const handleSync = async () => {
  try {
    const planId = Number(route.params.id)
    await executionPlanApi.syncPlan(planId)
    message.success('方案同步成功')
    fetchPlanDetail()

  } catch (error) {
    console.error('同步方案失败:', error)
    message.error('同步方案失败')
  }
}

// 查看所有执行记录
const handleViewAllRecords = () => {
  router.push(`/execution-records?plan_id=${route.params.id}`)
}

const formatDateTime = (dateTime: string) => {
  if (!dateTime) return '-'
  const date = new Date(dateTime)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

// 生命周期
onMounted(() => {
  fetchPlanDetail()

})
</script>

<style scoped>
.execution-plan-detail {
  padding: 0;
}

.page-header {
  background: transparent;
  border-radius: 0;
  margin-bottom: 16px;
  padding: 0 0 12px 0;
  box-shadow: none;
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
  color: var(--app-fg);
}

.header-desc {
  margin: 0;
  color: var(--app-muted);
  font-size: 14px;
}

.mb-4 {
  margin-bottom: 16px;
}

.loading-container,
.error-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 400px;
}

.stats-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
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
  border-color: var(--app-accent);
}

.drawer-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
}

.drawer-title-name {
  color: var(--app-fg-secondary);
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

.step-item {
  border: 1px solid var(--app-border);
  border-radius: 6px;
  padding: 16px;
  background: var(--app-surface);
}

.step-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.step-actions {
  margin-left: auto;
}

.step-number {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--app-accent);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 14px;
}

.step-info {
  flex: 1;
}

.step-name {
  font-weight: 600;
  color: var(--app-fg);
  margin-bottom: 4px;
}

.step-desc {
  color: var(--app-muted);
  font-size: 12px;
}

.empty-steps {
  text-align: center;
  padding: 40px 0;
}

/* 步骤详情样式 */
.step-detail {
  margin-top: 12px;
}

.step-detail h4 {
  margin: 0 0 8px 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--app-fg);
}

.script-content {
  margin-bottom: 16px;
}

.parameters {
  display: flex;
  flex-direction: column;
  gap: 8px;
  background: var(--app-surface-muted);
  padding: 12px;
  border-radius: 4px;
  border: 1px solid var(--app-border);
}

.parameter-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}

.param-key {
  font-weight: 600;
  color: var(--app-fg-secondary);
  min-width: 120px;
}

.param-value {
  color: var(--app-fg);
  background: var(--app-bg);
  padding: 2px 6px;
  border-radius: 3px;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
}

.parameter-item.override .param-key {
  color: var(--color-warning-6);
}

.parameter-item.override .param-value {
  background: var(--color-warning-1);
  border: 1px solid var(--color-warning-3);
}

.parameter-item.global .param-key {
  color: var(--app-accent);
}

.parameter-item.global .param-value {
  background: var(--color-primary-1);
  border: 1px solid var(--color-primary-3);
}

.global-parameters {
  display: flex;
  flex-direction: column;
  gap: 8px;
  background: var(--app-surface-muted);
  padding: 12px;
  border-radius: 4px;
  border: 1px solid var(--app-border);
}

.global-parameters .parameter-item {
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
  padding: 10px 12px;
  border-bottom: 1px solid var(--color-border-1);
  background: #fff;
  border-radius: 4px;
}

.global-parameters .param-key {
  font-weight: 500;
  color: var(--app-fg);
  min-width: auto;
}

.global-parameters .param-value {
  padding: 4px 6px;
  font-size: 13px;
  word-break: break-all;
}

.global-parameters .param-description {
  font-size: 12px;
  color: #86909c;
  line-height: 1.5;
}

.no-parameters {
  text-align: center;
  padding: 20px 0;
}

/* 位置参数样式 */
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

/* 脚本代码块样式 */
.script-code-block {
  background: #f7f8fa;
  border: 1px solid #e5e6eb;
  border-radius: 6px;
  overflow: hidden;
}

.script-code-block pre {
  margin: 0;
  padding: 16px;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 13px;
  line-height: 1.5;
  color: #4e5969;
  background: transparent;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 800px;
  overflow-y: auto;
}

.script-code-block code {
  background: transparent;
  padding: 0;
  font-family: inherit;
  font-size: inherit;
  color: inherit;
}

/* 目标主机样式 */
.target-hosts {
  margin-top: 12px;
  padding: 8px 0;
}

.target-hosts-label {
  font-size: 12px;
  color: #86909c;
  margin-bottom: 6px;
}
</style>
