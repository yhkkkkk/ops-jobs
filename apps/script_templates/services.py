"""
脚本模板服务
"""
import re
import logging
from .models import ScriptTemplate, DefaultScriptTemplate

logger = logging.getLogger(__name__)


class ScriptTemplateService:
    """脚本模板服务"""
    
    @staticmethod
    def get_template_content(template):
        """获取模板内容"""
        try:
            return {
                'success': True,
                'data': {
                    'script_content': template.script_content,
                    'script_type': template.script_type,
                    'name': template.name,
                    'description': template.description,
                    'version': template.version
                }
            }

        except Exception as e:
            logger.error(f"获取模板内容失败: {template.name} - {e}")
            return {
                'success': False,
                'message': f'获取模板内容失败: {str(e)}'
            }
    
    @staticmethod
    def create_default_templates():
        """创建默认脚本模板"""
        default_templates = {
            'shell': {
                'content': '''#!/bin/bash

# Shell脚本模板
# 在这里编写您的Shell脚本

set -e  # 遇到错误立即退出

echo "开始执行Shell脚本"

# 您的脚本内容
echo "Hello World"

echo "脚本执行完成"
''',
                'description': 'Shell脚本默认模板'
            },
            'python': {
                'content': '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Python脚本模板
在这里编写您的Python脚本
"""

import sys
import os

def main():
    """主函数"""
    print("开始执行Python脚本")

    # 您的脚本内容
    print("Hello World")

    print("脚本执行完成")
    return 0

if __name__ == "__main__":
    sys.exit(main())
''',
                'description': 'Python脚本默认模板'
            },
            'powershell': {
                'content': '''# PowerShell脚本模板
# 在这里编写您的PowerShell脚本

Write-Host "开始执行PowerShell脚本"

# 您的脚本内容
Write-Host "Hello World"

Write-Host "脚本执行完成"
''',
                'description': 'PowerShell脚本默认模板'
            },

        }
        
        created_count = 0
        for script_type, template_data in default_templates.items():
            template, created = DefaultScriptTemplate.objects.get_or_create(
                script_type=script_type,
                defaults={
                    'template_content': template_data['content'],
                    'description': template_data['description']
                }
            )
            if created:
                created_count += 1
                logger.info(f"创建默认模板: {script_type}")
        
        return {
            'success': True,
            'created_count': created_count,
            'message': f'成功创建 {created_count} 个默认模板'
        }
    
    # 删除复杂的变量验证，简化模板系统
