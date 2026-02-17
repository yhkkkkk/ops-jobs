<template>
  <div class="meta-lines">
    <div class="meta-line">{{ createdText || '-' }}</div>
    <div class="meta-line">{{ updatedText || '-' }}</div>
  </div>
</template>

<script setup lang="ts">
const props = defineProps({
  createdText: {
    type: String,
    default: '-'
  },
  updatedText: {
    type: String,
    default: '-'
  }
})
</script>

<style scoped>
.meta-lines {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.meta-line {
  font-size: 12px;
  line-height: 1.4;
  color: var(--color-text-3);
}
</style>
