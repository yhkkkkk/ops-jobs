<template>
  <a-modal
    v-model:visible="modalVisible"
    :title="modalTitle"
    :width="500"
    :footer="false"
    :mask-closable="false"
    :esc-to-close="false"
  >
    <a-form
      ref="formRef"
      :model="form"
      :rules="rules"
      layout="vertical"
    >
      <a-form-item label="分组名称" field="name">
        <a-input
          v-model="form.name"
          placeholder="请输入分组名称"
          allow-clear
        />
      </a-form-item>

      <a-form-item label="父分组" field="parent">
        <a-select
          v-model="form.parent"
          placeholder="请选择父分组（可选）"
          allow-clear
          allow-search
          :loading="groupsLoading"
        >
          <a-option
            v-for="group in availableParentGroups"
            :key="group.id"
            :value="group.id"
            :label="group.full_path || group.name"
            :disabled="group.id === currentGroupId"
          >
            <span :style="{ paddingLeft: (group.level || 0) * 20 + 'px' }">
              {{ group.name }}
            </span>
          </a-option>
        </a-select>
      </a-form-item>

      <a-form-item label="排序" field="sort_order">
        <a-input-number
          v-model="form.sort_order"
          :min="0"
          :max="9999"
          placeholder="0"
          style="width: 100%"
        />
        <div class="form-tip">
          <icon-info-circle />
          <span>数字越小排序越靠前</span>
        </div>
      </a-form-item>

      <a-form-item label="描述" field="description">
        <a-textarea
          v-model="form.description"
          placeholder="请输入分组描述（可选）"
          :rows="3"
        />
      </a-form-item>

      <!-- 自定义按钮 -->
      <a-form-item>
        <div style="text-align: right; margin-top: 20px;">
          <a-space>
            <a-button @click="handleCancel">
              取消
            </a-button>
            <a-button
              type="primary"
              @click="handleSubmit"
              :loading="loading"
            >
              保存
            </a-button>
          </a-space>
        </div>
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { Message } from '@arco-design/web-vue'
import { IconInfoCircle } from '@arco-design/web-vue/es/icon'
import { hostGroupApi } from '@/api/ops'
import type { HostGroup } from '@/types'

interface Props {
  visible: boolean
  group?: HostGroup | null
  parentGroup?: HostGroup | null // 用于添加子分组时指定父分组
}

interface Emits {
  (e: 'update:visible', visible: boolean): void
  (e: 'success'): void
}

const props = withDefaults(defineProps<Props>(), {
  group: null,
  parentGroup: null,
})

const emit = defineEmits<Emits>()

const formRef = ref()
const loading = ref(false)
const groupsLoading = ref(false)
const allGroups = ref<HostGroup[]>([])

// 表单数据
const form = reactive({
  name: '',
  parent: null as number | null,
  sort_order: 0,
  description: '',
})

// 表单验证规则
const rules = {
  name: [
    { required: true, message: '请输入分组名称' },
    { minLength: 2, message: '分组名称至少2个字符' },
    { maxLength: 50, message: '分组名称最多50个字符' },
  ],
  sort_order: [
    { type: 'number', min: 0, max: 9999, message: '排序值范围：0-9999' },
  ],
}

// 计算属性
const modalVisible = computed({
  get: () => props.visible,
  set: (value) => emit('update:visible', value),
})

const isEdit = computed(() => !!props.group?.id)

const currentGroupId = computed(() => props.group?.id || null)

const modalTitle = computed(() => {
  if (props.parentGroup) {
    return `为"${props.parentGroup.name}"添加子分组`
  }
  return isEdit.value ? '编辑分组' : '新增分组'
})

// 可选的父分组（排除自己和自己的子孙节点）
const availableParentGroups = computed(() => {
  if (!isEdit.value) {
    return allGroups.value
  }
  
  // 编辑时，排除自己和自己的子孙节点
  const currentGroup = props.group!
  return allGroups.value.filter(group => {
    if (group.id === currentGroup.id) return false
    
    // 检查是否是当前分组的子孙节点
    let parent = allGroups.value.find(g => g.id === group.parent)
    while (parent) {
      if (parent.id === currentGroup.id) return false
      parent = allGroups.value.find(g => g.id === parent!.parent)
    }
    
    return true
  })
})

// 重置表单
const resetForm = () => {
  Object.assign(form, {
    name: '',
    parent: props.parentGroup?.id || null,
    sort_order: 0,
    description: '',
  })
  formRef.value?.resetFields()
}

// 监听分组数据变化
watch(
  () => props.group,
  (group) => {
    if (group) {
      // 编辑模式，填充表单数据
      Object.assign(form, {
        name: group.name,
        parent: group.parent,
        sort_order: group.sort_order || 0,
        description: group.description || '',
      })
    } else {
      // 新增模式，重置表单
      resetForm()
    }
  },
  { immediate: true }
)

// 监听父分组变化（用于添加子分组）
watch(
  () => props.parentGroup,
  (parentGroup) => {
    if (parentGroup && !props.group) {
      form.parent = parentGroup.id
    }
  },
  { immediate: true }
)

// 提交表单
const handleSubmit = async () => {
  try {
    await formRef.value?.validate()
    loading.value = true

    const data = {
      name: form.name,
      parent: form.parent,
      sort_order: form.sort_order,
      description: form.description,
    }

    if (isEdit.value) {
      await hostGroupApi.updateGroup(props.group!.id, data)
      Message.success('分组更新成功')
    } else {
      await hostGroupApi.createGroup(data)
      Message.success('分组创建成功')
    }

    emit('success')
    modalVisible.value = false
  } catch (error: any) {
    console.error('保存分组失败:', error)
    let errorMessage = isEdit.value ? '分组更新失败' : '分组创建失败'
    if (error.response?.data?.message) {
      errorMessage += ': ' + error.response.data.message
    }
    Message.error(errorMessage)
  } finally {
    loading.value = false
  }
}

// 获取所有分组列表
const fetchAllGroups = async () => {
  groupsLoading.value = true
  try {
    const response = await hostGroupApi.getSimpleList()
    allGroups.value = response || []
  } catch (error) {
    console.error('获取分组列表失败:', error)
    allGroups.value = []
  } finally {
    groupsLoading.value = false
  }
}

// 取消操作
const handleCancel = () => {
  modalVisible.value = false
  resetForm()
}

// 监听模态框显示状态，每次打开时重新获取分组数据
watch(
  () => props.visible,
  async (newVisible) => {
    if (newVisible) {
      // 模态框打开时重新获取分组数据，确保数据是最新的
      console.log('分组表单打开，重新获取分组数据')
      await fetchAllGroups()
    }
  },
  { immediate: false }
)

// 组件挂载时获取分组列表
onMounted(() => {
  fetchAllGroups()
})
</script>

<style scoped>
.form-tip {
  display: flex;
  align-items: center;
  margin-top: 4px;
  font-size: 12px;
  color: #86909c;
}

.form-tip .arco-icon {
  margin-right: 4px;
}
</style>
