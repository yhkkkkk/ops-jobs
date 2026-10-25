<template>
  <div id="app">
    <n-config-provider :theme-overrides="platformThemeOverrides">
      <n-message-provider>
        <n-notification-provider>
          <n-dialog-provider>
            <router-view />
          </n-dialog-provider>
        </n-notification-provider>
      </n-message-provider>
    </n-config-provider>
  </div>
</template>

<script setup lang="ts">
import { platformThemeOverrides } from './components/ui/theme'
</script>

<style>
#app {
  width: 100%;
  height: 100vh;
}
</style>
