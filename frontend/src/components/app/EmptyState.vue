<template>
  <div class="app-card app-empty-state">
    <div class="app-empty-state__mark">
      <slot name="icon">-</slot>
    </div>
    <div>
      <h2>{{ title }}</h2>
      <p v-if="description">{{ description }}</p>
    </div>
    <div v-if="$slots.actions" class="app-empty-state__actions">
      <slot name="actions" />
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  title: string
  description?: string
}>()
</script>

<style scoped>
.app-empty-state {
  display: grid;
  place-items: center;
  gap: 12px;
  min-height: 220px;
  padding: 32px 20px;
  text-align: center;
}

.app-empty-state__mark {
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  border-radius: 12px;
  color: var(--app-muted);
  background: var(--app-surface-soft);
  font-family: var(--app-mono);
  font-size: 18px;
}

.app-empty-state h2 {
  margin: 0;
  color: var(--app-fg);
  font-size: 16px;
  font-weight: 650;
}

.app-empty-state p {
  margin: 6px 0 0;
  color: var(--app-muted);
  font-size: 13px;
  line-height: 1.6;
}

.app-empty-state__actions {
  margin-top: 4px;
}
</style>
