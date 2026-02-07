import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { favoriteApi } from '@/api/ops'

export type FavoriteType = 'job_template' | 'execution_plan' | 'script_template'

export const useFavoritesStore = defineStore('favorites', () => {
  // 状态：favoriteType -> objectId -> isFavorited
  const favorites = ref<Record<FavoriteType, Record<number, boolean>>>({
    job_template: {},
    script_template: {},
    execution_plan: {}
  })

  // 正在进行的请求缓存，避免重复请求
  const pendingRequests = ref<Map<string, Promise<any>>>(new Map())

  // 生成请求key
  const getRequestKey = (type: FavoriteType, action: 'check' | 'toggle' | 'batch', objectId?: number) => {
    return `${type}:${action}:${objectId || 'batch'}`
  }

  // 检查是否已收藏
  const isFavorite = (type: FavoriteType, objectId: number): boolean => {
    return favorites.value[type]?.[objectId] || false
  }

  // 批量检查收藏状态
  const batchCheckFavorites = async (
    type: FavoriteType,
    objectIds: number[]
  ): Promise<void> => {
    if (objectIds.length === 0) return

    const requestKey = getRequestKey(type, 'batch')

    // 如果已有相同请求在进行中，等待完成
    if (pendingRequests.value.has(requestKey)) {
      await pendingRequests.value.get(requestKey)
      return
    }

    const requestPromise = (async () => {
      try {
        // 并发请求所有对象的收藏状态
        const requests = objectIds.map(id =>
          favoriteApi.check({
            favorite_type: type,
            object_id: id
          }).catch(() => ({ data: { content: { is_favorited: false } } }))
        )

        const responses = await Promise.allSettled(requests)
        const favoriteStatus: Record<number, boolean> = {}

        responses.forEach((result, index) => {
          const objectId = objectIds[index]
          if (result.status === 'fulfilled') {
            favoriteStatus[objectId] = result.value.is_favorited || false
          } else {
            favoriteStatus[objectId] = false
          }
        })

        // 更新store中的状态
        if (!favorites.value[type]) {
          favorites.value[type] = {}
        }
        Object.assign(favorites.value[type], favoriteStatus)
      } catch (error) {
        console.error('批量检查收藏状态失败:', error)
      }
    })()

    pendingRequests.value.set(requestKey, requestPromise)
    await requestPromise
    pendingRequests.value.delete(requestKey)
  }

  // 切换收藏状态
  const toggleFavorite = async (
    type: FavoriteType,
    objectId: number,
    category: 'personal' | 'team' | 'common' | 'other' = 'personal'
  ): Promise<boolean> => {
    const requestKey = getRequestKey(type, 'toggle', objectId)

    // 如果已有相同请求在进行中，等待完成
    if (pendingRequests.value.has(requestKey)) {
      await pendingRequests.value.get(requestKey)
      return isFavorite(type, objectId)
    }

    const requestPromise = (async () => {
      try {
        const response = await favoriteApi.toggle({
          favorite_type: type,
          object_id: objectId,
          category
        })

        // 更新store中的状态
        if (!favorites.value[type]) {
          favorites.value[type] = {}
        }
        favorites.value[type][objectId] = response.is_favorited

        return response.is_favorited
      } catch (error) {
        console.error('切换收藏状态失败:', error)
        throw error
      }
    })()

    pendingRequests.value.set(requestKey, requestPromise)
    const result = await requestPromise
    pendingRequests.value.delete(requestKey)
    return result
  }

  // 清除指定类型的收藏状态
  const clearFavorites = (type?: FavoriteType) => {
    if (type) {
      favorites.value[type] = {}
    } else {
      // 清除所有收藏状态
      favorites.value = {
        job_template: {},
        script_template: {},
        execution_plan: {}
      }
    }
  }

  // 获取指定类型的收藏对象ID列表
  const getFavoritedIds = (type: FavoriteType): number[] => {
    const typeFavorites = favorites.value[type] || {}
    return Object.entries(typeFavorites)
      .filter(([, isFavorited]) => isFavorited)
      .map(([id]) => Number(id))
  }

  // 刷新指定类型的收藏状态
  const refreshFavorites = async (type: FavoriteType, objectIds: number[]) => {
    await batchCheckFavorites(type, objectIds)
  }

  return {
    // 状态
    favorites,

    // 方法
    isFavorite,
    batchCheckFavorites,
    toggleFavorite,
    clearFavorites,
    getFavoritedIds,
    refreshFavorites
  }
})
