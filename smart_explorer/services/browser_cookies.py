from __future__ import annotations

from typing import Dict

try:
    import browser_cookie3  # type: ignore
except ImportError:  # pragma: no cover - handled in caller
    browser_cookie3 = None  # type: ignore[assignment]


def collect_sharepoint_cookies(netloc: str) -> Dict[str, str]:
    """
    Attempt to load SharePoint cookies (FedAuth, rtFa) from common desktop browsers.
    netloc should be the hostname portion of the SharePoint site.
    """
    if not browser_cookie3 or not netloc:
        return {}

    targets = []

    def add_target(host: str) -> None:
        if host and host not in targets:
            targets.append(host)
        if host and not host.startswith("."):
            dotted = "." + host
            if dotted not in targets:
                targets.append(dotted)

    add_target(netloc)

    # Include parent domains for tenant-specific hosts (e.g., rtFa on .sharepoint.com)
    parts = netloc.split(".")
    if len(parts) > 2:
        parent = ".".join(parts[-2:])
        add_target(parent)

    collectors = [
        getattr(browser_cookie3, "edge", None),
        getattr(browser_cookie3, "chrome", None),
        getattr(browser_cookie3, "chromium", None),
        getattr(browser_cookie3, "firefox", None),
    ]

    required = {"fedauth": "FedAuth", "rtfa": "rtFa"}
    cookies: Dict[str, str] = {}
    for target in targets:
        for fn in collectors:
            if not fn:
                continue
            try:
                jar = fn(domain_name=target)
            except Exception:
                continue
            for cookie in jar:
                name = (cookie.name or "").strip()
                if not name or not cookie.value:
                    continue
                key = name.lower()
                mapped = required.get(key)
                if mapped and mapped not in cookies:
                    cookies[mapped] = cookie.value
            if all(k in cookies for k in required.values()):
                break
        if all(k in cookies for k in required.values()):
            break
    return cookies
