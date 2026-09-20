import pytest

from apps.system_config.models import SystemConfig
from apps.system_config.serializers import (
    NotificationConfigSerializer,
    SENSITIVE_CONFIG_VALUE,
    SystemConfigSerializer,
    SystemConfigUpdateSerializer,
)


pytestmark = pytest.mark.django_db


@pytest.mark.parametrize('value', ['', None, SENSITIVE_CONFIG_VALUE])
def test_sensitive_config_placeholder_keeps_existing_value(value):
    config = SystemConfig.objects.create(
        key='integration.api_key',
        value='real-secret',
        category='security',
    )
    serializer = SystemConfigUpdateSerializer(
        config,
        data={'value': value, 'description': 'updated'},
        partial=True,
    )

    assert serializer.is_valid(), serializer.errors
    serializer.save()
    config.refresh_from_db()

    assert config.value == 'real-secret'
    assert config.description == 'updated'
    assert serializer.data['value'] == SENSITIVE_CONFIG_VALUE


def test_system_config_response_masks_credential_value():
    config = SystemConfig.objects.create(
        key='cloud.provider.credential',
        value='credential-value',
        category='security',
    )

    assert SystemConfigSerializer(config).data['value'] == SENSITIVE_CONFIG_VALUE


def test_notification_webhook_accepts_mask_placeholder():
    serializer = NotificationConfigSerializer(data={
        'dingtalk_enabled': True,
        'dingtalk_webhook': SENSITIVE_CONFIG_VALUE,
        'feishu_enabled': False,
        'feishu_webhook': '',
        'wechatwork_enabled': False,
        'wechatwork_webhook': '',
        'levels': ['error'],
    })

    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data['dingtalk_webhook'] == SENSITIVE_CONFIG_VALUE
