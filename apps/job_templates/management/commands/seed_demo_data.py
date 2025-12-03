"""
为整个平台创建一批可开箱演示的数据：
- 演示用户（若不存在）
- 主机分组、主机、服务器账号
- 作业模板（含步骤）与执行方案
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction
from apps.hosts.models import HostGroup, Host, ServerAccount
from apps.job_templates.models import JobTemplate, JobStep, ExecutionPlan, PlanStep
from apps.job_templates.sync_service import TemplateChangeDetector


class Command(BaseCommand):
    help = "创建演示环境所需的基础数据，重复执行会复用已有对象"

    def handle(self, *args, **options):
        with transaction.atomic():
            operator = self._ensure_demo_user()
            account = self._ensure_server_account()
            groups = self._ensure_host_groups(operator)
            hosts = self._ensure_hosts(operator, account, groups)
            template = self._ensure_job_template(operator, account, hosts)
            plan = self._ensure_execution_plan(operator, template)

        self.stdout.write(self.style.SUCCESS("✅ 演示数据创建完毕"))
        self.stdout.write(f"- demo 用户: {operator.username}")
        self.stdout.write(f"- 服务器账号: {account.name}")
        self.stdout.write(f"- 主机数量: {len(hosts)}")
        self.stdout.write(f"- 作业模板: {template.name}")
        self.stdout.write(f"- 执行方案: {plan.name}")

    def _ensure_demo_user(self) -> User:
        user = User.objects.filter(is_superuser=True).first()
        if user:
            return user
        return User.objects.create_superuser(
            username="demo_admin",
            email="demo@example.com",
            password="DemoPass123!",
        )

    def _ensure_server_account(self) -> ServerAccount:
        account, _ = ServerAccount.objects.get_or_create(
            name="演示运维账号",
            defaults={
                "username": "deploy",
                "password": "demo_password",
                "description": "用于演示的统一执行账号",
            },
        )
        return account

    def _ensure_host_groups(self, operator: User) -> dict:
        root_group, _ = HostGroup.objects.get_or_create(
            name="演示集群",
            defaults={
                "description": "演示环境根分组",
                "created_by": operator,
                "sort_order": 1,
            },
        )
        prod_group, _ = HostGroup.objects.get_or_create(
            name="生产集群",
            parent=root_group,
            defaults={
                "description": "生产环境主机",
                "created_by": operator,
                "sort_order": 2,
            },
        )
        staging_group, _ = HostGroup.objects.get_or_create(
            name="预发布集群",
            parent=root_group,
            defaults={
                "description": "预发布/灰度环境主机",
                "created_by": operator,
                "sort_order": 3,
            },
        )
        return {
            "root": root_group,
            "prod": prod_group,
            "staging": staging_group,
        }

    def _ensure_hosts(self, operator: User, account: ServerAccount, groups: dict) -> list:
        host_specs = [
            {
                "name": "web-01",
                "ip": "10.0.0.11",
                "group": groups["prod"],
                "role": "Web 前端",
            },
            {
                "name": "web-02",
                "ip": "10.0.0.12",
                "group": groups["prod"],
                "role": "Web 前端",
            },
            {
                "name": "app-01",
                "ip": "10.0.1.21",
                "group": groups["staging"],
                "role": "业务服务",
            },
        ]

        hosts = []
        for spec in host_specs:
            host, _ = Host.objects.get_or_create(
                ip_address=spec["ip"],
                defaults={
                    "name": spec["name"],
                    "port": 22,
                    "os_type": "linux",
                    "username": account.username,
                    "auth_type": "password",
                    "password": account.password,
                    "status": "online",
                    "description": f"{spec['role']}（演示数据）",
                    "environment": "prod",
                    "created_by": operator,
                },
            )
            host.groups.add(spec["group"])
            hosts.append(host)
        return hosts

    def _ensure_job_template(
        self, operator: User, account: ServerAccount, hosts: list
    ) -> JobTemplate:
        template, created = JobTemplate.objects.get_or_create(
            name="演示-蓝绿发布流程",
            defaults={
                "description": "包含文件分发、服务部署与验证的典型流程",
                "category": "演示",
                "tags_json": {"env": "demo", "owner": "platform"},
                "global_parameters": {
                    "package_url": "https://demo-artifacts.local/app.tar.gz",
                    "service_name": "demo-service",
                },
                "created_by": operator,
            },
        )

        if created:
            template.steps.all().delete()
            self._create_template_steps(template, account, hosts)
        elif template.steps.count() == 0:
            self._create_template_steps(template, account, hosts)

        return template

    def _create_template_steps(
        self, template: JobTemplate, account: ServerAccount, hosts: list
    ):
        target_host_ids = [host.id for host in hosts[:2]]

        file_step = JobStep.objects.create(
            template=template,
            name="分发制品",
            description="将最新制品推送到目标主机",
            step_type="file_transfer",
            order=1,
            step_parameters=[],
            timeout=300,
            ignore_error=False,
            transfer_type="upload",
            local_path="/data/packages/demo-service.tar.gz",
            remote_path="/tmp/demo-service.tar.gz",
            overwrite_policy="overwrite",
        )
        file_step.target_hosts.set(target_host_ids)

        deploy_step = JobStep.objects.create(
            template=template,
            name="部署并重启服务",
            description="解压并重启 systemd 服务",
            step_type="script",
            order=2,
            step_parameters=[],
            timeout=600,
            ignore_error=False,
            script_type="shell",
            script_content=(
                "cd /opt/demo-service && \\\n"
                "tar -xf /tmp/demo-service.tar.gz && \\\n"
                "systemctl restart demo-service && \\\n"
                "systemctl status demo-service -l --no-pager"
            ),
            account_id=account.id,
        )
        deploy_step.target_hosts.set(target_host_ids)

        verify_step = JobStep.objects.create(
            template=template,
            name="健康检查",
            description="执行 HTTP 探活，失败立即终止",
            step_type="script",
            order=3,
            step_parameters=[],
            timeout=120,
            ignore_error=False,
            script_type="shell",
            script_content=(
                "curl -fsS http://127.0.0.1:8080/healthz || exit 1\n"
                "echo 'health check passed'"
            ),
            account_id=account.id,
        )
        verify_step.target_hosts.set(target_host_ids)

    def _ensure_execution_plan(
        self, operator: User, template: JobTemplate
    ) -> ExecutionPlan:
        plan, created = ExecutionPlan.objects.get_or_create(
            template=template,
            name="演示-生产全量发布",
            defaults={
                "description": "包含全部步骤的发布方案",
                "created_by": operator,
                "global_parameters_snapshot": template.global_parameters,
            },
        )

        if created or plan.planstep_set.count() == 0:
            plan.planstep_set.all().delete()
            for step in template.steps.all().order_by("order"):
                plan_step = PlanStep.objects.create(
                    plan=plan,
                    step=step,
                    order=step.order,
                    step_hash=TemplateChangeDetector.calculate_step_hash(step),
                )
                plan_step.copy_from_template_step()
                plan_step.save()

        return plan

