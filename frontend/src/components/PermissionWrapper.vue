<template>
  <div v-if="hasPermission">
    <slot />
  </div>
  <div v-else-if="fallback" class="permission-fallback">
    <slot name="fallback">
      <a-result
        status="403"
        title="权限不足"
        sub-title="您没有权限访问此内容"
      >
        <template #extra>
          <a-button type="primary" @click="handleRequestPermission">
            申请权限
          </a-button>
        </template>
      </a-result>
    </slot>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { usePermission } from '@/utils/permissions'
import type { PermissionLevel, ResourceType } from '@/types'

interface Props {
  resourceType: ResourceType
  permission: PermissionLevel
  resourceId?: number
  fallback?: boolean // 是否显示权限不足的提示
}

interface Emits {
  (e: 'permission-denied'): void
  (e: 'request-permission'): void
}

const props = withDefaults(defineProps<Props>(), {
  fallback: false
})

const emit = defineEmits<Emits>()

// 使用权限检查组合函数
const { has, check, loading } = usePermission(
  props.resourceType,
  props.permission,
  props.resourceId
)

// 计算是否显示内容
const hasPermission = computed(() => {
  return has.value
})

// 组件挂载时检查权限
onMounted(async () => {
  if (!has.value) {
    await check()
  }
})

// 处理申请权限
const handleRequestPermission = () => {
  emit('request-permission')
}
</script>

<style scoped>
.permission-fallback {
  padding: 20px;
  text-align: center;
}
</style>
