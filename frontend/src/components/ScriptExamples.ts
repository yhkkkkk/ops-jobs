/**
 * 脚本示例代码
 * 用于快速执行、脚本模板、作业模板等功能
 */

export const SCRIPT_EXAMPLES = {
  shell: `#!/bin/bash

# 定义获取当前时间和PID的函数
function job_get_now
{
    echo "[\`date +'%Y-%m-%d %H:%M:%S'\`][PID:$$]"
}

# 在脚本开始运行时调用，打印当前的时间戳及PID
function job_start
{
    echo "$(job_get_now) job_start"
}

# 在脚本执行成功的逻辑分支处调用，打印当前的时间戳及PID
function job_success
{
    local msg="$*"
    echo "$(job_get_now) job_success:[$msg]"
    exit 0
}

# 在脚本执行失败的逻辑分支处调用，打印当前的时间戳及PID
function job_fail
{
    local msg="$*"
    echo "$(job_get_now) job_fail:[$msg]"
    exit 1
}

# 在当前脚本执行时，第一行输出当前时间和进程ID，详见上面函数：job_get_now
job_start

###### 作业平台中执行脚本成功和失败的标准只取决于脚本最后一条执行语句的返回值
###### 如果返回值为0，则认为此脚本执行成功，如果非0，则认为脚本执行失败
###### 可在此处开始编写您的脚本逻辑代码`,

  python: `#!/usr/bin/env python
# -*- coding: utf8 -*-

import datetime
import os
import sys

def _now(format="%Y-%m-%d %H:%M:%S"):
    return datetime.datetime.now().strftime(format)

##### 可在脚本开始运行时调用，打印当时的时间戳及PID。
def job_start():
    print("[%s][PID:%s] job_start" % (_now(), os.getpid()))
    sys.stdout.flush()

##### 可在脚本执行成功的逻辑分支处调用，打印当时的时间戳及PID。
def job_success(msg):
    print("[%s][PID:%s] job_success:[%s]" % (_now(), os.getpid(), msg))
    sys.stdout.flush()
    sys.exit(0)

##### 可在脚本执行失败的逻辑分支处调用，打印当时的时间戳及PID。
def job_fail(msg):
    print("[%s][PID:%s] job_fail:[%s]" % (_now(), os.getpid(), msg))
    sys.stdout.flush()
    sys.exit(1)

if __name__ == '__main__':

    job_start()

###### 脚本执行成功和失败的标准只取决于最后一段执行语句的返回值
###### 如果返回值为0，则认为此脚本执行成功，如果非0，则认为脚本执行失败
###### Python脚本为了避免因长时间未刷新缓冲区导致标准输出异常，
###### 建议在print的下一行使用 sys.stdout.flush() 来强制将被缓存的输出信息刷新到控制台上
###### 可在此处开始编写您的脚本逻辑代码`,

  powershell: `##### 可在脚本开始运行时调用，打印当时的时间戳及PID。
function job_start
{
    $cu_date = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "[{0}][PID:{1}] job_start" -f $cu_date,$pid
}

##### 可在脚本执行成功的逻辑分支处调用，打印当时的时间戳及PID。
function job_success
{
    $cu_date = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    if($args.count -ne 0)
    {
        $args | foreach {$arg_str=$arg_str + " " + $_}
        "[{0}][PID:{1}] job_success:[{2}]" -f $cu_date,$pid,$arg_str.TrimStart(' ')
    }
    else
    {
        "[{0}][PID:{1}] job_success:[]" -f $cu_date,$pid
    }
    exit 0
}

##### 可在脚本执行失败的逻辑分支处调用，打印当时的时间戳及PID。
function job_fail
{
    $cu_date = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    if($args.count -ne 0)
    {
        $args | foreach {$arg_str=$arg_str + " " + $_}
        "[{0}][PID:{1}] job_fail:[{2}]" -f $cu_date,$pid,$arg_str.TrimStart(' ')
    }
    else
    {
        "[{0}][PID:{1}] job_fail:[]" -f $cu_date,$pid
    }
    exit 1
}

job_start

###### 作业平台中执行脚本成功和失败的标准只取决于脚本最后一条执行语句的返回值
###### 如果返回值为0，则认为此脚本执行成功，如果非0，则认为脚本执行失败
###### 可在此处开始编写您的脚本逻辑代码`,


}

/**
 * 获取指定脚本类型的示例代码
 * @param scriptType 脚本类型
 * @returns 示例代码
 */
export function getScriptExample(scriptType: string): string {
  return SCRIPT_EXAMPLES[scriptType as keyof typeof SCRIPT_EXAMPLES] || SCRIPT_EXAMPLES.shell
}

/**
 * 脚本类型配置
 */
export const SCRIPT_TYPES = [
  { value: 'shell', label: 'Shell', color: 'blue' },
  { value: 'python', label: 'Python', color: 'green' },
  { value: 'powershell', label: 'PowerShell', color: 'purple' }
]

/**
 * 获取脚本类型显示文本
 * @param scriptType 脚本类型
 * @returns 显示文本
 */
export function getScriptTypeText(scriptType: string): string {
  const type = SCRIPT_TYPES.find(t => t.value === scriptType)
  return type?.label || scriptType
}

/**
 * 获取脚本类型颜色
 * @param scriptType 脚本类型
 * @returns 颜色
 */
export function getScriptTypeColor(scriptType: string): string {
  const type = SCRIPT_TYPES.find(t => t.value === scriptType)
  return type?.color || 'gray'
}
