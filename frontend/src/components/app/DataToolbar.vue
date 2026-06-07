<template>
  <section class="app-card app-data-toolbar">
    <div class="app-data-toolbar__head">
      <div>
        <h2>{{ title }}</h2>
        <p v-if="description">{{ description }}</p>
      </div>
      <span v-if="activeCount > 0" class="app-data-toolbar__count">
        {{ activeCount }} 个筛选
      </span>
    </div>
    <div class="app-data-toolbar__filters">
      <slot />
    </div>
    <div v-if="$slots.actions" class="app-data-toolbar__actions">
      <slot name="actions" />
    </div>
  </section>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  title?: string
  description?: string
  activeCount?: number
}>(), {
  title: '筛选条件',
  activeCount: 0,
})
</script>

<style scoped>
.app-data-toolbar {
  display: grid;
  gap: 16px;
  padding: 18px;
}

.app-data-toolbar__head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.app-data-toolbar__head h2 {
  margin: 0;
  color: var(--app-fg);
  font-size: 16px;
  line-height: 1.3;
  font-weight: 650;
}

.app-data-toolbar__head p {
  margin: 4px 0 0;
  color: var(--app-muted);
  font-size: 13px;
  line-height: 1.5;
}

.app-data-toolbar__count {
  display: inline-flex;
  align-items: center;
  height: 24px;
  padding: 0 9px;
  border-radius: var(--app-radius-pill);
  color: var(--app-accent);
  background: var(--app-accent-soft);
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}

.app-data-toolbar__filters {
  min-width: 0;
}

.app-data-toolbar__actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>
