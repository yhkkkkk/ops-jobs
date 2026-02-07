import { ref, computed, onMounted, onUnmounted } from 'vue'

/**
 * 通用的“未保存更改”检测 composable
 *
 * 用法示例：
 * const {
 *   setOriginalData,
 *   checkForChanges,
 *   markAsSaved,
 *   canLeave,
 *   setupLifecycle
 * } = useUnsavedChanges()
 *
 * // 初始化时记录原始数据
 * setOriginalData(form)
 *
 * // 表单变更时调用
 * checkForChanges(form)
 *
 * // 保存成功后调用
 * markAsSaved(form)
 *
 * // 在组件挂载时调用，自动绑定 beforeunload 监听
 * setupLifecycle()
 */
export function useUnsavedChanges<T = any>() {
  const originalData = ref<T | null>(null)
  const hasChanges = ref(false)

  const canLeave = computed(() => !hasChanges.value)

  const clone = (data: T): T => {
    // 对于普通对象/数组足够用，避免引入深拷贝库
    try {
      return JSON.parse(JSON.stringify(data))
    } catch {
      return data
    }
  }

  const setOriginalData = (data: T) => {
    if (data == null) return
    originalData.value = clone(data)
    hasChanges.value = false
  }

  const checkForChanges = (currentData: T) => {
    if (currentData == null) {
      hasChanges.value = false
      return false
    }
    if (originalData.value == null) {
      // 如果还没有原始数据，记录一次
      originalData.value = clone(currentData)
      hasChanges.value = false
      return false
    }
    const changed =
      JSON.stringify(currentData) !== JSON.stringify(originalData.value)
    hasChanges.value = changed
    return changed
  }

  const markAsSaved = (currentData?: T) => {
    if (currentData != null) {
      setOriginalData(currentData)
    } else if (originalData.value != null) {
      hasChanges.value = false
    }
  }

  const beforeUnloadHandler = (e: BeforeUnloadEvent) => {
    if (!hasChanges.value) return
    // 兼容各浏览器的提示逻辑
    e.preventDefault()
    e.returnValue = ''
  }

  const setupLifecycle = () => {
    if (typeof window === 'undefined') return
    onMounted(() => {
      window.addEventListener('beforeunload', beforeUnloadHandler)
    })
    onUnmounted(() => {
      window.removeEventListener('beforeunload', beforeUnloadHandler)
    })
  }

  return {
    setOriginalData,
    checkForChanges,
    markAsSaved,
    canLeave,
    setupLifecycle,
  }
}


