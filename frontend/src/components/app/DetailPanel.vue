<template>
  <section :class="['app-card', 'app-detail-panel', { 'app-detail-panel--dense': dense }]">
    <div class="app-detail-panel__head">
      <div>
        <h2>{{ title }}</h2>
        <p v-if="description">{{ description }}</p>
      </div>
      <slot name="extra" />
    </div>
    <div class="app-detail-panel__body">
      <slot />
    </div>
  </section>
</template>

<script setup lang="ts">
defineProps<{
  title: string
  description?: string
  dense?: boolean
}>()
</script>

<style scoped>
.app-detail-panel {
  padding: 18px;
}

.app-detail-panel--dense {
  padding: 12px 14px;
}

.app-detail-panel__head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 14px;
}

.app-detail-panel--dense .app-detail-panel__head {
  margin-bottom: 8px;
}

.app-detail-panel__head h2 {
  margin: 0;
  color: var(--app-fg);
  font-size: 16px;
  line-height: 1.3;
  font-weight: 650;
}

.app-detail-panel--dense .app-detail-panel__head h2 {
  font-size: 15px;
}

.app-detail-panel__head p {
  margin: 4px 0 0;
  color: var(--app-muted);
  font-size: 13px;
  line-height: 1.5;
}

.app-detail-panel--dense .app-detail-panel__head p {
  margin-top: 2px;
  font-size: 12px;
  line-height: 1.35;
}

.app-detail-panel__body {
  min-width: 0;
}
</style>
