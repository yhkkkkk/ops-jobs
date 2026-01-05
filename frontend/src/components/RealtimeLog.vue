<template>
  <div class="realtime-log-container">
    <!-- 顶部控制栏 -->
    <div class="control-bar">
      <div class="connection-status">
        <a-space>
          <a-tag v-if="connected" color="green">
            <template #icon><icon-check-circle /></template>
            已连接
          </a-tag>
          <a-tag v-else color="red">
            <template #icon><icon-close-circle /></template>
            未连接
          </a-tag>

          <a-button v-if="!connected" type="primary" size="small" @click="() => connect()" :loading="connecting">
            连接实时日志
          </a-button>
          <a-button v-else type="outline" size="small" @click="disconnect">
            断开连接
          </a-button>
        </a-space>
      </div>

      <div class="control-actions">
        <a-space>
          <a-button size="small" @click="clearLogs">
            <template #icon><icon-delete /></template>
            清空日志
          </a-button>

          <a-switch v-model="autoScroll" size="small">
            <template #checked>自动滚动</template>
            <template #unchecked>手动滚动</template>
          </a-switch>
        </a-space>
      </div>
    </div>

    <a-alert
      v-if="channelWarning || structureWarning"
      type="warning"
      show-icon
      class="sse-warning"
    >
      <template #message>日志通道提示</template>
      <template #description>
        <div v-if="channelWarning">
          当前日志通道已回退为 {{ channelWarning }}，可能缺少结构化字段。
        </div>
        <div v-if="structureWarning">
          部分日志缺少 {{ missingFields.join('、') || '必要' }} 字段，已按简化模式展示。
        </div>
      </template>
    </a-alert>

    <!-- 执行概览 -->
    <div v-if="status" class="log-summary">
      <a-descriptions :column="4" size="small">
        <a-descriptions-item label="总步骤数">
          {{ Object.keys(stepLogs).length }}
        </a-descriptions-item>
        <a-descriptions-item label="总主机数">
          {{ status.total_hosts }}
        </a-descriptions-item>
        <a-descriptions-item label="成功主机">
          <span style="color: #52c41a;">{{ status.success_hosts }}</span>
        </a-descriptions-item>
        <a-descriptions-item label="失败主机">
          <span style="color: #ff4d4f;">{{ status.failed_hosts }}</span>
        </a-descriptions-item>
      </a-descriptions>
    </div>

    <!-- 主体内容：渐进式布局 -->
    <div v-if="logs.length === 0" class="empty-logs">
      <a-empty description="暂无日志数据" />
    </div>

    <div v-else class="execution-flow-layout" :class="{ 'has-selected-step': selectedStepId }">
      <!-- 主容器：单栏或双栏布局 -->
      <div class="execution-flow-container">
        <!-- 左侧：时间线侧边栏 -->
        <div class="timeline-sidebar" :class="{ 'collapsed': selectedStepId }">
          <div class="vertical-timeline" ref="logContainer">
            <div
              v-for="(stepLog, stepId, index) in stepLogs"
              :key="stepId"
              class="timeline-step-item"
            >
              <!-- 时间线连接线 -->
              <div 
                v-if="index < Object.keys(stepLogs).length - 1" 
                class="timeline-connector"
                :class="getConnectorClass(stepLog.status)"
              ></div>
              
              <!-- 步骤节点 -->
              <div class="timeline-step-node">
                <!-- 左侧时间线圆点 -->
                <div class="timeline-dot" :class="`dot-${stepLog.status}`">
                  <div class="dot-inner">
                    <span class="step-number">{{ stepLog.step_order || (index + 1) }}</span>
                  </div>
                </div>
                
                <!-- 右侧步骤卡片 -->
                <div 
                  class="timeline-step-card"
                  :class="{ 
                    'step-active': selectedStepId === stepId,
                    [`step-${stepLog.status}`]: true
                  }"
                  @click="selectStep(stepId)"
                >
                  <div class="step-card-content">
                    <div class="step-title-row">
                      <h5 class="step-title">{{ stepLog.step_name }}</h5>
                      <a-tag
                        :color="getStepStatusColor(stepLog.status)"
                        size="small"
                        class="step-status-tag"
                      >
                        {{ getStepStatusText(stepLog.status) }}
                      </a-tag>
                    </div>
                    <div class="step-meta-row">
                      <span class="step-hosts">
                        <icon-user /> {{ stepLog.hostCount || 0 }} 台主机
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 右侧：日志详情面板（仅当选中步骤时显示） -->
        <div v-if="selectedStepId && stepLogs[selectedStepId]" class="logs-detail-panel">
          <div class="step-detail-content">
            <!-- 步骤信息头部 -->
            <div class="step-detail-header">
              <div class="step-detail-info">
                <h3>{{ stepLogs[selectedStepId].step_name }}</h3>
                <a-tag :color="getStepStatusColor(stepLogs[selectedStepId].status)" size="small">
                  {{ getStepStatusText(stepLogs[selectedStepId].status) }}
                </a-tag>
              </div>
            </div>

            <!-- 主机状态统计 -->
            <div class="host-status-stats">
              <div v-for="(count, status) in getHostStatusCounts(selectedStepId)" :key="status" class="status-item">
                <div class="status-circle" :class="`status-${status}`">
                  <span class="status-count">{{ count }}</span>
                </div>
                <div class="status-info">
                  <span class="status-label">{{ getHostStatusText(status) }}</span>
                </div>
              </div>
            </div>

            <!-- 主机分组显示 -->
            <div class="host-groups-container">
              <div
                v-for="(group, status) in getStepHostGroups(selectedStepId)"
                :key="status"
                class="host-group"
                v-show="group.hosts.length > 0"
              >
                <div class="host-group-header" @click.stop="toggleGroup(selectedStepId, status)">
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
                      @click.stop="toggleGroup(selectedStepId, status)"
                      title="展开/收起分组"
                    >
                      <icon-down
                        :class="{ 'rotate-180': group.expanded }"
                        class="expand-icon"
                      />
                    </a-button>
                  </div>
                </div>

                <div v-show="group.expanded" class="host-group-content">
                  <a-tabs
                    v-if="group.hosts.length > 0"
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
                          <div class="host-name">{{ hostLog.host_name }}</div>
                        </div>
                      </template>

                      <!-- 主机日志内容 -->
                      <div class="host-log-content">
                        <!-- 主机信息头部 -->
                        <div class="host-info-header">
                          <div class="host-info">
                            <h5>{{ hostLog.host_name }}</h5>
                            <a-space>
                              <a-tag :color="getHostStatusColor(hostLog.status)">
                                {{ getHostStatusText(hostLog.status) }}
                              </a-tag>
                              <span class="host-ip">{{ hostLog.host_ip }}</span>
                            </a-space>
                          </div>

                          <!-- 文件传输进度条 -->
                          <div v-if="hostLog.progress && hostLog.progress.percent > 0" class="transfer-progress">
                            <div class="progress-info">
                              <span class="progress-text">文件传输进度</span>
                              <span class="progress-stats">
                                {{ formatBytes(hostLog.progress.speed) }}/s
                                <span v-if="hostLog.progress.eta > 0">
                                  · 剩余 {{ formatTime(hostLog.progress.eta) }}
                                </span>
                              </span>
                            </div>
                            <a-progress
                              :percent="hostLog.progress.percent"
                              :color="hostLog.progress.percent === 100 ? '#52c41a' : '#1890ff'"
                              size="small"
                              :show-text="true"
                            />
                          </div>
                        </div>

                        <!-- 实时日志内容 -->
                        <div class="log-section">
                          <div class="log-section-header">
                            <h5>实时日志</h5>
                          </div>
                          <div class="log-text-container">
                            <pre class="log-text">{{ getHostLogs(selectedStepId, hostLog.host_id) }}</pre>
                          </div>
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
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { Message } from '@arco-design/web-vue'
import { IconCheckCircle, IconCloseCircle, IconDelete } from '@arco-design/web-vue/es/icon'
import { useAuthStore } from '@/stores/auth'
import { buildSseUrl } from '@/utils/env'

interface Props {
  executionId: string
  autoConnect?: boolean
}

interface LogEntry {
  timestamp: string
  host: string
  type: string
  content: string
  step?: string
  stepOrder?: number
}

interface TaskStatus {
  status: string
  progress: number
  total_hosts: number
  success_hosts: number
  failed_hosts: number
  running_hosts: number
  message: string
}

const props = withDefaults(defineProps<Props>(), {
  autoConnect: true
})

const connected = ref(false)
const connecting = ref(false)
const autoScroll = ref(true)
const logs = ref<LogEntry[]>([])
const status = ref<TaskStatus | null>(null)
const stepLogs = ref<Record<string, any>>({})
const selectedStepId = ref<string>('')
const selectedHostIds = ref<Record<string, string>>({})
const hostGroups = ref<Record<string, Record<string, any>>>({})
const expandedSteps = ref<Record<string, boolean>>({})
const logContainer = ref<HTMLElement>()
const channelWarning = ref<string | null>(null)
const structureWarning = ref(false)
const missingFields = ref<string[]>([])

// 重连相关
const reconnectAttempts = ref(0)
const maxReconnectAttempts = 5
const reconnectTimeout = ref<NodeJS.Timeout | null>(null)
const eventSource = ref<EventSource | null>(null)

const recordStructureHints = (data: any) => {
  if (!data) return
  if (data.fallback_channel || (data.channel && !['redis_stream', 'redis', 'default'].includes(data.channel))) {
    channelWarning.value = data.channel || 'fallback'
  }
  if (data.structure_missing) {
    structureWarning.value = true
    const current = new Set(missingFields.value)
    ;(data.missing_fields || []).forEach((f: string) => current.add(f))
    missingFields.value = Array.from(current)
  }
}

const connect = async (isReconnect = false) => {
  if (!props.executionId) {
    Message.error('执行ID不能为空')
    return
  }

  if (connected.value || connecting.value) {
    return
  }

  if (eventSource.value) {
    eventSource.value.close()
    eventSource.value = null
  }

  // 清理重连定时器
  if (reconnectTimeout.value) {
    clearTimeout(reconnectTimeout.value)
    reconnectTimeout.value = null
  }

  // 重置告警提示
  channelWarning.value = null
  structureWarning.value = false
  missingFields.value = []

  connecting.value = true
  
  if (isReconnect) {
    addSystemLog(`正在尝试重连... (${reconnectAttempts.value + 1}/${maxReconnectAttempts})`, 'info')
  }

  try {
    // 获取认证token
    const authStore = useAuthStore()
    const token = authStore.token

    // 获取执行ID
    const executionId = props.executionId

    // 构建SSE URL，包含token参数，使用环境变量配置的基准路径
    const sseUrl = token
      ? buildSseUrl(`combined/${executionId}/`, `token=${encodeURIComponent(token)}`)
      : buildSseUrl(`combined/${executionId}/`)

    console.log('🔗 SSE连接URL:', sseUrl)
    eventSource.value = new EventSource(sseUrl)

    eventSource.value.onopen = (event) => {
      console.log('✅ SSE连接已打开:', event)
      connected.value = true
      connecting.value = false
      reconnectAttempts.value = 0  // 重置重连计数
      addSystemLog('已连接到实时日志流')
    }

    // 处理标准message事件（包含connection_established等）
    eventSource.value.addEventListener('message', (event) => {
      console.log('📡 收到message事件:', event)
      try {
        const data = JSON.parse(event.data)
        console.log('📡 message事件数据:', data)
        recordStructureHints(data)

        if (data.type === 'connection_established') {
          addSystemLog(data.message)
        } else if (data.type === 'log') {
          // 处理日志消息
          const hostName = data.host_name || data.host_ip || '未知主机'
          const stepName = data.step_name || '未知步骤'
          const stepOrder = data.step_order || 1

          addLog({
            timestamp: data.timestamp || new Date().toISOString(),
            host: hostName,
            type: data.log_type || 'info',
            content: data.content || '',
            step: stepName,
            stepOrder: stepOrder
          })

          // 更新步骤日志结构
          updateStepLogs(stepName, stepOrder, hostName, data)
        } else if (data.type === 'status') {
          // 处理状态消息
          status.value = data

          if (data.status === 'failed') {
            addSystemLog(`任务执行失败: ${data.message || '未知错误'}`, 'error')
          } else if (data.status === 'completed') {
            addSystemLog(`任务执行完成: ${data.message || ''}`, 'info')
          }
        } else if (data.type === 'error') {
          addSystemLog(`错误: ${data.message}`, 'error')
          // 更新状态为失败
          status.value = {
            ...status.value,
            status: 'failed',
            message: data.message
          }
        } else if (data.type === 'debug') {
          // 可选：在开发环境下显示调试信息
          if (process.env.NODE_ENV === 'development') {
            addSystemLog(`[调试] ${data.message}`, 'info')
          }
        }
      } catch (e) {
        console.error('解析message事件失败:', e, event)
      }
    })

    // 保留原有的事件监听器作为备用
    eventSource.value.addEventListener('connected', (event) => {
      console.log('📡 收到connected事件:', event)
      try {
        const data = JSON.parse(event.data)
        console.log('📡 connected事件数据:', data)
        addSystemLog(data.message)
      } catch (e) {
        console.error('解析connected事件失败:', e)
        addSystemLog('连接成功')
      }
    })

    eventSource.value.addEventListener('log', (event) => {
      console.log('📝 收到log事件:', event)
      try {
        const data = JSON.parse(event.data)
        console.log('📝 log事件数据:', data)
        recordStructureHints(data)
        const hostName = data.host_name || data.host_ip || '未知主机'
        const stepName = data.step_name || '未知步骤'
        const stepOrder = data.step_order || 1

        addLog({
          timestamp: data.timestamp || new Date().toISOString(),
          host: hostName,
          type: data.log_type || 'info',
          content: data.content || '',
          step: stepName,
          stepOrder: stepOrder
        })

        // 更新步骤日志结构
        updateStepLogs(stepName, stepOrder, hostName, data)
      } catch (e) {
        console.error('解析日志数据失败:', e, event)
      }
    })

    eventSource.value.addEventListener('status', (event) => {
      try {
        const data = JSON.parse(event.data)
        status.value = data

        // 如果状态是失败，添加一条系统日志
        if (data.status === 'failed') {
          addSystemLog(`任务执行失败: ${data.message || '未知错误'}`, 'error')
        } else if (data.status === 'completed') {
          addSystemLog(`任务执行完成: ${data.message || ''}`, 'info')
        }
      } catch (e) {
        console.error('解析状态数据失败:', e)
      }
    })

    eventSource.value.addEventListener('heartbeat', (event) => {
      console.log('💓 收到heartbeat事件:', event)
      // 心跳消息，不处理
    })

    eventSource.value.addEventListener('debug', (event) => {
      try {
        const data = JSON.parse(event.data)
        console.log('[实时日志调试]', data.message)
        // 可选：在开发环境下显示调试信息
        if (process.env.NODE_ENV === 'development') {
          addSystemLog(`[调试] ${data.message}`, 'info')
        }
      } catch (e) {
        console.error('解析调试消息失败:', e)
      }
    })

    eventSource.value.addEventListener('error', (event: any) => {
      try {
        if (event.data) {
          const data = JSON.parse(event.data)
          addSystemLog(`错误: ${data.message}`, 'error')
          // 更新状态为失败
          status.value = {
            ...status.value,
            status: 'failed',
            message: data.message
          }
        } else {
          addSystemLog('服务器错误', 'error')
        }
      } catch (e) {
        addSystemLog('服务器错误或数据格式错误', 'error')
      }
    })

    eventSource.value.onerror = (event) => {
      console.error('❌ SSE连接错误:', event)
      console.error('❌ EventSource readyState:', eventSource.value?.readyState)
      connected.value = false
      connecting.value = false
      
      // 检查连接状态
      if (eventSource.value?.readyState === EventSource.CLOSED) {
        addSystemLog('连接已关闭', 'error')
        
        // 如果连接中断且当前状态不是完成状态，则尝试重连
        if (status.value?.status === 'running' && reconnectAttempts.value < maxReconnectAttempts) {
          reconnectAttempts.value++
          addSystemLog(`连接中断，将在3秒后尝试重连...`, 'warning')
          
          reconnectTimeout.value = setTimeout(() => {
            connect(true)
          }, 3000)
        } else if (reconnectAttempts.value >= maxReconnectAttempts) {
          addSystemLog('重连次数已达上限，停止重连', 'error')
          status.value = {
            ...status.value,
            status: 'failed',
            message: '连接中断，重连失败'
          }
        } else {
          addSystemLog('连接中断', 'error')
        }
      } else if (eventSource.value?.readyState === EventSource.CONNECTING) {
        addSystemLog('正在重新连接...', 'info')
      }
    }

  } catch (error) {
    connecting.value = false
    Message.error('连接失败')
    console.error('SSE连接失败:', error)
  }
}

const disconnect = () => {
  if (eventSource.value) {
    eventSource.value.close()
    eventSource.value = null
  }
  
  // 清理重连定时器
  if (reconnectTimeout.value) {
    clearTimeout(reconnectTimeout.value)
    reconnectTimeout.value = null
  }
  
  connected.value = false
  reconnectAttempts.value = 0
  addSystemLog('已断开日志连接')
}

const addLog = (log: LogEntry) => {
  logs.value.push(log)
  if (autoScroll.value) {
    nextTick(() => {
      scrollToBottom()
    })
  }
}

const updateStepLogs = (stepName: string, stepOrder: number, hostName: string, logData: any) => {
  // 对于快速执行，统一使用一个步骤ID
  const stepId = stepName === '快速执行' ? 'quick_execute' : `step_${stepOrder}_${stepName}`
  const hostKey = logData.host_id || hostName

  // 初始化步骤日志
  if (!stepLogs.value[stepId]) {
    stepLogs.value[stepId] = {
      step_name: stepName,
      step_order: stepOrder,
      status: 'running',
      hostCount: 0,
      hosts: {}
    }

    // 自动选择第一个步骤
    if (!selectedStepId.value) {
      selectedStepId.value = stepId
    }
  }

  // 初始化主机日志
  if (!stepLogs.value[stepId].hosts[hostKey]) {
    stepLogs.value[stepId].hosts[hostKey] = {
      host_id: hostKey,
      host_name: hostName,
      host_ip: logData.host_ip || hostName,
      status: 'running',
      logs: []
    }
    stepLogs.value[stepId].hostCount++
  }

  // 构建日志条目
  const logEntry: any = {
    timestamp: logData.timestamp || new Date().toISOString(),
    type: logData.log_type || 'info',
    content: logData.content || ''
  }

  // 如果包含进度信息，添加进度数据
  if (logData.progress_percent !== undefined) {
    logEntry.progress = {
      percent: logData.progress_percent,
      speed: logData.transfer_speed || 0,
      eta: logData.eta_seconds || 0,
      fileSize: logData.file_size || 0,
      transferred: logData.transferred || 0,
      localPath: logData.local_path || '',
      remotePath: logData.remote_path || ''
    }
  }

  // 添加日志到主机
  stepLogs.value[stepId].hosts[hostKey].logs.push(logEntry)

  // 更新主机状态
  const host = stepLogs.value[stepId].hosts[hostKey]
  if (logData.log_type === 'error' || logData.content?.includes('失败')) {
    host.status = 'failed'
  } else if (logData.content?.includes('完成') || logData.content?.includes('成功')) {
    host.status = 'success'
  }

  // 如果有进度信息，更新主机的进度状态
  if (logData.progress_percent !== undefined) {
    host.progress = {
      percent: logData.progress_percent,
      speed: logData.transfer_speed || 0,
      eta: logData.eta_seconds || 0
    }
  }

  // 更新步骤状态
  const hosts = Object.values(stepLogs.value[stepId].hosts)
  const failedCount = hosts.filter((h: any) => h.status === 'failed').length
  const successCount = hosts.filter((h: any) => h.status === 'success').length

  if (failedCount > 0) {
    stepLogs.value[stepId].status = 'failed'
  } else if (successCount === hosts.length) {
    stepLogs.value[stepId].status = 'success'
  } else {
    stepLogs.value[stepId].status = 'running'
  }
}

const addSystemLog = (message: string, type: string = 'info') => {
  addLog({
    timestamp: new Date().toISOString(),
    host: '系统',
    type,
    content: message
  })
}

const clearLogs = () => {
  logs.value = []
}

const scrollToBottom = () => {
  if (logContainer.value) {
    logContainer.value.scrollTop = logContainer.value.scrollHeight
  }
}

const formatTime = (timestamp: string | number) => {
  if (typeof timestamp === 'string') {
    return new Date(timestamp).toLocaleTimeString()
  } else {
    // 格式化秒数为可读时间
    const seconds = Math.floor(timestamp)
    if (seconds < 60) {
      return `${seconds}秒`
    } else if (seconds < 3600) {
      const minutes = Math.floor(seconds / 60)
      const remainingSeconds = seconds % 60
      return `${minutes}分${remainingSeconds}秒`
    } else {
      const hours = Math.floor(seconds / 3600)
      const minutes = Math.floor((seconds % 3600) / 60)
      return `${hours}小时${minutes}分钟`
    }
  }
}

const formatBytes = (bytes: number) => {
  if (bytes === 0) return '0 B'

  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))

  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}

// 选择步骤（点击步骤时切换选中状态）
const selectStep = (stepId: string) => {
  // 如果点击的是已选中的步骤，则取消选中（回到单栏布局）
  if (selectedStepId.value === stepId) {
    selectedStepId.value = ''
  } else {
    selectedStepId.value = stepId
    
    // 自动滚动到底部
    if (autoScroll.value) {
      nextTick(() => {
        scrollToBottom()
      })
    }
  }
}

// 切换步骤展开/收起（保留兼容性，但不再使用）
const toggleStep = (stepId: string) => {
  selectStep(stepId)
}

const getConnectorClass = (status: string) => {
  switch (status) {
    case 'success': return 'connector-success'
    case 'failed': return 'connector-failed'
    case 'running': return 'connector-running'
    default: return 'connector-pending'
  }
}

const getStepStatusColor = (status: string) => {
  switch (status) {
    case 'pending': return 'gray'
    case 'running': return 'blue'
    case 'success': return 'green'
    case 'failed': return 'red'
    default: return 'gray'
  }
}

const getStepStatusText = (status: string) => {
  switch (status) {
    case 'pending': return '等待中'
    case 'running': return '执行中'
    case 'success': return '成功'
    case 'failed': return '失败'
    default: return '未知'
  }
}

const getHostStatusColor = (status: string) => {
  switch (status) {
    case 'waiting': return 'gray'
    case 'running': return 'blue'
    case 'success': return 'green'
    case 'failed': return 'red'
    default: return 'gray'
  }
}

const getHostStatusText = (status: string) => {
  switch (status) {
    case 'waiting': return '等待中'
    case 'running': return '执行中'
    case 'success': return '成功'
    case 'failed': return '失败'
    default: return '未知'
  }
}

const getHostStatusCounts = (stepId: string) => {
  if (!stepLogs.value[stepId]) return {}

  const hosts = Object.values(stepLogs.value[stepId].hosts)
  const counts: Record<string, number> = {}

  hosts.forEach((host: any) => {
    counts[host.status] = (counts[host.status] || 0) + 1
  })

  return counts
}

const getStepHostGroups = (stepId: string) => {
  if (!stepLogs.value[stepId]) return {}

  const hosts = Object.values(stepLogs.value[stepId].hosts)
  const groups: Record<string, any> = {}

  hosts.forEach((host: any) => {
    if (!groups[host.status]) {
      groups[host.status] = {
        hosts: [],
        expanded: true
      }
    }
    groups[host.status].hosts.push(host)
  })

  return groups
}

const toggleGroup = (stepId: string, status: string) => {
  if (!hostGroups.value[stepId]) {
    hostGroups.value[stepId] = {}
  }
  if (!hostGroups.value[stepId][status]) {
    hostGroups.value[stepId][status] = { expanded: true }
  }
  hostGroups.value[stepId][status].expanded = !hostGroups.value[stepId][status].expanded
}

const getHostLogs = (stepId: string, hostId: string) => {
  if (!stepLogs.value[stepId] || !stepLogs.value[stepId].hosts[hostId]) {
    return ''
  }

  return stepLogs.value[stepId].hosts[hostId].logs
    .map((log: any) => `[${formatTime(log.timestamp)}] ${log.content}`)
    .join('\n')
}


// 监听 autoScroll 变化
watch(autoScroll, (newVal) => {
  if (newVal) {
    nextTick(() => {
      scrollToBottom()
    })
  }
})

onMounted(() => {
  if (props.autoConnect) {
    connect()
  }
})

onUnmounted(() => {
  disconnect()
})
</script>

<style scoped>
.realtime-log-container {
  display: flex;
  flex-direction: column;
  height: 700px;
  border: 1px solid #e8e8e8;
  border-radius: 6px;
}

.control-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid #e8e8e8;
  background-color: #fafafa;
}

.connection-status {
  flex: 1;
}

.control-actions {
  flex: 1;
  display: flex;
  justify-content: flex-end;
}

.log-summary {
  padding: 16px;
  border-bottom: 1px solid #e8e8e8;
  background-color: #f9f9f9;
}

.empty-logs {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 400px;
  color: #999;
}

/* 执行流程布局 */
.execution-flow-layout {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* 主容器：单栏或双栏布局 */
.execution-flow-container {
  flex: 1;
  display: flex;
  flex-direction: row;
  overflow: hidden;
}

/* 左侧：时间线侧边栏 */
.timeline-sidebar {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  transition: all 0.3s ease;
  border-right: 1px solid #e8e8e8;
}

/* 当选中步骤时，左侧时间线收缩 */
.timeline-sidebar.collapsed {
  flex: 0 0 350px;
  min-width: 350px;
  max-width: 350px;
}

/* 右侧：日志详情面板 */
.logs-detail-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  background-color: #fff;
  overflow: hidden;
}

/* 垂直时间线主体 */
.vertical-timeline {
  flex: 1;
  padding: 24px 40px;
  overflow-y: auto;
  background-color: #fafafa;
}

.timeline-step-item {
  position: relative;
  display: flex;
  margin-bottom: 24px;
}

.timeline-step-item:last-child {
  margin-bottom: 0;
}

/* 时间线连接线 */
.timeline-connector {
  position: absolute;
  left: 20px;
  top: 40px; /* 从圆点底部开始（圆点高度40px） */
  width: 2px;
  height: calc(100% - 40px + 24px); /* 覆盖整个步骤项高度 + margin-bottom间距 */
  background-color: #e8e8e8;
  z-index: 0;
}

.timeline-connector.connector-success {
  background: linear-gradient(180deg, #52c41a 0%, #73d13d 100%);
}

.timeline-connector.connector-failed {
  background: linear-gradient(180deg, #ff4d4f 0%, #ff7875 100%);
  border-style: dashed;
}

.timeline-connector.connector-running {
  background: linear-gradient(180deg, #1890ff 0%, #40a9ff 100%);
  animation: flowAnimation 2s infinite;
}

.timeline-connector.connector-pending {
  background-color: #e8e8e8;
}

@keyframes flowAnimation {
  0% {
    background-position: 0% 50%;
  }
  50% {
    background-position: 100% 50%;
  }
  100% {
    background-position: 0% 50%;
  }
}

/* 时间线节点容器 */
.timeline-step-node {
  position: relative;
  display: flex;
  width: 100%;
  z-index: 1;
}

/* 时间线圆点 */
.timeline-dot {
  position: absolute;
  left: 0;
  top: 0;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  border: 3px solid;
  background-color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.timeline-dot.dot-success {
  border-color: #52c41a;
  background: linear-gradient(135deg, #f6ffed 0%, #ffffff 100%);
}

.timeline-dot.dot-failed {
  border-color: #ff4d4f;
  background: linear-gradient(135deg, #fff2f0 0%, #ffffff 100%);
}

.timeline-dot.dot-running {
  border-color: #1890ff;
  background: linear-gradient(135deg, #e6f7ff 0%, #ffffff 100%);
  animation: dotPulse 2s infinite;
}

.timeline-dot.dot-pending {
  border-color: #d9d9d9;
  background: linear-gradient(135deg, #f5f5f5 0%, #ffffff 100%);
}

@keyframes dotPulse {
  0%, 100% {
    box-shadow: 0 0 0 0 rgba(24, 144, 255, 0.4);
  }
  50% {
    box-shadow: 0 0 0 8px rgba(24, 144, 255, 0);
  }
}

.dot-inner {
  display: flex;
  align-items: center;
  justify-content: center;
}

.step-number {
  font-size: 14px;
  font-weight: 700;
  color: #262626;
}

.timeline-dot.dot-success .step-number {
  color: #52c41a;
}

.timeline-dot.dot-failed .step-number {
  color: #ff4d4f;
}

.timeline-dot.dot-running .step-number {
  color: #1890ff;
}

.timeline-dot.dot-pending .step-number {
  color: #666;
}

/* 步骤卡片 */
.timeline-step-card {
  margin-left: 60px;
  width: calc(100% - 60px);
  background: #ffffff;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
  overflow: hidden;
}

.timeline-step-card:hover {
  border-color: #40a9ff;
  box-shadow: 0 4px 12px rgba(64, 169, 255, 0.15);
}

.timeline-step-card.step-active {
  border-color: #1890ff;
  box-shadow: 0 4px 16px rgba(24, 144, 255, 0.2);
}

.timeline-step-card.step-expanded {
  border-color: #1890ff;
  box-shadow: 0 4px 16px rgba(24, 144, 255, 0.2);
}

.timeline-step-card.step-success {
  border-left: 3px solid #52c41a;
}

.timeline-step-card.step-failed {
  border-left: 3px solid #ff4d4f;
}

.timeline-step-card.step-running {
  border-left: 3px solid #1890ff;
}

.timeline-step-card.step-pending {
  border-left: 3px solid #d9d9d9;
}

.step-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  background-color: #fff;
}

.step-card-content {
  flex: 1;
}

.step-title-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.step-title {
  font-size: 16px;
  font-weight: 600;
  color: #262626;
  margin: 0;
  flex: 1;
}

.step-status-tag {
  font-weight: 500;
  border-radius: 4px;
}

.step-meta-row {
  display: flex;
  align-items: center;
  gap: 16px;
  font-size: 13px;
  color: #666;
}

.step-hosts {
  display: flex;
  align-items: center;
  gap: 4px;
}

.step-card-arrow {
  color: #999;
  transition: transform 0.3s ease;
}

.step-card-arrow .rotate-180 {
  transform: rotate(180deg);
}

/* 步骤详情内容 */
.step-detail-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background-color: #fff;
}

.step-detail-header {
  padding: 16px 20px;
  border-bottom: 1px solid #e8e8e8;
  background-color: white;
  flex-shrink: 0;
}

.step-detail-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.step-detail-info h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}

.host-status-stats {
  display: flex;
  gap: 16px;
  padding: 16px;
  border-bottom: 1px solid #e8e8e8;
  background-color: #f9f9f9;
}

.status-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-circle {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  color: white;
}

.status-circle.status-success {
  background-color: #52c41a;
}

.status-circle.status-failed {
  background-color: #ff4d4f;
}

.status-circle.status-running {
  background-color: #1890ff;
}

.status-circle.status-waiting {
  background-color: #d9d9d9;
}

.status-info {
  display: flex;
  flex-direction: column;
}

.status-label {
  font-size: 12px;
  color: #666;
}

.host-groups-container {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 16px;
  min-height: 0;
  max-width: 100%;
}

.host-group {
  margin-bottom: 16px;
  border: 1px solid #e8e8e8;
  border-radius: 6px;
  background-color: white;
}

.host-group-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background-color: #fafafa;
  border-bottom: 1px solid #e8e8e8;
  cursor: pointer;
}

.group-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.group-count {
  font-size: 14px;
  color: #666;
}

.group-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.expand-icon {
  transition: transform 0.3s;
}

.expand-icon.rotate-180 {
  transform: rotate(180deg);
}

.host-group-content {
  padding: 16px;
}

.host-tabs {
  background-color: white;
}

.host-tab-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.host-name {
  font-weight: 500;
  font-size: 13px;
}

.host-log-content {
  padding: 16px 0;
}

.host-info-header {
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid #e8e8e8;
}

.transfer-progress {
  margin-top: 12px;
}

.progress-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  font-size: 12px;
}

.progress-text {
  font-weight: 500;
  color: #333;
}

.progress-stats {
  color: #666;
  font-family: monospace;
}

.host-info h5 {
  margin: 0 0 8px 0;
  font-size: 16px;
}

.host-ip {
  font-family: monospace;
  font-size: 12px;
  color: #666;
}

.log-section {
  margin-bottom: 16px;
}

.log-section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.log-section-header h5 {
  margin: 0;
  font-size: 14px;
  color: #333;
}

.log-text-container {
  border: 1px solid #e8e8e8;
  border-radius: 4px;
  background-color: #1e1e1e;
  max-height: 400px;
  overflow-y: auto;
  overflow-x: auto;
}

.log-text-container::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

.log-text-container::-webkit-scrollbar-track {
  background-color: #2d2d2d;
  border-radius: 4px;
}

.log-text-container::-webkit-scrollbar-thumb {
  background-color: #555;
  border-radius: 4px;
}

.log-text-container::-webkit-scrollbar-thumb:hover {
  background-color: #777;
}

.log-text {
  margin: 0;
  padding: 12px;
  font-family: 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.4;
  color: #d4d4d4;
  white-space: pre-wrap;
  word-wrap: break-word;
  background-color: #1e1e1e;
}

.task-status {
  padding: 12px 16px;
  border-bottom: 1px solid #e8e8e8;
  background-color: #f9f9f9;
}

.status-message {
  margin-top: 8px;
}

.log-content {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
  background-color: #1e1e1e;
  color: #d4d4d4;
  font-family: 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.4;
}

.empty-logs {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #999;
}

.log-entry {
  margin-bottom: 2px;
  padding: 2px 0;
  word-wrap: break-word;
}

.timestamp {
  color: #808080;
  margin-right: 8px;
  font-size: 12px;
}

.host-info {
  color: #569cd6;
  font-weight: bold;
  margin-right: 8px;
  font-size: 12px;
}

.step-info {
  color: #ce9178;
  font-weight: bold;
  margin-right: 8px;
  font-size: 12px;
}

.log-content-text {
  white-space: pre-wrap;
}

/* 分组视图样式 */
.host-grouped-view, .step-grouped-view {
  padding: 8px;
}

.host-group, .step-group {
  margin-bottom: 16px;
  border: 1px solid #333;
  border-radius: 4px;
  background-color: #2d2d2d;
}

.host-group-header, .step-group-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background-color: #3c3c3c;
  border-bottom: 1px solid #333;
}

.host-group-header h4, .step-group-header h4 {
  margin: 0;
  color: #d4d4d4;
  font-size: 14px;
}

.host-group-logs, .step-group-logs {
  padding: 8px 12px;
  max-height: 300px;
  overflow-y: auto;
}

/* 不同类型日志的颜色 */
.log-info .log-content-text {
  color: #4ec9b0;
}

.log-stdout .log-content-text {
  color: #d4d4d4;
}

.log-stderr .log-content-text {
  color: #f44747;
}

.log-error .log-content-text {
  color: #f44747;
}

.log-warning .log-content-text {
  color: #ffcc02;
}

.log-success .log-content-text {
  color: #4ec9b0;
}

.sse-warning {
  margin: 12px 0;
}
</style>
