<template>
  <aside class="flow-setting-panel" :class="{ 'flow-setting-panel--collapsed': collapsed }">
    <div class="flow-setting-panel__toggle">
      <n-button size="tiny" @click="emit('update:collapsed', !collapsed)">
        {{ collapsed ? '展开设置' : '收起' }}
      </n-button>
    </div>
    <template v-if="!collapsed">
      <n-tabs v-model:value="activeTab" type="line" size="small" class="flow-setting-tabs">
        <n-tab-pane name="variables" tab="全局变量">
          <FlowVariableEditor v-if="!readonly" :model-value="variables" @update:model-value="emit('update:variables', $event)" />
          <FlowVariableReadOnlyPanel v-else :variables="variables" empty-text="暂无全局变量" />
        </n-tab-pane>
        <n-tab-pane name="base" tab="基础信息">
          <n-form label-placement="top" size="small" :disabled="readonly">
            <n-form-item label="名称" required>
              <n-input :value="name" placeholder="流水线名称" @update:value="emit('update:name', $event)" />
            </n-form-item>
            <n-form-item label="说明">
              <n-input
                type="textarea"
                :value="description"
                placeholder="用途、窗口、负责人"
                :autosize="{ minRows: 2, maxRows: 4 }"
                @update:value="emit('update:description', $event)"
              />
            </n-form-item>
            <n-form-item label="分类">
              <n-input :value="category" placeholder="如：发布 / 巡检" @update:value="emit('update:category', $event)" />
            </n-form-item>
            <n-form-item label="状态">
              <n-switch :value="isActive" @update:value="emit('update:isActive', $event)" />
              <span class="setting-switch-label">{{ isActive ? '启用' : '停用' }}</span>
            </n-form-item>
            <n-form-item label="公共目录">
              <n-switch :value="isPublic" @update:value="emit('update:isPublic', $event)" />
              <span class="setting-switch-label">{{ isPublic ? '目录可见' : '仅自己' }}</span>
            </n-form-item>
          </n-form>
        </n-tab-pane>
        <n-tab-pane name="notify" tab="通知">
          <n-form label-placement="top" size="small" :disabled="readonly">
            <n-form-item label="启用 Webhook 通知">
              <n-switch
                :value="notifyConfig.enabled"
                @update:value="patchNotify({ enabled: $event })"
              />
            </n-form-item>
            <n-form-item label="通知事件">
              <n-checkbox-group
                :value="notifyConfig.events"
                @update:value="patchNotify({ events: $event as string[] })"
              >
                <n-space>
                  <n-checkbox value="success" label="成功" />
                  <n-checkbox value="failed" label="失败" />
                  <n-checkbox value="paused" label="暂停" />
                </n-space>
              </n-checkbox-group>
            </n-form-item>
            <n-form-item label="Webhook URL">
              <n-input
                :value="notifyConfig.webhook_url"
                placeholder="https://example.com/hooks/flow"
                @update:value="patchNotify({ webhook_url: $event })"
              />
            </n-form-item>
            <n-alert type="info" :bordered="false">
              任务进入对应状态时 POST JSON（含任务 ID、状态、executor 等）。
            </n-alert>
          </n-form>
        </n-tab-pane>
      </n-tabs>
    </template>
  </aside>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import FlowVariableEditor from './FlowVariableEditor.vue'
import FlowVariableReadOnlyPanel from './FlowVariableReadOnlyPanel.vue'
import {
  NAlert, NButton, NCheckbox, NCheckboxGroup, NForm, NFormItem, NInput, NSpace, NSwitch, NTabPane, NTabs,
} from 'naive-ui'

export interface FlowNotifyConfig {
  enabled: boolean
  events: string[]
  webhook_url: string
}

const props = withDefaults(defineProps<{
  collapsed?: boolean
  readonly?: boolean
  name: string
  description: string
  category: string
  isActive: boolean
  isPublic: boolean
  variables: Record<string, any>
  notifyConfig: FlowNotifyConfig
  initialTab?: 'variables' | 'base' | 'notify'
}>(), {
  collapsed: false,
  readonly: false,
  initialTab: 'variables',
})

const emit = defineEmits<{
  'update:collapsed': [value: boolean]
  'update:name': [value: string]
  'update:description': [value: string]
  'update:category': [value: string]
  'update:isActive': [value: boolean]
  'update:isPublic': [value: boolean]
  'update:variables': [value: Record<string, any>]
  'update:notifyConfig': [value: FlowNotifyConfig]
}>()

const activeTab = ref(props.initialTab)
watch(() => props.initialTab, value => {
  if (value) activeTab.value = value
})

const patchNotify = (patch: Partial<FlowNotifyConfig>) => {
  emit('update:notifyConfig', { ...props.notifyConfig, ...patch })
}
</script>

<style scoped>
.flow-setting-panel {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  height: 100%;
  overflow: hidden;
  background: #fff;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
}
.flow-setting-panel--collapsed {
  width: 44px;
  align-items: center;
  padding-top: 8px;
}
.flow-setting-panel__toggle {
  display: flex;
  justify-content: flex-end;
  padding: 8px 8px 0;
}
.flow-setting-tabs {
  flex: 1;
  min-height: 0;
  padding: 0 10px 10px;
  overflow: hidden;
}
.flow-setting-tabs :deep(.n-tabs-pane-wrapper),
.flow-setting-tabs :deep(.n-tab-pane) {
  height: 100%;
  overflow: auto;
}
.setting-switch-label {
  margin-left: 8px;
  color: var(--app-muted);
  font-size: 12px;
}
</style>
