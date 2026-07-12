"""Encryption and display helpers for Flow secret variable payloads."""

from apps.hosts.utils import CredentialEncryptionError, decrypt_password, encrypt_password


def encrypt_flow_secret_values(values):
    if not isinstance(values, dict):
        raise ValueError("密文变量必须是对象")
    try:
        return {str(key): encrypt_password(str(value)) for key, value in values.items()}
    except CredentialEncryptionError as exc:
        raise RuntimeError("密文变量加密失败") from exc


def decrypt_flow_secret_values(values):
    if not isinstance(values, dict):
        raise ValueError("密文变量必须是对象")
    try:
        return {str(key): decrypt_password(str(value)) for key, value in values.items()}
    except CredentialEncryptionError as exc:
        raise RuntimeError("密文变量解密失败") from exc


def mask_flow_secret_values(values, secret_keys):
    secret_keys = {str(key) for key in secret_keys}
    return {
        key: "****" if str(key) in secret_keys and value not in (None, "") else value
        for key, value in (values or {}).items()
    }