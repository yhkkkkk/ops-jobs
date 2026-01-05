<template>
  <div id="app">
    <router-view />
  </div>
</template>

<script setup lang="ts">
// 根组件，只负责渲染路由视图
</script>

<style>
#app {
  width: 100%;
  height: 100vh;
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  background-color: #f5f5f5;
}

/* 分页组件样式优化 */
.arco-pagination {
  margin-top: 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
}

.arco-pagination .arco-pagination-list {
  margin: 0 auto;
}

.arco-pagination .arco-pagination-options {
  margin-left: auto;
  white-space: nowrap;
}

/* 确保分页组件不会超出容器 */
.arco-card .arco-card-body {
  padding-right: 20px;
  overflow-x: auto;
}

/* 修复分页选择器显示问题 */
.arco-pagination-options .arco-select {
  min-width: 80px;
}

.arco-pagination-options .arco-select-view {
  min-width: 80px;
}

/* 危险操作样式 */
.text-red-500 {
  color: #f53f3f !important;
}
</style>
