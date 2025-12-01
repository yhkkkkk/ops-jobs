<template>
  <a-modal
    v-model:visible="visible"
    :title="title"
    :width="500"
    :footer="false"
    :closable="false"
    :mask-closable="false"
    class="success-modal"
  >
    <div class="success-content">
      <!-- 成功图标 -->
      <div class="success-icon">
        <icon-check-circle-fill :size="64" style="color: #00b42a" />
      </div>
      
      <!-- 成功消息 -->
      <div class="success-message">
        <h3>{{ message }}</h3>
        <p v-if="description" class="description">{{ description }}</p>
      </div>
      
      <!-- 操作按钮 -->
      <div class="action-buttons">
        <a-space direction="vertical" :size="12" style="width: 100%">
          <a-button
            v-for="action in actions"
            :key="action.key"
            :type="action.type || 'outline'"
            :status="action.status"
            :size="action.size || 'large'"
            :loading="action.loading"
            block
            @click="handleAction(action)"
          >
            <template #icon v-if="action.icon">
              <component :is="action.icon" />
            </template>
            {{ action.label }}
          </a-button>
        </a-space>
      </div>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { IconCheckCircleFill } from '@arco-design/web-vue/es/icon'

interface Action {
  key: string
  label: string
  type?: 'primary' | 'secondary' | 'outline' | 'dashed' | 'text'
  status?: 'normal' | 'warning' | 'success' | 'danger'
  size?: 'mini' | 'small' | 'medium' | 'large'
  icon?: any
  loading?: boolean
  handler?: () => void | Promise<void>
}

interface Props {
  modelValue?: boolean
  title?: string
  message: string
  description?: string
  actions?: Action[]
}

interface Emits {
  (e: 'update:modelValue', value: boolean): void
  (e: 'action', action: Action): void
}

const props = withDefaults(defineProps<Props>(), {
  modelValue: false,
  title: '操作成功',
  actions: () => []
})

const emit = defineEmits<Emits>()

const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})

const handleAction = async (action: Action) => {
  if (action.handler) {
    try {
      await action.handler()
    } catch (error) {
      console.error('Action handler error:', error)
    }
  }
  
  emit('action', action)
  
  // 如果是关闭类型的操作，自动关闭弹窗
  if (action.key === 'close' || action.key === 'cancel') {
    visible.value = false
  }
}
</script>

<style scoped>
.success-modal :deep(.arco-modal-header) {
  text-align: center;
  border-bottom: none;
  padding-bottom: 0;
}

.success-content {
  text-align: center;
  padding: 20px 0;
}

.success-icon {
  margin-bottom: 20px;
}

.success-message {
  margin-bottom: 30px;
}

.success-message h3 {
  margin: 0 0 8px 0;
  font-size: 18px;
  font-weight: 600;
  color: #1d2129;
}

.success-message .description {
  margin: 0;
  color: #86909c;
  font-size: 14px;
  line-height: 1.5;
}

.action-buttons {
  max-width: 300px;
  margin: 0 auto;
}

.success-modal :deep(.arco-btn) {
  height: 44px;
  font-size: 14px;
  font-weight: 500;
}
</style>
