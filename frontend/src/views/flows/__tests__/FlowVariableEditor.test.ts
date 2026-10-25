// @vitest-environment happy-dom

import { defineComponent, h, nextTick, ref } from 'vue'
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { NMessageProvider } from 'naive-ui'
import FlowVariableEditor from '../components/FlowVariableEditor.vue'

const InputStub = defineComponent({
  props: {
    value: { type: [String, Number, Boolean], default: '' },
    placeholder: { type: String, default: '' },
    type: { type: String, default: 'text' },
  },
  emits: ['update:value'],
  template: `
    <input
      :value="value"
      :placeholder="placeholder"
      @input="$emit('update:value', $event.target.value)"
    />
  `,
})

const ButtonStub = defineComponent({
  emits: ['click'],
  template: '<button type="button" @click="$emit(\'click\')"><slot /><slot name="icon" /></button>',
})

const mountEditor = () => {
  const model = ref<Record<string, any>>({})
  const wrapper = mount(
    defineComponent({
      setup() {
        return () =>
          h(NMessageProvider, null, {
            default: () =>
              h(FlowVariableEditor, {
                modelValue: model.value,
                'onUpdate:modelValue': (value: Record<string, any>) => {
                  model.value = value
                },
              }),
          })
      },
    }),
    {
      global: {
        stubs: {
          NButton: ButtonStub,
          NInput: InputStub,
          NSelect: true,
          NCheckbox: true,
          NEmpty: true,
          Plus: true,
        },
      },
    },
  )
  return { wrapper, model }
}

describe('FlowVariableEditor model synchronization', () => {
  it('preserves local drafts on its own v-model echo and resyncs a real external replacement', async () => {
    const { wrapper, model } = mountEditor()

    const addButtons = () =>
      wrapper.findAll('button').filter(btn => btn.text().includes('新增变量'))
    await addButtons()[0].trigger('click')
    await addButtons()[0].trigger('click')
    expect(wrapper.findAll('.variable-table__row')).toHaveLength(2)

    const keyInput = () => wrapper.find('input[placeholder="DeployPath"]')
    expect(keyInput().exists()).toBe(true)
    await keyInput().setValue('LocalKey')
    await nextTick()
    expect(wrapper.findAll('.variable-table__row')).toHaveLength(2)
    expect(model.value).toHaveProperty('LocalKey')

    model.value = {
      ExternalKey: {
        name: '外部变量',
        type: 'boolean',
        widget: 'input',
        default: true,
        required: true,
        show_on_start: true,
      },
    }
    await nextTick()

    expect(wrapper.findAll('.variable-table__row')).toHaveLength(1)
    expect(keyInput().element.value).toBe('ExternalKey')
  })
})
