import os
from typing import Tuple


def split_name(name: str) -> Tuple[str, str]:
    base, ext = os.path.splitext(name)
    return base, ext


def safe_new_name(dir_path: str, desired_name: str) -> str:
    """
    If a file with desired_name exists, append (n) before extension.
    """
    base, ext = split_name(desired_name)
    candidate = desired_name
    n = 1
    while os.path.exists(os.path.join(dir_path, candidate)):
        candidate = f"{base} ({n}){ext}"
        n += 1
    return candidate


def apply_rename(path: str, new_name: str) -> str:
    dir_path = os.path.dirname(path)
    final_name = safe_new_name(dir_path, new_name)
    new_path = os.path.join(dir_path, final_name)
    os.rename(path, new_path)
    return new_path

