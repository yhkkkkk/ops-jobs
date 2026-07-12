import os
import uuid
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User

from apps.hosts.fabric_ssh_manager import FabricSSHError, fabric_ssh_manager
from apps.hosts.models import Host, ServerAccount
from apps.hosts.utils import CredentialEncryptionError, encrypt_password


pytestmark = pytest.mark.django_db


def _host_with_account(user, account):
    return Host.objects.create(
        name=f"host-{uuid.uuid4().hex[:6]}",
        os_type="linux",
        device_type="physical",
        internal_ip="127.0.0.1",
        account=account,
        created_by=user,
    )


def test_credential_encryption_fails_closed_when_key_is_unavailable():
    with patch("apps.hosts.utils.get_encryption_key", return_value=None):
        with pytest.raises(CredentialEncryptionError):
            encrypt_password("plain-text-secret")


def test_fabric_decrypts_private_key_before_writing_temporary_key_file():
    user = User.objects.create_user(f"key-{uuid.uuid4().hex[:6]}", password="pass")
    private_key = "-----BEGIN PRIVATE KEY-----\nsecret\n-----END PRIVATE KEY-----"
    account = ServerAccount.objects.create(
        name=f"account-{uuid.uuid4().hex[:6]}",
        username="root",
        private_key=encrypt_password(private_key),
    )
    host = _host_with_account(user, account)

    info = fabric_ssh_manager._get_connection_info(host)

    try:
        with open(info["key_filename"], encoding="utf-8") as key_file:
            assert key_file.read() == private_key
    finally:
        if info["key_filename"] and os.path.exists(info["key_filename"]):
            os.unlink(info["key_filename"])


def test_fabric_rejects_undecryptable_password_instead_of_using_raw_value():
    user = User.objects.create_user(f"password-{uuid.uuid4().hex[:6]}", password="pass")
    account = ServerAccount.objects.create(
        name=f"account-{uuid.uuid4().hex[:6]}",
        username="root",
        password="not-a-valid-fernet-token",
    )
    host = _host_with_account(user, account)

    with pytest.raises(FabricSSHError, match="解密失败"):
        fabric_ssh_manager._get_connection_info(host)

def test_account_serializer_reports_credential_encryption_failure():
    from rest_framework import serializers

    from apps.hosts.serializers import ServerAccountSerializer

    serializer = ServerAccountSerializer(
        data={
            "name": f"account-{uuid.uuid4().hex[:6]}",
            "username": "root",
            "password": "plain-text-secret",
        }
    )
    assert serializer.is_valid(), serializer.errors

    with patch(
        "apps.hosts.serializers.encrypt_password",
        side_effect=CredentialEncryptionError("key unavailable"),
    ):
        with pytest.raises(serializers.ValidationError, match="凭据加密失败"):
            serializer.save()

    assert ServerAccount.objects.count() == 0