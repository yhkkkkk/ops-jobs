<template>
  <div class="host-group-tree">
    <HostGroupTreeNode
      v-for="group in groups"
      :key="group.id"
      :group="group"
      :level="0"
      :selected-group-id="selectedGroupId"
      :expanded-groups="expandedGroups"
      @select-group="$emit('select-group', $event)"
      @toggle-expand="$emit('toggle-expand', $event)"
      @edit-group="$emit('edit-group', $event)"
      @delete-group="$emit('delete-group', $event)"
      @add-subgroup="$emit('add-subgroup', $event)"
      @test-connection="$emit('test-connection', $event)"
    />
  </div>
</template>

<script setup lang="ts">
import type { HostGroup } from '@/types'
import HostGroupTreeNode from './HostGroupTreeNode.vue'

interface Props {
  groups: HostGroup[]
  selectedGroupId: number | null
  expandedGroups: number[]
}

interface Emits {
  (e: 'select-group', groupId: number | null): void
  (e: 'toggle-expand', groupId: number): void
  (e: 'edit-group', group: HostGroup): void
  (e: 'delete-group', group: HostGroup): void
  (e: 'add-subgroup', parentGroup: HostGroup): void
  (e: 'test-connection', group: HostGroup): void
}

defineProps<Props>()
defineEmits<Emits>()
</script>

<style scoped>
.host-group-tree {
  /* 树形结构样式 */
}
</style>
