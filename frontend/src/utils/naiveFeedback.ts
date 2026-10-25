import { createDiscreteApi } from 'naive-ui'

/**
 * 模块级（非组件上下文）使用的 Naive UI 消息/对话框 API。
 * 组件内请优先使用 useMessage()/useDialog()。
 */
export const { message, dialog } = createDiscreteApi(['message', 'dialog'])
