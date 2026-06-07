<template>
  <button
    v-if="clickable"
    type="button"
    class="app-card app-metric-card app-metric-card--button"
    @click="$emit('click')"
  >
    <MetricCardBody
      :label="label"
      :value="displayValue"
      :note="note"
      :variant="variant"
    >
      <template v-if="$slots.icon" #icon><slot name="icon" /></template>
    </MetricCardBody>
  </button>
  <article v-else class="app-card app-metric-card">
    <MetricCardBody
      :label="label"
      :value="displayValue"
      :note="note"
      :variant="variant"
    >
      <template v-if="$slots.icon" #icon><slot name="icon" /></template>
    </MetricCardBody>
  </article>
</template>

<script setup lang="ts">
import { computed, defineComponent, h } from 'vue'
import { formatCompactNumber, type StatusVariant } from './uiPrimitives'

const props = withDefaults(defineProps<{
  label: string
  value?: number | string | null
  note?: string
  variant?: StatusVariant
  clickable?: boolean
}>(), {
  variant: 'info',
  clickable: false,
})

defineEmits<{
  click: []
}>()

const displayValue = computed(() => formatCompactNumber(props.value))

const MetricCardBody = defineComponent({
  name: 'MetricCardBody',
  props: {
    label: { type: String, required: true },
    value: { type: String, required: true },
    note: { type: String, default: '' },
    variant: { type: String, default: 'info' },
  },
  setup(bodyProps, { slots }) {
    return () => h('div', { class: 'app-metric-card__body' }, [
      h('div', { class: 'app-metric-top' }, [
        h('div', [
          h('p', { class: 'app-metric-label' }, bodyProps.label),
          h('div', { class: 'app-metric-value' }, bodyProps.value),
        ]),
        slots.icon
          ? h('span', { class: ['app-metric-icon', `app-metric-icon--${bodyProps.variant}`] }, slots.icon())
          : null,
      ]),
      bodyProps.note ? h('p', { class: 'app-metric-note' }, bodyProps.note) : null,
    ])
  },
})
</script>

<style scoped>
.app-metric-card {
  width: 100%;
  text-align: left;
}

.app-metric-card--button {
  border: 1px solid var(--app-border);
}

.app-metric-card__body {
  display: grid;
  gap: 14px;
}

.app-metric-icon--success {
  color: var(--app-success);
  background: var(--app-success-soft);
}

.app-metric-icon--warn {
  color: var(--app-warn);
  background: var(--app-warn-soft);
}

.app-metric-icon--danger {
  color: var(--app-danger);
  background: var(--app-danger-soft);
}

.app-metric-icon--muted {
  color: var(--app-muted);
  background: var(--app-surface-soft);
}
</style>
