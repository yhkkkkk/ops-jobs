#!/usr/bin/env node

/**
 * 分析打包体积脚本
 * 用于对比 Monaco Editor 优化前后的打包体积
 */

const fs = require('fs')
const path = require('path')
const { execSync } = require('child_process')

// 颜色输出
const colors = {
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  magenta: '\x1b[35m',
  cyan: '\x1b[36m',
  white: '\x1b[37m',
  reset: '\x1b[0m'
}

function colorLog(color, message) {
  console.log(`${colors[color]}${message}${colors.reset}`)
}

// 获取文件大小
function getFileSize(filePath) {
  try {
    const stats = fs.statSync(filePath)
    return stats.size
  } catch (error) {
    return 0
  }
}

// 格式化文件大小
function formatSize(bytes) {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

// 分析 dist 目录
function analyzeDist() {
  const distPath = path.join(__dirname, '../dist')
  
  if (!fs.existsSync(distPath)) {
    colorLog('red', '❌ dist 目录不存在，请先运行 npm run build')
    return
  }

  colorLog('blue', '\n📊 打包体积分析')
  colorLog('blue', '=' .repeat(50))

  const files = fs.readdirSync(distPath, { withFileTypes: true })
  let totalSize = 0
  const fileSizes = []

  files.forEach(file => {
    if (file.isFile()) {
      const filePath = path.join(distPath, file.name)
      const size = getFileSize(filePath)
      totalSize += size
      fileSizes.push({
        name: file.name,
        size: size,
        formattedSize: formatSize(size)
      })
    } else if (file.isDirectory() && file.name === 'assets') {
      // 分析 assets 目录
      const assetsPath = path.join(distPath, 'assets')
      const assetFiles = fs.readdirSync(assetsPath)
      
      assetFiles.forEach(assetFile => {
        const assetPath = path.join(assetsPath, assetFile)
        const size = getFileSize(assetPath)
        totalSize += size
        fileSizes.push({
          name: `assets/${assetFile}`,
          size: size,
          formattedSize: formatSize(size)
        })
      })
    }
  })

  // 按大小排序
  fileSizes.sort((a, b) => b.size - a.size)

  // 输出结果
  colorLog('green', '\n📁 文件大小详情:')
  fileSizes.forEach(file => {
    const isLarge = file.size > 1024 * 1024 // 大于 1MB
    const color = isLarge ? 'yellow' : 'white'
    colorLog(color, `  ${file.name.padEnd(30)} ${file.formattedSize}`)
  })

  colorLog('cyan', `\n📈 总大小: ${formatSize(totalSize)}`)

  // Monaco Editor 相关文件分析
  const monacoFiles = fileSizes.filter(file => 
    file.name.includes('monaco') || 
    file.name.includes('editor') ||
    file.name.includes('vs/')
  )

  if (monacoFiles.length > 0) {
    colorLog('magenta', '\n🎯 Monaco Editor 相关文件:')
    monacoFiles.forEach(file => {
      colorLog('magenta', `  ${file.name.padEnd(30)} ${file.formattedSize}`)
    })
    
    const monacoTotalSize = monacoFiles.reduce((sum, file) => sum + file.size, 0)
    colorLog('magenta', `  Monaco Editor 总大小: ${formatSize(monacoTotalSize)}`)
  }

  // 优化建议
  colorLog('yellow', '\n💡 优化建议:')
  if (totalSize > 5 * 1024 * 1024) {
    colorLog('yellow', '  - 总大小超过 5MB，建议启用代码分割')
  }
  if (monacoFiles.length > 0) {
    const monacoTotalSize = monacoFiles.reduce((sum, file) => sum + file.size, 0)
    if (monacoTotalSize > 2 * 1024 * 1024) {
      colorLog('yellow', '  - Monaco Editor 占用超过 2MB，建议使用 CDN 加载')
    }
  }
  colorLog('yellow', '  - 考虑启用 gzip 压缩')
  colorLog('yellow', '  - 使用 Tree Shaking 移除未使用的代码')
}

// 构建并分析
function buildAndAnalyze() {
  colorLog('blue', '🚀 开始构建项目...')
  
  try {
    execSync('npm run build', { 
      cwd: path.join(__dirname, '..'),
      stdio: 'inherit'
    })
    colorLog('green', '✅ 构建完成')
    analyzeDist()
  } catch (error) {
    colorLog('red', '❌ 构建失败:', error.message)
  }
}

// 主函数
function main() {
  const args = process.argv.slice(2)
  
  if (args.includes('--build')) {
    buildAndAnalyze()
  } else {
    analyzeDist()
  }
}

main()
