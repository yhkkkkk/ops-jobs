"""
仪表盘序列化器
"""
from rest_framework import serializers


class DashboardOverviewSerializer(serializers.Serializer):
    """仪表盘概览数据序列化器"""
    
    # 主机统计
    total_hosts = serializers.IntegerField(help_text="主机总数")
    online_hosts = serializers.IntegerField(help_text="在线主机数")
    offline_hosts = serializers.IntegerField(help_text="离线主机数")
    
    # 模板统计
    total_templates = serializers.IntegerField(help_text="模板总数")
    total_plans = serializers.IntegerField(help_text="执行方案总数")
    
    # 执行统计
    total_executions = serializers.IntegerField(help_text="执行记录总数")
    today_executions = serializers.IntegerField(help_text="今日执行数")
    success_rate = serializers.FloatField(help_text="成功率")
    
    # 定时任务统计
    total_scheduled_jobs = serializers.IntegerField(help_text="定时任务总数")
    active_scheduled_jobs = serializers.IntegerField(help_text="活跃定时任务数")


class DashboardStatisticsSerializer(serializers.Serializer):
    """仪表盘统计数据序列化器"""
    
    execution_trend = serializers.ListField(
        child=serializers.DictField(),
        help_text="执行趋势数据"
    )
    success_rate_trend = serializers.ListField(
        child=serializers.DictField(),
        help_text="成功率趋势数据"
    )
    host_status_distribution = serializers.DictField(help_text="主机状态分布")
    template_category_distribution = serializers.DictField(help_text="模板分类分布")


class DashboardRecentActivitySerializer(serializers.Serializer):
    """仪表盘最近活动序列化器"""
    
    recent_executions = serializers.ListField(
        child=serializers.DictField(),
        help_text="最近执行记录"
    )
    recent_templates = serializers.ListField(
        child=serializers.DictField(),
        help_text="最近创建的模板"
    )
    recent_hosts = serializers.ListField(
        child=serializers.DictField(),
        help_text="最近添加的主机"
    )


class DashboardSystemStatusSerializer(serializers.Serializer):
    """仪表盘系统状态序列化器"""
    
    host_status = serializers.DictField(help_text="主机状态统计")
    system_info = serializers.DictField(help_text="系统信息")
    service_status = serializers.DictField(help_text="服务状态")
    last_check = serializers.DateTimeField(help_text="最后检查时间")


class OpsOverviewSerializer(serializers.Serializer):
    """运维台概览数据序列化器（面向运维关注的指标）"""
    
    agents_total = serializers.IntegerField(help_text="Agent 总数")
    agents_online = serializers.IntegerField(help_text="Agent 在线数（computed_status）")
    agents_offline = serializers.IntegerField(help_text="Agent 离线数（computed_status）")
    agents_pending = serializers.IntegerField(help_text="Agent 待激活数（status 字段）")
    agents_disabled = serializers.IntegerField(help_text="Agent 已禁用数（status 字段）")
    running_tasks = serializers.IntegerField(help_text="当前运行任务数")
    fail_rate_24h = serializers.FloatField(help_text="过去24小时任务失败率（%）")
    task_p50_ms = serializers.FloatField(help_text="任务 P50 延时（ms）", default=0.0)
    task_p95_ms = serializers.FloatField(help_text="任务 P95 延时（ms）", default=0.0)
    task_p99_ms = serializers.FloatField(help_text="任务 P99 延时（ms）", default=0.0)
    heartbeat_alerts = serializers.IntegerField(help_text="心跳告警数（离线 agent 数）", default=0)
    heartbeat_alerts_hosts = serializers.ListField(child=serializers.DictField(), help_text="心跳异常主机列表（示例: host_name, agent_id, last_heartbeat_at, threshold_seconds）", default=list)
    top_failure_hosts = serializers.ListField(child=serializers.DictField(), help_text="过去24小时失败最多的主机 TOP 列表", default=list)
    last_updated = serializers.DateTimeField(help_text="数据更新时间")
