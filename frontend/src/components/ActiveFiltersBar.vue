<template>
  <div v-if="visibleItems.length" class="active-filters">
    <span class="active-filters__label">已筛选</span>
    <a-space wrap>
      <a-tag
        v-for="item in visibleItems"
        :key="item.key"
        closable
        @close="handleClose(item.key)"
      >
        {{ item.label }}：{{ item.display }}
      </a-tag>
    </a-space>
    <a-button
      type="text"
      size="mini"
      class="active-filters__clear"
      @click="emit('clear-all')"
    >
      清空
    </a-button>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface FilterItem {
  key: string
  label: string
  display: string
}

const props = defineProps<{ items: FilterItem[] }>()
const emit = defineEmits<{ (e: 'clear', key: string): void; (e: 'clear-all'): void }>()

const visibleItems = computed(() =>
  props.items.filter(item => item.display !== undefined && item.display !== '')
)

const handleClose = (key: string) => {
  emit('clear', key)
}
</script>

<style scoped>
.active-filters {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.active-filters__label {
  color: var(--color-text-3);
  font-size: 12px;
}

.active-filters__clear {
  margin-left: 4px;
}
</style>
