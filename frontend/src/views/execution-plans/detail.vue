<template>
  <div class="execution-plan-detail">
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
            <h2>{{ plan?.name || '执行方案详情' }}</h2>
            <p class="header-desc">{{ plan?.description || '暂无描述' }}</p>
          </div>
        </div>
        <div class="header-right">
          <a-space>
            <a-button @click="handleRefresh">
              <template #icon>
                <icon-refresh />
              </template>
              刷新
            </a-button>
            <a-button
              @click="handleEdit"
              v-permission="{ resourceType: 'executionplan', permission: 'change', resourceId: plan?.id }"
            >
              <template #icon>
                <icon-edit />
              </template>
              编辑方案
            </a-button>
            <a-button
              type="primary"
              @click="handleExecute"
              v-permission="{ resourceType: 'executionplan', permission: 'execute', resourceId: plan?.id }"
            >
              <template #icon>
                <icon-play-arrow />
              </template>
              执行方案
            </a-button>
          </a-space>
        </div>
      </div>
    </div>

    <div v-if="loading" class="loading-container">
      <a-spin size="large" />
    </div>

    <div v-else-if="plan" class="detail-content">
      <a-row :gutter="24">
        <!-- 基本信息 -->
        <a-col :span="8">
          <a-card title="基本信息" class="mb-4">
            <a-descriptions :column="1" bordered>
              <a-descriptions-item label="方案名称">
                {{ plan.name }}
              </a-descriptions-item>
              <a-descriptions-item label="所属模板">
                <a-link @click="handleViewTemplate">{{ plan.template_name }}</a-link>
              </a-descriptions-item>
              <a-descriptions-item label="方案描述">
                {{ plan.description || '暂无描述' }}
              </a-descriptions-item>
              <a-descriptions-item label="同步状态">
                <a-tag v-if="plan.needs_sync" color="orange">
                  <template #icon>
                    <icon-exclamation-circle />
                  </template>
                  需要同步
                </a-tag>
                <a-tag v-else color="green">
                  <template #icon>
                    <icon-check-circle />
                  </template>
                  已同步
                </a-tag>
              </a-descriptions-item>
              <a-descriptions-item label="创建人">
                {{ plan.created_by_name }}
              </a-descriptions-item>
              <a-descriptions-item label="创建时间">
                {{ formatDateTime(plan.created_at) }}
              </a-descriptions-item>
              <a-descriptions-item label="更新时间">
                {{ formatDateTime(plan.updated_at) }}
              </a-descriptions-item>
              <a-descriptions-item label="执行统计">
                <div class="stats-info">
                  <span>总执行: {{ plan.total_executions || 0 }} 次</span>
                  <span>成功率: {{ plan.success_rate || 0 }}%</span>
                </div>
              </a-descriptions-item>
            </a-descriptions>
          </a-card>

          <!-- 模板全局变量 -->
          <a-card title="模板全局变量" class="mb-4">
            <GlobalVariablesPanel
              :variables="plan.template_global_parameters || {}"
              title="模板全局变量"
              empty-text="该模板暂无全局变量"
            />
          </a-card>
        </a-col>

        <!-- 执行步骤 -->
        <a-col :span="16">
          <a-card title="执行步骤" class="mb-4">
        <template #extra>
          <a-space>
            <a-tag>共 {{ steps.length }} 个步骤</a-tag>
            <a-button v-if="plan.needs_sync" type="outline" size="small" @click="handleViewTemplate">
              <template #icon>
                <icon-sync />
              </template>
              去模板同步
            </a-button>
            <a-button
              v-if="plan.needs_sync"
              type="primary"
              size="small"
              @click="handleSync"
              v-permission="{ resourceType: 'executionplan', permission: 'change', resourceId: plan?.id }"
            >
              <template #icon>
                <icon-sync />
              </template>
              同步方案
            </a-button>
          </a-space>
        </template>



        <div v-if="steps.length === 0" class="empty-steps">
          <a-empty description="暂无执行步骤" />
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

    <div v-else class="error-container">
      <a-result
        status="404"
        title="执行方案不存在"
        subtitle="请检查方案ID是否正确"
      >
        <template #extra>
          <a-button type="primary" @click="handleBack">
            返回
          </a-button>
        </template>
      </a-result>
    </div>
  </div>


</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import { executionPlanApi } from '@/api/ops'
import type { ExecutionPlan } from '@/types'
import StepCard from '@/components/StepCard.vue'
import GlobalVariablesPanel from '@/components/GlobalVariablesPanel.vue'


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
    Message.error('获取方案详情失败');
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
  // if (plan.value?.template) {
  //   router.push(`/job-templates/detail/${plan.value.template}`)
  // }
  if (plan.value?.template) {
    // 1. 使用 router.resolve 解析出完整的 URL
    // 这样做的好处是无论你的路由模式是 history 还是 hash (#)，它都能生成正确的链接
    const routeUrl = router.resolve({
      path: `/job-templates/detail/${plan.value.template}`
    })

    // 2. 使用 window.open 打开新标签页
    // '_blank' 参数表示在新窗口/标签页打开
    window.open(routeUrl.href, '_blank')
  }
}

// 同步方案
const handleSync = async () => {
  try {
    const planId = Number(route.params.id)
    await executionPlanApi.syncPlan(planId)
    Message.success('方案同步成功')
    fetchPlanDetail()

  } catch (error) {
    console.error('同步方案失败:', error)
    Message.error('同步方案失败')
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

.step-item {
  border: 1px solid var(--color-border-2);
  border-radius: 6px;
  padding: 16px;
  background: var(--color-bg-1);
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
  background: var(--color-primary-6);
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
  color: var(--color-text-1);
  margin-bottom: 4px;
}

.step-desc {
  color: var(--color-text-3);
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
  color: var(--color-text-1);
}

.script-content {
  margin-bottom: 16px;
}

.parameters {
  display: flex;
  flex-direction: column;
  gap: 8px;
  background: var(--color-fill-1);
  padding: 12px;
  border-radius: 4px;
  border: 1px solid var(--color-border-2);
}

.parameter-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}

.param-key {
  font-weight: 600;
  color: var(--color-text-2);
  min-width: 120px;
}

.param-value {
  color: var(--color-text-1);
  background: var(--color-bg-2);
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
  color: var(--color-primary-6);
}

.parameter-item.global .param-value {
  background: var(--color-primary-1);
  border: 1px solid var(--color-primary-3);
}

.global-parameters {
  display: flex;
  flex-direction: column;
  gap: 8px;
  background: var(--color-fill-1);
  padding: 12px;
  border-radius: 4px;
  border: 1px solid var(--color-border-2);
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
  color: var(--color-text-1);
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
