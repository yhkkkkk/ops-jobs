<template>
  <a-drawer
    v-model:visible="drawerVisible"
    :title="title"
    :width="width"
    :footer="false"
    placement="right"
    :mask-closable="closableOnMask"
    @close="handleClose"
  >
    <!-- 进度概览 -->
    <div class="progress-overview">
      <a-space size="large">
        <!-- 总数 -->
        <div class="progress-item">
          <div class="progress-label">总数</div>
          <div class="progress-value">{{ progress.total }}</div>
        </div>
        <!-- 成功 -->
        <div class="progress-item">
          <div class="progress-label success">成功</div>
          <div class="progress-value success">{{ progress.success_count }}</div>
        </div>
        <!-- 失败 -->
        <div class="progress-item">
          <div class="progress-label danger">失败</div>
          <div class="progress-value danger">{{ progress.failed_count }}</div>
        </div>
        <!-- 进行中 -->
        <div class="progress-item">
          <div class="progress-label warning">进行中</div>
          <div class="progress-value warning">{{ progress.completed - progress.success_count - progress.failed_count }}</div>
        </div>
      </a-space>
    </div>

    <!-- 进度条 -->
    <div class="progress-bar-section">
      <a-progress
        :percent="totalPercent"
        :status="progressBarStatus"
        :show-text="false"
        size="large"
      />
      <div class="progress-text">
        <span class="percent-text">{{ totalPercent }}%</span>
        <span class="status-text" :class="progress.status">
          {{ statusText }}
        </span>
      </div>
    </div>

    <!-- 状态消息 -->
    <a-alert
      v-if="progress.message"
      :type="alertType"
      :show-icon="true"
      class="status-message"
    >
      {{ progress.message }}
    </a-alert>

    <!-- 实时日志 -->
    <div class="log-section">
      <div class="log-header">
        <div class="log-title">
          <icon-code />
          <span>实时日志</span>
          <a-tag size="small" color="blue">{{ progress.logs.length }} 条</a-tag>
        </div>
        <a-space>
          <a-button
            size="small"
            :disabled="progress.logs.length === 0"
            @click="handleClearLogs"
          >
            <template #icon>
              <icon-delete />
            </template>
            清空
          </a-button>
          <a-button
            size="small"
            :disabled="progress.logs.length === 0"
            @click="handleExportLogs"
          >
            <template #icon>
              <icon-download />
            </template>
            导出
          </a-button>
        </a-space>
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
        <div v-if="progress.logs.length === 0" class="log-empty">
          暂无日志
        </div>
      </div>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted } from 'vue'
import {
  IconCode,
  IconDelete,
  IconDownload
} from '@arco-design/web-vue/es/icon'
import { Message } from '@arco-design/web-vue'
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
  if (status === 'failed' || status === 'error') return 'danger'
  if (status === 'running') return 'normal'
  return 'normal'
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
  Message.success('日志已清空')
}

// 导出日志
const handleExportLogs = () => {
  if (props.progress.logs.length === 0) {
    Message.warning('没有可导出的日志')
    return
  }

  const logs = props.progress.logs.map(log => {
    return `[${log.timestamp}] [${log.host_name}] ${log.content}`
  }).join('\n')

  const blob = new Blob([logs], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `progress-${Date.now()}.log`
  a.click()
  URL.revokeObjectURL(url)
  Message.success('日志导出成功')
}

// 关闭抽屉
const handleClose = () => {
  emit('close')
}
</script>

<style scoped lang="less">
.progress-overview {
  display: flex;
  justify-content: center;
  padding: 16px 0;
  background: var(--color-fill-1);
  border-radius: 4px;
  margin-bottom: 16px;
}

.progress-item {
  text-align: center;
  min-width: 80px;
}

.progress-label {
  font-size: 12px;
  color: var(--color-text-3);
  margin-bottom: 4px;

  &.success {
    color: rgb(var(--green-6));
  }

  &.danger {
    color: rgb(var(--red-6));
  }

  &.warning {
    color: rgb(var(--orange-6));
  }
}

.progress-value {
  font-size: 24px;
  font-weight: bold;
  color: var(--color-text-1);

  &.success {
    color: rgb(var(--green-6));
  }

  &.danger {
    color: rgb(var(--red-6));
  }

  &.warning {
    color: rgb(var(--orange-6));
  }
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
  color: var(--color-text-1);
}

.status-text {
  font-weight: 500;

  &.idle {
    color: var(--color-text-3);
  }

  &.running {
    color: rgb(var(--blue-6));
  }

  &.completed,
  &.success {
    color: rgb(var(--green-6));
  }

  &.failed,
  &.error {
    color: rgb(var(--red-6));
  }

  &.completed_with_errors {
    color: rgb(var(--orange-6));
  }

  &.stopped {
    color: rgb(var(--gray-6));
  }
}

.status-message {
  margin-bottom: 16px;
}

.log-section {
  border: 1px solid var(--color-border-2);
  border-radius: 4px;
  overflow: hidden;
}

.log-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: var(--color-fill-2);
  border-bottom: 1px solid var(--color-border-2);
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

  &.info {
    color: #9cdcfe;
  }

  &.success {
    color: #6a9955;
  }

  &.error {
    color: #f14c4c;
  }

  &.warning {
    color: #cca700;
  }

  &.debug {
    color: #808080;
  }

  &.auto-scrolled {
    background: rgba(255, 255, 255, 0.05);
  }
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
