/**
 * 脚本验证工具
 * 用于检测脚本中的最佳实践问题并提供建议
 */

export interface ScriptValidationResult {
  line: number
  column: number
  severity: 'error' | 'warning' | 'info'
  message: string
  suggestion?: string
  code: string
}

export interface ScriptValidationOptions {
  language: 'shell' | 'python' | 'powershell' | 'perl' | 'javascript' | 'go'
  strictMode?: boolean
}

/**
 * 脚本验证规则
 */
export class ScriptValidator {
  private language: string
  constructor(options: ScriptValidationOptions) {
    this.language = options.language
    // strictMode 用于未来扩展，暂时保留但不使用
    // this.strictMode = options.strictMode || false
  }

  /**
   * 验证脚本内容
   */
  validate(script: string): ScriptValidationResult[] {
    const results: ScriptValidationResult[] = []
    const lines = script.split('\n')

    lines.forEach((line, index) => {
      const lineNumber = index + 1
      const trimmedLine = line.trim()

      // 跳过空行和注释行
      if (!trimmedLine || trimmedLine.startsWith('#')) {
        return
      }

      // 根据语言类型进行验证
      switch (this.language) {
        case 'shell':
        case 'bash':
          results.push(...this.validateShellLine(line, lineNumber))
          break
        case 'python':
          results.push(...this.validatePythonLine(line, lineNumber))
          break
        case 'powershell':
          results.push(...this.validatePowerShellLine(line, lineNumber))
          break
        case 'perl':
          // Perl 暂不做语法级校验，仅预留扩展点
          break
        case 'javascript':
        case 'js':
        case 'go':
          // 暂不对 JS/Go 做语法级校验，仅预留扩展点
          break
      }
    })

    return results
  }

  /**
   * 验证Shell脚本行
   */
  private validateShellLine(line: string, lineNumber: number): ScriptValidationResult[] {
    const results: ScriptValidationResult[] = []
    const trimmedLine = line.trim()

    // 检查cd命令的错误处理
    const cdMatch = trimmedLine.match(/^cd\s+([^|&;]+)(?:\s*$|\s*[|&;])/)
    if (cdMatch) {
      const cdPath = cdMatch[1].trim()
      const column = line.indexOf('cd') + 1
      
      // 检查是否缺少错误处理
      if (!trimmedLine.includes('||') && !trimmedLine.includes('&&')) {
        results.push({
          line: lineNumber,
          column: column,
          severity: 'warning',
          message: `cd命令缺少错误处理`,
          suggestion: `请使用 "cd ${cdPath} || exit" 或 "cd ${cdPath} || return" 处理目录不存在的情况`,
          code: 'cd-without-error-handling'
        })
      }
      // 检查cd命令后是否缺少后续命令
      else if (trimmedLine.match(/^cd\s+[^|&;]+\s*\|\|\s*$/)) {
        results.push({
          line: lineNumber,
          column: column,
          severity: 'error',
          message: `cd命令后缺少后续处理命令`,
          suggestion: `请在 || 后添加处理命令，如 "cd ${cdPath} || exit 1" 或 "cd ${cdPath} || { echo '目录不存在'; exit 1; }"`,
          code: 'cd-incomplete-error-handling'
        })
      }
    }

    // 检查mkdir命令的错误处理
    const mkdirMatch = trimmedLine.match(/^mkdir\s+([^|&;]+)(?:\s*$|\s*[|&;])/)
    if (mkdirMatch && !trimmedLine.includes('||') && !trimmedLine.includes('&&')) {
      const dirPath = mkdirMatch[1].trim()
      const column = line.indexOf('mkdir') + 1
      
      results.push({
        line: lineNumber,
        column: column,
        severity: 'warning',
        message: `mkdir命令缺少错误处理`,
        suggestion: `建议使用 "mkdir -p ${dirPath} || { echo '创建目录失败'; exit 1; }" 处理创建失败的情况`,
        code: 'mkdir-without-error-handling'
      })
    }

    // 检查rm命令的危险操作
    const rmMatch = trimmedLine.match(/^rm\s+(-rf\s+)?\/([^|&;]+)(?:\s*$|\s*[|&;])/)
    if (rmMatch && rmMatch[1]) {
      const column = line.indexOf('rm') + 1
      
      results.push({
        line: lineNumber,
        column: column,
        severity: 'error',
        message: `危险的rm -rf操作`,
        suggestion: `请确认路径正确，建议先检查目录是否存在: if [ -d "${rmMatch[2]}" ]; then rm -rf "${rmMatch[2]}"; fi`,
        code: 'dangerous-rm-command'
      })
    }

    // 检查变量使用是否加引号
    const unquotedVarMatch = trimmedLine.match(/\$\{[^}]+\}/g)
    if (unquotedVarMatch) {
      unquotedVarMatch.forEach(match => {
        const fullMatch = line.match(new RegExp(`[^"]${match.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}[^"]`))
        if (fullMatch) {
          const column = line.indexOf(match) + 1
          
          results.push({
            line: lineNumber,
            column: column,
            severity: 'info',
            message: `变量使用建议加引号`,
            suggestion: `建议使用 "${match}" 避免空格和特殊字符问题`,
            code: 'unquoted-variable'
          })
        }
      })
    }

    // 检查管道命令的错误处理
    const pipeMatch = trimmedLine.match(/^[^|]*\|[^|]*$/)
    if (pipeMatch && !trimmedLine.includes('set -e') && !trimmedLine.includes('set -o pipefail')) {
      const column = line.indexOf('|') + 1
      
      results.push({
        line: lineNumber,
        column: column,
        severity: 'info',
        message: `管道命令建议设置错误处理`,
        suggestion: `建议在脚本开头添加 "set -e" 和 "set -o pipefail" 确保管道中任何命令失败都会终止脚本`,
        code: 'pipe-without-error-handling'
      })
    }

    return results
  }

  /**
   * 验证Python脚本行
   */
  private validatePythonLine(line: string, lineNumber: number): ScriptValidationResult[] {
    const results: ScriptValidationResult[] = []
    const trimmedLine = line.trim()

    // 检查os.chdir的使用
    const chdirMatch = trimmedLine.match(/os\.chdir\(['"]([^'"]+)['"]\)/)
    if (chdirMatch) {
      const column = line.indexOf('os.chdir') + 1
      
      results.push({
        line: lineNumber,
        column: column,
        severity: 'warning',
        message: `os.chdir缺少错误处理`,
        suggestion: `建议使用 try-except 处理目录不存在的情况: try: os.chdir('${chdirMatch[1]}'); except OSError: print('目录不存在'); sys.exit(1)`,
        code: 'chdir-without-error-handling'
      })
    }

    // 检查文件操作
    const fileOpMatch = trimmedLine.match(/(open|os\.remove|os\.rmdir|shutil\.rmtree)\(['"]([^'"]+)['"]\)/)
    if (fileOpMatch) {
      const column = line.indexOf(fileOpMatch[1]) + 1
      
      results.push({
        line: lineNumber,
        column: column,
        severity: 'info',
        message: `文件操作建议添加错误处理`,
        suggestion: `建议使用 try-except 处理文件操作异常`,
        code: 'file-operation-without-error-handling'
      })
    }

    return results
  }

  /**
   * 验证PowerShell脚本行
   */
  private validatePowerShellLine(line: string, lineNumber: number): ScriptValidationResult[] {
    const results: ScriptValidationResult[] = []
    const trimmedLine = line.trim()

    // 检查Set-Location的使用
    const cdMatch = trimmedLine.match(/Set-Location\s+['"]([^'"]+)['"]/)
    if (cdMatch) {
      const column = line.indexOf('Set-Location') + 1
      
      results.push({
        line: lineNumber,
        column: column,
        severity: 'warning',
        message: `Set-Location缺少错误处理`,
        suggestion: `建议使用 try-catch 处理目录不存在的情况: try { Set-Location '${cdMatch[1]}' } catch { Write-Error '目录不存在'; exit 1 }`,
        code: 'setlocation-without-error-handling'
      })
    }

    // 检查Remove-Item的危险操作
    const rmMatch = trimmedLine.match(/Remove-Item\s+['"]([^'"]+)['"]\s+-Recurse\s+-Force/)
    if (rmMatch) {
      const column = line.indexOf('Remove-Item') + 1
      
      results.push({
        line: lineNumber,
        column: column,
        severity: 'error',
        message: `危险的Remove-Item操作`,
        suggestion: `请确认路径正确，建议先检查目录是否存在: if (Test-Path '${rmMatch[1]}') { Remove-Item '${rmMatch[1]}' -Recurse -Force }`,
        code: 'dangerous-remove-item'
      })
    }

    return results
  }
}

/**
 * 创建脚本验证器
 */
export function createScriptValidator(options: ScriptValidationOptions): ScriptValidator {
  return new ScriptValidator(options)
}

/**
 * 快速验证脚本
 */
export function validateScript(
  script: string,
  language: 'shell' | 'python' | 'powershell' | 'perl' | 'javascript' | 'go'
): ScriptValidationResult[] {
  const validator = createScriptValidator({ language })
  return validator.validate(script)
}

/**
 * 获取验证结果的严重程度统计
 */
export function getValidationSummary(results: ScriptValidationResult[]) {
  return {
    total: results.length,
    errors: results.filter(r => r.severity === 'error').length,
    warnings: results.filter(r => r.severity === 'warning').length,
    info: results.filter(r => r.severity === 'info').length,
  }
}
