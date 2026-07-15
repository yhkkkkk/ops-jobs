"""Encryption and display helpers for Flow secret variable payloads."""

import copy

from apps.hosts.utils import CredentialEncryptionError, decrypt_password, encrypt_password


SECRET_MASK = "****"


def is_flow_secret_variable(definition):
    if not isinstance(definition, dict):
        return False
    return bool(definition.get("secret")) or str(definition.get("type") or "").lower() in {
        "password",
        "secret",
    } or str(definition.get("widget") or "").lower() in {"password", "secret"}


def flow_secret_variable_keys(variables):
    return {
        str(key)
        for key, definition in (variables or {}).items()
        if is_flow_secret_variable(definition)
    }


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
        key: SECRET_MASK if str(key) in secret_keys and value not in (None, "") else value
        for key, value in (values or {}).items()
    }


def split_flow_secret_values(values, secret_keys, existing_encrypted=None):
    """Return public masked values and encrypted values without reusing plaintext."""
    if not isinstance(values, dict):
        raise ValueError("流程变量必须是对象")

    secret_keys = {str(key) for key in secret_keys}
    existing_encrypted = dict(existing_encrypted or {})
    public_values = copy.deepcopy(values)
    plaintext_secrets = {}

    for key in secret_keys:
        value = values.get(key)
        if value not in (None, "", SECRET_MASK):
            plaintext_secrets[key] = value
        if key in values:
            public_values[key] = SECRET_MASK if value not in (None, "") else value

    encrypted_values = {
        key: value for key, value in existing_encrypted.items() if key in secret_keys
    }
    encrypted_values.update(encrypt_flow_secret_values(plaintext_secrets))
    return public_values, encrypted_values


def prepare_flow_secret_defaults(variables, existing_encrypted=None):
    """Move secret variable defaults out of public template variable definitions."""
    if not isinstance(variables, dict):
        raise ValueError("flow variables must be an object")

    public_variables = copy.deepcopy(variables)
    existing_encrypted = dict(existing_encrypted or {})
    secret_keys = flow_secret_variable_keys(public_variables)
    plaintext_defaults = {}

    for key in secret_keys:
        definition = public_variables[key]
        default = definition.pop("default", None)
        if default not in (None, "", SECRET_MASK):
            plaintext_defaults[key] = default
        encrypted_exists = key in existing_encrypted or key in plaintext_defaults
        definition["has_default"] = encrypted_exists

    encrypted_defaults = {
        key: value for key, value in existing_encrypted.items() if key in secret_keys
    }
    encrypted_defaults.update(encrypt_flow_secret_values(plaintext_defaults))
    return public_variables, encrypted_defaults