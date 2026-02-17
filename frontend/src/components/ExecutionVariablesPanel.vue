<template>
  <GlobalVariablesPanel
    class="execution-variables"
    :variables="variables"
    title="执行变量"
    empty-text="暂无执行变量"
  />
</template>

<script setup lang="ts">
import GlobalVariablesPanel from '@/components/GlobalVariablesPanel.vue'

defineProps({
  variables: {
    type: Object,
    default: () => ({})
  }
})
</script>

<style scoped>
.execution-variables {
  margin-top: 24px;
}
</style>
