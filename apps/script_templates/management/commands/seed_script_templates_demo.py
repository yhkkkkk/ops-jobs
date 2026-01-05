"""
创建一批脚本模板 demo 数据，用于演示脚本库功能。
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction
from apps.script_templates.models import ScriptTemplate


class Command(BaseCommand):
    help = "创建脚本模板演示数据（可重复执行，已存在则跳过）"

    def handle(self, *args, **options):
        with transaction.atomic():
            creator = self._get_creator()
            created = self._ensure_templates(creator)

        if created:
            self.stdout.write(self.style.SUCCESS(f"✅ 新增 {created} 条脚本模板 demo 数据"))
        else:
            self.stdout.write(self.style.NOTICE("脚本模板 demo 数据已存在，无需重复创建"))

    def _get_creator(self) -> User:
        user = User.objects.filter(is_superuser=True).first()
        if user:
            return user
        return User.objects.create_superuser(
            username="demo_admin",
            email="demo@example.com",
            password="DemoPass123!",
        )

    def _ensure_templates(self, creator: User) -> int:
        demo_specs = [
            {
                "name": "系统巡检脚本",
                "description": "收集 CPU/内存/磁盘等资源使用情况",
                "script_type": "shell",
                "category": "monitoring",
                "script_content": """#!/bin/bash
set -e
echo "=== 基础信息 ==="
hostname
uptime

echo "=== CPU 使用情况 ==="
top -bn1 | head -n5

echo "=== 内存 ==="
free -h

echo "=== 磁盘 ==="
df -h | grep -E '/$|/data'
""",
                "tags": {"env": "prod", "type": "inspect"},
            },
            {
                "name": "Nginx 平滑重载",
                "description": "提前执行配置自检，成功后平滑重启",
                "script_type": "shell",
                "category": "maintenance",
                "script_content": """#!/bin/bash
set -e
nginx -t
systemctl reload nginx
echo "Nginx reloaded successfully"
""",
                "tags": {"service": "nginx"},
            },
            {
                "name": "Python 进程内存泄漏快照",
                "description": "使用 tracemalloc 输出热点并 dump 到文件",
                "script_type": "python",
                "category": "monitoring",
                "script_content": """#!/usr/bin/env python3
import tracemalloc
import time

tracemalloc.start()
time.sleep(3)

snapshot = tracemalloc.take_snapshot()
top_stats = snapshot.statistics('lineno')[:15]

for stat in top_stats:
    print(stat)
""",
                "tags": {"lang": "python", "usage": "debug"},
            },
            {
                "name": "Windows IIS 重启",
                "description": "用于 PowerShell 下重启 IIS 并输出站点状态",
                "script_type": "powershell",
                "category": "maintenance",
                "script_content": """Import-Module WebAdministration
iisreset /restart
Get-Website | Select-Object name,state,physicalPath
""",
                "tags": {"os": "windows"},
            },
        ]

        created = 0
        for spec in demo_specs:
            template, is_created = ScriptTemplate.objects.get_or_create(
                name=spec["name"],
                defaults={
                    "description": spec["description"],
                    "script_type": spec["script_type"],
                    "template_type": "system",
                    "category": spec["category"],
                    "script_content": spec["script_content"],
                    "version": "1.0.0",
                    "is_active": True,
                    "tags_json": spec["tags"],
                    "usage_count": 0,
                    "is_public": True,
                    "created_by": creator,
                },
            )
            if is_created:
                created += 1
        return created

