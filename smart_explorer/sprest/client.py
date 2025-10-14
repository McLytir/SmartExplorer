from __future__ import annotations

import json
import os
import time
import urllib.parse
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import httpx


COOKIES_FILE = "sp_cookies.json"


def _load_cookies() -> Dict[str, Dict[str, str]]:
    try:
        if os.path.exists(COOKIES_FILE):
            with open(COOKIES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save_cookies(data: Dict[str, Dict[str, str]]) -> None:
    try:
        tmp = COOKIES_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, COOKIES_FILE)
    except Exception:
        pass


@dataclass
class Digest:
    value: str
    expires_at: float

    def valid(self) -> bool:
        return time.time() < self.expires_at - 10


class SharePointClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self._cookies_store = _load_cookies()  # base_url -> {cookie: value}
        self._digest: Optional[Digest] = None

    # Cookies management
    def set_cookies_from_header(self, cookie_header: str) -> None:
        jar: Dict[str, str] = {}
        parts = [p.strip() for p in cookie_header.split(";") if p.strip()]
        for p in parts:
            if "=" in p:
                k, v = p.split("=", 1)
                if k.lower() in ("fedauth", "rtfa") or k.isalpha():
                    jar[k] = v
        self._cookies_store[self.base_url] = jar
        _save_cookies(self._cookies_store)

    def set_cookie(self, name: str, value: str) -> None:
        jar = self._cookies_store.setdefault(self.base_url, {})
        jar[name] = value
        _save_cookies(self._cookies_store)

    def has_cookies(self) -> bool:
        return bool(self._cookies_store.get(self.base_url))

    def _http(self) -> httpx.Client:
        cookies = httpx.Cookies()
        for k, v in (self._cookies_store.get(self.base_url) or {}).items():
            cookies.set(k, v, domain=urllib.parse.urlparse(self.base_url).hostname)
        return httpx.Client(cookies=cookies, timeout=30.0, headers={
            "Accept": "application/json;odata=nometadata",
            "User-Agent": "SmartExplorer/0.1",
        })

    # Digest handling
    def _ensure_digest(self) -> str:
        if self._digest and self._digest.valid():
            return self._digest.value
        url = f"{self.base_url}/_api/contextinfo"
        with self._http() as client:
            resp = client.post(url)
            resp.raise_for_status()
            data = resp.json()
        # Handles metadata modes (nometadata or verbose)
        val = (
            data.get("FormDigestValue")
            or data.get("d", {}).get("GetContextWebInformation", {}).get("FormDigestValue")
        )
        timeout_sec = (
            data.get("FormDigestTimeoutSeconds")
            or data.get("d", {}).get("GetContextWebInformation", {}).get("FormDigestTimeoutSeconds")
            or 1800
        )
        self._digest = Digest(value=val, expires_at=time.time() + float(timeout_sec))
        return self._digest.value

    # List folder children (folders + files)
    def list_children(self, server_relative_url: str) -> Tuple[List[dict], List[dict]]:
        # Ensure starts with /
        if not server_relative_url.startswith("/"):
            server_relative_url = "/" + server_relative_url
        # Encode but keep slashes to match SharePoint expectations
        enc = urllib.parse.quote(server_relative_url, safe="/")
        folders_url = f"{self.base_url}/_api/web/GetFolderByServerRelativeUrl('{enc}')/Folders?$select=Name,ServerRelativeUrl,TimeLastModified,UniqueId"
        files_url = f"{self.base_url}/_api/web/GetFolderByServerRelativeUrl('{enc}')/Files?$select=Name,ServerRelativeUrl,Length,TimeLastModified,UniqueId"
        with self._http() as client:
            rf = client.get(folders_url)
            rf.raise_for_status()
            rfi = client.get(files_url)
            rfi.raise_for_status()
            fdata = rf.json()
            idata = rfi.json()
        # Robustly support verbose/nometadata
        folders = fdata.get("value") or fdata.get("d", {}).get("results", [])
        files = idata.get("value") or idata.get("d", {}).get("results", [])
        return folders, files

    # Rename by MoveTo to a new ServerRelativeUrl
    def rename(self, server_relative_url: str, new_name: str, is_folder: bool) -> str:
        # Compute new target URL
        if not server_relative_url.startswith("/"):
            server_relative_url = "/" + server_relative_url
        parent = server_relative_url.rsplit("/", 1)[0]
        new_url = f"{parent}/{new_name}"
        enc_old = urllib.parse.quote(server_relative_url, safe="/")
        enc_new = urllib.parse.quote(new_url, safe="/")

        digest = self._ensure_digest()
        headers = {
            "X-RequestDigest": digest,
            "IF-MATCH": "*",
        }
        with self._http() as client:
            if is_folder:
                # Folder moveTo
                url = f"{self.base_url}/_api/web/GetFolderByServerRelativeUrl('{enc_old}')/moveTo(newurl='{enc_new}')"
            else:
                # File moveto flags=1 => overwrite if exists (we rely on conflict check beforehand)
                url = f"{self.base_url}/_api/web/GetFileByServerRelativeUrl('{enc_old}')/moveto(newurl='{enc_new}',flags=1)"
            resp = client.post(url, headers=headers)
            if resp.status_code >= 400:
                # Some tenants require POST with X-HTTP-Method: MERGE
                headers2 = dict(headers)
                headers2["X-HTTP-Method"] = "MERGE"
                resp = client.post(url, headers=headers2)
            resp.raise_for_status()
        return new_url

    # Discover default document library (title and server-relative URL)
    def get_default_doclib(self) -> Tuple[str, str]:
        # Query all document libraries (BaseTemplate 101) and pick a reasonable default
        # Prefer one named "Documents" or "Shared Documents", else first non-hidden
        select = "Title,RootFolder/ServerRelativeUrl,Hidden"
        url = f"{self.base_url}/_api/web/Lists?$select={urllib.parse.quote(select)}&$expand=RootFolder&$filter=BaseTemplate eq 101"
        with self._http() as client:
            resp = client.get(url)
            resp.raise_for_status()
            data = resp.json()
        lists = data.get("value") or data.get("d", {}).get("results", [])
        # Filter out hidden lists
        visible = [l for l in lists if not l.get("Hidden", False)] or lists
        # Helpers
        def title_of(l):
            return (l.get("Title") or "").strip()
        def url_of(l):
            rf = l.get("RootFolder") or {}
            return (rf.get("ServerRelativeUrl") or "").strip()
        # Prefer canonical names
        preferred = None
        for l in visible:
            if title_of(l).lower() in ("documents", "shared documents"):
                preferred = l
                break
        chosen = preferred or (visible[0] if visible else (lists[0] if lists else None))
        if not chosen:
            # Fallback to site root
            return ("", "/")
        return title_of(chosen), url_of(chosen)
