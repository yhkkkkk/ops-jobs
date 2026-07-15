// @vitest-environment happy-dom

import { defineComponent, nextTick } from 'vue'
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import FlowVariableEditor from '../components/FlowVariableEditor.vue'

const InputStub = defineComponent({
  props: {
    modelValue: { type: [String, Number, Boolean], default: '' },
    placeholder: { type: String, default: '' },
  },
  emits: ['update:modelValue', 'input'],
  template: `
    <input
      :value="modelValue"
      :placeholder="placeholder"
      @input="$emit('update:modelValue', $event.target.value); $emit('input', $event.target.value)"
    />
  `,
})

const ButtonStub = defineComponent({
  emits: ['click'],
  template: '<button type="button" @click="$emit(\'click\')"><slot /><slot name="icon" /></button>',
})

const mountEditor = () => {
  let wrapper: ReturnType<typeof mount>
  wrapper = mount(FlowVariableEditor, {
    props: {
      modelValue: {},
      'onUpdate:modelValue': (value: Record<string, any>) => wrapper.setProps({ modelValue: value }),
    },
    global: {
      stubs: {
        AButton: ButtonStub,
        AInput: InputStub,
        AInputPassword: InputStub,
        ATextarea: InputStub,
        ASelect: true,
        AOption: true,
        ACheckbox: true,
        AEmpty: true,
        IconPlus: true,
        IconDelete: true,
      },
    },
  })
  return wrapper
}

describe('FlowVariableEditor model synchronization', () => {
  it('preserves local drafts on its own v-model echo and resyncs a real external replacement', async () => {
    const wrapper = mountEditor()

    await wrapper.get('button').trigger('click')
    await wrapper.get('button').trigger('click')
    const keyInputs = () => wrapper.findAll('input[placeholder="Key，例如 CheckHost"]')
    expect(keyInputs()).toHaveLength(2)

    await keyInputs()[0].setValue('LocalKey')
    await nextTick()
    expect(keyInputs()).toHaveLength(2)
    expect(keyInputs()[1].element.value).toBe('')

    await wrapper.setProps({
      modelValue: {
        ExternalKey: {
          name: '外部变量',
          type: 'boolean',
          widget: 'input',
          default: true,
          required: true,
          show_on_start: true,
        },
      },
    })
    await nextTick()

    expect(keyInputs()).toHaveLength(1)
    expect(keyInputs()[0].element.value).toBe('ExternalKey')
  })
})
