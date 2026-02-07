import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ArcoResolver } from 'unplugin-vue-components/resolvers';
import svgLoader from 'vite-svg-loader'
import Pages from 'vite-plugin-pages'
import { resolve } from 'path'
import * as path from "node:path";


export default defineConfig({
  plugins: [
    vue(),
      // 添加SVG加载器
    svgLoader({
      defaultImport: 'component' // 默认以组件方式导入
    }),

    // 自动路由配置
    Pages({
      dirs: 'src/views', // 页面目录
      extensions: ['vue', 'tsx', 'jsx'], // 支持的文件扩展名
      exclude: ['**/components/**'], // 排除的目录
      routeStyle: 'next', // 路由风格 (nuxt/next)
      extendRoute(route) {
        // 扩展路由配置，可以设置中文标题和keepAlive属性
        const customRoutes = {
        };

        // 如果是自定义路由，添加额外配置
        if (route.path in customRoutes) {
          return {
            ...route,
            meta: {
              ...route.meta,
              ...customRoutes[route.path]
            }
          };
        }

        return route;
      }
    }),
    // 自动导入Vue API
    AutoImport({
      // 自动导入的API来源
      imports: [
        'vue',
        'vue-router',
        'pinia',
        '@vueuse/core',
      ],
      // 生成类型声明文件
      dts: 'src/auto-imports.d.ts',
    }),
    // 自动导入组件
    Components({
      dirs: ['src/components'],
      extensions: ['vue'],
      // 生成类型声明文件
      dts: 'src/components.d.ts',
      // 添加Arco Design组件的解析器
      resolvers: [
        ArcoResolver({
          sideEffect: true,  // 启用副作用导入以自动导入相关样式
          resolveIcons: true, // 解析图标组件
        }),
      ],
      directoryAsNamespace: true,
      globalNamespaces: ['global'],
      deep: true,
      // 排除views目录以避免命名冲突
      exclude: [/[\\/]views[\\/]/],
    }),
  ],
  // 路径解析配置
  resolve: {
    alias: {
      '@': path.join(__dirname, "./src"), // @ 指向 src 目录
    },
  },

  // 开发服务器配置
  server: {
    host: '127.0.0.1', // 绑定到 IPv4 地址
    port: 5173,        // 开发服务器端口
    open: true,        // 自动打开浏览器
    cors: true,        // 启用 cors
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000', // Django WSGI 后端地址
        changeOrigin: true,               // 改变请求头中的 origin
        ws: false,                        // 不支持 WebSocket
        secure: false,                   // 不验证 SSL 证书
      },
      // SSE 代理到 ASGI 服务器 - 匹配 /sse/sse/combined/ 路径
      '/sse/sse': {
        target: 'http://127.0.0.1:8001', // Django ASGI 服务器地址
        changeOrigin: true,
        ws: false,
        secure: false,
        rewrite: (path) => path.replace(/^\/sse\/sse/, '/api/realtime/sse'),
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks: {
          vue: ['vue', 'vue-router', 'pinia'],
          arco: ['@arco-design/web-vue'],
          charts: ['echarts'],
          // Monaco Editor 单独分包，按需加载
          'monaco-editor': ['monaco-editor'],
        },
      },
      external: (id) => {
        // 如果使用CDN方案，可以将monaco-editor标记为外部依赖
        // return id === 'monaco-editor'
        return false
      },
    },
    // 优化构建
    chunkSizeWarningLimit: 1000,
    minify: 'terser',
    terserOptions: {
      compress: {
        drop_console: true,
        drop_debugger: true,
      },
    },
  },
})
