<template>
  <div class="group-tree-node">
    <!-- 分组节点 -->
    <div
      class="group-item"
      :class="{ 
        active: selectedGroupId === group.id,
        'has-children': hasChildren
      }"
      :style="{ paddingLeft: level * 20 + 'px' }"
      @click="$emit('select-group', group.id)"
      @contextmenu.prevent="showContextMenu"
    >
      <div class="group-info">
        <!-- 展开/收起按钮 -->
        <a-button
          v-if="hasChildren"
          type="text"
          size="mini"
          @click.stop="$emit('toggle-expand', group.id)"
          class="expand-btn"
        >
          <icon-down
            :class="{ 'expanded': isExpanded }"
            class="expand-icon"
          />
        </a-button>
        <div v-else class="expand-placeholder"></div>
        
        <!-- 分组图标和名称 -->
        <icon-folder class="group-icon" />
        <span class="group-name">{{ group.name }}</span>
      </div>
      
      <div class="group-actions">
        <span class="group-count">{{ group.total_host_count ?? group.host_count ?? 0 }}</span>
        <a-dropdown v-if="!readOnly" @select="handleMenuSelect">
          <a-button type="text" size="mini" @click.stop>
            <icon-more />
          </a-button>
          <template #content>
            <a-doption value="edit">
              <template #icon>
                <icon-edit />
              </template>
              编辑
            </a-doption>
            <a-doption value="add-subgroup">
              <template #icon>
                <icon-folder-add />
              </template>
              添加子分组
            </a-doption>
            <a-doption value="test-connection">
              <template #icon>
                <icon-wifi />
              </template>
              测试连接
            </a-doption>
            <a-doption value="delete" class="danger">
              <template #icon>
                <icon-delete />
              </template>
              删除
            </a-doption>
          </template>
        </a-dropdown>
      </div>
    </div>

    <!-- 子分组 -->
    <div v-if="hasChildren && isExpanded" class="children">
      <HostGroupTreeNode
        v-for="child in group.children"
        :key="child.id"
        :group="child"
        :level="level + 1"
        :selected-group-id="selectedGroupId"
        :expanded-groups="expandedGroups"
        :read-only="readOnly"
        @select-group="$emit('select-group', $event)"
        @toggle-expand="$emit('toggle-expand', $event)"
        @edit-group="$emit('edit-group', $event)"
        @delete-group="$emit('delete-group', $event)"
        @add-subgroup="$emit('add-subgroup', $event)"
        @test-connection="$emit('test-connection', $event)"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { 
  IconDown, 
  IconFolder, 
  IconMore, 
  IconEdit, 
  IconFolderAdd, 
  IconWifi, 
  IconDelete 
} from '@arco-design/web-vue/es/icon'
import type { HostGroup } from '@/types'

interface Props {
  group: HostGroup
  level: number
  selectedGroupId: number | null
  expandedGroups: number[]
  readOnly?: boolean
}

interface Emits {
  (e: 'select-group', groupId: number): void
  (e: 'toggle-expand', groupId: number): void
  (e: 'edit-group', group: HostGroup): void
  (e: 'delete-group', group: HostGroup): void
  (e: 'add-subgroup', parentGroup: HostGroup): void
  (e: 'test-connection', group: HostGroup): void
}

const props = withDefaults(defineProps<Props>(), {
  readOnly: false,
})
const emit = defineEmits<Emits>()

// 计算属性
const hasChildren = computed(() => {
  return props.group.children && props.group.children.length > 0
})

const isExpanded = computed(() => {
  return props.expandedGroups.includes(props.group.id)
})

// 处理菜单选择
const handleMenuSelect = (value: string) => {
  switch (value) {
    case 'edit':
      emit('edit-group', props.group)
      break
    case 'add-subgroup':
      emit('add-subgroup', props.group)
      break
    case 'test-connection':
      emit('test-connection', props.group)
      break
    case 'delete':
      emit('delete-group', props.group)
      break
  }
}

// 显示右键菜单
const showContextMenu = (event: MouseEvent) => {
  if (props.readOnly) return
  // TODO: 实现右键菜单
  console.log('Right click on group:', props.group.name)
}
</script>

<style scoped>
.group-tree-node {
  /* 节点容器 */
}

.group-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  margin: 2px 0;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
  user-select: none;
}

.group-item:hover {
  background-color: #f7f8fa;
}

.group-item.active {
  background-color: #e8f4ff;
  color: #1890ff;
}

.group-info {
  display: flex;
  align-items: center;
  flex: 1;
  min-width: 0;
}

.expand-btn {
  width: 20px;
  height: 20px;
  padding: 0;
  margin-right: 4px;
  flex-shrink: 0;
}

.expand-placeholder {
  width: 20px;
  height: 20px;
  margin-right: 4px;
  flex-shrink: 0;
}

.expand-icon {
  transition: transform 0.2s;
}

.expand-icon.expanded {
  transform: rotate(90deg);
}

.group-icon {
  margin-right: 8px;
  color: #86909c;
  flex-shrink: 0;
}

.group-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.group-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.group-count {
  font-size: 12px;
  color: #86909c;
  background: #f2f3f5;
  padding: 2px 6px;
  border-radius: 10px;
  min-width: 20px;
  text-align: center;
}

.children {
  /* 子节点容器 */
}

/* 危险操作样式 */
:deep(.arco-dropdown-option.danger) {
  color: #f53f3f;
}

:deep(.arco-dropdown-option.danger:hover) {
  background-color: #ffece8;
  color: #f53f3f;
}
</style>
