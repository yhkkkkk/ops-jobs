"""
初始化Admin界面对象级权限命令
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group
from django.contrib.contenttypes.models import ContentType
from guardian.shortcuts import assign_perm
from apps.job_templates.models import JobTemplate
from apps.executor.models import ExecutionRecord
from apps.accounts.models import UserProfile


class Command(BaseCommand):
    help = '初始化Admin界面的对象级权限'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true', help='重置所有权限')
        parser.add_argument('--demo', action='store_true', help='创建演示权限')

    def handle(self, *args, **options):
        if options['reset']:
            self.reset_all_permissions()
        elif options['demo']:
            self.setup_demo_permissions()
        else:
            self.setup_basic_permissions()

    def setup_basic_permissions(self):
        """设置基本权限"""
        self.stdout.write('开始设置基本对象级权限...')
        
        # 获取或创建管理员用户
        admin_user, _ = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@example.com',
                'is_staff': True,
                'is_superuser': True,
                'is_active': True
            }
        )
        
        # 获取或创建管理员组
        admin_group, _ = Group.objects.get_or_create(name='Administrators')
        
        # 为管理员组分配所有权限
        self.assign_group_permissions(admin_group)
        
        # 将admin用户添加到管理员组
        admin_user.groups.add(admin_group)
        
        self.stdout.write(
            self.style.SUCCESS(f'成功设置基本权限，管理员用户: {admin_user.username}')
        )

    def setup_demo_permissions(self):
        """设置演示权限"""
        self.stdout.write('开始设置演示对象级权限...')
        
        # 创建测试用户
        dev_user, _ = User.objects.get_or_create(
            username='developer',
            defaults={'email': 'dev@example.com', 'is_staff': True}
        )
        
        ops_user, _ = User.objects.get_or_create(
            username='operator',
            defaults={'email': 'ops@example.com', 'is_staff': True}
        )
        
        # 创建用户组
        dev_group, _ = Group.objects.get_or_create(name='Developers')
        ops_group, _ = Group.objects.get_or_create(name='Operators')
        
        # 为开发组分配权限
        self.assign_developer_permissions(dev_group)
        dev_user.groups.add(dev_group)
        
        # 为运维组分配权限
        self.assign_operator_permissions(ops_group)
        ops_user.groups.add(ops_group)
        
        # 创建用户档案
        self.create_user_profiles()
        
        self.stdout.write(
            self.style.SUCCESS('成功设置演示权限')
        )

    def assign_group_permissions(self, group):
        """为管理员组分配所有权限"""
        # 获取所有内容类型
        content_types = ContentType.objects.filter(
            app_label__in=[
                'job_templates', 'hosts', 'scheduler', 'script_templates',
                'executor', 'accounts', 'permissions'
            ]
        )
        
        for ct in content_types:
            # 分配增删改查权限
            assign_perm(f'{ct.app_label}.add_{ct.model}', group)
            assign_perm(f'{ct.app_label}.change_{ct.model}', group)
            assign_perm(f'{ct.app_label}.delete_{ct.model}', group)
            assign_perm(f'{ct.app_label}.view_{ct.model}', group)
        
        self.stdout.write(f'为组 {group.name} 分配了所有权限')

    def assign_developer_permissions(self, group):
        """为开发组分配权限"""
        # 开发组可以管理作业模板和执行计划
        content_types = ContentType.objects.filter(
            app_label__in=['job_templates', 'script_templates']
        )
        
        for ct in content_types:
            assign_perm(f'{ct.app_label}.add_{ct.model}', group)
            assign_perm(f'{ct.app_label}.change_{ct.model}', group)
            assign_perm(f'{ct.app_label}.view_{ct.model}', group)
        
        # 可以查看执行记录
        ct = ContentType.objects.get_for_model(ExecutionRecord)
        assign_perm('executor.view_executionrecord', group)
        
        self.stdout.write(f'为开发组 {group.name} 分配了开发相关权限')

    def assign_operator_permissions(self, group):
        """为运维组分配权限"""
        # 运维组可以管理主机和执行作业
        content_types = ContentType.objects.filter(
            app_label__in=['hosts', 'executor']
        )
        
        for ct in content_types:
            assign_perm(f'{ct.app_label}.add_{ct.model}', group)
            assign_perm(f'{ct.app_label}.change_{ct.model}', group)
            assign_perm(f'{ct.app_label}.view_{ct.model}', group)
        
        # 可以查看作业模板
        ct = ContentType.objects.get_for_model(JobTemplate)
        assign_perm('job_templates.view_jobtemplate', group)
        
        self.stdout.write(f'为运维组 {group.name} 分配了运维相关权限')

    def create_user_profiles(self):
        """创建用户档案"""
        for user in User.objects.filter(is_staff=True):
            profile, created = UserProfile.objects.get_or_create(
                user=user,
                defaults={
                    'role': 'admin' if user.is_superuser else 'developer',
                    'can_execute_scripts': True,
                    'can_transfer_files': True,
                    'can_manage_hosts': True,
                    'can_create_jobs': True,
                    'can_execute_jobs': True,
                    'max_concurrent_tasks': 10
                }
            )
            
            if created:
                self.stdout.write(f'为用户 {user.username} 创建了档案')

    def reset_all_permissions(self):
        """重置所有权限"""
        self.stdout.write('开始重置所有对象级权限...')
        
        # 获取所有内容类型
        content_types = ContentType.objects.filter(
            app_label__in=[
                'job_templates', 'hosts', 'scheduler', 'script_templates',
                'executor', 'accounts', 'permissions'
            ]
        )
        
        # 删除所有对象级权限
        for ct in content_types:
            from guardian.models import UserObjectPermission, GroupObjectPermission
            UserObjectPermission.objects.filter(content_type=ct).delete()
            GroupObjectPermission.objects.filter(content_type=ct).delete()
        
        self.stdout.write(
            self.style.SUCCESS('成功重置所有对象级权限')
        )
