<template>
  <div class="flow-run-data-view">
    <a-tabs size="small">
      <a-tab-pane key="fields" title="字段">
        <a-empty v-if="rows.length === 0" :description="emptyText" />
        <div v-else class="run-data-fields">
          <div v-for="(row, index) in rows" :key="`${row.key}-${index}`" class="run-data-row">
            <span>{{ row.key }}</span>
            <pre v-if="row.multiline">{{ row.value }}</pre>
            <strong v-else>{{ row.value }}</strong>
          </div>
        </div>
      </a-tab-pane>
      <a-tab-pane key="json" title="JSON">
        <pre class="run-data-json">{{ formattedJson }}</pre>
      </a-tab-pane>
    </a-tabs>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { flowRunDisplayRows, formatFlowRunDisplayJson } from '../flowUtils'

const props = withDefaults(defineProps<{
  value?: Record<string, any>
  emptyText?: string
}>(), {
  value: () => ({}),
  emptyText: '暂无数据',
})

const rows = computed(() => flowRunDisplayRows(props.value || {}))
const formattedJson = computed(() => formatFlowRunDisplayJson(props.value || {}))
</script>

<style scoped>
.flow-run-data-view {
  min-width: 0;
}

.run-data-fields {
  display: grid;
  gap: 6px;
  max-height: 180px;
  overflow: auto;
  padding-right: 4px;
}

.run-data-row {
  display: grid;
  grid-template-columns: minmax(96px, .28fr) minmax(0, 1fr);
  gap: 8px;
  align-items: start;
  min-width: 0;
  padding: 8px 10px;
  background: var(--app-surface-soft);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
}

.run-data-row span,
.run-data-row strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.run-data-row span {
  color: var(--app-muted);
  font-size: 12px;
  line-height: 1.45;
}

.run-data-row strong {
  color: var(--app-fg);
  font-size: 12px;
  line-height: 1.45;
  font-weight: 500;
}

.run-data-row pre,
.run-data-json {
  margin: 0;
  overflow: auto;
  color: var(--app-fg);
  font-family: var(--app-mono);
  font-size: 12px;
  line-height: 1.45;
  white-space: pre-wrap;
  word-break: break-word;
}

.run-data-row pre {
  max-height: 120px;
}

.run-data-json {
  max-height: 180px;
  padding: 9px 10px;
  background: var(--app-surface-soft);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
}

@media (max-width: 720px) {
  .run-data-row {
    grid-template-columns: 1fr;
  }
}
</style>
