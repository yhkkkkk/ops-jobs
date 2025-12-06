from django.db import models
from django.contrib.auth.models import User


class HostGroup(models.Model):
    """主机分组"""
    name = models.CharField(max_length=100, verbose_name="分组名称")
    description = models.TextField(blank=True, verbose_name="描述")
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE,
                              related_name='children', verbose_name="父分组")
    sort_order = models.IntegerField(default=0, verbose_name="排序")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="创建人")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "主机分组"
        verbose_name_plural = "主机分组"
        ordering = ['sort_order', 'name']
        permissions = [
            ('manage_hostgroup', '管理主机分组'),
        ]

    def __str__(self):
        return self.name

    @property
    def full_path(self):
        """获取完整路径"""
        if self.parent:
            return f"{self.parent.full_path} / {self.name}"
        return self.name

    @property
    def level(self):
        """获取层级深度"""
        if self.parent:
            return self.parent.level + 1
        return 0

    def get_descendants(self, include_self=False):
        """获取所有子孙节点"""
        descendants = []
        if include_self:
            descendants.append(self)

        for child in self.children.all():
            descendants.extend(child.get_descendants(include_self=True))

        return descendants

    def get_ancestors(self, include_self=False):
        """获取所有祖先节点"""
        ancestors = []
        if include_self:
            ancestors.append(self)

        if self.parent:
            ancestors.extend(self.parent.get_ancestors(include_self=True))

        return ancestors

    def can_move_to(self, target_parent):
        """检查是否可以移动到目标父节点"""
        if target_parent is None:
            return True

        # 不能移动到自己或自己的子节点
        if target_parent == self or target_parent in self.get_descendants():
            return False

        return True


class Host(models.Model):
    """主机信息"""
    OS_CHOICES = [
        ('linux', 'Linux'),
        ('windows', 'Windows'),
        ('aix', 'AIX'),
        ('solaris', 'Solaris'),
    ]

    STATUS_CHOICES = [
        ('online', '在线'),
        ('offline', '离线'),
        ('unknown', '未知'),
    ]

    CLOUD_PROVIDER_CHOICES = [
        ('aliyun', '阿里云'),
        ('tencent', '腾讯云'),
        ('aws', 'AWS'),
        ('azure', 'Azure'),
        ('huawei', '华为云'),
        ('baidu', '百度云'),
        ('ucloud', 'UCloud'),
        ('qiniu', '七牛云'),
        ('idc', '自建机房'),
        ('other', '其他'),
    ]

    DEVICE_TYPE_CHOICES = [
        ('vm', '虚拟机'),
        ('container', '容器'),
        ('physical', '物理机'),
        ('k8s_node', 'K8s节点'),
    ]

    ENVIRONMENT_CHOICES = [
        ('dev', '开发环境'),
        ('test', '测试环境'),
        ('staging', '预生产环境'),
        ('prod', '生产环境'),
    ]

    # === 基本信息 ===
    name = models.CharField(max_length=100, verbose_name="主机名")
    port = models.IntegerField(default=22, verbose_name="SSH端口")
    os_type = models.CharField(max_length=20, choices=OS_CHOICES, verbose_name="操作系统")
    account = models.ForeignKey('ServerAccount', on_delete=models.PROTECT, null=True, blank=True, 
                               verbose_name="服务器账号", related_name='hosts',
                               help_text="用于SSH连接的服务器账号，如果为空则需要在执行时指定")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='unknown', verbose_name="状态")
    groups = models.ManyToManyField(HostGroup, blank=True, verbose_name="所属分组")
    description = models.TextField(blank=True, verbose_name="描述")

    # === 网络信息 ===
    public_ip = models.GenericIPAddressField(null=True, blank=True, verbose_name="外网IP")
    internal_ip = models.GenericIPAddressField(null=True, blank=True, verbose_name="内网IP")
    internal_mac = models.CharField(max_length=17, blank=True, verbose_name="内网MAC地址")
    external_mac = models.CharField(max_length=17, blank=True, verbose_name="外网MAC地址")
    gateway = models.GenericIPAddressField(null=True, blank=True, verbose_name="网关")
    dns_servers = models.CharField(max_length=255, blank=True, verbose_name="DNS服务器")

    # === 云厂商信息 ===
    cloud_provider = models.CharField(max_length=20, choices=CLOUD_PROVIDER_CHOICES, null=True, blank=True, verbose_name="云厂商")
    instance_id = models.CharField(max_length=100, null=True, blank=True, verbose_name="实例ID")
    region = models.CharField(max_length=50, null=True, blank=True, verbose_name="地域")
    zone = models.CharField(max_length=50, null=True, blank=True, verbose_name="可用区")
    instance_type = models.CharField(max_length=50, null=True, blank=True, verbose_name="实例类型")
    network_type = models.CharField(max_length=50, null=True, blank=True, verbose_name="网络类型")

    # === 硬件信息 ===
    device_type = models.CharField(max_length=20, choices=DEVICE_TYPE_CHOICES, default='vm', verbose_name="设备类型")
    cpu_cores = models.IntegerField(null=True, blank=True, verbose_name="CPU核心数")
    memory_gb = models.FloatField(null=True, blank=True, verbose_name="内存(GB)")
    disk_gb = models.FloatField(null=True, blank=True, verbose_name="磁盘(GB)")

    # === 系统详细信息 ===
    os_version = models.CharField(max_length=100, null=True, blank=True, verbose_name="操作系统版本")
    kernel_version = models.CharField(max_length=100, null=True, blank=True, verbose_name="内核版本")
    hostname = models.CharField(max_length=100, null=True, blank=True, verbose_name="主机名称")
    cpu_model = models.CharField(max_length=200, null=True, blank=True, verbose_name="CPU型号")
    os_arch = models.CharField(max_length=50, null=True, blank=True, verbose_name="操作系统位数")
    cpu_arch = models.CharField(max_length=50, null=True, blank=True, verbose_name="CPU架构")
    boot_time = models.DateTimeField(null=True, blank=True, verbose_name="系统启动时间")

    # === 业务信息 ===
    environment = models.CharField(max_length=20, choices=ENVIRONMENT_CHOICES, null=True, blank=True, verbose_name="环境类型")
    business_system = models.CharField(max_length=100, null=True, blank=True, verbose_name="业务系统")
    service_role = models.CharField(max_length=100, null=True, blank=True, verbose_name="服务角色")
    remarks = models.TextField(blank=True, verbose_name="备注")

    # === 管理信息 ===
    owner = models.CharField(max_length=100, null=True, blank=True, verbose_name="负责人")
    department = models.CharField(max_length=100, null=True, blank=True, verbose_name="所属部门")

    # === 时间信息 ===
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="创建人")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")
    last_check_time = models.DateTimeField(null=True, blank=True, verbose_name="最后检查时间")

    class Meta:
        verbose_name = "主机"
        verbose_name_plural = "主机"
        permissions = [
            ('execute_host', '在主机上执行操作'),
        ]

    def __str__(self):
        # 优先显示内网IP，如果没有则显示外网IP
        display_ip = self.internal_ip or self.public_ip or 'N/A'
        return f"{self.name}({display_ip})"
    
    @property
    def ip_address(self):
        """兼容属性：返回内网IP或外网IP（优先内网IP）"""
        return self.internal_ip or self.public_ip


class ServerAccount(models.Model):
    """服务器账号"""

    name = models.CharField(max_length=100, verbose_name='账号名称')
    username = models.CharField(max_length=50, verbose_name='用户名')
    password = models.TextField(blank=True, verbose_name='密码')
    private_key = models.TextField(blank=True, verbose_name='私钥')
    description = models.TextField(blank=True, verbose_name='描述')

    class Meta:
        verbose_name = '服务器账号'
        verbose_name_plural = '服务器账号'

    def __str__(self):
        return f"{self.name} ({self.username})"
