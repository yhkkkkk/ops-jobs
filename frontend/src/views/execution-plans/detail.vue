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
            返回列表
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
            <a-button @click="handleEdit">
              <template #icon>
                <icon-edit />
              </template>
              编辑方案
            </a-button>
            <a-button type="primary" @click="handleExecute">
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
      <!-- 基本信息 -->
      <a-card title="基本信息" class="mb-4">
        <a-descriptions :column="2" bordered>
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
      <a-card v-if="plan" title="模板全局变量" class="mb-4">
        <div v-if="plan.template_global_parameters && Object.keys(plan.template_global_parameters).length > 0" class="global-parameters">
          <div
            v-for="(value, key) in plan.template_global_parameters"
            :key="key"
            class="parameter-item global"
          >
            <span class="param-key">{{ key }}:</span>
            <span class="param-value">{{ value }}</span>
          </div>
        </div>
        <div v-else class="no-parameters">
          <a-empty description="该模板暂无全局变量" :image-style="{ height: '40px' }" />
        </div>
      </a-card>

      <!-- 执行步骤 -->
      <a-card title="执行步骤" class="mb-4">
        <template #extra>
          <a-space>
            <a-tag>共 {{ steps.length }} 个步骤</a-tag>
            <a-button v-if="plan.needs_sync" type="outline" size="small" @click="goToTemplate">
              <template #icon>
                <icon-sync />
              </template>
              去模板同步
            </a-button>
            <a-button v-if="plan.needs_sync" type="primary" size="small" @click="handleSync">
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
          <div
            v-for="(step, index) in steps"
            :key="step.id"
            class="step-item"
          >
            <div class="step-header">
              <div class="step-number">{{ index + 1 }}</div>
              <div class="step-info">
                <div class="step-name">{{ step.step_name }}</div>
                <div class="step-desc">{{ step.step_description || '无描述' }}</div>
              </div>
              <div class="step-type">
                <a-tag :color="getStepTypeColor(step.step_type)">
                  {{ getStepTypeText(step.step_type) }}
                </a-tag>
              </div>
              <div class="step-actions">
                <a-button
                  type="text"
                  size="small"
                  @click="toggleStepDetail(step.id)"
                >
                  <template #icon>
                    <icon-eye v-if="!expandedSteps.includes(step.id)" />
                    <icon-eye-invisible v-else />
                  </template>
                  {{ expandedSteps.includes(step.id) ? '收起' : '查看详情' }}
                </a-button>
              </div>
            </div>

            <div class="step-config">
              <a-descriptions :column="3" size="small">
                <a-descriptions-item label="执行顺序">
                  {{ step.order }}
                </a-descriptions-item>
                <a-descriptions-item label="超时时间">
                  {{ step.effective_timeout || step.step_timeout || 300 }}秒
                </a-descriptions-item>
                <a-descriptions-item label="错误处理">
                  {{ step.step_ignore_error ? '忽略错误继续' : '遇错停止' }}
                </a-descriptions-item>
              </a-descriptions>
            </div>

            <!-- 步骤详细内容（展开时显示） -->
            <div v-if="expandedSteps.includes(step.id)" class="step-detail">
              <a-divider />

              <!-- 脚本执行步骤 -->
              <div v-if="step.step_type === 'script'" class="step-script">
                <h4>执行配置</h4>
                <a-descriptions :column="2" size="small" class="mb-4">
                  <a-descriptions-item label="脚本类型">
                    {{ step.step_script_type || '未指定' }}
                  </a-descriptions-item>
                  <a-descriptions-item label="执行账号">
                    {{ step.step_account_name || (step.step_account_id ? `ID: ${step.step_account_id}` : '默认') }}
                  </a-descriptions-item>
                </a-descriptions>

                <h4>脚本内容</h4>
                <div class="script-content">
                  <div class="script-code-block">
                    <pre><code>{{ step.step_script_content || '无脚本内容' }}</code></pre>
                  </div>
                </div>

                <h4 style="margin-top: 16px">位置参数</h4>
                <div v-if="getPositionalArgs(step).length > 0" class="positional-args">
                  <div
                    v-for="(arg, index) in getPositionalArgs(step)"
                    :key="index"
                    class="positional-arg-item"
                  >
                    <span class="arg-index">${{ index + 1 }}</span>
                    <span class="arg-value">{{ arg }}</span>
                  </div>
                </div>
                <div v-else class="no-parameters">
                  <a-empty description="无位置参数" :image-style="{ height: '40px' }" />
                </div>
              </div>

              <!-- 文件传输步骤 -->
              <div v-else-if="step.step_type === 'file_transfer'" class="step-file-transfer">
                <h4>传输配置</h4>
                <a-descriptions :column="2" size="small">
                  <a-descriptions-item label="传输方向">
                    {{ step.step_transfer_type === 'upload' ? '上传' : '下载' }}
                  </a-descriptions-item>
                  <a-descriptions-item label="执行账号">
                    {{ step.step_account_name || (step.step_account_id ? `ID: ${step.step_account_id}` : '默认') }}
                  </a-descriptions-item>
                  <a-descriptions-item label="本地路径">
                    {{ step.step_local_path || '未配置' }}
                  </a-descriptions-item>
                  <a-descriptions-item label="远程路径">
                    {{ step.step_remote_path || '未配置' }}
                  </a-descriptions-item>
                </a-descriptions>
              </div>

              <!-- 覆盖参数 -->
              <div v-if="step.override_parameters && Object.keys(step.override_parameters).length > 0" class="override-params">
                <h4 style="margin-top: 16px">覆盖参数</h4>
                <div class="parameters">
                  <div
                    v-for="(value, key) in step.override_parameters"
                    :key="key"
                    class="parameter-item override"
                  >
                    <span class="param-key">{{ key }}:</span>
                    <span class="param-value">{{ value }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </a-card>

      <!-- 执行历史 -->
      <a-card title="执行历史">
        <template #extra>
          <a-button size="small" @click="handleViewAllRecords">
            查看全部
          </a-button>
        </template>

        <div class="execution-history">
          <a-empty description="暂无执行记录" />
        </div>
      </a-card>
    </div>

    <div v-else class="error-container">
      <a-result
        status="404"
        title="执行方案不存在"
        subtitle="请检查方案ID是否正确"
      >
        <template #extra>
          <a-button type="primary" @click="handleBack">
            返回列表
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


const route = useRoute()
const router = useRouter()

// 响应式数据
const loading = ref(false)
const plan = ref<ExecutionPlan | null>(null)
const steps = ref<any[]>([])
const expandedSteps = ref<number[]>([])


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
  router.push(`/execution-plans/${route.params.id}/execute`)
}

// 查看所属模板详情
const handleViewTemplate = () => {
  if (plan.value?.template) {
    router.push(`/job-templates/detail/${plan.value.template}`)
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

// 切换步骤详情展开状态
const toggleStepDetail = (stepId: number) => {
  const index = expandedSteps.value.indexOf(stepId)
  if (index > -1) {
    expandedSteps.value.splice(index, 1)
  } else {
    expandedSteps.value.push(stepId)
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

// 获取位置参数
const getPositionalArgs = (step: any) => {
  // 优先使用有效参数（如果有覆盖）
  if (step.effective_parameters && Array.isArray(step.effective_parameters)) {
    return step.effective_parameters.filter((arg: string) => arg.trim() !== '')
  }

  // 否则使用快照中的参数
  if (step.step_parameters && Array.isArray(step.step_parameters)) {
    return step.step_parameters.filter((arg: string) => arg.trim() !== '')
  }

  return []
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

.execution-history {
  min-height: 200px;
  display: flex;
  align-items: center;
  justify-content: center;
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
  max-height: 300px;
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
