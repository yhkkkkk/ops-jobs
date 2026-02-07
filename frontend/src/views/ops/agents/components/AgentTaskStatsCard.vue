<template>
  <a-card class="task-stats-card" :bordered="false">
    <div class="stats-header">
      <span class="stats-title">任务执行统计</span>
      <a-tag v-if="healthStatus" :color="healthStatusColor">{{ healthStatusText }}</a-tag>
    </div>

    <div class="stats-content">
      <!-- 成功率进度环 -->
      <div class="progress-section">
        <a-progress
          type="circle"
          :percent="successRate"
          :stroke-color="progressColor"
          :width="100"
          :format="() => `${successRate.toFixed(1)}%`"
        >
          <template #icon>
            <icon-check-circle :style="{ color: progressColor }" />
          </template>
        </a-progress>
        <div class="progress-label">成功率</div>
      </div>

      <!-- 统计数字 -->
      <div class="stats-numbers">
        <div class="stat-item">
          <div class="stat-value total">{{ stats.total || 0 }}</div>
          <div class="stat-label">总任务</div>
        </div>
        <div class="stat-item">
          <div class="stat-value success">{{ stats.success || 0 }}</div>
          <div class="stat-label">成功</div>
        </div>
        <div class="stat-item">
          <div class="stat-value failed">{{ stats.failed || 0 }}</div>
          <div class="stat-label">失败</div>
        </div>
        <div class="stat-item">
          <div class="stat-value cancelled">{{ stats.cancelled || 0 }}</div>
          <div class="stat-label">取消</div>
        </div>
      </div>
    </div>

    <!-- 平均执行时长 -->
    <div class="stats-footer">
      <div class="avg-duration">
        <icon-clock-circle />
        <span>平均执行时长: <strong>{{ formatDuration(stats.avg_duration_ms) }}</strong></span>
      </div>
      <div class="last-updated" v-if="stats.last_updated">
        更新于: {{ formatTime(stats.last_updated) }}
      </div>
    </div>
  </a-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { IconCheckCircle, IconClockCircle } from '@arco-design/web-vue/es/icon'

const props = defineProps<{
  stats: {
    total?: number
    success?: number
    failed?: number
    cancelled?: number
    avg_duration_ms?: number
    success_rate?: number
    health_status?: string
    last_updated?: string
  }
}>()

// 计算成功率
const successRate = computed(() => {
  if (!props.stats?.success_rate && props.stats?.success_rate !== 0) {
    const total = props.stats?.total || 0
    const success = props.stats?.success || 0
    return total > 0 ? (success / total) * 100 : 0
  }
  return props.stats.success_rate
})

// 健康状态
const healthStatus = computed(() => props.stats?.health_status)

const healthStatusColor = computed(() => {
  const status = healthStatus.value
  if (status === 'healthy') return 'green'
  if (status === 'warning') return 'orange'
  if (status === 'critical') return 'red'
  return 'gray'
})

const healthStatusText = computed(() => {
  const status = healthStatus.value
  const texts: Record<string, string> = {
    healthy: '健康',
    warning: '警告',
    critical: '危险',
    unknown: '未知'
  }
  return texts[status] || '未知'
})

// 进度环颜色
const progressColor = computed(() => {
  const rate = successRate.value
  if (rate >= 95) return '#0fbf60'
  if (rate >= 80) return '#ffb940'
  return '#f53f3f'
})

// 格式化时长
const formatDuration = (ms?: number) => {
  if (!ms) return '0ms'
  if (ms < 1000) return `${ms.toFixed(0)}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  return `${(ms / 60000).toFixed(1)}m`
}

// 格式化时间
const formatTime = (timeStr?: string) => {
  if (!timeStr) return '-'
  try {
    const date = new Date(timeStr)
    const now = new Date()
    const diff = now.getTime() - date.getTime()
    
    // 小于5分钟显示"刚刚"
    if (diff < 5 * 60 * 1000) return '刚刚'
    
    // 小于1小时显示"xx分钟前"
    if (diff < 60 * 60 * 1000) return `${Math.floor(diff / 60000)}分钟前`
    
    // 小于24小时显示"xx小时前"
    if (diff < 24 * 60 * 60 * 1000) return `${Math.floor(diff / 3600000)}小时前`
    
    // 其他显示日期
    return date.toLocaleDateString('zh-CN')
  } catch {
    return timeStr
  }
}
</script>

<style scoped lang="less">
.task-stats-card {
  border-radius: 6px;
  
  .stats-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
    
    .stats-title {
      font-size: 16px;
      font-weight: 600;
      color: var(--color-text-1);
    }
  }
  
  .stats-content {
    display: flex;
    align-items: center;
    gap: 32px;
    
    .progress-section {
      text-align: center;
      
      .progress-label {
        margin-top: 8px;
        font-size: 13px;
        color: var(--color-text-3);
      }
    }
    
    .stats-numbers {
      flex: 1;
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 16px;
      
      .stat-item {
        text-align: center;
        
        .stat-value {
          font-size: 24px;
          font-weight: 600;
          line-height: 1.2;
          
          &.total { color: var(--color-text-1); }
          &.success { color: #0fbf60; }
          &.failed { color: #f53f3f; }
          &.cancelled { color: #ffb940; }
        }
        
        .stat-label {
          margin-top: 4px;
          font-size: 12px;
          color: var(--color-text-3);
        }
      }
    }
  }
  
  .stats-footer {
    margin-top: 16px;
    padding-top: 16px;
    border-top: 1px solid var(--color-border-2);
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 13px;
    color: var(--color-text-3);
    
    .avg-duration {
      display: flex;
      align-items: center;
      gap: 6px;
      
      strong {
        color: var(--color-text-1);
      }
    }
    
    .last-updated {
      color: var(--color-text-4);
    }
  }
}
</style>
