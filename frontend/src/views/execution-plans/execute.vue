<template>
  <div class="execution-plan-execute">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-content">
        <div class="header-left">
          <a-button type="text" @click="handleBack">
            <template #icon>
              <icon-arrow-left />
            </template>
            返回详情
          </a-button>
          <div class="header-info">
            <h2>执行方案: {{ plan?.name || '加载中...' }}</h2>
            <p class="header-desc">配置执行参数并启动方案执行</p>
          </div>
        </div>
      </div>
    </div>

    <div v-if="loading" class="loading-container">
      <a-spin size="large" />
    </div>

    <div v-else-if="plan" class="execute-content">
      <a-row :gutter="24">
        <!-- 左侧：执行配置 -->
        <a-col :span="16">
          <a-card title="执行配置">
            <a-form :model="executeForm" layout="vertical">
              <a-form-item label="执行名称" required>
                <a-input
                  v-model="executeForm.name"
                  placeholder="请输入执行名称"
                  :max-length="200"
                />
              </a-form-item>

              <a-form-item label="执行描述">
                <a-textarea
                  v-model="executeForm.description"
                  placeholder="请输入执行描述（可选）"
                  :rows="3"
                  :max-length="500"
                />
              </a-form-item>

              <a-form-item label="Agent-Server" required>
                <a-select
                  v-model="selectedAgentServerId"
                  placeholder="请选择 Agent-Server"
                  allow-clear
                  allow-search
                  :loading="agentServerLoading"
                  :filter-option="filterAgentServerOption"
                >
                  <a-option
                    v-for="server in agentServers"
                    :key="server.id"
                    :value="server.id"
                    :label="`${server.name} (${server.base_url})`"
                  >
                    {{ server.name }} ({{ server.base_url }})
                  </a-option>
                </a-select>
              </a-form-item>

              <a-form-item label="执行模式">
                <a-radio-group v-model="executeForm.execution_mode">
                  <a-radio value="parallel">并行执行</a-radio>
                  <a-radio value="serial">串行执行</a-radio>
                  <a-radio value="rolling">滚动执行</a-radio>
                </a-radio-group>
              </a-form-item>

              <div v-if="executeForm.execution_mode === 'rolling'" class="rolling-config">
                <a-row :gutter="16">
                  <a-col :span="12">
                    <a-form-item label="批次大小">
                      <a-input-number
                        v-model="executeForm.rolling_batch_size"
                        :min="1"
                        :max="100"
                        style="width: 100%"
                      />
                    </a-form-item>
                  </a-col>
                  <a-col :span="12">
                    <a-form-item label="批次延迟(秒)">
                      <a-input-number
                        v-model="executeForm.rolling_batch_delay"
                        :min="0"
                        :max="3600"
                        style="width: 100%"
                      />
                    </a-form-item>
                  </a-col>
                </a-row>
              </div>

              <a-form-item label="执行参数">
                <div class="parameters-section">
                  <div class="parameters-header">
                    <span>全局参数（可覆盖模板中的参数）</span>
                    <a-button type="text" size="small" @click="addParameter">
                      <template #icon>
                        <icon-plus />
                      </template>
                      添加参数
                    </a-button>
                  </div>
                  <div class="parameters-list">
                    <div
                      v-for="(param, index) in executeForm.execution_parameters"
                      :key="index"
                      class="parameter-item"
                    >
                      <a-input
                        v-model="param.key"
                        placeholder="参数名"
                        style="width: 120px"
                      />
                      <span style="margin: 0 8px">=</span>
                      <a-input
                        v-model="param.value"
                        placeholder="参数值"
                        style="flex: 1"
                      />
                      <a-button
                        type="text"
                        status="danger"
                        @click="removeParameter(index)"
                        style="margin-left: 8px"
                      >
                        <template #icon>
                          <icon-delete />
                        </template>
                      </a-button>
                    </div>
                  </div>
                </div>
              </a-form-item>

              <a-form-item>
                <a-space>
                  <a-button
                    type="primary"
                    size="large"
                    :loading="executing"
                    @click="handleExecute"
                  >
                    <template #icon>
                      <icon-play-arrow />
                    </template>
                    开始执行
                  </a-button>
                  <a-button size="large" @click="handleBack">
                    取消
                  </a-button>
                </a-space>
              </a-form-item>
            </a-form>
          </a-card>
        </a-col>

        <!-- 右侧：方案信息 -->
        <a-col :span="8">
          <a-card title="方案信息">
            <a-descriptions :column="1" size="small">
              <a-descriptions-item label="方案名称">
                {{ plan.name }}
              </a-descriptions-item>
              <a-descriptions-item label="所属模板">
                {{ plan.template_name }}
              </a-descriptions-item>
              <a-descriptions-item label="步骤数量">
                {{ plan.step_count || 0 }} 个
              </a-descriptions-item>
              <a-descriptions-item label="同步状态">
                <a-tag v-if="plan.needs_sync" color="orange">
                  需要同步
                </a-tag>
                <a-tag v-else color="green">
                  已同步
                </a-tag>
              </a-descriptions-item>
            </a-descriptions>

            <a-divider />

            <div class="execution-tips">
              <h4>执行提示</h4>
              <ul>
                <li>请确保方案已同步到最新状态</li>
                <li>并行执行速度快，但资源消耗大</li>
                <li>串行执行稳定，适合有依赖的操作</li>
                <li>滚动执行可控制并发数量</li>
                <li>执行参数会覆盖模板中的默认参数</li>
              </ul>
            </div>
          </a-card>
        </a-col>
      </a-row>
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
import { ref, reactive, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import { executionPlanApi } from '@/api/ops'
import { agentServerApi } from '@/api/agents'
import type { ExecutionPlan } from '@/types'

const route = useRoute()
const router = useRouter()

// 响应式数据
const loading = ref(false)
const executing = ref(false)
const plan = ref<ExecutionPlan | null>(null)

const agentServers = ref<any[]>([])
const selectedAgentServerId = ref<number | null>(null)
const agentServerLoading = ref(false)

const filterAgentServerOption = (input: string, option: any) => {
  const label = String(option?.label ?? option?.value ?? '')
  return label.toLowerCase().includes(input.toLowerCase())
}

const fetchAgentServers = async () => {
  try {
    agentServerLoading.value = true
    const resp = await agentServerApi.getAgentServers({ page_size: 200, is_active: true })
    agentServers.value = resp?.results || []
  } catch (error) {
    console.error('获取Agent-Server列表失败:', error)
    agentServers.value = []
  } finally {
    agentServerLoading.value = false
  }
}

// 执行表单
const executeForm = reactive({
  name: '',
  description: '',
  execution_mode: 'parallel',
  rolling_batch_size: 1,
  rolling_batch_delay: 0,
  execution_parameters: [] as Array<{key: string, value: string}>
})

// 获取方案详情
const fetchPlanDetail = async () => {
  try {
    loading.value = true
    const planId = Number(route.params.id)
    plan.value = await executionPlanApi.getPlan(planId)
    
    // 设置默认执行名称
    if (plan.value) {
      executeForm.name = `执行方案: ${plan.value.name}`
      executeForm.description = `执行方案 ${plan.value.name} - ${new Date().toLocaleString()}`
    }
  } catch (error) {
    console.error('获取方案详情失败:', error)
    Message.error('获取方案详情失败')
  } finally {
    loading.value = false
  }
}

// 添加参数
const addParameter = () => {
  executeForm.execution_parameters.push({ key: '', value: '' })
}

// 删除参数
const removeParameter = (index: number) => {
  executeForm.execution_parameters.splice(index, 1)
}

// 执行方案
const handleExecute = async () => {
  if (!executeForm.name.trim()) {
    Message.error('请输入执行名称')
    return
  }
  if (!selectedAgentServerId.value) {
    Message.error('请选择 Agent-Server')
    return
  }

  try {
    executing.value = true
    
    // 构建执行参数
    const executionParameters: Record<string, string> = {}
    executeForm.execution_parameters.forEach(param => {
      if (param.key.trim() && param.value.trim()) {
        executionParameters[param.key.trim()] = param.value.trim()
      }
    })

    const executeData = {
      name: executeForm.name,
      description: executeForm.description,
      execution_mode: executeForm.execution_mode,
      rolling_batch_size: executeForm.rolling_batch_size,
      rolling_batch_delay: executeForm.rolling_batch_delay,
      execution_parameters: executionParameters,
      agent_server_id: selectedAgentServerId.value,
      trigger_type: 'manual'
    }

    const planId = Number(route.params.id)
    const result = await executionPlanApi.executePlan(planId, executeData)
    
    Message.success('方案执行已启动')
    
    // 跳转到执行记录详情页面
    router.push(`/execution-records/${result.execution_record_id}`)
  } catch (error) {
    console.error('执行方案失败:', error)
    Message.error('执行方案失败')
  } finally {
    executing.value = false
  }
}

// 返回详情页
const handleBack = () => {
  router.push(`/execution-plans/detail/${route.params.id}`)
}

// 生命周期
onMounted(() => {
  fetchPlanDetail()
  fetchAgentServers()
})
</script>

<style scoped>
.execution-plan-execute {
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

.loading-container,
.error-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 400px;
}

.rolling-config {
  margin-top: 12px;
  padding: 12px;
  background: var(--color-bg-1);
  border-radius: 6px;
}

.parameters-section {
  border: 1px solid var(--color-border-2);
  border-radius: 6px;
  padding: 12px;
  background: var(--color-bg-1);
}

.parameters-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  font-size: 13px;
  color: var(--color-text-2);
}

.parameters-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.parameter-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.execution-tips {
  margin-top: 16px;
}

.execution-tips h4 {
  margin: 0 0 8px 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-1);
}

.execution-tips ul {
  margin: 0;
  padding-left: 16px;
  color: var(--color-text-3);
  font-size: 12px;
  line-height: 1.6;
}

.execution-tips li {
  margin-bottom: 4px;
}
</style>
