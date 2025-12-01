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
