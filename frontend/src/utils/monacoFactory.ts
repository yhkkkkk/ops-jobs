// Monaco Editor 工厂函数 - 按需加载和优化

import { setupMonacoWorkers } from '@/utils/monacoWorkers'

let monacoInstance: any = null
let isLoading = false
let loadPromise: Promise<any> | null = null

// 语言映射
export const languageMap = {
  shell: 'shell',
  bash: 'shell',
  python: 'python',
  powershell: 'powershell',
  perl: 'perl',
  js: 'javascript',
  node: 'javascript',
  sql: 'sql',
  javascript: 'javascript',
  go: 'go',
  golang: 'go',
  typescript: 'typescript',
  json: 'json',
  yaml: 'yaml',
  xml: 'xml',
}

// 获取Monaco语言
export const getMonacoLanguage = (lang: string) => {
  const key = (lang || '').toLowerCase()
  return languageMap[key] || 'plaintext'
}

const languageReady: Record<string, boolean> = {}

const ensureBasicLanguage = async (
  monaco: any,
  id: 'shell' | 'powershell' | 'perl' | 'go',
  loader: () => Promise<{ language: any; conf: any }>
) => {
  if (languageReady[id]) return
  const languages = monaco.languages.getLanguages?.() || []
  if (!languages.find((lang: any) => lang.id === id)) {
    monaco.languages.register({ id })
  }
  const mod = await loader()
  monaco.languages.setMonarchTokensProvider(id, mod.language)
  monaco.languages.setLanguageConfiguration(id, mod.conf)
  languageReady[id] = true
}

const ensureBuiltInLanguage = async (monaco: any, id: 'javascript' | 'typescript' | 'json' | 'css' | 'html') => {
  const languages = monaco.languages.getLanguages?.() || []
  const target = languages.find((lang: any) => lang.id === id)
  if (target?.loader) {
    await target.loader()
  }
}

export const ensureMonacoLanguage = async (monaco: any, lang?: string) => {
  if (!lang) return
  const resolved = getMonacoLanguage(lang)
  if (resolved === 'javascript') {
    await ensureBuiltInLanguage(monaco, 'javascript')
  }
  if (resolved === 'typescript') {
    await ensureBuiltInLanguage(monaco, 'typescript')
  }
  if (resolved === 'shell') {
    await ensureBasicLanguage(monaco, 'shell', () => import('monaco-editor/esm/vs/basic-languages/shell/shell'))
  }
  if (resolved === 'powershell') {
    await ensureBasicLanguage(monaco, 'powershell', () => import('monaco-editor/esm/vs/basic-languages/powershell/powershell'))
  }
  if (resolved === 'perl') {
    await ensureBasicLanguage(monaco, 'perl', () => import('monaco-editor/esm/vs/basic-languages/perl/perl'))
  }
  if (resolved === 'go') {
    await ensureBasicLanguage(monaco, 'go', () => import('monaco-editor/esm/vs/basic-languages/go/go'))
  }
}

// 动态加载Monaco Editor
export const loadMonaco = async (): Promise<any> => {
  if (monacoInstance) {
    return monacoInstance
  }

  if (isLoading && loadPromise) {
    return loadPromise
  }

  isLoading = true
  loadPromise = new Promise(async (resolve, reject) => {
    try {
      // 动态导入Monaco Editor
      const monacoModule = await import('monaco-editor')
      monacoInstance = monacoModule.default || monacoModule

      setupMonacoWorkers()

      isLoading = false
      resolve(monacoInstance)
    } catch (error) {
      isLoading = false
      loadPromise = null
      reject(error)
    }
  })

  return loadPromise
}

// 从CDN加载Monaco Editor
export const loadMonacoFromCDN = (): Promise<any> => {
  return new Promise((resolve, reject) => {
    if ((window as any).monaco) {
      resolve((window as any).monaco)
      return
    }

    // 检查是否已经在加载中
    if (isLoading) {
      const checkLoaded = () => {
        if ((window as any).monaco) {
          resolve((window as any).monaco)
        } else {
          setTimeout(checkLoaded, 100)
        }
      }
      checkLoaded()
      return
    }

    isLoading = true

    // 创建script标签加载Monaco Editor
    const script = document.createElement('script')
    script.src = 'https://cdn.jsdelivr.net/npm/monaco-editor@0.45.0/min/vs/loader.js'
    script.onload = () => {
      // 配置Monaco Editor的路径
      ;(window as any).require.config({
        paths: {
          vs: 'https://cdn.jsdelivr.net/npm/monaco-editor@0.45.0/min/vs'
        }
      })

      // 配置Web Worker
      ;(window as any).MonacoEnvironment = {
        getWorkerUrl: function (moduleId: string, label: string) {
          if (label === 'json') {
            return 'https://cdn.jsdelivr.net/npm/monaco-editor@0.45.0/min/vs/language/json/json.worker.js'
          }
          if (label === 'css' || label === 'scss' || label === 'less') {
            return 'https://cdn.jsdelivr.net/npm/monaco-editor@0.45.0/min/vs/language/css/css.worker.js'
          }
          if (label === 'html' || label === 'handlebars' || label === 'razor') {
            return 'https://cdn.jsdelivr.net/npm/monaco-editor@0.45.0/min/vs/language/html/html.worker.js'
          }
          if (label === 'typescript' || label === 'javascript') {
            return 'https://cdn.jsdelivr.net/npm/monaco-editor@0.45.0/min/vs/language/typescript/ts.worker.js'
          }
          return 'https://cdn.jsdelivr.net/npm/monaco-editor@0.45.0/min/vs/editor/editor.worker.js'
        }
      }

      // 加载Monaco Editor
      ;(window as any).require(['vs/editor/editor.main'], () => {
        monacoInstance = (window as any).monaco
        isLoading = false
        resolve(monacoInstance)
      })
    }
    script.onerror = () => {
      isLoading = false
      reject(new Error('Failed to load Monaco Editor from CDN'))
    }
    document.head.appendChild(script)
  })
}

// 创建编辑器实例
export const createEditor = async (
  container: HTMLElement,
  options: any = {}
): Promise<any> => {
  const monaco = await loadMonaco()
  
  const defaultOptions = {
    automaticLayout: true,
    fontSize: 14,
    lineNumbers: 'on',
    minimap: { enabled: false },
    scrollBeyondLastLine: false,
    wordWrap: 'on',
    folding: true,
    lineDecorationsWidth: 10,
    lineNumbersMinChars: 3,
    glyphMargin: false,
    contextmenu: true,
    selectOnLineNumbers: true,
    roundedSelection: false,
    cursorStyle: 'line',
    accessibilitySupport: 'off',
    tabSize: 2,
    insertSpaces: true,
    detectIndentation: false,
    // 优化性能的配置
    renderWhitespace: 'none',
    renderControlCharacters: false,
    renderIndentGuides: false,
    hideCursorInOverviewRuler: true,
    overviewRulerBorder: false,
    scrollbar: {
      vertical: 'auto',
      horizontal: 'auto',
      useShadows: false,
      verticalHasArrows: false,
      horizontalHasArrows: false,
      verticalScrollbarSize: 8,
      horizontalScrollbarSize: 8,
    },
    ...options,
  }

  if (typeof defaultOptions.language === 'string') {
    await ensureMonacoLanguage(monaco, defaultOptions.language)
  }

  return monaco.editor.create(container, defaultOptions)
}

// 预加载Monaco Editor（在应用启动时调用）
export const preloadMonaco = () => {
  // 在空闲时间预加载Monaco Editor
  if ('requestIdleCallback' in window) {
    requestIdleCallback(() => {
      loadMonaco().catch(console.error)
    })
  } else {
    setTimeout(() => {
      loadMonaco().catch(console.error)
    }, 1000)
  }
}

// 清理Monaco Editor实例
export const disposeMonaco = () => {
  if (monacoInstance) {
    monacoInstance = null
  }
  isLoading = false
  loadPromise = null
}
