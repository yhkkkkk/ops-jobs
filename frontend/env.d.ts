/// <reference types="vite/client" />

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}

declare module 'monaco-editor' {
  export * from 'monaco-editor/esm/vs/editor/editor.api'
}

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string
  readonly VITE_SSE_BASE_URL?: string
  readonly VITE_MOCK_API?: string
  readonly VITE_MOCK_LATENCY_MS?: string
}
