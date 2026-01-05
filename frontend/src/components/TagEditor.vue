<template>
  <div class="tag-editor">
    <div class="tag-list">
      <a-tag
        v-for="(tag, index) in tags"
        :key="index"
        closable
        @close="removeTag(index)"
        class="tag-item"
      >
        <strong>{{ tag.key }}:</strong> {{ tag.value }}
      </a-tag>
      
      <a-tag
        v-if="!showInput"
        @click="showAddInput"
        class="add-tag"
        style="background: #fafafa; border-style: dashed;"
      >
        <template #icon>
          <icon-plus />
        </template>
        添加标签
      </a-tag>
    </div>

    <!-- 添加标签输入框 -->
    <div v-if="showInput" class="tag-input">
      <a-space>
        <a-input
          ref="keyInputRef"
          v-model="newTag.key"
          placeholder="键"
          size="small"
          style="width: 100px"
          @keyup.enter="focusValueInput"
        />
        <span>:</span>
        <a-input
          ref="valueInputRef"
          v-model="newTag.value"
          placeholder="值"
          size="small"
          style="width: 120px"
          @keyup.enter="addTag"
        />
        <a-button type="primary" size="small" @click="addTag">
          <template #icon>
            <icon-check />
          </template>
        </a-button>
        <a-button size="small" @click="cancelAdd">
          <template #icon>
            <icon-close />
          </template>
        </a-button>
      </a-space>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, nextTick, watch } from 'vue'
import { IconPlus, IconCheck, IconClose } from '@arco-design/web-vue/es/icon'

interface Tag {
  key: string
  value: string
}

interface Props {
  modelValue?: Tag[]
  placeholder?: string
  maxTags?: number
}

interface Emits {
  (e: 'update:modelValue', value: Tag[]): void
  (e: 'change', value: Tag[]): void
}

const props = withDefaults(defineProps<Props>(), {
  modelValue: () => [],
  placeholder: '添加标签',
  maxTags: 10
})

const emit = defineEmits<Emits>()

// 响应式数据
const tags = ref<Tag[]>([...props.modelValue])
const showInput = ref(false)
const newTag = reactive<Tag>({
  key: '',
  value: ''
})

// 引用
const keyInputRef = ref()
const valueInputRef = ref()

// 监听外部值变化
watch(() => props.modelValue, (newValue) => {
  tags.value = [...newValue]
}, { deep: true })

// 显示添加输入框
const showAddInput = () => {
  if (tags.value.length >= props.maxTags) {
    return
  }
  showInput.value = true
  nextTick(() => {
    keyInputRef.value?.focus()
  })
}

// 聚焦到值输入框
const focusValueInput = () => {
  if (newTag.key.trim()) {
    valueInputRef.value?.focus()
  }
}

// 添加标签
const addTag = () => {
  const key = newTag.key.trim()
  const value = newTag.value.trim()
  
  if (!key || !value) {
    return
  }
  
  // 检查是否已存在相同的键
  const existingIndex = tags.value.findIndex(tag => tag.key === key)
  if (existingIndex >= 0) {
    // 更新现有标签的值
    tags.value[existingIndex].value = value
  } else {
    // 添加新标签
    tags.value.push({ key, value })
  }
  
  // 重置输入
  newTag.key = ''
  newTag.value = ''
  showInput.value = false
  
  // 触发更新
  updateValue()
}

// 取消添加
const cancelAdd = () => {
  newTag.key = ''
  newTag.value = ''
  showInput.value = false
}

// 移除标签
const removeTag = (index: number) => {
  tags.value.splice(index, 1)
  updateValue()
}

// 更新值
const updateValue = () => {
  emit('update:modelValue', [...tags.value])
  emit('change', [...tags.value])
}
</script>

<style scoped>
.tag-editor {
  width: 100%;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.tag-item {
  margin: 0;
}

.add-tag {
  cursor: pointer;
  margin: 0;
}

.add-tag:hover {
  border-color: #1890ff;
  color: #1890ff;
}

.tag-input {
  margin-top: 8px;
}
</style>
