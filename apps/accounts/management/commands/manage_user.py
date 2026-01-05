from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User


class Command(BaseCommand):
  help = '账户管理：add / reset / enable 用户'

  def add_arguments(self, parser):
    parser.add_argument('action', type=str, help='执行动作: add/reset/enable')
    parser.add_argument('-u', required=False, help='账户名称')
    parser.add_argument('-p', required=False, help='账户密码')
    parser.add_argument('-n', required=False, help='账户昵称')
    parser.add_argument('-s', default=False, action='store_true', help='是否超级用户 (默认否)')

  def echo_success(self, msg):
    self.stdout.write(self.style.SUCCESS(msg))

  def echo_error(self, msg):
    self.stderr.write(self.style.ERROR(msg))

  def print_usage_help(self):
    message = '''
账户管理命令用法：
  manage_user add    创建账户，例如：manage_user add -u admin -p 123 -n 管理员 -s
  manage_user reset  重置账户密码，例如：manage_user reset -u admin -p 123
  manage_user enable 启用被禁用的账户，例如：manage_user enable -u admin
'''
    self.stdout.write(message)

  def handle(self, *args, **options):
    action = options['action']
    username = options.get('u')
    password = options.get('p')
    nickname = options.get('n')
    is_super = options.get('s', False)

    if action == 'add':
      if not all((username, password, nickname)):
        self.echo_error('缺少参数')
        return self.print_usage_help()
      if User.objects.filter(username=username).exists():
        return self.echo_error(f'已存在登录名为【{username}】的用户')
      user = User.objects.create_user(username=username, password=password, first_name=nickname)
      if is_super:
        user.is_staff = True
        user.is_superuser = True
        user.save()
      self.echo_success('创建用户成功')

    elif action == 'enable':
      if not username:
        self.echo_error('缺少参数')
        return self.print_usage_help()
      user = User.objects.filter(username=username).first()
      if not user:
        return self.echo_error(f'未找到登录名为【{username}】的账户')
      user.is_active = True
      user.save()
      cache.delete(user.username)
      self.echo_success('账户已启用')

    elif action == 'reset':
      if not all((username, password)):
        self.echo_error('缺少参数')
        return self.print_usage_help()
      user = User.objects.filter(username=username).first()
      if not user:
        return self.echo_error(f'未找到登录名为【{username}】的账户')
      user.set_password(password)
      user.save()
      cache.delete(user.username)
      self.echo_success('账户密码已重置')

    else:
      self.echo_error('未识别的操作')
      self.print_usage_help()
