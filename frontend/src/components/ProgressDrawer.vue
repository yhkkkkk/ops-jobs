<template>
  <n-drawer
    v-model:show="drawerVisible"
    :width="width"
    :mask-closable="closableOnMask"
    @after-leave="handleClose"
  >
    <n-drawer-content :title="title" :body-content-style="{ padding: '20px' }">
      <!-- 进度概览 -->
      <div class="progress-overview">
        <n-space :size="32">
          <div class="progress-item">
            <div class="progress-label">总数</div>
            <div class="progress-value">{{ progress.total }}</div>
          </div>
          <div class="progress-item">
            <div class="progress-label success">成功</div>
            <div class="progress-value success">{{ progress.success_count }}</div>
          </div>
          <div class="progress-item">
            <div class="progress-label danger">失败</div>
            <div class="progress-value danger">{{ progress.failed_count }}</div>
          </div>
          <div class="progress-item">
            <div class="progress-label warning">进行中</div>
            <div class="progress-value warning">{{ progress.completed - progress.success_count - progress.failed_count }}</div>
          </div>
        </n-space>
      </div>

      <!-- 进度条 -->
      <div class="progress-bar-section">
        <n-progress
          type="line"
          :percentage="totalPercent"
          :status="progressBarStatus"
          :show-indicator="false"
          :height="12"
        />
        <div class="progress-text">
          <span class="percent-text">{{ totalPercent }}%</span>
          <span class="status-text" :class="progress.status">
            {{ statusText }}
          </span>
        </div>
      </div>

      <!-- 状态消息 -->
      <n-alert
        v-if="progress.message"
        :type="alertType"
        :show-icon="true"
        class="status-message"
      >
        {{ progress.message }}
      </n-alert>

      <!-- 实时日志 -->
      <div class="log-section">
        <div class="log-header">
          <div class="log-title">
            <Code2 :size="15" />
            <span>实时日志</span>
            <n-tag size="small" type="info">{{ progress.logs.length }} 条</n-tag>
          </div>
          <n-space :size="8">
            <n-button size="small" :disabled="progress.logs.length === 0" @click="handleClearLogs">
              <template #icon><Trash2 :size="14" /></template>
              清空
            </n-button>
            <n-button size="small" :disabled="progress.logs.length === 0" @click="handleExportLogs">
              <template #icon><Download :size="14" /></template>
              导出
            </n-button>
          </n-space>
        </div>

        <!-- 日志容器 -->
        <div ref="logContainerRef" class="log-container">
          <div
            v-for="(log, index) in progress.logs"
            :key="index"
            class="log-item"
            :class="[log.log_type, { 'auto-scrolled': autoScrolled }]"
          >
            <span class="log-time">{{ formatTime(log.timestamp) }}</span>
            <span class="log-host" v-if="log.host_name">[{{ log.host_name }}]</span>
            <span class="log-content">{{ log.content }}</span>
          </div>
          <div v-if="progress.logs.length === 0" class="log-empty">暂无日志</div>
        </div>
      </div>
    </n-drawer-content>
  </n-drawer>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted } from 'vue'
import {
  NAlert,
  NButton,
  NDrawer,
  NDrawerContent,
  NProgress,
  NSpace,
  NTag,
  useMessage
} from 'naive-ui'
import { Code2, Download, Trash2 } from 'lucide-vue-next'
import type { ProgressState, ProgressLog } from '@/composables/useSSEProgress'
import { formatTime } from '@/utils/date'

// Props
interface Props {
  /** 抽屉是否可见 */
  visible: boolean
  /** 标题 */
  title: string
  /** 宽度 */
  width?: number | string
  /** 进度状态 */
  progress: ProgressState
  /** 点击遮罩层是否可关闭 */
  closableOnMask?: boolean
  /** 是否自动滚动到底部 */
  autoScroll?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  width: 700,
  closableOnMask: false,
  autoScroll: true
})

// Emits
const emit = defineEmits<{
  (e: 'update:visible', visible: boolean): void
  (e: 'close'): void
}>()

const message = useMessage()

// 抽屉可见性
const drawerVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val)
})

// 日志容器 ref
const logContainerRef = ref<HTMLElement | null>(null)
const autoScrolled = ref(true)

// 计算属性
const totalPercent = computed(() => {
  if (props.progress.total === 0) return 0
  return Math.round((props.progress.completed / props.progress.total) * 100)
})

const progressBarStatus = computed(() => {
  const status = props.progress.status.toLowerCase()
  if (status === 'completed' || status === 'success') return 'success'
  if (status === 'failed' || status === 'error') return 'error'
  return 'default'
})

const statusText = computed(() => {
  const statusMap: Record<string, string> = {
    idle: '等待开始',
    running: '执行中',
    completed: '已完成',
    completed_with_errors: '部分失败',
    failed: '失败',
    success: '成功',
    error: '错误',
    stopped: '已停止'
  }
  return statusMap[props.progress.status.toLowerCase()] || props.progress.status
})

const alertType = computed(() => {
  const status = props.progress.status.toLowerCase()
  if (status === 'error' || status === 'failed') return 'error'
  if (status === 'completed_with_errors') return 'warning'
  if (status === 'success' || status === 'completed') return 'success'
  return 'info'
})

// 自动滚动到底部
const scrollToBottom = () => {
  if (props.autoScroll && logContainerRef.value) {
    logContainerRef.value.scrollTop = logContainerRef.value.scrollHeight
    autoScrolled.value = true
  }
}

// 监听日志变化，自动滚动
watch(
  () => props.progress.logs.length,
  () => {
    nextTick(() => {
      scrollToBottom()
    })
  }
)

// 监听滚动，手动滚动时取消自动滚动
const handleScroll = () => {
  if (logContainerRef.value) {
    const { scrollTop, scrollHeight, clientHeight } = logContainerRef.value
    // 如果滚动到底部，启用自动滚动
    if (scrollTop + clientHeight >= scrollHeight - 10) {
      autoScrolled.value = true
    } else {
      autoScrolled.value = false
    }
  }
}

onMounted(() => {
  if (logContainerRef.value) {
    logContainerRef.value.addEventListener('scroll', handleScroll)
  }
})

// 清空日志
const handleClearLogs = () => {
  props.progress.logs = []
  message.success('日志已清空')
}

// 导出日志
const handleExportLogs = () => {
  if (props.progress.logs.length === 0) {
    message.warning('没有可导出的日志')
    return
  }

  const logs = props.progress.logs.map(log => {
    return `[${log.timestamp}] [${log.host_name}] ${log.content}`
  }).join('\n')

  const blob = new Blob([logs], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `progress-${Date.now()}.log`
  link.click()
  URL.revokeObjectURL(url)
  message.success('日志导出成功')
}

// 关闭抽屉
const handleClose = () => {
  emit('close')
}
</script>

<style scoped>
.progress-overview {
  display: flex;
  justify-content: center;
  padding: 16px 0;
  background: var(--app-surface-muted);
  border-radius: 4px;
  margin-bottom: 16px;
}

.progress-item {
  text-align: center;
  min-width: 80px;
}

.progress-label {
  font-size: 12px;
  color: var(--app-muted);
  margin-bottom: 4px;
}

.progress-label.success,
.progress-value.success {
  color: #16a34a;
}

.progress-label.danger,
.progress-value.danger {
  color: #dc2626;
}

.progress-label.warning,
.progress-value.warning {
  color: #d97706;
}

.progress-value {
  font-size: 24px;
  font-weight: bold;
  color: var(--app-fg);
}

.progress-bar-section {
  margin-bottom: 16px;
}

.progress-text {
  display: flex;
  justify-content: space-between;
  margin-top: 8px;
  font-size: 14px;
}

.percent-text {
  font-weight: bold;
  color: var(--app-fg);
}

.status-text {
  font-weight: 500;
  color: var(--app-muted);
}

.status-text.running {
  color: #2f6feb;
}

.status-text.completed,
.status-text.success {
  color: #16a34a;
}

.status-text.failed,
.status-text.error {
  color: #dc2626;
}

.status-text.completed_with_errors {
  color: #d97706;
}

.status-text.stopped {
  color: #6b7280;
}

.status-message {
  margin-bottom: 16px;
}

.log-section {
  border: 1px solid var(--app-border);
  border-radius: 4px;
  overflow: hidden;
}

.log-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: var(--app-surface-soft);
  border-bottom: 1px solid var(--app-border);
}

.log-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 500;
}

.log-container {
  max-height: 400px;
  overflow-y: auto;
  background: #1e1e1e;
  padding: 8px 12px;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 12px;
  line-height: 1.6;
}

.log-item {
  padding: 2px 0;
  color: #d4d4d4;
}

.log-item.info {
  color: #9cdcfe;
}

.log-item.success {
  color: #6a9955;
}

.log-item.error {
  color: #f14c4c;
}

.log-item.warning {
  color: #cca700;
}

.log-item.debug {
  color: #808080;
}

.log-item.auto-scrolled {
  background: rgba(255, 255, 255, 0.05);
}

.log-time {
  color: #569cd6;
  margin-right: 8px;
}

.log-host {
  color: #ce9178;
  margin-right: 8px;
}

.log-content {
  color: #d4d4d4;
  white-space: pre-wrap;
  word-break: break-all;
}

.log-empty {
  color: #808080;
  text-align: center;
  padding: 20px 0;
}
</style>
