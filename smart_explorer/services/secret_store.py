from __future__ import annotations

import os
from typing import Optional


_SERVICE_NAME = "SmartExplorer"


def _get_keyring():
    try:
        import keyring  # type: ignore
        return keyring
    except Exception:
        return None


def get_secret(account: str, *, service: str = _SERVICE_NAME) -> Optional[str]:
    env_key = os.getenv(account) or os.getenv(account.upper())
    if env_key:
        return env_key
    kr = _get_keyring()
    if not kr:
        return None
    try:
        return kr.get_password(service, account)
    except Exception:
        return None


def set_secret(account: str, value: str, *, service: str = _SERVICE_NAME) -> bool:
    kr = _get_keyring()
    if not kr:
        return False
    try:
        kr.set_password(service, account, value)
        return True
    except Exception:
        return False


def delete_secret(account: str, *, service: str = _SERVICE_NAME) -> bool:
    kr = _get_keyring()
    if not kr:
        return False
    try:
        kr.delete_password(service, account)
        return True
    except Exception:
        return False


def has_secret(account: str, *, service: str = _SERVICE_NAME) -> bool:
    return get_secret(account, service=service) is not None

