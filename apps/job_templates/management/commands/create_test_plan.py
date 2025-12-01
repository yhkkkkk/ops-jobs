"""
为复杂作业模板创建执行方案
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from apps.job_templates.models import JobTemplate, ExecutionPlan, PlanStep
from apps.hosts.models import Host


class Command(BaseCommand):
    help = '为系统维护与监控作业创建执行方案'

    def handle(self, *args, **options):
        # 获取管理员用户
        try:
            admin_user = User.objects.filter(is_superuser=True).first()
            if not admin_user:
                self.stdout.write(
                    self.style.ERROR('未找到管理员用户')
                )
                return
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'获取管理员用户失败: {e}')
            )
            return

        # 获取作业模板
        try:
            template = JobTemplate.objects.get(name="系统维护与监控作业")
        except JobTemplate.DoesNotExist:
            self.stdout.write(
                self.style.ERROR('未找到"系统维护与监控作业"模板，请先运行 create_complex_template 命令')
            )
            return

        # 检查是否有主机
        hosts = Host.objects.all()
        if not hosts.exists():
            self.stdout.write(
                self.style.WARNING('系统中没有主机，将创建一个测试主机')
            )
            
            # 创建一个测试主机
            test_host = Host.objects.create(
                name="测试主机",
                ip_address="127.0.0.1",
                port=22,
                description="用于测试实时日志的本地主机",
                status="online",
                created_by=admin_user
            )
            hosts = [test_host]
            self.stdout.write(
                self.style.SUCCESS(f'创建测试主机: {test_host.name} ({test_host.ip_address})')
            )
        else:
            hosts = list(hosts)

        # 创建执行方案
        plan_name = "系统维护监控执行方案"
        
        # 检查是否已存在
        if ExecutionPlan.objects.filter(name=plan_name).exists():
            self.stdout.write(
                self.style.WARNING(f'执行方案 "{plan_name}" 已存在，跳过创建')
            )
            return

        execution_plan = ExecutionPlan.objects.create(
            name=plan_name,
            description="用于测试实时日志功能的系统维护监控执行方案，包含完整的系统检查、清理、备份流程",
            template=template,
            created_by=admin_user
        )

        # 为每个步骤创建执行计划步骤
        template_steps = template.steps.all().order_by('order')
        
        for step in template_steps:
            plan_step = PlanStep.objects.create(
                plan=execution_plan,
                step=step,
                order=step.order,
                step_name=step.name,
                step_description=step.description,
                step_type=step.step_type,
                step_script_content=step.script_content or "",
                step_script_type=step.script_type,
                step_timeout=step.timeout,
                step_ignore_error=step.ignore_error,
                step_parameters=step.step_parameters or [],
                step_target_host_ids=[host.id for host in hosts],
                step_target_group_ids=[]
            )
            
            # 主机已经在创建时设置了
            
            self.stdout.write(f'  创建步骤: {step.order}. {step.name}')

        self.stdout.write(
            self.style.SUCCESS(f'成功创建执行方案: {plan_name}')
        )
        self.stdout.write(
            self.style.SUCCESS(f'方案ID: {execution_plan.id}')
        )
        self.stdout.write(
            self.style.SUCCESS(f'包含 {execution_plan.steps.count()} 个步骤')
        )
        self.stdout.write(
            self.style.SUCCESS(f'目标主机数: {len(hosts)}')
        )
        
        # 显示主机列表
        self.stdout.write(self.style.SUCCESS('\n目标主机:'))
        for host in hosts:
            self.stdout.write(f'  - {host.name} ({host.ip_address}:{host.port})')
            
        # 显示模板的全局参数
        self.stdout.write(self.style.SUCCESS('\n模板全局参数:'))
        for key, value in template.global_parameters.items():
            self.stdout.write(f'  - {key}: {value}')
        
        self.stdout.write(
            self.style.SUCCESS('\n✅ 执行方案创建完成！')
        )
        self.stdout.write(
            self.style.SUCCESS('现在可以在前端执行这个方案来测试实时日志功能了。')
        )
        self.stdout.write(
            self.style.SUCCESS('预计执行时间: 15分钟')
        )
