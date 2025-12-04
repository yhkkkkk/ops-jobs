"""
脚本模板服务
"""
import re
import logging
from .models import ScriptTemplate

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
