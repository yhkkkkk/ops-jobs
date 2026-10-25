<template>
  <n-button
    v-if="hasPermission"
    :loading="loading"
    @click="handleClick"
  >
    <slot />
  </n-button>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { NButton } from 'naive-ui'
import { usePermission } from '@/utils/permissions'
import type { PermissionLevel, ResourceType } from '@/types'

interface Props {
  resourceType: ResourceType
  permission: PermissionLevel
  resourceId?: number
  fallback?: boolean // 是否在无权限时显示禁用状态
}

interface Emits {
  (e: 'click', event: MouseEvent): void
  (e: 'permission-denied'): void
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

// 计算是否显示按钮
const hasPermission = computed(() => {
  if (props.fallback) return true
  return has.value
})

// 组件挂载时检查权限
onMounted(async () => {
  if (!has.value) {
    await check()
  }
})

// 点击处理
const handleClick = (event: MouseEvent) => {
  if (has.value) {
    emit('click', event)
  } else {
    emit('permission-denied')
  }
}
</script>
