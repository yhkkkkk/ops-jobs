import pytest

from apps.flows.secret_service import decrypt_flow_secret_values, encrypt_flow_secret_values, mask_flow_secret_values


def test_flow_secret_values_encrypt_decrypt_and_mask_without_plaintext_leakage():
    values = {"ApiToken": "token-value", "Password": "p@ss"}

    encrypted = encrypt_flow_secret_values(values)

    assert encrypted != values
    assert all(value not in encrypted.values() for value in values.values())
    assert decrypt_flow_secret_values(encrypted) == values
    assert mask_flow_secret_values({"Region": "sh", **values}, values.keys()) == {
        "Region": "sh",
        "ApiToken": "****",
        "Password": "****",
    }


def test_flow_secret_values_fail_closed_for_invalid_ciphertext():
    with pytest.raises(RuntimeError, match="密文变量"):
        decrypt_flow_secret_values({"ApiToken": "not-a-ciphertext"})