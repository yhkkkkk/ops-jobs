"""
切换验证码开关的管理命令
"""
from django.core.management.base import BaseCommand
from django.conf import settings
import os
import re


class Command(BaseCommand):
    help = '切换验证码开关'

    def add_arguments(self, parser):
        parser.add_argument(
            '--enable',
            action='store_true',
            help='启用验证码',
        )
        parser.add_argument(
            '--disable',
            action='store_true',
            help='禁用验证码',
        )
        parser.add_argument(
            '--status',
            action='store_true',
            help='查看当前验证码状态',
        )

    def handle(self, *args, **options):
        settings_file = os.path.join(settings.BASE_DIR, 'ops_job', 'settings.py')
        
        if options['status']:
            self.show_status()
            return
        
        if options['enable']:
            self.update_setting(settings_file, True)
            self.stdout.write(
                self.style.SUCCESS('验证码已启用')
            )
        elif options['disable']:
            self.update_setting(settings_file, False)
            self.stdout.write(
                self.style.SUCCESS('验证码已禁用')
            )
        else:
            self.stdout.write(
                self.style.ERROR('请指定 --enable、--disable 或 --status 参数')
            )

    def show_status(self):
        """显示当前验证码状态"""
        current_status = getattr(settings, 'CAPTCHA_ENABLED', True)
        status_text = "启用" if current_status else "禁用"
        self.stdout.write(f'当前验证码状态: {status_text}')

    def update_setting(self, settings_file, enabled):
        """更新设置文件中的验证码开关"""
        try:
            with open(settings_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # 使用正则表达式替换 CAPTCHA_ENABLED 的值
            pattern = r'CAPTCHA_ENABLED\s*=\s*(True|False)'
            replacement = f'CAPTCHA_ENABLED = {enabled}'
            
            if re.search(pattern, content):
                new_content = re.sub(pattern, replacement, content)
            else:
                # 如果没找到，在验证码配置部分添加
                captcha_config_pattern = r'(# 验证码配置\n)'
                if re.search(captcha_config_pattern, content):
                    new_content = re.sub(
                        captcha_config_pattern,
                        f'\\1CAPTCHA_ENABLED = {enabled}  # 是否启用验证码\n',
                        content
                    )
                else:
                    # 如果连验证码配置注释都没有，添加到文件末尾
                    new_content = content + f'\n\n# 验证码配置\nCAPTCHA_ENABLED = {enabled}  # 是否启用验证码\n'

            with open(settings_file, 'w', encoding='utf-8') as f:
                f.write(new_content)

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'更新设置文件失败: {str(e)}')
            )
