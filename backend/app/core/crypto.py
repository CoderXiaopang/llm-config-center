from cryptography.fernet import Fernet

from app.core.config import get_settings


def _fernet() -> Fernet:
    return Fernet(get_settings().llm_config_master_key.encode())


def encrypt_api_key(api_key: str) -> str:
    return _fernet().encrypt(api_key.encode()).decode()


def decrypt_api_key(encrypted_api_key: str) -> str:
    return _fernet().decrypt(encrypted_api_key.encode()).decode()


def mask_secret(secret: str) -> str:
    if len(secret) <= 8:
        return f"{secret[:2]}****{secret[-2:]}"
    return f"{secret[:3]}****{secret[-4:]}"

