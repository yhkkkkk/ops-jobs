import sys
from types import ModuleType, SimpleNamespace

import pytest
from django.contrib.auth.models import User

from apps.hosts.cloud_sync_service import CloudSyncService
from apps.hosts.models import Host
from apps.system_config.models import ConfigManager


pytestmark = pytest.mark.django_db


class FakeEC2Client:
    def __init__(self, pages):
        self.pages = pages

    def get_paginator(self, operation_name):
        assert operation_name == "describe_instances"
        return SimpleNamespace(paginate=lambda: self.pages)


def _aws_pages(instance):
    return [{"Reservations": [{"Instances": [instance]}]}]


def _configure_aws(monkeypatch, pages):
    values = {
        "cloud.aws.access_key": "access-key",
        "cloud.aws.secret_key": "secret-key",
        "cloud.aws.region": "us-east-1",
    }
    monkeypatch.setattr(ConfigManager, "get", lambda key, default="": values.get(key, default))
    monkeypatch.setitem(sys.modules, "boto3", SimpleNamespace(client=lambda *args, **kwargs: FakeEC2Client(pages)))


def test_sync_aws_hosts_creates_host_from_ec2_instance(monkeypatch):
    user = User.objects.create_user("aws-sync-user", password="pass")
    _configure_aws(
        monkeypatch,
        _aws_pages(
            {
                "InstanceId": "i-0123456789abcdef0",
                "InstanceType": "t3.medium",
                "State": {"Name": "running"},
                "Platform": "windows",
                "PrivateIpAddress": "10.0.0.8",
                "PublicIpAddress": "203.0.113.8",
                "Placement": {"AvailabilityZone": "us-east-1a"},
                "Tags": [{"Key": "Name", "Value": "billing-win"}],
                "CpuOptions": {"CoreCount": 2, "ThreadsPerCore": 2},
                "NetworkInterfaces": [{"Attachment": {"DeviceIndex": 0}, "MacAddress": "02:00:00:00:00:08"}],
            }
        ),
    )

    result = CloudSyncService.sync_cloud_hosts("aws", user=user)

    host = Host.objects.get(cloud_provider="aws", instance_id="i-0123456789abcdef0")
    assert result["success"] is True
    assert result["synced_hosts"] == 1
    assert host.name == "billing-win"
    assert host.os_type == "windows"
    assert host.port == 3389
    assert host.internal_ip == "10.0.0.8"
    assert host.public_ip == "203.0.113.8"
    assert host.internal_mac == "02:00:00:00:00:08"
    assert host.cpu_cores == 4
    assert host.status == "online"


def test_sync_aws_hosts_updates_existing_instance_without_duplicate(monkeypatch):
    user = User.objects.create_user("aws-update-user", password="pass")
    host = Host.objects.create(
        name="old-name",
        os_type="linux",
        device_type="physical",
        cloud_provider="aws",
        instance_id="i-existing",
        region="us-east-1",
        status="online",
        created_by=user,
    )
    _configure_aws(
        monkeypatch,
        _aws_pages(
            {
                "InstanceId": "i-existing",
                "InstanceType": "m7i.large",
                "State": {"Name": "stopped"},
                "PrivateIpAddress": "10.0.0.9",
                "Placement": {"AvailabilityZone": "us-east-1b"},
                "Tags": [{"Key": "Name", "Value": "updated-name"}],
                "NetworkInterfaces": [],
            }
        ),
    )

    result = CloudSyncService.sync_cloud_hosts("aws", user=user)

    host.refresh_from_db()
    assert result["success"] is True
    assert result["synced_hosts"] == 0
    assert result["updated_hosts"] == 1
    assert Host.objects.filter(cloud_provider="aws", instance_id="i-existing").count() == 1
    assert host.name == "updated-name"
    assert host.status == "offline"
    assert host.port == 22
    assert host.zone == "us-east-1b"

def test_sync_aliyun_hosts_creates_host_without_obsolete_credential_fields(monkeypatch):
    user = User.objects.create_user("aliyun-sync-user", password="pass")
    values = {
        "cloud.aliyun.access_key": "access-key",
        "cloud.aliyun.secret_key": "secret-key",
        "cloud.aliyun.region": "cn-hangzhou",
    }
    monkeypatch.setattr(ConfigManager, "get", lambda key, default="": values.get(key, default))

    instance = SimpleNamespace(
        instance_name="aliyun-web",
        instance_id="i-aliyun",
        region_id="cn-hangzhou",
        zone_id="cn-hangzhou-a",
        instance_type="ecs.g6.large",
        os_name="Alibaba Cloud Linux",
        cpu=2,
        memory=4096,
        status="Running",
        network_interfaces=None,
        public_ip_address=None,
    )
    response = SimpleNamespace(body=SimpleNamespace(instances=SimpleNamespace(instance=[instance])))

    class FakeEcsClient:
        def __init__(self, config):
            self.config = config

        def describe_instances(self, request):
            return response

    ecs_package = ModuleType("alibabacloud_ecs20140526")
    ecs_package.__path__ = []
    ecs_client_module = ModuleType("alibabacloud_ecs20140526.client")
    ecs_client_module.Client = FakeEcsClient
    ecs_models_module = ModuleType("alibabacloud_ecs20140526.models")
    ecs_models_module.DescribeInstancesRequest = lambda: object()
    openapi_package = ModuleType("alibabacloud_tea_openapi")
    openapi_package.__path__ = []
    openapi_models_module = ModuleType("alibabacloud_tea_openapi.models")
    openapi_models_module.Config = lambda **kwargs: SimpleNamespace(**kwargs)
    monkeypatch.setitem(sys.modules, "alibabacloud_ecs20140526", ecs_package)
    monkeypatch.setitem(sys.modules, "alibabacloud_ecs20140526.client", ecs_client_module)
    monkeypatch.setitem(sys.modules, "alibabacloud_ecs20140526.models", ecs_models_module)
    monkeypatch.setitem(sys.modules, "alibabacloud_tea_openapi", openapi_package)
    monkeypatch.setitem(sys.modules, "alibabacloud_tea_openapi.models", openapi_models_module)

    result = CloudSyncService.sync_aliyun_hosts(user=user)

    host = Host.objects.get(cloud_provider="aliyun", instance_id="i-aliyun")
    assert result["success"] is True
    assert host.port == 22
    assert host.memory_gb == 4