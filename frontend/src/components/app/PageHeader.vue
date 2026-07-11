<template>
  <header :class="['app-page-header', { 'app-page-header--dense': dense }]">
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
  dense?: boolean
}>()
</script>

<style scoped>
.app-page-header__copy {
  min-width: 0;
}

.app-page-header__actions {
  flex: 0 0 auto;
}

:global(.app-page-header--dense) {
  gap: 12px;
}

:global(.app-page-header--dense .app-page-eyebrow) {
  margin-bottom: 0;
  font-size: 10px;
  line-height: 1.25;
}

:global(.app-page-header--dense .app-page-title) {
  font-size: 20px;
  line-height: 1.2;
}

:global(.app-page-header--dense .app-page-desc) {
  margin-top: 2px;
  max-width: 560px;
  font-size: 12px;
  line-height: 1.35;
}

@media (max-width: 720px) {
  .app-page-header__actions {
    width: 100%;
  }
}
</style>
