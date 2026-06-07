<template>
  <header class="app-page-header">
    <div class="app-page-header__copy">
      <p v-if="eyebrow" class="app-page-eyebrow">{{ eyebrow }}</p>
      <h1 class="app-page-title">{{ title }}</h1>
      <p v-if="description" class="app-page-desc">{{ description }}</p>
    </div>
    <div v-if="$slots.actions" class="app-page-header__actions">
      <slot name="actions" />
    </div>
  </header>
</template>

<script setup lang="ts">
defineProps<{
  title: string
  eyebrow?: string
  description?: string
}>()
</script>

<style scoped>
.app-page-header__copy {
  min-width: 0;
}

.app-page-header__actions {
  flex: 0 0 auto;
}

@media (max-width: 720px) {
  .app-page-header__actions {
    width: 100%;
  }
}
</style>
