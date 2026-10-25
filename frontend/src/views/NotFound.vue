<template>
  <div class="not-found">
    <n-result
      status="404"
      title="404"
      subtitle="抱歉，您访问的页面不存在"
    >
      <template #footer>
        <n-button type="primary" @click="goHome">
          返回首页
        </n-button>
      </template>
    </n-result>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { NButton, NResult } from 'naive-ui'

const router = useRouter()

const goHome = () => {
  router.push('/dashboard')
}
</script>

<style scoped>
.not-found {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 60vh;
}
</style>
