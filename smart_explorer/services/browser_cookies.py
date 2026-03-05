from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List

try:
    import browser_cookie3  # type: ignore
except ImportError:  # pragma: no cover - handled in caller
    browser_cookie3 = None  # type: ignore[assignment]

_LAST_CAPTURE_HINT: str | None = None


def get_last_capture_hint() -> str | None:
    return _LAST_CAPTURE_HINT


def collect_sharepoint_cookie_records(netloc: str) -> List[dict]:
    """
    Attempt to load SharePoint cookies (FedAuth, rtFa) from common desktop browsers.
    netloc should be the hostname portion of the SharePoint site.
    """
    global _LAST_CAPTURE_HINT
    _LAST_CAPTURE_HINT = None
    if not browser_cookie3 or not netloc:
        return {}

    # Ignore accidental scheme/path/port fragments.
    host = (netloc or "").strip().split("://")[-1].split("/")[0].split(":")[0].strip().lower()
    if not host:
        return {}

    targets = []

    def add_target(host: str) -> None:
        if host and host not in targets:
            targets.append(host)
        if host and not host.startswith("."):
            dotted = "." + host
            if dotted not in targets:
                targets.append(dotted)

    add_target(host)

    # Include parent domains for tenant-specific hosts (e.g., rtFa on .sharepoint.com)
    parts = host.split(".")
    if len(parts) > 2:
        parent = ".".join(parts[-2:])
        add_target(parent)

    collectors = [
        getattr(browser_cookie3, "edge", None),
        getattr(browser_cookie3, "opera", None),
        getattr(browser_cookie3, "opera_gx", None),
        getattr(browser_cookie3, "chrome", None),
        getattr(browser_cookie3, "chromium", None),
        getattr(browser_cookie3, "firefox", None),
    ]

    # Keep canonical SharePoint auth cookie names where possible, but also collect
    # modern SPO auth cookies for tenants that no longer expose both FedAuth/rtFa.
    interesting = {
        "fedauth": "FedAuth",
        "rtfa": "rtFa",
        "spoidcrl": "SPOIDCRL",
        "spoidcrlid": "SPOIDCRLID",
    }
    cookies: Dict[str, dict] = {}

    def _domain_matches(cookie_domain: str, host: str) -> bool:
        d = (cookie_domain or "").lstrip(".").lower()
        h = (host or "").lstrip(".").lower()
        return d == h or d.endswith("." + h)

    # Only accept FedAuth on the exact tenant host; accept rtFa on parent sharepoint domain.
    tenant_host = host.lstrip(".")
    parent_host = ".".join(parts[-2:]) if len(parts) > 2 else tenant_host

    def _process_jar(jar) -> None:
        for cookie in jar or []:
            name = (getattr(cookie, "name", "") or "").strip()
            value = getattr(cookie, "value", None)
            domain = (getattr(cookie, "domain", "") or "").strip()
            if not name or not value:
                continue
            key = name.lower()
            canonical = interesting.get(key)
            if not canonical or canonical in cookies:
                continue
            # Accept tenant-host cookies and parent sharepoint-domain cookies.
            if _domain_matches(domain, tenant_host) or _domain_matches(domain, parent_host):
                expires_raw = getattr(cookie, "expires", None)
                try:
                    expires_at = float(expires_raw) if expires_raw not in (None, "", 0) else None
                except Exception:
                    expires_at = None
                cookies[canonical] = {
                    "name": canonical,
                    "value": value,
                    "domain": domain or None,
                    "path": (getattr(cookie, "path", None) or "/"),
                    "secure": bool(getattr(cookie, "secure", True)),
                    "http_only": False,
                    "expires_at": expires_at,
                }

    def _has_minimum_auth() -> bool:
        # Prefer classic pair when present.
        if "FedAuth" in cookies and "rtFa" in cookies:
            return True
        # Fallback for modern auth cookie names.
        return any(k in cookies for k in ("SPOIDCRL", "SPOIDCRLID", "FedAuth", "rtFa"))

    def _remember_capture_error(exc: Exception) -> None:
        global _LAST_CAPTURE_HINT
        name = exc.__class__.__name__.lower()
        msg = str(exc).lower()
        if "requiresadminerror" in name or "requires admin" in msg:
            _LAST_CAPTURE_HINT = (
                "Opera cookie decryption requires elevated privileges on this machine. "
                "Run SmartExplorer as Administrator, then retry Capture Cookies."
            )

    def _iter_edge_cookie_files() -> list[str]:
        if os.name != "nt":
            return []
        base = os.environ.get("LOCALAPPDATA")
        if not base:
            return []
        user_data = Path(base) / "Microsoft" / "Edge" / "User Data"
        if not user_data.exists():
            return []
        paths: list[str] = []
        for profile in user_data.iterdir():
            if not profile.is_dir():
                continue
            candidate_new = profile / "Network" / "Cookies"
            candidate_old = profile / "Cookies"
            if candidate_new.exists():
                paths.append(str(candidate_new))
            elif candidate_old.exists():
                paths.append(str(candidate_old))
        return paths

    def _iter_opera_cookie_files() -> list[tuple[str, str, str | None]]:
        if os.name != "nt":
            return []
        local = os.environ.get("LOCALAPPDATA") or ""
        roaming = os.environ.get("APPDATA") or ""
        base_profiles = [
            ("opera", Path(roaming) / "Opera Software" / "Opera Stable"),
            ("opera_gx", Path(roaming) / "Opera Software" / "Opera GX Stable"),
            # Some setups store profile data under Local.
            ("opera", Path(local) / "Opera Software" / "Opera Stable"),
            ("opera_gx", Path(local) / "Opera Software" / "Opera GX Stable"),
        ]
        found: list[tuple[str, str, str | None]] = []
        for browser_name, base in base_profiles:
            if not base.exists():
                continue
            local_state = base / "Local State"
            key_file = str(local_state) if local_state.exists() else None
            direct_candidates = [
                base / "Network" / "Cookies",
                base / "Cookies",
            ]
            for p in direct_candidates:
                if p.exists():
                    found.append((browser_name, str(p), key_file))
            for profile_dir in base.iterdir():
                if not profile_dir.is_dir():
                    continue
                profile_name = profile_dir.name.lower()
                if profile_name != "default" and not profile_name.startswith("profile"):
                    continue
                prof_candidates = [
                    profile_dir / "Network" / "Cookies",
                    profile_dir / "Cookies",
                ]
                for p in prof_candidates:
                    if p.exists():
                        found.append((browser_name, str(p), key_file))
        return found

    for target in targets:
        for fn in collectors:
            if not fn:
                continue
            # First, try with the domain filter for speed
            try:
                jar = fn(domain_name=target)
                _process_jar(jar)
            except Exception as exc:
                _remember_capture_error(exc)
                jar = None
            if _has_minimum_auth():
                break
            # If domain-filtered lookup failed, fall back to full jar to handle alternate profiles/hosts
            try:
                jar = fn()
                _process_jar(jar)
            except Exception as exc:
                _remember_capture_error(exc)
                pass
            if _has_minimum_auth():
                break
        if _has_minimum_auth():
            break

    # Edge-specific fallback: explicitly scan all Edge profiles on Windows.
    edge_fn = getattr(browser_cookie3, "edge", None)
    if edge_fn and not _has_minimum_auth():
        for cookie_file in _iter_edge_cookie_files():
            for target in targets:
                try:
                    jar = edge_fn(cookie_file=cookie_file, domain_name=target)
                    _process_jar(jar)
                except Exception as exc:
                    _remember_capture_error(exc)
                    continue
                if _has_minimum_auth():
                    break
            if _has_minimum_auth():
                break

    # Opera-specific fallback: scan Opera/Opera GX cookie DB locations on Windows.
    if not _has_minimum_auth():
        opera_fn = getattr(browser_cookie3, "opera", None)
        opera_gx_fn = getattr(browser_cookie3, "opera_gx", None)
        for browser_name, cookie_file, key_file in _iter_opera_cookie_files():
            fn = opera_fn if browser_name == "opera" else opera_gx_fn
            if not fn:
                continue
            for target in targets:
                try:
                    if key_file:
                        jar = fn(cookie_file=cookie_file, key_file=key_file, domain_name=target)
                    else:
                        jar = fn(cookie_file=cookie_file, domain_name=target)
                    _process_jar(jar)
                except Exception as exc:
                    _remember_capture_error(exc)
                    continue
                if _has_minimum_auth():
                    break
            if _has_minimum_auth():
                break

    return list(cookies.values())


def collect_sharepoint_cookies(netloc: str) -> Dict[str, str]:
    return {
        str(record.get("name") or ""): str(record.get("value") or "")
        for record in collect_sharepoint_cookie_records(netloc)
        if record.get("name") and record.get("value") is not None
    }
