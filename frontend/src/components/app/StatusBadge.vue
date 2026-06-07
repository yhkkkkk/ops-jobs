<template>
  <span :class="['app-status-badge', `app-status-badge--${resolvedVariant}`]">
    <span class="app-status-badge__dot" aria-hidden="true" />
    <slot>{{ text || status || '-' }}</slot>
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { resolveStatusVariant, type StatusVariant } from './uiPrimitives'

const props = defineProps<{
  status?: string | null
  text?: string
  variant?: StatusVariant
}>()

const resolvedVariant = computed(() => props.variant ?? resolveStatusVariant(props.status))
</script>

<style scoped>
.app-status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 24px;
  padding: 3px 9px;
  border-radius: var(--app-radius-pill);
  font-size: 12px;
  line-height: 1.2;
  font-weight: 650;
  white-space: nowrap;
}

.app-status-badge__dot {
  width: 6px;
  height: 6px;
  border-radius: var(--app-radius-pill);
  background: currentColor;
}

.app-status-badge--success {
  color: var(--app-success);
  background: var(--app-success-soft);
}

.app-status-badge--info {
  color: var(--app-accent);
  background: var(--app-accent-soft);
}

.app-status-badge--warn {
  color: var(--app-warn);
  background: var(--app-warn-soft);
}

.app-status-badge--danger {
  color: var(--app-danger);
  background: var(--app-danger-soft);
}

.app-status-badge--muted {
  color: var(--app-muted);
  background: var(--app-surface-soft);
}
</style>
