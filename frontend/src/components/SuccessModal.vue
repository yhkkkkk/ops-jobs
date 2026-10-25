<template>
  <n-modal
    v-model:show="visible"
    preset="card"
    :title="title"
    :style="{ width: '500px' }"
    :closable="false"
    :mask-closable="false"
    :close-on-esc="false"
    class="success-modal"
  >
    <div class="success-content">
      <!-- 成功图标 -->
      <div class="success-icon">
        <CheckCircle2 :size="64" style="color: #16a34a" />
      </div>

      <!-- 成功消息 -->
      <div class="success-message">
        <h3>{{ message }}</h3>
        <p v-if="description" class="description">{{ description }}</p>
      </div>

      <!-- 操作按钮 -->
      <div class="action-buttons">
        <n-space vertical :size="12" style="width: 100%">
          <n-button
            v-for="action in actions"
            :key="action.key"
            v-bind="buttonProps(action)"
            @click="handleAction(action)"
          >
            <template v-if="action.icon" #icon>
              <component :is="action.icon" />
            </template>
            {{ action.label }}
          </n-button>
        </n-space>
      </div>
    </div>
  </n-modal>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { NButton, NModal, NSpace } from 'naive-ui'
import { CheckCircle2 } from 'lucide-vue-next'

interface Action {
  key: string
  label: string
  type?: 'primary' | 'secondary' | 'outline' | 'dashed' | 'text'
  status?: 'normal' | 'warning' | 'success' | 'danger'
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

// 兼容旧的 action.type/status 语义，映射到 Naive UI 按钮属性
const buttonProps = (action: Action) => {
  const legacyType = action.type || 'outline'
  const naiveType = action.status === 'danger'
    ? 'error'
    : action.status === 'warning'
      ? 'warning'
      : action.status === 'success'
        ? 'success'
        : legacyType === 'primary'
          ? 'primary'
          : 'default'
  return {
    type: naiveType,
    secondary: legacyType !== 'primary' && legacyType !== 'text',
    text: legacyType === 'text',
    dashed: legacyType === 'dashed',
    block: true,
    size: 'large',
    loading: action.loading,
  } as const
}

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
  color: var(--app-fg);
}

.success-message .description {
  margin: 0;
  color: var(--app-muted);
  font-size: 14px;
  line-height: 1.5;
}

.action-buttons {
  max-width: 300px;
  margin: 0 auto;
}

.success-modal :deep(.n-button) {
  height: 44px;
  font-size: 14px;
  font-weight: 500;
}
</style>
