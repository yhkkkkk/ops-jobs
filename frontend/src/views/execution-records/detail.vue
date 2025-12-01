<template>
  <div class="execution-detail-container">
    <!-- 基本信息 -->
    <a-card class="info-card" title="执行信息">
      <template #extra>
        <a-space>
          <a-button @click="goBack">
            <template #icon><icon-arrow-left /></template>
            返回
          </a-button>
          <a-button
            v-if="executionInfo.status === 'failed'"
            type="primary"
            @click="handleRetry"
          >
            <template #icon><icon-refresh /></template>
            重试
          </a-button>
          <a-button
            v-if="executionInfo.status === 'success' || executionInfo.status === 'cancelled'"
            type="primary"
            @click="handleRetry"
          >
            <template #icon><icon-refresh /></template>
            重做
          </a-button>
          <a-button
            v-if="executionInfo.status === 'running'"
            status="danger"
            @click="handleCancel"
          >
            <template #icon><icon-close /></template>
            取消执行
          </a-button>
        </a-space>
      </template>
      <a-descriptions :column="2" bordered>
        <a-descriptions-item label="执行名称">
          {{ displayName || '-' }}
        </a-descriptions-item>
        <a-descriptions-item label="执行ID">
          <a-typography-text copyable>{{ executionInfo.execution_id || '-' }}</a-typography-text>
        </a-descriptions-item>
        <a-descriptions-item label="执行类型">
          <a-tag :color="getExecutionTypeColor(executionInfo.execution_type)">
            {{ getExecutionTypeText(executionInfo.execution_type) }}
          </a-tag>
        </a-descriptions-item>
        <a-descriptions-item label="执行状态">
          <a-tag :color="getStatusColor(executionInfo.status)">
            <template #icon>
              <component :is="getStatusIcon(executionInfo.status)" />
            </template>
            {{ getStatusText(executionInfo.status) }}
          </a-tag>
        </a-descriptions-item>
        <a-descriptions-item label="执行用户">
          {{ executionInfo.executed_by_name || '-' }}
        </a-descriptions-item>
        <a-descriptions-item label="创建时间">
          {{ formatDateTime(executionInfo.created_at) }}
        </a-descriptions-item>
        <a-descriptions-item label="开始时间">
          {{ formatDateTime(executionInfo.started_at) }}
        </a-descriptions-item>
        <a-descriptions-item label="结束时间">
          {{ formatDateTime(executionInfo.finished_at) }}
        </a-descriptions-item>
        <a-descriptions-item label="执行时长">
          <span v-if="executionInfo.started_at && executionInfo.finished_at">
            {{ formatDuration(executionInfo.started_at, executionInfo.finished_at) }}
          </span>
          <span v-else-if="executionInfo.started_at">
            {{ formatDuration(executionInfo.started_at, new Date()) }}
          </span>
          <span v-else>-</span>
        </a-descriptions-item>
      </a-descriptions>
    </a-card>

    <!-- 实时日志 -->
    <a-card v-if="executionInfo.is_running && executionId" class="realtime-card" title="实时日志">
      <RealtimeLog :execution-id="executionId" :auto-connect="true" />
    </a-card>

    <!-- 执行日志 -->
    <a-card v-if="!executionInfo.is_running" class="logs-card" title="执行流程">
      <template #extra>
        <a-space>
          <a-button size="small" @click="refreshLogs">
            <template #icon><icon-refresh /></template>
            刷新
          </a-button>
        </a-space>
      </template>

      <div v-if="loading" class="loading-container">
        <a-spin size="large" />
      </div>

      <div v-else-if="(!stepLogs || Object.keys(stepLogs).length === 0) && (!hostLogs || Object.keys(hostLogs).length === 0)" class="empty-logs">
        <a-empty :description="getEmptyLogsDescription()" />
      </div>

      <div v-else class="execution-flow-layout">
        <!-- 日志摘要 -->
        <div v-if="logSummary" class="log-summary">
          <a-descriptions :column="4" size="small">
            <a-descriptions-item label="总步骤数">
              {{ logSummary.total_steps || Object.keys(stepLogs).length }}
            </a-descriptions-item>
            <a-descriptions-item label="总主机数">
              {{ logSummary.total_hosts || getTotalHostCount() }}
            </a-descriptions-item>
            <a-descriptions-item label="成功主机">
              {{ logSummary.success_hosts || getHostCountByStatus('success') }}
            </a-descriptions-item>
            <a-descriptions-item label="失败主机">
              {{ logSummary.failed_hosts || getHostCountByStatus('failed') }}
            </a-descriptions-item>
          </a-descriptions>
        </div>

        <!-- 左右分栏布局 -->
        <div class="execution-flow-container">
          <!-- 左侧步骤列表 -->
          <div class="steps-sidebar">
            <div class="steps-header">
              <div class="steps-header-content">
                <h4>执行流程</h4>
                <span class="steps-count">总步骤数 {{ Object.keys(stepLogs).length }}</span>
            </div>
            </div>
            
            <!-- 步骤流程连接线 -->
            <div class="steps-flow">
              <div
                v-for="(stepLog, stepId, index) in stepLogs"
                :key="stepId"
                class="step-flow-item"
                :class="{ 'step-active': selectedStepId === stepId }"
                @click="selectStep(stepId)"
              >
                <!-- 步骤连接线 -->
                <div v-if="index > 0" class="step-connector"></div>
                
                <!-- 步骤节点 -->
                <div class="step-node">
                  <div class="step-node-content">
                  <div class="step-order">步骤 {{ stepLog.step_order }}</div>
                    <div class="step-name">{{ stepLog.step_name }}</div>
                <div class="step-status">
                  <a-tag
                    :color="getStepStatusColor(stepLog.status)"
                    size="small"
                        class="step-status-tag"
                  >
                    {{ getStepStatusText(stepLog.status) }}
                  </a-tag>
                </div>
                    <!-- 步骤时间信息 -->
                    <div class="step-timing">
                      <div v-if="stepLog.started_at || stepLog.start_time" class="step-start-time">
                        开始: {{ formatDateTime(stepLog.started_at || stepLog.start_time) }}
                      </div>
                      <div v-if="stepLog.finished_at || stepLog.end_time" class="step-duration">
                        耗时: {{ formatDuration(stepLog.started_at || stepLog.start_time, stepLog.finished_at || stepLog.end_time) }}
                      </div>
                    </div>
                    <!-- 主机统计 -->
                    <div class="step-host-stats">
                      <div class="host-count-circle">
                        <span class="host-count">{{ getTotalHostCountInStep(stepId) }}</span>
                      </div>
                    </div>
                  </div>
                  
                  <!-- 步骤操作按钮 -->
                  <div class="step-actions">
                    <a-dropdown v-if="canRetryStep(stepLog)" trigger="click" @click.stop>
                      <a-button size="small" type="text" title="步骤操作">
                        <template #icon><icon-settings /></template>
                      </a-button>
                      <template #content>
                        <a-doption @click="() => handleStepRetry('failed_only', stepId)">
                          <IconExclamation /> 仅重试失败主机
                        </a-doption>
                        <a-doption @click="() => handleStepRetry('all', stepId)">
                          <IconRefresh /> 重试该步骤
                        </a-doption>
                        <a-doption @click="() => handleStepIgnoreError(stepId)">
                          <IconCheck /> 忽略错误继续
                        </a-doption>
                      </template>
                    </a-dropdown>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- 右侧步骤详情 -->
          <div class="step-detail-panel">
            <div v-if="!selectedStepId" class="no-step-selected">
              <a-empty description="请选择左侧步骤查看详情" />
            </div>
            <div v-else class="step-detail-content">
              <!-- 步骤详情头部 -->
              <div class="step-detail-header">
                <div class="step-detail-info">
                  <h3>{{ stepLogs[selectedStepId].step_name }}</h3>
                  <div class="step-detail-meta">
                    <a-tag :color="getStepStatusColor(stepLogs[selectedStepId].status)">
                      {{ getStepStatusText(stepLogs[selectedStepId].status) }}
                    </a-tag>
                    <span class="step-order-text">步骤 {{ stepLogs[selectedStepId].step_order }}</span>
                  </div>
                </div>
                <div class="step-detail-actions">
                  <a-space>
                    <a-button 
                      type="primary" 
                      size="small"
                      @click="toggleLogDisplay(selectedStepId)"
                    >
                      <template #icon>
                        <icon-eye v-if="!showLogsForStep[selectedStepId]" />
                        <icon-eye-invisible v-else />
                      </template>
                      {{ showLogsForStep[selectedStepId] ? '隐藏日志' : '查询日志' }}
                    </a-button>
                    
                    <a-dropdown v-if="canRetryStep(stepLogs[selectedStepId])" trigger="click">
                      <a-button size="small">
                        <IconRefresh /> 步骤操作 <IconDown />
                      </a-button>
                      <template #content>
                        <a-doption @click="() => handleStepRetry('failed_only', selectedStepId)">
                          <IconExclamation /> 仅重试失败主机
                        </a-doption>
                        <a-doption @click="() => handleStepRetry('all', selectedStepId)">
                          <IconRefresh /> 重试该步骤
                        </a-doption>
                        <a-doption @click="() => handleStepIgnoreError(selectedStepId)">
                          <IconCheck /> 忽略错误继续
                        </a-doption>
                      </template>
                    </a-dropdown>

                    <a-dropdown trigger="click">
                      <a-button size="small">
                        批量复制 <IconDown />
                      </a-button>
                      <template #content>
                        <a-doption @click="() => copyHostsByStatusInStep(selectedStepId, 'success')">
                          <IconCopy /> 复制成功主机IP
                        </a-doption>
                        <a-doption @click="() => copyHostsByStatusInStep(selectedStepId, 'failed')">
                          <IconCopy /> 复制失败主机IP
                        </a-doption>
                        <a-doption @click="() => copyHostsByStatusInStep(selectedStepId, 'running')">
                          <IconCopy /> 复制运行中主机IP
                        </a-doption>
                        <a-doption @click="() => copyHostsByStatusInStep(selectedStepId, 'pending')">
                          <IconCopy /> 复制等待中主机IP
                        </a-doption>
                        <a-doption @click="() => copyHostsByStatusInStep(selectedStepId, 'all')">
                          <IconCopy /> 复制所有主机IP
                        </a-doption>
                      </template>
                    </a-dropdown>
                  </a-space>
                </div>
              </div>

              <!-- 主机列表概览 -->
              <div class="host-overview">
                <div class="host-overview-header">
                  <h4>主机概览</h4>
                  <span class="host-total">共 {{ getTotalHostCountInStep(selectedStepId) }} 台主机</span>
                </div>
                <div class="host-status-summary">
                  <div class="status-summary-item success">
                    <icon-check-circle />
                    <span class="status-count">{{ getHostCountByStatusInStep(selectedStepId, 'success') }}</span>
                    <span class="status-label">成功</span>
                  </div>
                  <div class="status-summary-item failed">
                    <icon-close-circle />
                    <span class="status-count">{{ getHostCountByStatusInStep(selectedStepId, 'failed') }}</span>
                    <span class="status-label">失败</span>
                  </div>
                  <div class="status-summary-item running">
                    <icon-clock-circle />
                    <span class="status-count">{{ getHostCountByStatusInStep(selectedStepId, 'running') }}</span>
                    <span class="status-label">执行中</span>
                  </div>
                  <div class="status-summary-item pending">
                    <icon-minus-circle />
                    <span class="status-count">{{ getHostCountByStatusInStep(selectedStepId, 'pending') }}</span>
                    <span class="status-label">等待中</span>
                  </div>
                </div>
              </div>

              <!-- 日志提示区域 -->
              <div v-if="!showLogsForStep[selectedStepId]" class="logs-prompt-area">
                <div class="prompt-content">
                  <div class="prompt-icon">
                    <icon-eye />
                  </div>
                  <h3>查看执行日志</h3>
                  <p>点击上方的"查询日志"按钮查看该步骤的详细执行日志</p>
                </div>
              </div>

              <!-- 日志详情区域 -->
              <div v-if="showLogsForStep[selectedStepId]" class="logs-detail-area">
                <!-- 搜索栏 -->
                <div class="search-bar">
                  <a-space>
                    <a-input-search
                      :value="hostSearchTexts[selectedStepId] || ''"
                      placeholder="搜索主机名称或IP"
                      size="small"
                      style="width: 200px;"
                      @change="(value) => updateSearchText(selectedStepId, value)"
                      @search="(value) => updateSearchText(selectedStepId, value)"
                      @update:value="(value) => updateSearchText(selectedStepId, value)"
                      allow-clear
                    />
                    <a-input-search
                      :value="logSearchTexts[selectedStepId] || ''"
                      placeholder="搜索日志内容"
                      size="small"
                      style="width: 200px;"
                      @change="(value) => updateLogSearchText(selectedStepId, value)"
                      @search="(value) => updateLogSearchText(selectedStepId, value)"
                      @update:value="(value) => updateLogSearchText(selectedStepId, value)"
                      allow-clear
                    />
                  </a-space>
              </div>

              <!-- 主机分组显示 -->
              <div class="host-groups-container">
                <div
                  v-for="(group, status) in stepHostGroups[selectedStepId]"
                  :key="status"
                  class="host-group"
                  v-show="group.hosts.length > 0"
                >
                  <div class="host-group-header" @click="toggleGroupInStep(selectedStepId, status)">
                    <div class="group-info">
                      <a-tag
                        :color="getHostStatusColor(status)"
                        class="group-status-tag"
                      >
                        {{ getHostStatusText(status) }}
                      </a-tag>
                      <span class="group-count">{{ group.hosts.length }}台主机</span>
                    </div>
                    <div class="group-actions">
                      <a-button
                        size="small"
                        type="text"
                        @click.stop="copyHostsByStatusInStep(selectedStepId, status)"
                        title="复制该状态下的所有主机IP"
                      >
                        <template #icon><IconCopy /></template>
                        复制IP
                      </a-button>
                      <a-button
                        size="small"
                        type="text"
                        @click.stop="toggleGroupInStep(selectedStepId, status)"
                        title="展开/收起分组"
                      >
                      <IconDown
                        :class="{ 'rotate-180': group.expanded }"
                        class="expand-icon"
                      />
                      </a-button>
                    </div>
                  </div>

                  <div v-show="group.expanded" class="host-group-content">
                    <div v-if="group.hosts.length === 0" class="no-hosts">
                      <a-empty description="该状态下暂无主机" />
                    </div>
                    <a-tabs
                      v-else
                      v-model:active-key="selectedHostIds[selectedStepId]"
                      type="card"
                      size="small"
                      class="host-tabs"
                      :tab-position="'top'"
                      :scrollable="true"
                    >
                      <a-tab-pane
                        v-for="hostLog in group.hosts"
                        :key="hostLog.host_id"
                        :class="`host-tab-${hostLog.status}`"
                      >
                        <template #title>
                          <div class="host-tab-title">
                            <div class="host-name">{{ getHostDisplayName(hostLog) }}</div>
                          </div>
                        </template>

                  <!-- 主机日志内容 -->
                  <div class="host-log-content">
                    <!-- 主机信息头部 -->
                    <div class="host-info-header">
                      <div class="host-info">
                        <h5>{{ getHostDisplayName(hostLog) }}</h5>
                        <a-space>
                          <a-tag :color="getHostStatusColor(hostLog.status)">
                            {{ getHostStatusText(hostLog.status) }}
                          </a-tag>
                          <a-button
                            size="small"
                            type="text"
                            @click="copyHostIP(getHostIP(hostLog))"
                            title="复制IP地址"
                          >
                            <template #icon><IconCopy /></template>
                            {{ getHostIP(hostLog) }}
                          </a-button>
                        </a-space>
                      </div>
                    </div>

                    <!-- 标准输出日志 -->
                    <div v-if="hostLog.stdout || hostLog.logs" class="log-section">
                      <div class="log-section-header">
                        <h5>标准输出</h5>
                        <a-space>
                          <a-button size="small" @click="zoomLogs(hostLog.stdout || hostLog.logs, '标准输出')">
                            <template #icon><IconEye /></template>
                            放大查看
                          </a-button>
                          <a-button size="small" @click="copyLogs(hostLog.stdout || hostLog.logs)">
                            <template #icon><IconCopy /></template>
                            复制日志
                          </a-button>
                        </a-space>
                      </div>
                      <div class="log-text-container">
                              <pre class="log-text" v-html="highlightLogContent(hostLog.stdout || hostLog.logs, selectedStepId)"></pre>
                      </div>
                    </div>

                    <!-- 错误日志 -->
                    <div v-if="hostLog.stderr || hostLog.error_logs" class="log-section error-section">
                      <div class="log-section-header">
                        <h5>错误输出</h5>
                        <a-space>
                          <a-button size="small" @click="zoomLogs(hostLog.stderr || hostLog.error_logs, '错误输出')">
                            <template #icon><IconEye /></template>
                            放大查看
                          </a-button>
                          <a-button size="small" @click="copyLogs(hostLog.stderr || hostLog.error_logs)">
                            <template #icon><IconCopy /></template>
                            复制
                          </a-button>
                        </a-space>
                      </div>
                      <div class="log-text-container">
                              <pre class="log-text error-text" v-html="highlightLogContent(hostLog.stderr || hostLog.error_logs, selectedStepId)"></pre>
                      </div>
                    </div>

                    <!-- 如果没有日志 -->
                    <div v-if="!(hostLog.stdout || hostLog.logs) && !(hostLog.stderr || hostLog.error_logs)" class="no-logs">
                      <a-empty description="该主机在此步骤暂无日志数据" />
                    </div>
                  </div>
                </a-tab-pane>
              </a-tabs>
            </div>
          </div>
        </div>
      </div>
      </div>
    </div>
  </div>
</div>
</a-card>


  </div>

  <!-- 日志放大模态框 -->
  <a-modal
    v-model:visible="logZoomVisible"
    :title="logZoomTitle"
    width="90%"
    :footer="false"
    :mask-closable="false"
  >
    <div class="log-zoom-container">
      <div class="log-zoom-header">
        <a-space>
          <a-button @click="copyZoomLogs">
            <template #icon><IconCopy /></template>
            复制全部
          </a-button>
          <a-button @click="logZoomVisible = false">
            <template #icon><IconClose /></template>
            关闭
          </a-button>
        </a-space>
      </div>
      <div class="log-zoom-content">
        <pre class="log-zoom-text" v-html="logZoomContent"></pre>
      </div>
    </div>
  </a-modal>
</template>

<script setup>
import { ref, reactive, computed, onMounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Message, Modal } from '@arco-design/web-vue'
import {
  IconRefresh,
  IconClose,
  IconSettings,
  IconCopy,
  IconDown,
  IconUp,
  IconArrowLeft,
  IconCheck,
  IconCheckCircle,
  IconCloseCircle,
  IconClockCircle,
  IconMinusCircle,
  IconExclamation,
  IconEye,
  IconEyeInvisible
} from '@arco-design/web-vue/es/icon'
import { executionRecordApi } from '@/api/ops'
import RealtimeLog from '@/components/RealtimeLog.vue'

const route = useRoute()
const router = useRouter()

// 响应式数据
const loading = ref(false)
const executionInfo = ref({})
const logSummary = ref(null)
const stepLogs = ref({})
const selectedStepId = ref(null)
const selectedHostId = ref(null)

const hostSearchTexts = ref({}) // 每个步骤的主机搜索文本
const logSearchTexts = ref({}) // 每个步骤的日志搜索文本
const selectedHostIds = ref({}) // 每个步骤选中的主机ID
const groupExpandedState = ref({})
const showLogsForStep = ref({}) // 控制每个步骤的日志显示状态

// 日志放大相关
const logZoomVisible = ref(false)
const logZoomTitle = ref('')
const logZoomContent = ref('')
const logZoomRawContent = ref('')

// 获取步骤的主机分组（带搜索过滤）
const getHostGroupsForStep = (stepId) => {
  const stepLog = stepLogs.value[stepId]
  if (!stepLog) {
    return {}
  }

  // 兼容新旧格式：优先使用hosts，其次使用host_logs
  const hosts = stepLog.hosts || stepLog.host_logs
  if (!hosts) {
    return {}
  }

  // 确保搜索文本是响应式的
  const hostSearchText = (hostSearchTexts.value[stepId] || '').toLowerCase().trim()
  const logSearchText = (logSearchTexts.value[stepId] || '').toLowerCase().trim()
  


  const groups = {
    success: { hosts: [], expanded: groupExpandedState.value[`${stepId}_success`] !== false },
    failed: { hosts: [], expanded: groupExpandedState.value[`${stepId}_failed`] !== false },
    running: { hosts: [], expanded: groupExpandedState.value[`${stepId}_running`] !== false },
    pending: { hosts: [], expanded: groupExpandedState.value[`${stepId}_pending`] !== false }
  }

  let totalHosts = 0
  let filteredHosts = 0

  Object.values(hosts).forEach(hostLog => {
    totalHosts++
    
    // 应用主机名称/IP搜索过滤
    if (hostSearchText) {
      const hostName = (hostLog.hostname || hostLog.host_name || '').toLowerCase()
      const hostIP = (hostLog.host_ip || '').toLowerCase()
      if (!hostName.includes(hostSearchText) && !hostIP.includes(hostSearchText)) {
        return // 跳过不匹配的主机
      }
    }
    
    // 应用日志内容搜索过滤
    if (logSearchText) {
      const logs = (hostLog.stdout || hostLog.logs || '').toLowerCase()
      const errorLogs = (hostLog.stderr || hostLog.error_logs || '').toLowerCase()
      if (!logs.includes(logSearchText) && !errorLogs.includes(logSearchText)) {
        return // 跳过日志内容不匹配的主机
      }
    }
    
    filteredHosts++

    // 处理unknown状态，根据return_code判断
    let actualStatus = hostLog.status
    if (hostLog.status === 'unknown') {
      actualStatus = hostLog.return_code === 0 ? 'success' : 'failed'
    }
    
    if (groups[actualStatus]) {
      groups[actualStatus].hosts.push(hostLog)
    }
  })



  return groups
}

// 创建响应式的步骤主机分组计算属性
const stepHostGroups = computed(() => {
  // 包含搜索触发器以确保响应式更新
  searchTrigger.value
  
  // 确保追踪 hostSearchTexts 和 groupExpandedState 的变化
  const searchTexts = hostSearchTexts.value
  const expandedState = groupExpandedState.value
  
  const result = {}
  Object.keys(stepLogs.value).forEach(stepId => {
    result[stepId] = getHostGroupsForStep(stepId)
  })
  
  return result
})

// 监听搜索文本变化，强制更新计算属性
const searchTrigger = ref(0)
const triggerSearchUpdate = () => {
  searchTrigger.value++
}

// 计算属性 - 优化显示名称
const displayName = computed(() => {
  if (!executionInfo.value.name) return '-'

  // 移除 "执行方案: " 前缀
  let name = executionInfo.value.name
  if (name.startsWith('执行方案: ')) {
    name = name.replace('执行方案: ', '')
  }

  // 移除 #数字 后缀
  name = name.replace(/ #\d+$/, '')

  return name
})

// 计算属性 - 获取执行ID（用于SSE连接）
const executionId = computed(() => {
  return executionInfo.value.execution_id || null
})

// 计算属性 - 兼容旧格式的主机日志
const hostLogs = computed(() => {
  // 如果有步骤日志，返回空对象（使用步骤格式）
  if (Object.keys(stepLogs.value).length > 0) {
    return {}
  }

  // 如果没有步骤日志，检查是否有旧格式的主机日志
  const results = executionInfo.value.execution_results || {}
  return results.host_logs || {}
})

// 将step_results格式转换为step_logs格式
const convertStepResultsToStepLogs = (stepResults, executionRecord = null) => {
  if (!stepResults || typeof stepResults !== 'object') {
    return {}
  }

  const stepLogs = {}

  Object.entries(stepResults).forEach(([stepName, stepData]) => {
    const hosts = stepData.hosts || {}
    const stepHosts = {}

    Object.entries(hosts).forEach(([hostId, hostData]) => {
      // 将stdout/stderr转换为logs数组格式
      const logs = []

      // 处理stdout
      if (hostData.stdout) {
        hostData.stdout.split('\n').forEach(line => {
          if (line.trim()) {
            logs.push({
              timestamp: new Date().toISOString(),
              host_id: hostId,
              host_name: hostData.host_name,
              host_ip: hostData.host_ip,
              log_type: 'stdout',
              content: line.trim(),
              step_name: stepName,
              step_order: stepData.step_order || 1
            })
          }
        })
      }

      // 处理stderr
      if (hostData.stderr) {
        hostData.stderr.split('\n').forEach(line => {
          if (line.trim()) {
            logs.push({
              timestamp: new Date().toISOString(),
              host_id: hostId,
              host_name: hostData.host_name,
              host_ip: hostData.host_ip,
              log_type: 'stderr',
              content: line.trim(),
              step_name: stepName,
              step_order: stepData.step_order || 1
            })
          }
        })
      }

      stepHosts[hostId] = {
        host_id: hostId,
        host_name: hostData.host_name,
        host_ip: hostData.host_ip,
        status: hostData.success ? 'success' : 'failed',
        logs: logs,
        log_count: logs.length,
        // 同时提供原始的stdout/stderr格式，便于前端兼容
        stdout: hostData.stdout || '',
        stderr: hostData.stderr || '',
        start_time: hostData.start_time,
        end_time: hostData.end_time,
        execution_time: hostData.execution_time
      }
    })

    // 计算步骤的开始和结束时间
    let stepStartTime = null
    let stepEndTime = null
    let stepDuration = 0

    // 从主机数据中获取最早的开始时间和最晚的结束时间
    Object.values(stepHosts).forEach(hostData => {
      if (hostData.start_time) {
        if (!stepStartTime || new Date(hostData.start_time) < new Date(stepStartTime)) {
          stepStartTime = hostData.start_time
        }
      }
      if (hostData.end_time) {
        if (!stepEndTime || new Date(hostData.end_time) > new Date(stepEndTime)) {
          stepEndTime = hostData.end_time
        }
      }
      if (hostData.execution_time) {
        stepDuration = Math.max(stepDuration, hostData.execution_time)
      }
    })

    // 如果没有从主机数据获取到时间，尝试从执行记录获取
    if (!stepStartTime && executionRecord && executionRecord.started_at) {
      stepStartTime = executionRecord.started_at
    }
    if (!stepEndTime && executionRecord && executionRecord.finished_at) {
      stepEndTime = executionRecord.finished_at
    }
    if (!stepDuration && executionRecord && executionRecord.duration) {
      stepDuration = executionRecord.duration
    }

    // 添加步骤级别的信息，主机数据放在hosts字段中
    // 优先使用step_results中的时间信息
    stepLogs[stepName] = {
      step_order: stepData.step_order || 1,
      step_name: stepName,
      status: stepData.step_status || 'success',
      started_at: stepData.started_at || stepStartTime,
      finished_at: stepData.finished_at || stepEndTime,
      start_time: stepData.started_at || stepStartTime,  // 兼容字段
      end_time: stepData.finished_at || stepEndTime,      // 兼容字段
      duration: stepData.duration || stepDuration,
      hosts: stepHosts  // 主机数据放在hosts字段中
    }
  })

  return stepLogs
}

// 使用step_logs中的时间信息更新stepLogs
const updateStepLogsWithTiming = (stepLogs, stepLogsData) => {
  Object.entries(stepLogsData).forEach(([stepName, stepData]) => {
    if (stepLogs[stepName] && stepData) {
      // 计算步骤的开始和结束时间
      let stepStartTimes = []
      let stepEndTimes = []
      let stepExecutionTimes = []

      // 从主机数据中收集时间信息
      Object.entries(stepData).forEach(([key, value]) => {
        if (key === 'duration') return // 跳过duration字段

        if (typeof value === 'object' && value !== null) {
          if (value.start_time) stepStartTimes.push(value.start_time)
          if (value.end_time) stepEndTimes.push(value.end_time)
          if (value.execution_time) stepExecutionTimes.push(value.execution_time)
        }
      })

      // 更新步骤时间信息
      if (stepStartTimes.length > 0) {
        stepLogs[stepName].started_at = stepStartTimes.sort()[0] // 最早开始时间
        stepLogs[stepName].start_time = stepStartTimes.sort()[0]
      }

      if (stepEndTimes.length > 0) {
        stepLogs[stepName].finished_at = stepEndTimes.sort().reverse()[0] // 最晚结束时间
        stepLogs[stepName].end_time = stepEndTimes.sort().reverse()[0]
      }

      // 计算步骤的实际持续时间（结束时间 - 开始时间）
      if (stepStartTimes.length > 0 && stepEndTimes.length > 0) {
        try {
          const earliestStart = new Date(stepStartTimes.sort()[0])
          const latestEnd = new Date(stepEndTimes.sort().reverse()[0])
          const durationMs = latestEnd.getTime() - earliestStart.getTime()
          stepLogs[stepName].duration = durationMs / 1000 // 转换为秒
        } catch (e) {
          // 如果时间计算失败，使用最长的执行时间作为备选
          if (stepExecutionTimes.length > 0) {
            stepLogs[stepName].duration = Math.max(...stepExecutionTimes)
          }
        }
      } else if (stepExecutionTimes.length > 0) {
        // 如果没有开始/结束时间，使用最长的执行时间
        stepLogs[stepName].duration = Math.max(...stepExecutionTimes)
      }

      // 如果step_logs中有duration字段，优先使用
      if (stepData.duration !== null && stepData.duration !== undefined) {
        stepLogs[stepName].duration = stepData.duration
      }
    }
  })
}

// 将主机聚合格式转换为步骤格式
const convertHostLogsToStepLogs = (hostLogs) => {
  // 如果只有主机日志没有步骤信息，创建一个默认步骤
  return {
    'step_default': {
      step_name: '执行任务',
      step_order: 1,
      status: Object.values(hostLogs).some(h => h.status === 'failed') ? 'failed' : 'success',
      host_logs: hostLogs
    }
  }
}

// 将旧格式日志转换为步骤格式
const convertLegacyLogsToStepLogs = (legacyLogs) => {
  if (!legacyLogs || !Array.isArray(legacyLogs)) {
    return {}
  }

  // 按步骤分组
  const stepGroups = {}

  legacyLogs.forEach(log => {
    const stepName = log.step_name || '执行任务'
    const stepOrder = log.step_order || 1
    const hostId = log.host_id || 'unknown'
    const hostName = log.host_name || '未知主机'
    const hostIp = log.host_ip || ''
    const content = log.content || ''
    const logType = log.log_type || 'stdout'
    const timestamp = log.timestamp || ''

    // 初始化步骤
    if (!stepGroups[stepName]) {
      stepGroups[stepName] = {
        step_name: stepName,
        step_order: stepOrder,
        status: 'unknown',
        host_logs: {}
      }
    }

    // 初始化主机日志结构
    if (!stepGroups[stepName].host_logs[hostId]) {
      stepGroups[stepName].host_logs[hostId] = {
        host_id: hostId,
        host_name: hostName,
        host_ip: hostIp,
        status: 'unknown',
        logs: '',
        error_logs: '',
        start_time: timestamp,
        end_time: timestamp,
        log_count: 0
      }
    }

    const hostLog = stepGroups[stepName].host_logs[hostId]

    // 更新时间范围
    if (timestamp < hostLog.start_time) {
      hostLog.start_time = timestamp
    }
    if (timestamp > hostLog.end_time) {
      hostLog.end_time = timestamp
    }

    // 合并日志内容
    if (content.trim()) {
      const formattedLog = `[${timestamp}] ${content}\n`
      if (logType === 'stderr' || logType === 'error') {
        hostLog.error_logs += formattedLog
        hostLog.status = 'failed'
      } else {
        hostLog.logs += formattedLog
      }
      hostLog.log_count += 1
    }
  })

  // 设置默认状态和步骤状态
  Object.values(stepGroups).forEach(step => {
    let stepHasFailed = false
    let stepStartTime = null
    let stepEndTime = null
    
    Object.values(step.host_logs).forEach(hostLog => {
      if (hostLog.status === 'unknown') {
        hostLog.status = hostLog.error_logs ? 'failed' : 'success'
      }
      if (hostLog.status === 'failed') {
        stepHasFailed = true
      }
      
      // 收集步骤的时间范围
      if (hostLog.start_time) {
        if (!stepStartTime || hostLog.start_time < stepStartTime) {
          stepStartTime = hostLog.start_time
        }
      }
      if (hostLog.end_time) {
        if (!stepEndTime || hostLog.end_time > stepEndTime) {
          stepEndTime = hostLog.end_time
        }
      }
    })
    
    step.status = stepHasFailed ? 'failed' : 'success'
    step.started_at = stepStartTime
    step.finished_at = stepEndTime
  })

  return stepGroups
}

// 将旧格式日志转换为主机格式（兼容性保留）
const convertLegacyLogsToHostLogs = (legacyLogs) => {
  if (!legacyLogs || !Array.isArray(legacyLogs)) {
    return {}
  }

  const hostLogsMap = {}

  legacyLogs.forEach(log => {
    const hostId = log.host_id || 'unknown'
    const hostName = log.host_name || '未知主机'
    const hostIp = log.host_ip || ''
    const content = log.content || ''
    const logType = log.log_type || 'stdout'
    const timestamp = log.timestamp || ''

    // 初始化主机日志结构
    if (!hostLogsMap[hostId]) {
      hostLogsMap[hostId] = {
        host_id: hostId,
        host_name: hostName,
        host_ip: hostIp,
        status: 'unknown',
        logs: '',
        error_logs: '',
        start_time: timestamp,
        end_time: timestamp,
        log_count: 0
      }
    }

    // 更新时间范围
    if (timestamp < hostLogsMap[hostId].start_time) {
      hostLogsMap[hostId].start_time = timestamp
    }
    if (timestamp > hostLogsMap[hostId].end_time) {
      hostLogsMap[hostId].end_time = timestamp
    }

    // 合并日志内容
    if (content.trim()) {
      const formattedLog = `[${timestamp}] ${content}\n`
      if (logType === 'stderr' || logType === 'error') {
        hostLogsMap[hostId].error_logs += formattedLog
        hostLogsMap[hostId].status = 'failed'
      } else {
        hostLogsMap[hostId].logs += formattedLog
      }
      hostLogsMap[hostId].log_count += 1
    }
  })

  // 设置默认状态
  Object.values(hostLogsMap).forEach(hostLog => {
    if (hostLog.status === 'unknown') {
      hostLog.status = hostLog.error_logs ? 'failed' : 'success'
    }
  })

  return hostLogsMap
}

// 获取执行记录详情
const fetchExecutionDetail = async () => {
  loading.value = true
  try {
    const response = await executionRecordApi.getRecord(route.params.id)
    executionInfo.value = response

    // 处理日志数据
    if (response.execution_results) {
      console.log('Raw execution_results:', response.execution_results)

      // 检查是否是最新格式（有step_results字段）
      if (response.execution_results.step_results) {
        console.log('Using step_results format:', response.execution_results.step_results)
        // 最新格式：从step_results构建step_logs，传递执行记录信息
        stepLogs.value = convertStepResultsToStepLogs(response.execution_results.step_results, response)

        // step_results中已经包含了完整的时间信息，不再需要step_logs

        logSummary.value = response.execution_results.log_summary || null
      } else if (response.execution_results.step_logs) {
        console.log('Using step_logs format:', response.execution_results.step_logs)
        // 新格式：直接使用
        stepLogs.value = response.execution_results.step_logs
        logSummary.value = response.execution_results.log_summary || null
      } else if (response.execution_results.host_logs) {
        console.log('Using host_logs format:', response.execution_results.host_logs)
        // 中间格式：转换为步骤格式
        stepLogs.value = convertHostLogsToStepLogs(response.execution_results.host_logs)
        logSummary.value = response.execution_results.log_summary || null
      } else if (response.execution_results.logs) {
        console.log('Using legacy logs format:', response.execution_results.logs)
        // 旧格式：转换为新格式
        stepLogs.value = convertLegacyLogsToStepLogs(response.execution_results.logs)

        // 生成日志摘要
        const totalHosts = getTotalHostCount()
        const successCount = getHostCountByStatus('success')
        const failedCount = getHostCountByStatus('failed')

        logSummary.value = {
          total_steps: Object.keys(stepLogs.value).length,
          total_hosts: totalHosts,
          success_hosts: successCount,
          failed_hosts: failedCount,
          total_size: calculateTotalLogSize()
        }
      }
      
      console.log('Final stepLogs:', stepLogs.value)

      // 自动选择第一个步骤
      const stepIds = Object.keys(stepLogs.value)
      if (stepIds.length > 0 && !selectedStepId.value) {
        selectedStepId.value = stepIds[0]

        // 自动选择第一个主机
        const firstStep = stepLogs.value[stepIds[0]]
        if (firstStep && firstStep.host_logs) {
          const hostIds = Object.keys(firstStep.host_logs)
          if (hostIds.length > 0) {
            selectedHostId.value = hostIds[0]
            // 设置选中主机ID
            if (!selectedHostIds.value[stepIds[0]]) {
              selectedHostIds.value[stepIds[0]] = hostIds[0]
            }
          }
        }
      }
      
      // 初始化所有步骤的搜索文本
      stepIds.forEach(stepId => {
        if (!hostSearchTexts.value[stepId]) {
          hostSearchTexts.value[stepId] = ''
        }
        if (!logSearchTexts.value[stepId]) {
          logSearchTexts.value[stepId] = ''
        }
      })
    }
  } catch (error) {
    console.error('获取执行记录详情失败:', error)
    // 错误消息已由HTTP拦截器处理，这里不再重复显示
  } finally {
    loading.value = false
  }
}

// 刷新日志
const refreshLogs = () => {
  fetchExecutionDetail()
}

// 选择步骤
const selectStep = (stepId) => {
  selectedStepId.value = stepId

  // 自动选择该步骤的第一个主机
  const step = stepLogs.value[stepId]
  if (step) {
    // 兼容新旧格式：优先使用hosts，其次使用host_logs
    const hosts = step.hosts || step.host_logs
    if (hosts) {
      const hostIds = Object.keys(hosts)
      if (hostIds.length > 0) {
        // 如果没有选中主机或选中的主机不在当前步骤中，选择第一个主机
        if (!selectedHostIds.value[stepId] || !hostIds.includes(selectedHostIds.value[stepId])) {
          selectedHostIds.value[stepId] = hostIds[0]
        }
        selectedHostId.value = selectedHostIds.value[stepId]
      }
    }
  }
}

// 复制日志
const copyLogs = async (logContent) => {
  try {
    await navigator.clipboard.writeText(logContent)
    Message.success('日志已复制到剪贴板')
  } catch (error) {
    console.error('复制失败:', error)
    Message.error('复制失败')
  }
}

// 放大查看日志
const zoomLogs = (logContent, logType) => {
  logZoomTitle.value = `${logType} - 放大查看`
  logZoomRawContent.value = logContent
  logZoomContent.value = highlightLogContent(logContent, selectedStepId.value)
  logZoomVisible.value = true
}

// 复制放大日志
const copyZoomLogs = async () => {
  try {
    await navigator.clipboard.writeText(logZoomRawContent.value)
    Message.success('日志已复制到剪贴板')
  } catch (error) {
    console.error('复制失败:', error)
    Message.error('复制失败')
  }
}

// 复制主机IP
const copyHostIP = async (ip) => {
  try {
    await navigator.clipboard.writeText(ip)
    Message.success(`IP地址 ${ip} 已复制到剪贴板`)
  } catch (error) {
    console.error('复制失败:', error)
    Message.error('复制失败')
  }
}

// 获取总主机数量
const getTotalHostCount = () => {
  const allHosts = new Set()
  Object.values(stepLogs.value).forEach(step => {
    // 兼容新旧格式：优先使用hosts，其次使用host_logs
    const hosts = step.hosts || step.host_logs
    if (hosts) {
      Object.keys(hosts).forEach(hostId => {
        allHosts.add(hostId)
      })
    }
  })
  return allHosts.size
}

// 根据状态获取主机数量
const getHostCountByStatus = (status) => {
  const hostStatusMap = new Map()

  // 遍历所有步骤，收集每个主机的最终状态
  Object.values(stepLogs.value).forEach(step => {
    // 兼容新旧格式：优先使用hosts，其次使用host_logs
    const hosts = step.hosts || step.host_logs
    if (hosts) {
      Object.entries(hosts).forEach(([hostId, hostLog]) => {
        // 处理unknown状态，根据return_code判断
        let actualStatus = hostLog.status
        if (hostLog.status === 'unknown') {
          actualStatus = hostLog.return_code === 0 ? 'success' : 'failed'
        }
        
        // 如果主机有失败状态，优先记录失败
        if (actualStatus === 'failed' || !hostStatusMap.has(hostId)) {
          hostStatusMap.set(hostId, actualStatus)
        }
      })
    }
  })

  return Array.from(hostStatusMap.values()).filter(s => s === status).length
}

// 计算总日志大小
const calculateTotalLogSize = () => {
  let totalSize = 0
  Object.values(stepLogs.value).forEach(step => {
    // 兼容新旧格式：优先使用hosts，其次使用host_logs
    const hosts = step.hosts || step.host_logs
    if (hosts) {
      Object.values(hosts).forEach(hostLog => {
        totalSize += (hostLog.stdout || hostLog.logs || '').length + (hostLog.stderr || hostLog.error_logs || '').length
      })
    }
  })
  return totalSize
}

// 获取步骤状态颜色
const getStepStatusColor = (status) => {
  const colorMap = {
    'success': 'green',
    'failed': 'red',
    'running': 'blue',
    'pending': 'gray'
  }
  return colorMap[status] || 'gray'
}

// 获取步骤状态文本
const getStepStatusText = (status) => {
  const textMap = {
    'success': '成功',
    'failed': '失败',
    'running': '执行中',
    'pending': '等待中'
  }
  return textMap[status] || status
}

// 获取主机状态颜色
const getHostStatusColor = (status) => {
  const colorMap = {
    'success': 'green',
    'failed': 'red',
    'running': 'blue',
    'pending': 'gray',
    'unknown': 'orange'
  }
  return colorMap[status] || 'gray'
}

// 获取主机状态文本
const getHostStatusText = (status) => {
  const textMap = {
    'success': '成功',
    'failed': '失败',
    'running': '执行中',
    'pending': '等待中',
    'unknown': '未知'
  }
  return textMap[status] || status
}



// 注意：openRealtimeLog 函数已移除，现在使用内嵌的 RealtimeLog 组件

// 返回
const goBack = () => {
  router.back()
}



// 重试执行
const handleRetry = async () => {
  const isRetry = executionInfo.value.status === 'failed'
  const title = isRetry ? '确认重试' : '确认重做'
  const content = isRetry
    ? `确定要重试执行"${executionInfo.value.name}"吗？`
    : `确定要重做"${executionInfo.value.name}"吗？`

  try {
    await Modal.confirm({
      title,
      content,
      onOk: async () => {
        try {
          console.log('开始调用重做API, 执行记录ID:', route.params.id)
          const result = await executionRecordApi.retryExecution(route.params.id)
          console.log('重做API返回结果:', result)

          const successMessage = isRetry ? '重试成功' : '重做成功'
          Message.success(successMessage)

          // 如果返回了新的执行记录ID，跳转到新的执行记录详情页面
          // 注意：由于响应拦截器会自动提取content字段，result就是content的内容
          if (result && result.execution_record_id) {
            console.log('跳转到新的执行记录:', result.execution_record_id)
            await router.push(`/execution-records/${result.execution_record_id}`)
            console.log('跳转完成')
          } else {
            console.log('没有返回execution_record_id，刷新当前页面')
            console.log('result结构:', result)
            // 如果没有返回新的执行记录ID，刷新当前页面
            fetchExecutionDetail()
          }
        } catch (error) {
          console.error('重做操作失败:', error)
          Message.error('重做操作失败')
        }
      }
    })
  } catch (error) {
    console.error('重试失败:', error)
  }
}

// 取消执行
const handleCancel = async () => {
  try {
    await Modal.confirm({
      title: '确认取消',
      content: `确定要取消执行"${executionInfo.value.name}"吗？`,
      onOk: async () => {
        await executionRecordApi.cancelExecution(route.params.id)
        Message.success('取消成功')
        fetchExecutionDetail()
      }
    })
  } catch (error) {
    console.error('取消失败:', error)
  }
}

// 判断步骤是否可以重试
const canRetryStep = (step) => {
  if (!step) return false

  // 支持重试的步骤状态：失败、超时、取消
  const retryableStatuses = ['failed', 'timeout', 'cancelled']
  if (!retryableStatuses.includes(step.status)) return false

  // 支持重试的执行记录状态：失败、超时、取消、成功（可以重做）
  const retryableExecutionStatuses = ['failed', 'timeout', 'cancelled', 'success']
  if (!retryableExecutionStatuses.includes(executionInfo.value.status)) return false

  return true
}

// 步骤重试
const handleStepRetry = async (retryType, stepId) => {
  if (!stepId || !stepLogs.value[stepId]) {
    Message.warning('请先选择要重试的步骤')
    return
  }

  const step = stepLogs.value[stepId]
  const retryTypeText = {
    'failed_only': '仅重试失败主机',
    'all': '重试该步骤'
  }

  try {
    await Modal.confirm({
      title: '确认步骤重试',
      content: `确定要${retryTypeText[retryType]}执行步骤"${step.step_name}"吗？`,
      onOk: async () => {
        try {
          await executionRecordApi.retryStepInplace(route.params.id, stepId, retryType)
          Message.success('步骤重试成功')
          fetchExecutionDetail()
        } catch (error) {
          console.error('步骤重试API调用失败:', error)
          Message.error('步骤重试失败')
        }
      }
    })
  } catch (error) {
    console.error('步骤重试失败:', error)
  }
}

// 忽略错误继续
const handleStepIgnoreError = async (stepId) => {
  if (!stepId || !stepLogs.value[stepId]) {
    Message.warning('请先选择要忽略错误的步骤')
    return
  }

  const step = stepLogs.value[stepId]

  try {
    await Modal.confirm({
      title: '确认忽略错误',
      content: `确定要忽略步骤"${step.step_name}"的错误并继续执行后续步骤吗？`,
      onOk: async () => {
        try {
          await executionRecordApi.ignoreStepError(route.params.id, stepId)
          Message.success('已忽略错误，继续执行')
          fetchExecutionDetail()
        } catch (error) {
          console.error('忽略错误API调用失败:', error)
          Message.error('忽略错误失败')
        }
      }
    })
  } catch (error) {
    console.error('忽略错误失败:', error)
  }
}

// 获取空日志描述
const getEmptyLogsDescription = () => {
  if (executionInfo.value.status === 'cancelled') {
    return '任务已取消，暂无执行日志'
  } else if (executionInfo.value.status === 'pending') {
    return '任务尚未开始执行'
  } else {
    return '暂无日志数据'
  }
}

// 工具函数
const getExecutionTypeText = (type) => {
  const typeMap = {
    'quick_script': '快速脚本执行',
    'quick_file_transfer': '快速文件传输',
    'job_workflow': 'Job工作流执行',
    'scheduled_job': '定时作业执行'
  }
  return typeMap[type] || type
}

const getExecutionTypeColor = (type) => {
  const colorMap = {
    'quick_script': 'blue',
    'quick_file_transfer': 'green',
    'job_workflow': 'purple',
    'scheduled_job': 'orange'
  }
  return colorMap[type] || 'gray'
}

const getStatusText = (status) => {
  const statusMap = {
    'pending': '等待中',
    'running': '执行中',
    'success': '成功',
    'failed': '失败',
    'cancelled': '已取消'
  }
  return statusMap[status] || status
}

const getStatusColor = (status) => {
  const colorMap = {
    'pending': 'gray',
    'running': 'blue',
    'success': 'green',
    'failed': 'red',
    'cancelled': 'orange'
  }
  return colorMap[status] || 'gray'
}

const getStatusIcon = (status) => {
  const iconMap = {
    'pending': 'icon-pause',
    'running': 'icon-loading',
    'success': 'icon-check',
    'failed': 'icon-exclamation',
    'cancelled': 'icon-close'
  }
  return iconMap[status] || 'icon-pause'
}

const formatDuration = (startTime, endTime) => {
  if (!startTime || !endTime) {
    return '-'
  }
  
  const start = new Date(startTime)
  const end = new Date(endTime)
  
  // 检查日期是否有效
  if (isNaN(start.getTime()) || isNaN(end.getTime())) {
    return '-'
  }
  
  const duration = (end - start) / 1000
  
  if (duration < 0) {
    return '-'
  }

  if (duration < 60) {
    return `${duration.toFixed(1)}秒`
  } else if (duration < 3600) {
    const minutes = Math.floor(duration / 60)
    const seconds = (duration % 60).toFixed(1)
    return `${minutes}分${seconds}秒`
  } else {
    const hours = Math.floor(duration / 3600)
    const minutes = Math.floor((duration % 3600) / 60)
    const seconds = (duration % 60).toFixed(1)
    return `${hours}时${minutes}分${seconds}秒`
  }
}

const formatDateTime = (dateTime) => {
  if (!dateTime) return '-'
  return new Date(dateTime).toLocaleString('zh-CN')
}

const formatFileSize = (bytes) => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}



// 主机分组展开/收起
const toggleGroupInStep = (stepId, status) => {
  const stepKey = `${stepId}_${status}`
  const currentState = groupExpandedState.value[stepKey]
  groupExpandedState.value[stepKey] = !currentState
  // 强制更新计算属性
  triggerSearchUpdate()
}

// 展开所有步骤的主机分组
const expandAllSteps = () => {
  Object.keys(stepLogs.value).forEach(stepId => {
    ['success', 'failed', 'running', 'pending'].forEach(status => {
      const stepKey = `${stepId}_${status}`
      groupExpandedState.value[stepKey] = true
    })
  })
  // 强制更新计算属性
  triggerSearchUpdate()
}

// 收起所有步骤的主机分组
const collapseAllSteps = () => {
  Object.keys(stepLogs.value).forEach(stepId => {
    ['success', 'failed', 'running', 'pending'].forEach(status => {
      const stepKey = `${stepId}_${status}`
      groupExpandedState.value[stepKey] = false
    })
  })
  // 强制更新计算属性
  triggerSearchUpdate()
}

// 更新主机搜索文本
const updateSearchText = (stepId, value) => {

  
  // 确保 hostSearchTexts 是响应式的
  if (!hostSearchTexts.value[stepId]) {
    hostSearchTexts.value[stepId] = ''
  }
  
  // 更新搜索文本
  hostSearchTexts.value[stepId] = value
  
  // 触发搜索更新
  triggerSearchUpdate()
  

}

// 更新日志搜索文本
const updateLogSearchText = (stepId, value) => {

  
  // 确保 logSearchTexts 是响应式的
  if (!logSearchTexts.value[stepId]) {
    logSearchTexts.value[stepId] = ''
  }
  
  // 更新搜索文本
  logSearchTexts.value[stepId] = value
  
  // 触发搜索更新
  triggerSearchUpdate()
}

// 过滤主机（保留原有函数以兼容）
const filterHostsInStep = (stepId) => {
  updateSearchText(stepId, hostSearchTexts.value[stepId] || '')
}

// 获取步骤中指定状态的主机数量
const getHostCountByStatusInStep = (stepId, status) => {
  const stepLog = stepLogs.value[stepId]
  if (!stepLog) {
    return 0
  }
  
  // 兼容新旧格式：优先使用hosts，其次使用host_logs
  const hosts = stepLog.hosts || stepLog.host_logs
  if (!hosts) {
    console.log('No hosts found for step:', stepId, stepLog)
    return 0
  }
  
  const count = Object.values(hosts).filter(hostLog => {
    // 如果状态是unknown，根据return_code判断
    if (hostLog.status === 'unknown') {
      return hostLog.return_code === 0 ? status === 'success' : status === 'failed'
    }
    return hostLog.status === status
  }).length
  
  console.log(`Step ${stepId} status ${status} count:`, count, hosts)
  return count
}

// 切换步骤日志显示状态
const toggleLogDisplay = (stepId) => {
  showLogsForStep.value[stepId] = !showLogsForStep.value[stepId]
}

// 获取步骤中的总主机数量
const getTotalHostCountInStep = (stepId) => {
  const stepLog = stepLogs.value[stepId]
  if (!stepLog) {
    return 0
  }
  
  // 兼容新旧格式：优先使用hosts，其次使用host_logs
  const hosts = stepLog.hosts || stepLog.host_logs
  if (!hosts) {
    console.log('No hosts found for step total count:', stepId, stepLog)
    return 0
  }
  
  const count = Object.keys(hosts).length
  console.log(`Step ${stepId} total host count:`, count, hosts)
  return count
}

// 获取主机显示名称
const getHostDisplayName = (hostLog) => {
  // 如果主机信息是unknown、空字符串或null，尝试从executionInfo中获取实际主机信息
  if ((!hostLog.hostname || hostLog.hostname === 'unknown') && 
      (!hostLog.host_name || hostLog.host_name === 'unknown') && 
      (!hostLog.host_ip || hostLog.host_ip === 'unknown')) {
    // 从target_hosts中获取第一个主机信息（因为快速脚本执行通常只有一个主机）
    if (executionInfo.value.target_hosts && executionInfo.value.target_hosts.length > 0) {
      const targetHost = executionInfo.value.target_hosts[0]
      return targetHost.name || targetHost.ip_address || '未知主机'
    }
  }
  
  // 优先使用host_name，其次host_ip，最后hostname
  return hostLog.host_name || hostLog.host_ip || hostLog.hostname || '未知主机'
}

// 获取主机IP
const getHostIP = (hostLog) => {
  // 如果主机IP是unknown、空字符串或null，尝试从executionInfo中获取实际主机IP
  if (!hostLog.host_ip || hostLog.host_ip === 'unknown' || hostLog.host_ip === '') {
    // 从target_hosts中获取第一个主机信息
    if (executionInfo.value.target_hosts && executionInfo.value.target_hosts.length > 0) {
      const targetHost = executionInfo.value.target_hosts[0]
      return targetHost.ip_address || '未知IP'
    }
  }
  
  return hostLog.host_ip || '未知IP'
}

// 复制步骤中指定状态的主机IP
const copyHostsByStatusInStep = async (stepId, status) => {
  const stepLog = stepLogs.value[stepId]
  if (!stepLog) {
    Message.warning('该步骤暂无主机数据')
    return
  }

  // 兼容新旧格式：优先使用hosts，其次使用host_logs
  const hostData = stepLog.hosts || stepLog.host_logs
  if (!hostData) {
    Message.warning('该步骤暂无主机数据')
    return
  }

  let hosts = []
  if (status === 'all') {
    hosts = Object.values(hostData)
  } else {
    hosts = Object.values(hostData).filter(hostLog => hostLog.status === status)
  }

  if (hosts.length === 0) {
    Message.warning(`该步骤下没有${status === 'all' ? '' : status}状态的主机`)
    return
  }

  const ips = hosts.map(host => host.host_ip || host.ip_address).join('\n')
  try {
    await navigator.clipboard.writeText(ips)
    Message.success(`已复制 ${hosts.length} 台主机的IP地址`)
  } catch (err) {
    Message.error('复制失败，请手动复制')
  }
}

// 高亮日志内容中的搜索关键词
const highlightLogContent = (content, stepId) => {
  if (!content) return ''
  
  const searchText = logSearchTexts.value[stepId] || ''
  
  // 转义HTML特殊字符
  const escapedContent = content
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
  
  if (!searchText) return escapedContent
  
  // 高亮搜索关键词（不区分大小写）
  const regex = new RegExp(`(${searchText.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi')
  return escapedContent.replace(regex, '<mark class="log-highlight">$1</mark>')
}

// 初始化
onMounted(() => {
  fetchExecutionDetail()
  
  // 初始化搜索文本
  nextTick(() => {
    Object.keys(stepLogs.value).forEach(stepId => {
      if (!hostSearchTexts.value[stepId]) {
        hostSearchTexts.value[stepId] = ''
      }
      if (!logSearchTexts.value[stepId]) {
        logSearchTexts.value[stepId] = ''
      }
    })
  })
})
</script>

<style scoped>
.execution-detail-container {
  padding: 16px;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.info-card,
.realtime-card {
  margin-bottom: 16px;
}

.logs-card {
  margin-bottom: 16px;
  flex: 1;
  display: flex;
  flex-direction: column;
}

.realtime-urls {
  margin-top: 16px;
}

.loading-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 200px;
}

.empty-logs {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 200px;
}

.log-summary {
  margin-bottom: 20px;
  padding: 16px;
  background-color: #f8f9fa;
  border-radius: 8px;
  border: 1px solid #e8e8e8;
}

.log-content {
  margin-bottom: 16px;
}

.log-text {
  background-color: #1e1e1e;
  color: #d4d4d4;
  padding: 16px;
  border-radius: 6px;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.4;
  max-height: 600px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-wrap: break-word;
}

.log-pagination {
  display: flex;
  justify-content: center;
}



/* 步骤日志布局样式 */
.step-logs-layout {
  display: flex;
  height: 80vh;
  min-height: 700px;
  border: 1px solid #e8e8e8;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  background-color: #fff;
}

/* 左侧步骤列表 */
.step-list {
  border-right: 1px solid #e8e8e8;
  background-color: #f8f9fa;
  display: flex;
  flex-direction: column;
  min-width: 250px;
  max-width: 600px;
}



.step-list-header {
  padding: 16px;
  border-bottom: 1px solid #e8e8e8;
  background-color: #fff;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}

.step-list-header h4 {
  margin: 0;
  font-size: 14px;
  font-weight: 500;
}

.step-list-content {
  flex: 1;
  overflow-y: auto;
}



/* 右侧主机日志内容 */
.host-logs-content {
  display: flex;
  flex-direction: column;
  background-color: #fff;
  overflow: hidden;
}

.selected-step-logs {
  flex: 1;
  display: flex;
  flex-direction: column;
  height: 100%;
}

.step-header {
  padding: 20px;
  border-bottom: 1px solid #e8e8e8;
  background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
  display: flex;
  justify-content: space-between;
  align-items: center;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.08);
}

.step-info-header {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.step-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #262626;
}

.step-meta {
  display: flex;
  gap: 8px;
  align-items: center;
}

.step-order-tag, .step-status-tag {
  font-weight: 500;
  border-radius: 6px;
}

.step-actions {
  display: flex;
  align-items: center;
}

.step-header h4 {
  margin: 0;
  font-size: 14px;
  font-weight: 500;
}

.host-log-content {
  display: flex;
  flex-direction: column;
  padding: 16px;
}

.log-section {
  margin-bottom: 16px;
}

.log-section:last-child {
  margin-bottom: 0;
}

.log-section-header {
  padding: 8px 16px;
  background-color: #f8f9fa;
  border-bottom: 1px solid #f0f0f0;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.log-section-header h5 {
  margin: 0;
  font-size: 13px;
  font-weight: 500;
}

.log-text-container {
  border: 1px solid #e8e8e8;
  border-radius: 6px;
  overflow: hidden;
}

.log-text {
  margin: 0;
  background-color: #1e1e1e;
  color: #d4d4d4;
  padding: 16px;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.5;
  height: 400px;
  overflow-y: auto;
  overflow-x: auto;
  white-space: pre-wrap;
  word-wrap: break-word;
  border: none;
  border-radius: 0;
}

/* 日志滚动条样式 */
.log-text::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

.log-text::-webkit-scrollbar-track {
  background-color: #2d2d2d;
  border-radius: 4px;
}

.log-text::-webkit-scrollbar-thumb {
  background-color: #555;
  border-radius: 4px;
}

.log-text::-webkit-scrollbar-thumb:hover {
  background-color: #777;
}

.error-section .log-text {
  background-color: #2d1b1b;
  color: #ff6b6b;
}

.no-logs, .no-step-selected {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* 主机标签页样式 */
.host-tabs {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.host-tabs :deep(.ant-tabs-nav) {
  margin-bottom: 0;
  background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
  border-bottom: 2px solid #e8e8e8;
  padding: 12px 20px 0;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.host-tabs :deep(.ant-tabs-nav-wrap) {
  overflow-x: auto;
  overflow-y: hidden;
  scrollbar-width: thin;
  scrollbar-color: #d9d9d9 transparent;
}

.host-tabs :deep(.ant-tabs-nav-wrap)::-webkit-scrollbar {
  height: 6px;
}

.host-tabs :deep(.ant-tabs-nav-wrap)::-webkit-scrollbar-track {
  background-color: transparent;
}

.host-tabs :deep(.ant-tabs-nav-wrap)::-webkit-scrollbar-thumb {
  background-color: #d9d9d9;
  border-radius: 3px;
}

.host-tabs :deep(.ant-tabs-nav-wrap)::-webkit-scrollbar-thumb:hover {
  background-color: #bfbfbf;
}

.host-tabs :deep(.ant-tabs-nav-list) {
  display: flex;
  flex-wrap: nowrap;
}

.host-tabs :deep(.ant-tabs-tab) {
  margin-right: 12px;
  padding: 12px 24px;
  border-radius: 12px 12px 0 0;
  border: 2px solid #e8e8e8;
  background-color: #fff;
  transition: all 0.3s ease;
  white-space: nowrap;
  min-width: 160px;
  text-align: center;
  font-weight: 500;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.host-tabs :deep(.ant-tabs-tab:hover) {
  border-color: #40a9ff;
  color: #40a9ff;
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(64, 169, 255, 0.3);
}

.host-tabs :deep(.ant-tabs-tab-active) {
  background: linear-gradient(135deg, #1890ff 0%, #40a9ff 100%);
  border-color: #1890ff;
  color: #fff;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(24, 144, 255, 0.4);
}

.host-tabs :deep(.ant-tabs-tab-active .ant-tabs-tab-btn) {
  color: #fff;
}

.host-tabs :deep(.ant-tabs-content-holder) {
  flex: 1;
  overflow: hidden;
}

.host-tabs :deep(.ant-tabs-content) {
  height: 100%;
}

.host-tabs :deep(.ant-tabs-tabpane) {
  height: 100%;
  padding: 0;
}

/* 主机标签标题样式 */
.host-tab-title {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 2px 0;
}

.host-name {
  font-weight: 600;
  font-size: 14px;
  color: inherit;
}

.host-status-tag {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 6px;
  font-weight: 500;
}

/* 根据主机状态调整标签样式 */
.host-tabs :deep(.host-tab-success .ant-tabs-tab) {
  border-color: #52c41a;
}

.host-tabs :deep(.host-tab-success.ant-tabs-tab-active) {
  background-color: #52c41a;
  border-color: #52c41a;
}

.host-tabs :deep(.host-tab-failed .ant-tabs-tab) {
  border-color: #ff4d4f;
}

.host-tabs :deep(.host-tab-failed.ant-tabs-tab-active) {
  background-color: #ff4d4f;
  border-color: #ff4d4f;
}

.host-tabs :deep(.host-tab-running .ant-tabs-tab) {
  border-color: #1890ff;
}

.host-tabs :deep(.host-tab-running.ant-tabs-tab-active) {
  background-color: #1890ff;
  border-color: #1890ff;
}

/* 主机信息头部样式 */
.host-info-header {
  padding: 16px;
  border-bottom: 1px solid #e8e8e8;
  background-color: #f8f9fa;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.host-info h5 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #262626;
}

/* 主机分组样式 */
.host-groups-container {
  display: flex;
  flex-direction: column;
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  background-color: #fafafa;
}

.host-group {
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  margin-bottom: 16px;
  overflow: visible;
  background-color: #fff;
}

.host-group:last-child {
  margin-bottom: 0;
  flex: 1;
  display: flex;
  flex-direction: column;
}

.host-group-header {
  padding: 12px 16px;
  background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
  border-bottom: 1px solid #e8e8e8;
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  transition: background-color 0.2s;
}

.host-group-header:hover {
  background: linear-gradient(135deg, #e9ecef 0%, #dee2e6 100%);
}

.group-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.group-status-tag {
  font-weight: 600;
  border-radius: 6px;
}

.group-count {
  font-size: 14px;
  color: #666;
  font-weight: 500;
}

.group-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.expand-icon {
  transition: transform 0.2s;
  color: #666;
}

.expand-icon.rotate-180 {
  transform: rotate(180deg);
}

.host-group-content {
  display: flex;
  flex-direction: column;
  min-height: 200px;
  padding: 16px;
  background-color: #fafafa;
}

.no-hosts {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 150px;
  color: #999;
}

/* 步骤卡片头部样式 */
.step-card-header {
  padding: 16px 20px;
  border-bottom: 1px solid #e8e8e8;
  cursor: pointer;
  transition: background-color 0.2s;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.step-card-header:hover {
  background-color: #f8f9fa;
}

.step-info {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.step-order {
  font-size: 12px;
  color: #666;
  font-weight: 500;
}

.step-name {
  font-size: 14px;
  font-weight: 600;
  color: #262626;
}

.step-summary {
  display: flex;
  align-items: center;
  gap: 16px;
}

.host-status-summary {
  display: flex;
  align-items: center;
  gap: 12px;
}

.status-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  font-weight: 500;
  padding: 4px 8px;
  border-radius: 6px;
  background-color: #f8f9fa;
  border: 1px solid #e8e8e8;
}

.status-item.success {
  color: #52c41a;
  background-color: #f6ffed;
  border-color: #b7eb8f;
}

.status-item.success .arco-icon {
  color: #52c41a;
}

.status-item.failed {
  color: #ff4d4f;
  background-color: #fff2f0;
  border-color: #ffccc7;
}

.status-item.failed .arco-icon {
  color: #ff4d4f;
}

.status-item.running {
  color: #1890ff;
  background-color: #e6f7ff;
  border-color: #91d5ff;
}

.status-item.running .arco-icon {
  color: #1890ff;
}

.status-item.pending {
  color: #666;
  background-color: #f5f5f5;
  border-color: #d9d9d9;
}

.status-item.pending .arco-icon {
  color: #666;
}

.step-actions {
  display: flex;
  align-items: center;
}

.step-expanded-content {
  padding: 16px;
  background-color: #fafafa;
}

.step-detail-header {
  margin-bottom: 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

/* 执行流程布局样式 */
.execution-flow-layout {
  display: flex;
  flex-direction: column;
  gap: 16px;
  flex: 1;
  min-height: 0;
}

.execution-flow-container {
  display: flex;
  flex: 1;
  min-height: 900px;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  overflow: hidden;
  background-color: #fff;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

/* 左侧步骤侧边栏 */
.steps-sidebar {
  width: 280px;
  border-right: 1px solid #e8e8e8;
  background-color: #fafafa;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}

.steps-header {
  padding: 8px 12px;
  border-bottom: 1px solid #e8e8e8;
  background-color: #fff;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.steps-header-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.steps-header-actions {
  display: flex;
  gap: 4px;
}

.steps-header h4 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: #262626;
}

.steps-count {
  font-size: 12px;
  color: #666;
  background-color: #f0f0f0;
  padding: 2px 8px;
  border-radius: 10px;
}

.steps-flow {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
  position: relative;
}

.step-flow-item {
  position: relative;
  margin-bottom: 12px;
}

.step-flow-item:last-child {
  margin-bottom: 0;
}

.step-connector {
  position: absolute;
  left: 20px;
  top: -20px;
  width: 2px;
  height: 20px;
  background: linear-gradient(180deg, #d9d9d9 0%, #e8e8e8 100%);
  z-index: 1;
}

.step-flow-item.step-active .step-connector {
  background: linear-gradient(180deg, #1890ff 0%, #40a9ff 100%);
}

.step-node {
  position: relative;
  background-color: #fff;
  border: 1px solid #e8e8e8;
  border-radius: 6px;
  padding: 8px;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
}

.step-node:hover {
  border-color: #40a9ff;
  box-shadow: 0 4px 12px rgba(64, 169, 255, 0.2);
  transform: translateY(-2px);
}

.step-flow-item.step-active .step-node {
  border-color: #1890ff;
  background: linear-gradient(135deg, #e6f7ff 0%, #f0f9ff 100%);
  box-shadow: 0 6px 16px rgba(24, 144, 255, 0.3);
  transform: translateY(-2px);
}

.step-flow-item.step-active .step-node::before {
  content: '';
  position: absolute;
  left: -2px;
  top: -2px;
  bottom: -2px;
  width: 4px;
  background: linear-gradient(180deg, #1890ff 0%, #40a9ff 100%);
  border-radius: 2px;
}

.step-node-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.step-order {
  font-size: 10px;
  color: #666;
  font-weight: 500;
}

.step-name {
  font-size: 12px;
  font-weight: 600;
  color: #262626;
  line-height: 1.2;
}

.step-status {
  display: flex;
  justify-content: flex-start;
}

.step-status-tag {
  font-weight: 500;
}

.step-timing {
  display: flex;
  flex-direction: column;
  gap: 1px;
  font-size: 9px;
  color: #666;
}

.step-start-time,
.step-duration {
  display: flex;
  align-items: center;
  gap: 4px;
}

.step-host-stats {
  display: flex;
  justify-content: center;
  margin-top: 2px;
}

.host-count-circle {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: linear-gradient(135deg, #f0f0f0 0%, #e8e8e8 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid #d9d9d9;
}

.step-flow-item.step-active .host-count-circle {
  background: linear-gradient(135deg, #e6f7ff 0%, #bae7ff 100%);
  border-color: #40a9ff;
}

.host-count {
  font-size: 9px;
  font-weight: 600;
  color: #262626;
}

.step-flow-item.step-active .host-count {
  color: #1890ff;
}

.step-actions {
  position: absolute;
  top: 8px;
  right: 8px;
  opacity: 0;
  transition: opacity 0.2s;
}

.step-node:hover .step-actions,
.step-flow-item.step-active .step-actions {
  opacity: 1;
}

.step-item {
  margin-bottom: 8px;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  background-color: #fff;
  cursor: pointer;
  transition: all 0.3s ease;
  overflow: hidden;
}

.step-item:hover {
  border-color: #40a9ff;
  box-shadow: 0 2px 8px rgba(64, 169, 255, 0.2);
  transform: translateY(-1px);
}

.step-item.step-active {
  border-color: #1890ff;
  background: linear-gradient(135deg, #e6f7ff 0%, #f0f9ff 100%);
  box-shadow: 0 4px 12px rgba(24, 144, 255, 0.3);
  position: relative;
}

.step-item.step-active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 4px;
  background: linear-gradient(180deg, #1890ff 0%, #40a9ff 100%);
  border-radius: 2px;
}

.step-item-content {
  padding: 16px;
}

.step-item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.step-order {
  font-size: 12px;
  color: #666;
  font-weight: 500;
}

.step-status-tag {
  font-weight: 500;
}

.step-name {
  font-size: 14px;
  font-weight: 600;
  color: #262626;
  margin-bottom: 12px;
  line-height: 1.4;
}

.step-summary-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  font-weight: 500;
  padding: 2px 6px;
  border-radius: 4px;
  background-color: #f8f9fa;
  border: 1px solid #e8e8e8;
}

.stat-item.success {
  color: #52c41a;
  background-color: #f6ffed;
  border-color: #b7eb8f;
}

.stat-item.success .arco-icon {
  color: #52c41a;
}

.stat-item.failed {
  color: #ff4d4f;
  background-color: #fff2f0;
  border-color: #ffccc7;
}

.stat-item.failed .arco-icon {
  color: #ff4d4f;
}

.stat-item.running {
  color: #1890ff;
  background-color: #e6f7ff;
  border-color: #91d5ff;
}

.stat-item.running .arco-icon {
  color: #1890ff;
}

.stat-item.pending {
  color: #666;
  background-color: #f5f5f5;
  border-color: #d9d9d9;
}

.stat-item.pending .arco-icon {
  color: #666;
}

.step-item-actions {
  padding: 8px 16px;
  border-top: 1px solid #f0f0f0;
  background-color: #fafafa;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.step-item-indicator {
  display: flex;
  align-items: center;
}

.step-status-indicator {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: #d9d9d9;
}

.step-status-indicator.status-success {
  background-color: #52c41a;
  box-shadow: 0 0 0 2px rgba(82, 196, 26, 0.2);
}

.step-status-indicator.status-failed {
  background-color: #ff4d4f;
  box-shadow: 0 0 0 2px rgba(255, 77, 79, 0.2);
}

.step-status-indicator.status-running {
  background-color: #1890ff;
  box-shadow: 0 0 0 2px rgba(24, 144, 255, 0.2);
  animation: pulse 2s infinite;
}

.step-status-indicator.status-pending {
  background-color: #d9d9d9;
  box-shadow: 0 0 0 2px rgba(217, 217, 217, 0.2);
}

@keyframes pulse {
  0% {
    box-shadow: 0 0 0 0 rgba(24, 144, 255, 0.7);
  }
  70% {
    box-shadow: 0 0 0 6px rgba(24, 144, 255, 0);
  }
  100% {
    box-shadow: 0 0 0 0 rgba(24, 144, 255, 0);
  }
}

/* 右侧步骤详情面板 */
.step-detail-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  background-color: #fff;
  overflow: hidden;
}

.no-step-selected {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #fafafa;
}

.step-detail-content {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.step-detail-header {
  padding: 20px;
  border-bottom: 1px solid #e8e8e8;
  background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.step-detail-info h3 {
  margin: 0 0 8px 0;
  font-size: 18px;
  font-weight: 600;
  color: #262626;
}

.step-detail-meta {
  display: flex;
  align-items: center;
  gap: 12px;
}

.step-order-text {
  font-size: 14px;
  color: #666;
  font-weight: 500;
}

.step-detail-actions {
  display: flex;
  align-items: center;
}

/* 主机概览样式 */
.host-overview {
  padding: 12px 16px;
  border-bottom: 1px solid #e8e8e8;
  background-color: #fff;
  flex-shrink: 0;
}

.host-overview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.host-overview-header h4 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: #262626;
}

.host-total {
  font-size: 12px;
  color: #666;
  background-color: #f0f0f0;
  padding: 2px 8px;
  border-radius: 10px;
}

.host-status-summary {
  display: flex;
  gap: 8px;
  justify-content: center;
}

.status-summary-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 6px 8px;
  border-radius: 6px;
  background-color: #f8f9fa;
  border: 1px solid #e8e8e8;
  min-width: 50px;
}

.status-summary-item.success {
  background-color: #f6ffed;
  border-color: #b7eb8f;
}

.status-summary-item.success .arco-icon {
  color: #52c41a;
}

.status-summary-item.failed {
  background-color: #fff2f0;
  border-color: #ffccc7;
}

.status-summary-item.failed .arco-icon {
  color: #ff4d4f;
}

.status-summary-item.running {
  background-color: #e6f7ff;
  border-color: #91d5ff;
}

.status-summary-item.running .arco-icon {
  color: #1890ff;
}

.status-summary-item.pending {
  background-color: #f5f5f5;
  border-color: #d9d9d9;
}

.status-summary-item.pending .arco-icon {
  color: #666;
}

.status-count {
  font-size: 14px;
  font-weight: 600;
  color: #262626;
}

.status-label {
  font-size: 10px;
  color: #666;
  font-weight: 500;
}

/* 日志提示区域 */
.logs-prompt-area {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
  padding: 40px 20px;
}

.prompt-content {
  text-align: center;
  max-width: 400px;
  padding: 30px;
  background-color: #fff;
  border-radius: 12px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
  border: 1px solid #e8e8e8;
}

.prompt-icon {
  width: 60px;
  height: 60px;
  margin: 0 auto 20px;
  background: linear-gradient(135deg, #1890ff 0%, #40a9ff 100%);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 24px;
  box-shadow: 0 2px 8px rgba(24, 144, 255, 0.3);
}

.prompt-content h3 {
  margin: 0 0 8px 0;
  font-size: 18px;
  font-weight: 600;
  color: #262626;
}

.prompt-content p {
  margin: 0;
  font-size: 14px;
  color: #666;
  line-height: 1.5;
}

/* 日志详情区域 */
.logs-detail-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.search-bar {
  padding: 16px 20px;
  border-bottom: 1px solid #e8e8e8;
  background-color: #fff;
  flex-shrink: 0;
}

/* 日志搜索高亮样式 */
.log-highlight {
  background-color: #ffeb3b;
  color: #000;
  padding: 2px 4px;
  border-radius: 3px;
  font-weight: bold;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
}

/* 滚动条样式优化 */
.steps-list::-webkit-scrollbar,
.host-groups-container::-webkit-scrollbar {
  width: 6px;
}

.steps-list::-webkit-scrollbar-track,
.host-groups-container::-webkit-scrollbar-track {
  background-color: #f1f1f1;
  border-radius: 3px;
}

.steps-list::-webkit-scrollbar-thumb,
.host-groups-container::-webkit-scrollbar-thumb {
  background-color: #c1c1c1;
  border-radius: 3px;
}

.steps-list::-webkit-scrollbar-thumb:hover,
.host-groups-container::-webkit-scrollbar-thumb:hover {
  background-color: #a8a8a8;
}

/* 响应式设计 */
@media (max-width: 1200px) {
  .execution-flow-container {
    flex-direction: column;
    height: auto;
    min-height: 1000px;
  }
  
  .steps-sidebar {
    width: 100%;
    height: 500px;
    border-right: none;
    border-bottom: 1px solid #e8e8e8;
  }
  
  .step-detail-panel {
    height: 800px;
  }
  
  .host-status-summary {
    flex-wrap: wrap;
    gap: 12px;
  }
  
  .status-summary-item {
    min-width: 70px;
    padding: 8px 12px;
  }
}

/* 动画效果 */
.step-item {
  animation: fadeInUp 0.3s ease-out;
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.step-detail-content {
  animation: fadeIn 0.2s ease-out;
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

/* 日志放大模态框样式 */
.log-zoom-container {
  display: flex;
  flex-direction: column;
  height: 80vh;
}

.log-zoom-header {
  display: flex;
  justify-content: flex-end;
  padding: 16px 0;
  border-bottom: 1px solid #e8e8e8;
  margin-bottom: 16px;
}

.log-zoom-content {
  flex: 1;
  overflow: auto;
  background-color: #f8f9fa;
  border: 1px solid #e8e8e8;
  border-radius: 6px;
  padding: 16px;
}

.log-zoom-text {
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 14px;
  line-height: 1.5;
  color: #333;
  white-space: pre-wrap;
  word-wrap: break-word;
  margin: 0;
  background: transparent;
}

.log-zoom-text .highlight {
  background-color: #fff3cd;
  padding: 2px 4px;
  border-radius: 3px;
}
</style>
