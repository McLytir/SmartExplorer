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

    def _domain_matches(cookie_domain: str, host: str) -> bool:
        d = (cookie_domain or "").lstrip(".").lower()
        h = (host or "").lstrip(".").lower()
        return d == h or d.endswith("." + h)

    # Only accept FedAuth on the exact tenant host; accept rtFa on parent sharepoint domain.
    tenant_host = netloc.lstrip(".")
    parent_host = ".".join(parts[-2:]) if len(parts) > 2 else tenant_host

    def _process_jar(jar) -> None:
        for cookie in jar or []:
            name = (getattr(cookie, "name", "") or "").strip()
            value = getattr(cookie, "value", None)
            domain = (getattr(cookie, "domain", "") or "").strip()
            if not name or not value:
                continue
            key = name.lower()
            if key == "fedauth" and required["fedauth"] not in cookies:
                # Accept FedAuth on tenant host or parent sharepoint host
                if _domain_matches(domain, tenant_host) or _domain_matches(domain, parent_host):
                    cookies[required["fedauth"]] = value
                    continue
            if key == "rtfa" and required["rtfa"] not in cookies:
                # rtFa is typically scoped to the parent .sharepoint.com domain
                if _domain_matches(domain, parent_host):
                    cookies[required["rtfa"]] = value
                    continue

    for target in targets:
        for fn in collectors:
            if not fn:
                continue
            # First, try with the domain filter for speed
            try:
                jar = fn(domain_name=target)
                _process_jar(jar)
            except Exception:
                jar = None
            if all(k in cookies for k in required.values()):
                break
            # If domain-filtered lookup failed, fall back to full jar to handle alternate profiles/hosts
            try:
                jar = fn()
                _process_jar(jar)
            except Exception:
                pass
            if all(k in cookies for k in required.values()):
                break
        if all(k in cookies for k in required.values()):
            break
    return cookies
