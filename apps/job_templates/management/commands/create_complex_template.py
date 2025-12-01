"""
创建复杂的作业模板用于测试实时日志
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from apps.job_templates.models import JobTemplate, JobStep


class Command(BaseCommand):
    help = '创建一个包含多个步骤的复杂作业模板用于测试实时日志'

    def handle(self, *args, **options):
        # 获取管理员用户
        try:
            admin_user = User.objects.filter(is_superuser=True).first()
            if not admin_user:
                admin_user = User.objects.create_superuser(
                    username='admin',
                    email='admin@example.com',
                    password='admin123'
                )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'获取管理员用户失败: {e}')
            )
            return

        # 创建复杂的作业模板
        template_name = "系统维护与监控作业"
        
        # 检查是否已存在
        if JobTemplate.objects.filter(name=template_name).exists():
            self.stdout.write(
                self.style.WARNING(f'作业模板 "{template_name}" 已存在，跳过创建')
            )
            return

        # 创建作业模板
        job_template = JobTemplate.objects.create(
            name=template_name,
            description="包含系统检查、清理、备份、监控等多个步骤的综合维护作业，用于测试实时日志功能",
            category="系统维护",
            created_by=admin_user,
            tags_json=["系统维护", "监控", "备份", "清理", "测试"],
            global_parameters={
                "backup_path": "/tmp/backup",
                "log_days": "7",
                "check_interval": "5"
            }
        )

        # 步骤1: 系统信息收集
        JobStep.objects.create(
            template=job_template,
            name="系统信息收集",
            description="收集系统基本信息，包括CPU、内存、磁盘使用情况",
            step_type="script",
            order=1,
            script_type="shell",
            script_content="""#!/bin/bash
echo "=== 开始收集系统信息 ==="
echo "当前时间: $(date)"
echo "主机名: $(hostname)"
echo "操作系统: $(cat /etc/os-release | grep PRETTY_NAME)"
echo ""

echo "=== CPU信息 ==="
lscpu | head -20
echo ""

echo "=== 内存使用情况 ==="
free -h
echo ""

echo "=== 磁盘使用情况 ==="
df -h
echo ""

echo "=== 网络接口信息 ==="
ip addr show | grep -E "inet|link"
echo ""

echo "=== 系统负载 ==="
uptime
echo ""

echo "=== 正在运行的进程数 ==="
ps aux | wc -l
echo "系统信息收集完成"
sleep 3
""",
            timeout=60,
            ignore_error=False,
            step_parameters=[]
        )

        # 步骤2: 磁盘空间检查
        JobStep.objects.create(
            template=job_template,
            name="磁盘空间检查",
            description="检查各分区磁盘使用率，警告空间不足的分区",
            step_type="script",
            order=2,
            script_type="shell",
            script_content="""#!/bin/bash
echo "=== 开始磁盘空间检查 ==="

# 设置警告阈值（80%）
THRESHOLD=80

echo "磁盘使用率检查（警告阈值: ${THRESHOLD}%）"
echo "----------------------------------------"

# 检查每个分区
df -h | grep -vE '^Filesystem|tmpfs|cdrom' | awk '{ print $5 " " $1 " " $6 }' | while read output;
do
    usage=$(echo $output | awk '{ print $1}' | cut -d'%' -f1)
    partition=$(echo $output | awk '{ print $2 }')
    mount_point=$(echo $output | awk '{ print $3 }')
    
    echo "检查分区: $partition (挂载点: $mount_point) - 使用率: ${usage}%"
    
    if [ $usage -ge $THRESHOLD ]; then
        echo "⚠️  警告: 分区 $partition 使用率过高 (${usage}%)"
    else
        echo "✅ 正常: 分区 $partition 使用率正常 (${usage}%)"
    fi
    
    sleep 2
done

echo ""
echo "=== 查找大文件 (>100MB) ==="
find /var/log -type f -size +100M -exec ls -lh {} \\; 2>/dev/null | head -10 || echo "未找到大文件"

echo "磁盘空间检查完成"
sleep 2
""",
            timeout=120,
            ignore_error=False,
            step_parameters=[]
        )

        # 步骤3: 日志清理
        JobStep.objects.create(
            template=job_template,
            name="日志文件清理",
            description="清理超过指定天数的日志文件，释放磁盘空间",
            step_type="script",
            order=3,
            script_type="shell",
            script_content="""#!/bin/bash
echo "=== 开始日志文件清理 ==="

# 从参数获取保留天数，默认7天
DAYS=${1:-7}
echo "清理 ${DAYS} 天前的日志文件"

# 定义要清理的日志目录
LOG_DIRS="/var/log /tmp"

for dir in $LOG_DIRS; do
    if [ -d "$dir" ]; then
        echo "正在检查目录: $dir"
        
        # 查找并显示将要删除的文件
        echo "查找 ${DAYS} 天前的日志文件..."
        find $dir -name "*.log*" -type f -mtime +$DAYS 2>/dev/null | head -10 | while read file; do
            echo "  发现旧日志: $file"
            sleep 1
        done
        
        # 统计文件数量
        count=$(find $dir -name "*.log*" -type f -mtime +$DAYS 2>/dev/null | wc -l)
        echo "  找到 $count 个旧日志文件"
        
        if [ $count -gt 0 ]; then
            echo "  正在清理旧日志文件..."
            # 实际环境中取消注释下面这行来执行删除
            # find $dir -name "*.log*" -type f -mtime +$DAYS -delete 2>/dev/null
            echo "  ✅ 模拟清理完成 ($count 个文件)"
        else
            echo "  ✅ 无需清理"
        fi
        
        sleep 2
    else
        echo "目录不存在: $dir"
    fi
done

echo ""
echo "=== 清理临时文件 ==="
echo "正在清理 /tmp 目录中的临时文件..."
# find /tmp -type f -atime +1 -delete 2>/dev/null
echo "✅ 临时文件清理完成"

echo "日志文件清理任务完成"
sleep 2
""",
            timeout=180,
            ignore_error=True,  # 允许清理失败
            step_parameters=["${log_days}"]
        )

        # 步骤4: 服务状态检查
        JobStep.objects.create(
            template=job_template,
            name="服务状态检查",
            description="检查关键系统服务的运行状态",
            step_type="script",
            order=4,
            script_type="shell",
            script_content="""#!/bin/bash
echo "=== 开始服务状态检查 ==="

# 定义要检查的服务列表
SERVICES="ssh cron rsyslog"

echo "检查关键系统服务状态..."
echo "----------------------------------------"

for service in $SERVICES; do
    echo "正在检查服务: $service"

    if systemctl is-active --quiet $service 2>/dev/null; then
        echo "✅ $service: 运行中"

        # 获取服务详细信息
        echo "   启动时间: $(systemctl show $service --property=ActiveEnterTimestamp --value 2>/dev/null || echo '未知')"
        echo "   进程ID: $(systemctl show $service --property=MainPID --value 2>/dev/null || echo '未知')"
    else
        echo "❌ $service: 未运行或不存在"
    fi

    sleep 2
done

echo ""
echo "=== 检查系统负载 ==="
echo "当前负载: $(uptime | awk -F'load average:' '{print $2}')"

echo ""
echo "=== 检查内存使用 ==="
free -h | grep -E "Mem|Swap"

echo ""
echo "=== 检查网络连接 ==="
echo "活动网络连接数: $(netstat -an 2>/dev/null | grep ESTABLISHED | wc -l || echo '无法获取')"

echo "服务状态检查完成"
sleep 3
""",
            timeout=90,
            ignore_error=False,
            step_parameters=[]
        )

        # 步骤5: 数据备份模拟
        JobStep.objects.create(
            template=job_template,
            name="数据备份操作",
            description="模拟重要数据的备份过程",
            step_type="script",
            order=5,
            script_type="shell",
            script_content="""#!/bin/bash
echo "=== 开始数据备份操作 ==="

# 从参数获取备份路径
BACKUP_PATH=${1:-/tmp/backup}
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="$BACKUP_PATH/backup_$TIMESTAMP"

echo "备份目标路径: $BACKUP_DIR"

# 创建备份目录
echo "创建备份目录..."
mkdir -p "$BACKUP_DIR"
if [ $? -eq 0 ]; then
    echo "✅ 备份目录创建成功: $BACKUP_DIR"
else
    echo "❌ 备份目录创建失败"
    exit 1
fi

sleep 2

echo ""
echo "=== 备份系统配置文件 ==="
CONFIG_FILES="/etc/hosts /etc/hostname /etc/passwd"

for file in $CONFIG_FILES; do
    if [ -f "$file" ]; then
        echo "正在备份: $file"
        cp "$file" "$BACKUP_DIR/" 2>/dev/null
        if [ $? -eq 0 ]; then
            echo "✅ 备份成功: $(basename $file)"
        else
            echo "❌ 备份失败: $(basename $file)"
        fi
    else
        echo "⚠️  文件不存在: $file"
    fi
    sleep 1
done

echo ""
echo "=== 创建系统信息快照 ==="
echo "生成系统信息文件..."

{
    echo "备份时间: $(date)"
    echo "系统信息: $(uname -a)"
    echo "磁盘使用: "
    df -h
    echo ""
    echo "内存信息: "
    free -h
    echo ""
    echo "进程信息: "
    ps aux | head -20
} > "$BACKUP_DIR/system_info.txt"

echo "✅ 系统信息快照已保存"

sleep 2

echo ""
echo "=== 压缩备份文件 ==="
cd "$BACKUP_PATH"
ARCHIVE_NAME="backup_$TIMESTAMP.tar.gz"

echo "正在压缩备份文件..."
tar -czf "$ARCHIVE_NAME" "backup_$TIMESTAMP" 2>/dev/null

if [ $? -eq 0 ]; then
    echo "✅ 备份压缩完成: $ARCHIVE_NAME"
    echo "备份文件大小: $(ls -lh $ARCHIVE_NAME | awk '{print $5}')"

    # 清理临时目录
    rm -rf "$BACKUP_DIR"
    echo "✅ 临时文件清理完成"
else
    echo "❌ 备份压缩失败"
fi

echo ""
echo "=== 备份验证 ==="
if [ -f "$BACKUP_PATH/$ARCHIVE_NAME" ]; then
    echo "✅ 备份文件验证通过"
    echo "备份位置: $BACKUP_PATH/$ARCHIVE_NAME"
else
    echo "❌ 备份文件验证失败"
fi

echo "数据备份操作完成"
sleep 3
""",
            timeout=240,
            ignore_error=False,
            step_parameters=["${backup_path}"]
        )

        # 步骤6: 性能监控
        JobStep.objects.create(
            template=job_template,
            name="系统性能监控",
            description="持续监控系统性能指标一段时间",
            step_type="script",
            order=6,
            script_type="shell",
            script_content="""#!/bin/bash
echo "=== 开始系统性能监控 ==="

# 从参数获取监控间隔，默认5秒
INTERVAL=${1:-5}
DURATION=30  # 监控30秒

echo "监控间隔: ${INTERVAL}秒"
echo "监控时长: ${DURATION}秒"
echo "----------------------------------------"

START_TIME=$(date +%s)
COUNTER=0

while [ $(($(date +%s) - START_TIME)) -lt $DURATION ]; do
    COUNTER=$((COUNTER + 1))
    CURRENT_TIME=$(date '+%H:%M:%S')

    echo "[$CURRENT_TIME] 第 $COUNTER 次监控检查"

    # CPU使用率
    CPU_USAGE=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1 2>/dev/null || echo "0")
    echo "  CPU使用率: ${CPU_USAGE}%"

    # 内存使用率
    MEM_INFO=$(free | grep Mem)
    MEM_TOTAL=$(echo $MEM_INFO | awk '{print $2}')
    MEM_USED=$(echo $MEM_INFO | awk '{print $3}')
    MEM_PERCENT=$(awk "BEGIN {printf \"%.1f\", $MEM_USED/$MEM_TOTAL*100}")
    echo "  内存使用率: ${MEM_PERCENT}%"

    # 磁盘I/O (简化版)
    DISK_USAGE=$(df / | tail -1 | awk '{print $5}' | cut -d'%' -f1)
    echo "  根分区使用率: ${DISK_USAGE}%"

    # 系统负载
    LOAD_AVG=$(uptime | awk -F'load average:' '{print $2}' | awk '{print $1}' | cut -d',' -f1)
    echo "  系统负载: ${LOAD_AVG}"

    # 网络连接数
    CONNECTIONS=$(netstat -an 2>/dev/null | grep ESTABLISHED | wc -l || echo "0")
    echo "  活动连接数: ${CONNECTIONS}"

    echo "  ----------------------------------------"

    sleep $INTERVAL
done

echo ""
echo "=== 监控总结 ==="
echo "监控完成，共进行了 $COUNTER 次检查"
echo "平均监控间隔: ${INTERVAL}秒"

# 最终系统状态
echo ""
echo "=== 最终系统状态 ==="
echo "时间: $(date)"
echo "运行时间: $(uptime | awk '{print $3,$4}' | cut -d',' -f1)"
echo "当前用户: $(whoami)"
echo "系统性能监控完成"
sleep 2
""",
            timeout=120,
            ignore_error=True,
            step_parameters=["${check_interval}"]
        )

        # 步骤7: 清理和总结
        JobStep.objects.create(
            template=job_template,
            name="清理和总结报告",
            description="清理临时文件并生成执行总结报告",
            step_type="script",
            order=7,
            script_type="shell",
            script_content="""#!/bin/bash
echo "=== 开始清理和总结 ==="

REPORT_FILE="/tmp/maintenance_report_$(date +%Y%m%d_%H%M%S).txt"

echo "生成维护报告: $REPORT_FILE"
echo "========================================"

# 创建报告文件
{
    echo "系统维护与监控作业执行报告"
    echo "========================================"
    echo "执行时间: $(date)"
    echo "执行用户: $(whoami)"
    echo "主机名: $(hostname)"
    echo ""

    echo "执行步骤总结:"
    echo "1. ✅ 系统信息收集 - 完成"
    echo "2. ✅ 磁盘空间检查 - 完成"
    echo "3. ✅ 日志文件清理 - 完成"
    echo "4. ✅ 服务状态检查 - 完成"
    echo "5. ✅ 数据备份操作 - 完成"
    echo "6. ✅ 系统性能监控 - 完成"
    echo "7. ✅ 清理和总结报告 - 进行中"
    echo ""

    echo "系统当前状态:"
    echo "----------------------------------------"
    echo "CPU信息: $(lscpu | grep "Model name" | cut -d':' -f2 | xargs)"
    echo "内存总量: $(free -h | grep Mem | awk '{print $2}')"
    echo "磁盘使用: $(df -h / | tail -1 | awk '{print $5}')"
    echo "系统负载: $(uptime | awk -F'load average:' '{print $2}')"
    echo ""

    echo "维护建议:"
    echo "----------------------------------------"
    echo "- 定期执行此维护作业"
    echo "- 监控磁盘空间使用情况"
    echo "- 及时清理日志文件"
    echo "- 保持系统服务正常运行"
    echo "- 定期备份重要数据"
    echo ""

    echo "报告生成时间: $(date)"
    echo "========================================"

} > "$REPORT_FILE"

echo "✅ 维护报告已生成: $REPORT_FILE"

# 显示报告内容
echo ""
echo "=== 报告内容预览 ==="
head -20 "$REPORT_FILE"
echo "... (完整报告请查看文件)"

sleep 2

echo ""
echo "=== 清理临时文件 ==="
echo "正在清理执行过程中产生的临时文件..."

# 清理可能的临时文件
find /tmp -name "maintenance_*" -type f -mmin +60 2>/dev/null | head -5 | while read file; do
    echo "清理临时文件: $file"
    # rm -f "$file"  # 实际环境中取消注释
    sleep 1
done

echo "✅ 临时文件清理完成"

echo ""
echo "=== 作业执行完成 ==="
echo "所有维护步骤已成功执行"
echo "执行时间: $(date)"
echo "感谢使用系统维护作业模板！"

sleep 3
""",
            timeout=90,
            ignore_error=False,
            step_parameters=[]
        )

        self.stdout.write(
            self.style.SUCCESS(f'成功创建作业模板: {template_name}')
        )
        self.stdout.write(
            self.style.SUCCESS(f'模板ID: {job_template.id}')
        )
        self.stdout.write(
            self.style.SUCCESS(f'包含 {job_template.steps.count()} 个步骤')
        )

        # 显示步骤列表
        steps = job_template.steps.all().order_by('order')
        self.stdout.write(self.style.SUCCESS('\n步骤列表:'))
        for step in steps:
            self.stdout.write(f'  {step.order}. {step.name} ({step.timeout}秒)')

        total_time = sum(step.timeout for step in steps)
        self.stdout.write(f'\n预计总执行时间: {total_time}秒 ({total_time//60}分{total_time%60}秒)')

        self.stdout.write(
            self.style.SUCCESS('\n✅ 复杂作业模板创建完成！现在可以用来测试实时日志功能了。')
        )
