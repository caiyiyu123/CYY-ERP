from app.utils.security import (
    hash_password, verify_password,
    create_access_token, decode_access_token,
    encrypt_token, decrypt_token,
)


def test_password_hash_and_verify():
    password = "test_password_123"
    hashed = hash_password(password)
    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("wrong_password", hashed) is False


def test_jwt_create_and_decode():
    token = create_access_token(data={"sub": "admin", "role": "admin"})
    payload = decode_access_token(token)
    assert payload["sub"] == "admin"
    assert payload["role"] == "admin"


def test_jwt_invalid_token():
    payload = decode_access_token("invalid.token.here")
    assert payload is None


def test_fernet_encrypt_decrypt():
    original = "wb_api_token_abc123"
    encrypted = encrypt_token(original)
    assert encrypted != original
    decrypted = decrypt_token(encrypted)
    assert decrypted == original
