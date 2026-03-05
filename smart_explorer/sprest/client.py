from __future__ import annotations

import json
import os
import time
import urllib.parse
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple

import httpx


COOKIES_FILE = "sp_cookies.json"


@dataclass
class CookieRecord:
    name: str
    value: str
    domain: Optional[str] = None
    path: str = "/"
    secure: bool = True
    http_only: bool = False
    expires_at: Optional[float] = None

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "CookieRecord":
        expires_raw = data.get("expires_at")
        try:
            expires_at = float(expires_raw) if expires_raw not in (None, "", 0) else None
        except Exception:
            expires_at = None
        return CookieRecord(
            name=str(data.get("name") or "").strip(),
            value=str(data.get("value") or ""),
            domain=str(data.get("domain") or "").strip() or None,
            path=str(data.get("path") or "/").strip() or "/",
            secure=bool(data.get("secure", True)),
            http_only=bool(data.get("http_only", False)),
            expires_at=expires_at,
        )

    def expired(self) -> bool:
        return self.expires_at is not None and self.expires_at <= time.time()


def _load_cookies() -> Dict[str, Any]:
    try:
        if os.path.exists(COOKIES_FILE):
            with open(COOKIES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save_cookies(data: Dict[str, Any]) -> None:
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
        self._cookies_store = _load_cookies()  # host -> {cookie: value}
        parsed = urllib.parse.urlparse(self.base_url)
        self._resource_base = f"{parsed.scheme}://{parsed.netloc}"
        self._digests: Dict[str, Digest] = {}
        # Migrate legacy cookie entries stored by full base URL
        legacy = self._cookies_store.get(self.base_url)
        if legacy and self._cookie_store_key() not in self._cookies_store:
            self._cookies_store[self._cookie_store_key()] = legacy

    # Cookies management
    def set_cookies_from_header(self, cookie_header: str) -> None:
        records: List[CookieRecord] = []
        parts = [p.strip() for p in cookie_header.split(";") if p.strip()]
        for p in parts:
            if "=" in p:
                k, v = p.split("=", 1)
                if k.lower() in ("fedauth", "rtfa") or k.isalpha():
                    records.append(self._build_cookie_record(k, v))
        self._set_cookie_records(records)

    def set_cookie(self, name: str, value: str) -> None:
        self._upsert_cookie_record(self._build_cookie_record(name, value))

    def set_cookie_record(
        self,
        name: str,
        value: str,
        *,
        domain: Optional[str] = None,
        path: str = "/",
        secure: bool = True,
        http_only: bool = False,
        expires_at: Optional[float] = None,
    ) -> None:
        self._upsert_cookie_record(
            CookieRecord(
                name=str(name or "").strip(),
                value=str(value or ""),
                domain=str(domain or "").strip() or None,
                path=str(path or "/").strip() or "/",
                secure=bool(secure),
                http_only=bool(http_only),
                expires_at=expires_at,
            )
        )

    def has_cookies(self) -> bool:
        return bool(self._cookie_records())

    def _http(self) -> httpx.Client:
        cookies = httpx.Cookies()
        default_domain = urllib.parse.urlparse(self._resource_base).hostname
        for record in self._cookie_records():
            cookies.set(
                record.name,
                record.value,
                domain=record.domain or default_domain,
                path=record.path or "/",
            )
        return httpx.Client(cookies=cookies, timeout=30.0, headers={
            "Accept": "application/json;odata=nometadata",
            "User-Agent": "SmartExplorer/0.1",
        })

    # Digest handling
    def _ensure_digest(self, site_relative_url: Optional[str] = None) -> str:
        site_base = self._resolve_site(site_relative_url)
        digest = self._digests.get(site_base)
        if digest and digest.valid():
            return digest.value
        url = f"{site_base}/_api/contextinfo"
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
        new_digest = Digest(value=val, expires_at=time.time() + float(timeout_sec))
        self._digests[site_base] = new_digest
        return new_digest.value

    # List folder children (folders + files)
    def list_children(self, server_relative_url: str, *, site_relative_url: Optional[str] = None) -> Tuple[List[dict], List[dict]]:
        # Ensure starts with /
        if not server_relative_url.startswith("/"):
            server_relative_url = "/" + server_relative_url
        site_base = self._resolve_site(site_relative_url)
        # Encode but keep slashes to match SharePoint expectations
        enc = urllib.parse.quote(server_relative_url, safe="/")
        select = (
            "Name,ServerRelativeUrl,"
            "Folders/Name,Folders/ServerRelativeUrl,Folders/TimeLastModified,"
            "Files/Name,Files/ServerRelativeUrl,Files/Length,Files/TimeLastModified"
        )
        url = (
            f"{site_base}/_api/web/GetFolderByServerRelativeUrl('{enc}')"
            f"?$expand=Folders,Files&$select={urllib.parse.quote(select, safe=',/')}"
        )
        with self._http() as client:
            resp = client.get(url)
            resp.raise_for_status()
            data = resp.json()
        payload = data.get("d", data)
        folders = payload.get("Folders", [])
        if isinstance(folders, dict):
            folders = folders.get("results", [])
        files = payload.get("Files", [])
        if isinstance(files, dict):
            files = files.get("results", [])
        return folders, files

    # Rename by MoveTo to a new ServerRelativeUrl
    def rename(self, server_relative_url: str, new_name: str, is_folder: bool, *, site_relative_url: Optional[str] = None) -> str:
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
        site_base = self._resolve_site(site_relative_url)
        with self._http() as client:
            if is_folder:
                # Folder moveTo
                url = f"{site_base}/_api/web/GetFolderByServerRelativeUrl('{enc_old}')/moveTo(newurl='{enc_new}')"
            else:
                # File moveto flags=1 => overwrite if exists (we rely on conflict check beforehand)
                url = f"{site_base}/_api/web/GetFileByServerRelativeUrl('{enc_old}')/moveto(newurl='{enc_new}',flags=1)"
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

    def list_sites(self) -> List[dict]:
        sites: List[dict] = []
        # Include current site
        try:
            with self._http() as client:
                resp = client.get(f"{self.base_url}/_api/web?$select=Title,ServerRelativeUrl,Url,Id")
                resp.raise_for_status()
                root = resp.json().get("d", resp.json())
                sites.append({
                    "title": root.get("Title"),
                    "serverRelativeUrl": root.get("ServerRelativeUrl"),
                    "url": root.get("Url") or self.base_url,
                    "id": root.get("Id"),
                })
        except Exception:
            pass
        try:
            with self._http() as client:
                resp = client.get(f"{self.base_url}/_api/web/webs?$select=Title,ServerRelativeUrl,Url,Id")
                resp.raise_for_status()
                data = resp.json()
            items = data.get("value") or data.get("d", {}).get("results", [])
            for it in items:
                sites.append({
                    "title": it.get("Title"),
                    "serverRelativeUrl": it.get("ServerRelativeUrl"),
                    "url": it.get("Url"),
                    "id": it.get("Id"),
                })
        except Exception:
            pass
        return sites

    def list_libraries(self, site_relative_url: Optional[str] = None) -> List[dict]:
        select = "Title,RootFolder/ServerRelativeUrl,RootFolder/Name,RootFolder/UniqueId,Hidden,BaseTemplate"
        url = f"{self._resolve_site(site_relative_url)}/_api/web/Lists?$select={urllib.parse.quote(select)}&$expand=RootFolder&$filter=BaseTemplate eq 101"
        with self._http() as client:
            resp = client.get(url)
            resp.raise_for_status()
            data = resp.json()
        lists = data.get("value") or data.get("d", {}).get("results", [])
        libraries: List[dict] = []
        for lst in lists:
            if lst.get("Hidden"):
                continue
            root_folder = lst.get("RootFolder") or {}
            path = root_folder.get("ServerRelativeUrl") or ""
            if not path:
                path = (root_folder.get("ServerRelativePath") or {}).get("DecodedUrl") or ""
            if not path:
                list_id = lst.get("Id") or root_folder.get("UniqueId")
                if list_id:
                    try:
                        path = self._fetch_list_root_path(list_id, site_relative_url)
                    except Exception:
                        path = ""
            if not path and site_relative_url:
                name = (root_folder.get("Name") or "").strip()
                if name:
                    path = f"{site_relative_url.rstrip('/')}/{name}"
            path = (path or "").strip()
            if path and not path.startswith("/"):
                path = "/" + path
            if not path or path == "/":
                continue
            libraries.append({
                "title": lst.get("Title"),
                "server_relative_url": path,
                "name": root_folder.get("Name"),
                "id": lst.get("Id") or root_folder.get("UniqueId"),
            })
        return libraries

    def _fetch_list_root_path(self, list_id: str, site_relative_url: Optional[str]) -> str:
        site_base = self._resolve_site(site_relative_url)
        list_id = (list_id or "").strip("{}")
        if not list_id:
            return ""
        url = f"{site_base}/_api/web/Lists(guid'{list_id}')/RootFolder?$select=ServerRelativeUrl,ServerRelativePath"
        with self._http() as client:
            resp = client.get(url)
            resp.raise_for_status()
            data = resp.json()
        root = data.get("d", data) or {}
        path = (root.get("ServerRelativeUrl") or "").strip()
        if not path:
            path = ((root.get("ServerRelativePath") or {}).get("DecodedUrl") or "").strip()
        if path and not path.startswith("/"):
            path = "/" + path
        return path

    def copy_item(self, source_server_relative: str, target_server_relative: str, *,
                  is_folder: bool, overwrite: bool = False,
                  site_relative_url: Optional[str] = None) -> str:
        if not source_server_relative.startswith("/"):
            source_server_relative = "/" + source_server_relative
        if not target_server_relative.startswith("/"):
            target_server_relative = "/" + target_server_relative
        with self._http() as client:
            # Prefer body-based API: avoids URL-length limits for deep paths.
            try:
                self._copy_item_by_path(
                    client,
                    source_server_relative=source_server_relative,
                    target_server_relative=target_server_relative,
                    is_folder=is_folder,
                    overwrite=overwrite,
                    site_relative_url=site_relative_url,
                )
            except httpx.HTTPStatusError:
                # Fallback for older tenants that don't expose MoveCopyUtil.
                self._copy_item_legacy(
                    client,
                    source_server_relative=source_server_relative,
                    target_server_relative=target_server_relative,
                    is_folder=is_folder,
                    overwrite=overwrite,
                    site_relative_url=site_relative_url,
                )
        return target_server_relative

    def _copy_item_legacy(
        self,
        client: httpx.Client,
        *,
        source_server_relative: str,
        target_server_relative: str,
        is_folder: bool,
        overwrite: bool,
        site_relative_url: Optional[str],
    ) -> None:
        enc_src = urllib.parse.quote(source_server_relative, safe="/")
        enc_dst = urllib.parse.quote(target_server_relative, safe="/")
        digest = self._ensure_digest(site_relative_url)
        headers = {
            "X-RequestDigest": digest,
            "IF-MATCH": "*",
        }
        site_base = self._resolve_site(site_relative_url)
        if is_folder:
            url = f"{site_base}/_api/web/GetFolderByServerRelativeUrl('{enc_src}')/copyTo(strNewUrl='{enc_dst}')"
        else:
            url = f"{site_base}/_api/web/GetFileByServerRelativeUrl('{enc_src}')/copyTo(strNewUrl='{enc_dst}',boverwrite={'true' if overwrite else 'false'})"
        resp = client.post(url, headers=headers)
        resp.raise_for_status()

    def _copy_item_by_path(
        self,
        client: httpx.Client,
        *,
        source_server_relative: str,
        target_server_relative: str,
        is_folder: bool,
        overwrite: bool,
        site_relative_url: Optional[str],
    ) -> None:
        site_base = self._resolve_site(site_relative_url)
        digest = self._ensure_digest(site_relative_url)
        headers = {
            "X-RequestDigest": digest,
            "Content-Type": "application/json;odata=verbose",
        }
        src_abs = f"{self._resource_base}{source_server_relative}"
        dst_abs = f"{self._resource_base}{target_server_relative}"
        payload = {
            "srcPath": {"DecodedUrl": src_abs},
            "destPath": {"DecodedUrl": dst_abs},
            "options": {
                "KeepBoth": not overwrite,
                "ResetAuthorAndCreatedOnCopy": False,
                "ShouldBypassSharedLocks": True,
            },
        }
        method = "CopyFolderByPath" if is_folder else "CopyFileByPath"
        # Different SPO builds accept either dotted or slash form.
        endpoints = [
            f"{site_base}/_api/SP.MoveCopyUtil.{method}()",
            f"{site_base}/_api/SP.MoveCopyUtil/{method}",
        ]
        last_resp: Optional[httpx.Response] = None
        for endpoint in endpoints:
            resp = client.post(endpoint, headers=headers, json=payload)
            last_resp = resp
            if resp.status_code < 400:
                return
            if resp.status_code not in (400, 404):
                break
        if last_resp is not None:
            last_resp.raise_for_status()

    def move_item(self, source_server_relative: str, target_server_relative: str, *,
                  is_folder: bool, overwrite: bool = False,
                  site_relative_url: Optional[str] = None) -> str:
        if not source_server_relative.startswith("/"):
            source_server_relative = "/" + source_server_relative
        if not target_server_relative.startswith("/"):
            target_server_relative = "/" + target_server_relative
        with self._http() as client:
            # Prefer body-based API: avoids URL-length limits for deep paths.
            try:
                self._move_item_by_path(
                    client,
                    source_server_relative=source_server_relative,
                    target_server_relative=target_server_relative,
                    is_folder=is_folder,
                    overwrite=overwrite,
                    site_relative_url=site_relative_url,
                )
            except httpx.HTTPStatusError:
                # Fallback for older tenants that don't expose MoveCopyUtil.
                self._move_item_legacy(
                    client,
                    source_server_relative=source_server_relative,
                    target_server_relative=target_server_relative,
                    is_folder=is_folder,
                    overwrite=overwrite,
                    site_relative_url=site_relative_url,
                )
        return target_server_relative

    def _move_item_by_path(
        self,
        client: httpx.Client,
        *,
        source_server_relative: str,
        target_server_relative: str,
        is_folder: bool,
        overwrite: bool,
        site_relative_url: Optional[str],
    ) -> None:
        site_base = self._resolve_site(site_relative_url)
        digest = self._ensure_digest(site_relative_url)
        headers = {
            "X-RequestDigest": digest,
            "Content-Type": "application/json;odata=verbose",
        }
        src_abs = f"{self._resource_base}{source_server_relative}"
        dst_abs = f"{self._resource_base}{target_server_relative}"
        payload = {
            "srcPath": {"DecodedUrl": src_abs},
            "destPath": {"DecodedUrl": dst_abs},
            "options": {
                "KeepBoth": not overwrite,
                "ShouldBypassSharedLocks": True,
            },
        }
        method = "MoveFolderByPath" if is_folder else "MoveFileByPath"
        endpoints = [
            f"{site_base}/_api/SP.MoveCopyUtil.{method}()",
            f"{site_base}/_api/SP.MoveCopyUtil/{method}",
        ]
        last_resp: Optional[httpx.Response] = None
        for endpoint in endpoints:
            resp = client.post(endpoint, headers=headers, json=payload)
            last_resp = resp
            if resp.status_code < 400:
                return
            if resp.status_code not in (400, 404):
                break
        if last_resp is not None:
            last_resp.raise_for_status()

    def _move_item_legacy(
        self,
        client: httpx.Client,
        *,
        source_server_relative: str,
        target_server_relative: str,
        is_folder: bool,
        overwrite: bool,
        site_relative_url: Optional[str],
    ) -> None:
        enc_src = urllib.parse.quote(source_server_relative, safe="/")
        enc_dst = urllib.parse.quote(target_server_relative, safe="/")
        digest = self._ensure_digest(site_relative_url)
        headers = {
            "X-RequestDigest": digest,
            "IF-MATCH": "*",
        }
        site_base = self._resolve_site(site_relative_url)
        if is_folder:
            url = f"{site_base}/_api/web/GetFolderByServerRelativeUrl('{enc_src}')/moveTo(newurl='{enc_dst}')"
        else:
            url = f"{site_base}/_api/web/GetFileByServerRelativeUrl('{enc_src}')/moveTo(newUrl='{enc_dst}',flags={'1' if overwrite else '0'})"
        resp = client.post(url, headers=headers)
        if resp.status_code >= 400:
            headers2 = dict(headers)
            headers2["X-HTTP-Method"] = "MERGE"
            resp = client.post(url, headers=headers2)
        resp.raise_for_status()

    def delete_item(self, server_relative_url: str, *, is_folder: bool,
                    site_relative_url: Optional[str] = None, recycle: bool = True) -> None:
        if not server_relative_url.startswith("/"):
            server_relative_url = "/" + server_relative_url
        enc = urllib.parse.quote(server_relative_url, safe="/")
        digest = self._ensure_digest(site_relative_url)
        headers = {
            "X-RequestDigest": digest,
            "IF-MATCH": "*",
        }
        site_base = self._resolve_site(site_relative_url)
        with self._http() as client:
            if is_folder:
                if recycle:
                    url = f"{site_base}/_api/web/GetFolderByServerRelativeUrl('{enc}')/recycle()"
                else:
                    url = f"{site_base}/_api/web/GetFolderByServerRelativeUrl('{enc}')"
            else:
                if recycle:
                    url = f"{site_base}/_api/web/GetFileByServerRelativeUrl('{enc}')/recycle()"
                else:
                    url = f"{site_base}/_api/web/GetFileByServerRelativeUrl('{enc}')"
            if recycle:
                resp = client.post(url, headers=headers)
            else:
                resp = client.post(url, headers=dict(headers, **{"X-HTTP-Method": "DELETE"}))
            resp.raise_for_status()

    def create_folder(self, parent_server_relative: str, name: str, *,
                      site_relative_url: Optional[str] = None) -> str:
        if not parent_server_relative.startswith("/"):
            parent_server_relative = "/" + parent_server_relative
        parent_enc = urllib.parse.quote(parent_server_relative, safe="/")
        digest = self._ensure_digest(site_relative_url)
        headers = {"X-RequestDigest": digest}
        site_base = self._resolve_site(site_relative_url)
        safe_name = name.replace("'", "''")
        url = f"{site_base}/_api/web/GetFolderByServerRelativeUrl('{parent_enc}')/Folders/AddUsingPath(DecodedUrl='{safe_name}')"
        with self._http() as client:
            resp = client.post(url, headers=headers)
            resp.raise_for_status()
        return f"{parent_server_relative.rstrip('/')}/{name}"

    def upload_file(self, parent_server_relative: str, name: str, content: bytes, *,
                    site_relative_url: Optional[str] = None, overwrite: bool = True) -> str:
        if not parent_server_relative.startswith("/"):
            parent_server_relative = "/" + parent_server_relative
        parent_enc = urllib.parse.quote(parent_server_relative, safe="/")
        digest = self._ensure_digest(site_relative_url)
        headers = {
            "X-RequestDigest": digest,
            "Content-Type": "application/octet-stream",
        }
        site_base = self._resolve_site(site_relative_url)
        safe_name = name.replace("'", "''")
        url = f"{site_base}/_api/web/GetFolderByServerRelativeUrl('{parent_enc}')/Files/Add(url='{safe_name}',overwrite={'true' if overwrite else 'false'})"
        with self._http() as client:
            resp = client.post(url, headers=headers, content=content)
            resp.raise_for_status()
        return f"{parent_server_relative.rstrip('/')}/{name}"

    def download_file(self, server_relative_url: str, *,
                      site_relative_url: Optional[str] = None) -> bytes:
        if not server_relative_url.startswith("/"):
            server_relative_url = "/" + server_relative_url
        enc = urllib.parse.quote(server_relative_url, safe="/")
        site_base = self._resolve_site(site_relative_url)
        url = f"{site_base}/_api/web/GetFileByServerRelativeUrl('{enc}')/$value"
        with self._http() as client:
            resp = client.get(url)
            resp.raise_for_status()
            return resp.content

    # Fetch item metadata (file or folder) using SharePoint REST
        # Check-out / Check-in / Versions
    def checkout_file(self, server_relative_url: str, *, site_relative_url: Optional[str] = None) -> None:
        if not server_relative_url.startswith("/"):
            server_relative_url = "/" + server_relative_url
        enc = urllib.parse.quote(server_relative_url, safe="/")
        site_base = self._resolve_site(site_relative_url)
        digest = self._ensure_digest(site_relative_url)
        headers = {"X-RequestDigest": digest}
        url = f"{site_base}/_api/web/GetFileByServerRelativeUrl('{enc}')/CheckOut"
        with self._http() as client:
            resp = client.post(url, headers=headers)
            resp.raise_for_status()

    def checkin_file(self, server_relative_url: str, *, comment: str = "", checkin_type: int = 1,
                      site_relative_url: Optional[str] = None) -> None:
        # checkin_type: 0=Minor, 1=Major, 2=Overwrite
        if not server_relative_url.startswith("/"):
            server_relative_url = "/" + server_relative_url
        enc = urllib.parse.quote(server_relative_url, safe="/")
        site_base = self._resolve_site(site_relative_url)
        digest = self._ensure_digest(site_relative_url)
        headers = {"X-RequestDigest": digest}
        # escape single quotes in comment
        safe_comment = (comment or "").replace("'", "''")
        url = f"{site_base}/_api/web/GetFileByServerRelativeUrl('{enc}')/CheckIn(comment='{safe_comment}',checkintype={int(checkin_type)})"
        with self._http() as client:
            resp = client.post(url, headers=headers)
            resp.raise_for_status()

    def undo_checkout(self, server_relative_url: str, *, site_relative_url: Optional[str] = None) -> None:
        if not server_relative_url.startswith("/"):
            server_relative_url = "/" + server_relative_url
        enc = urllib.parse.quote(server_relative_url, safe="/")
        site_base = self._resolve_site(site_relative_url)
        digest = self._ensure_digest(site_relative_url)
        headers = {"X-RequestDigest": digest}
        url = f"{site_base}/_api/web/GetFileByServerRelativeUrl('{enc}')/UndoCheckOut"
        with self._http() as client:
            resp = client.post(url, headers=headers)
            resp.raise_for_status()

    def list_versions(self, server_relative_url: str, *, site_relative_url: Optional[str] = None) -> List[dict]:
        if not server_relative_url.startswith("/"):
            server_relative_url = "/" + server_relative_url
        enc = urllib.parse.quote(server_relative_url, safe="/")
        site_base = self._resolve_site(site_relative_url)
        select = "VersionLabel,Created,CreatedBy/Title,Size"
        url = f"{site_base}/_api/web/GetFileByServerRelativeUrl('{enc}')/Versions?$select={urllib.parse.quote(select)}&$expand=CreatedBy"
        with self._http() as client:
            resp = client.get(url)
            resp.raise_for_status()
            data = resp.json()
        items = data.get("value") or data.get("d", {}).get("results", [])
        versions: List[dict] = []
        for it in items:
            versions.append({
                "label": it.get("VersionLabel") or it.get("ID") or "",
                "created": it.get("Created"),
                "author": (it.get("CreatedBy") or {}).get("Title"),
                "size": it.get("Size"),
            })
        return versions

    def restore_version(self, server_relative_url: str, label: str, *, site_relative_url: Optional[str] = None) -> None:
        if not server_relative_url.startswith("/"):
            server_relative_url = "/" + server_relative_url
        enc = urllib.parse.quote(server_relative_url, safe="/")
        site_base = self._resolve_site(site_relative_url)
        digest = self._ensure_digest(site_relative_url)
        headers = {"X-RequestDigest": digest}
        safe_label = (label or "").replace("'", "''")
        url = f"{site_base}/_api/web/GetFileByServerRelativeUrl('{enc}')/Versions/RestoreByLabel(versionlabel='{safe_label}')"
        with self._http() as client:
            resp = client.post(url, headers=headers)
            resp.raise_for_status()

    def get_item_info(self, server_relative_url: str, *, is_folder: bool, site_relative_url: Optional[str] = None) -> dict:
        if not server_relative_url.startswith("/"):
            server_relative_url = "/" + server_relative_url
        enc = urllib.parse.quote(server_relative_url, safe="/")
        site_base = self._resolve_site(site_relative_url)
        if is_folder:
            url = (
                f"{site_base}/_api/web/GetFolderByServerRelativeUrl('{enc}')"
                f"?$select=Name,ServerRelativeUrl,ItemCount,TimeLastModified"
            )
        else:
            # Split query to avoid '&' issues in some shells
            url = (
                f"{site_base}/_api/web/GetFileByServerRelativeUrl('{enc}')"
                f"?$select=Name,ServerRelativeUrl,Length,TimeLastModified,Author/Title,ModifiedBy/Title" \
                f"&$expand=Author,ModifiedBy"
            )
        with self._http() as client:
            r = client.get(url)
            r.raise_for_status()
            data = r.json()
        payload = data.get("d", data) or {}
        info: dict = {
            "name": payload.get("Name"),
            "path": payload.get("ServerRelativeUrl"),
            "mtime": payload.get("TimeLastModified"),
            "isDir": bool(is_folder),
        }
        if is_folder:
            info["size"] = 0
            info["itemCount"] = payload.get("ItemCount")
        else:
            try:
                info["size"] = int(payload.get("Length") or 0)
            except Exception:
                info["size"] = 0
            auth = payload.get("Author") or {}
            mod = payload.get("ModifiedBy") or {}
            info["author"] = auth.get("Title")
            info["modifiedBy"] = mod.get("Title")
        return info

    def _stringify_field_value(self, value) -> str:
        if value is None:
            return ""
        if isinstance(value, (str, int, float, bool)):
            return str(value)
        try:
            return json.dumps(value, ensure_ascii=False)
        except Exception:
            return str(value)

    def list_item_fields(self, server_relative_url: str, *, is_folder: bool, site_relative_url: Optional[str] = None) -> List[dict]:
        if not server_relative_url.startswith("/"):
            server_relative_url = "/" + server_relative_url
        enc = urllib.parse.quote(server_relative_url, safe="/")
        site_base = self._resolve_site(site_relative_url)
        if is_folder:
            item_url = f"{site_base}/_api/web/GetFolderByServerRelativeUrl('{enc}')/ListItemAllFields"
            fields_url = (
                f"{site_base}/_api/web/GetFolderByServerRelativeUrl('{enc}')/ListItemAllFields/ParentList/Fields"
                f"?$select=InternalName,Title,TypeAsString,ReadOnlyField,Hidden,Required,Choices"
            )
        else:
            item_url = f"{site_base}/_api/web/GetFileByServerRelativeUrl('{enc}')/ListItemAllFields"
            fields_url = (
                f"{site_base}/_api/web/GetFileByServerRelativeUrl('{enc}')/ListItemAllFields/ParentList/Fields"
                f"?$select=InternalName,Title,TypeAsString,ReadOnlyField,Hidden,Required,Choices"
            )
        with self._http() as client:
            item_resp = client.get(item_url)
            item_resp.raise_for_status()
            fields_resp = client.get(fields_url)
            fields_resp.raise_for_status()
        item_payload = item_resp.json().get("d", item_resp.json()) or {}
        fields_payload = fields_resp.json()
        fields = fields_payload.get("value") or fields_payload.get("d", {}).get("results", [])

        out: List[dict] = []
        for f in fields:
            internal_name = str(f.get("InternalName") or "").strip()
            if not internal_name:
                continue
            value = self._stringify_field_value(item_payload.get(internal_name))
            raw_choices = f.get("Choices")
            choices: List[str] = []
            if isinstance(raw_choices, dict):
                choices = [str(x) for x in (raw_choices.get("results") or []) if str(x).strip()]
            elif isinstance(raw_choices, list):
                choices = [str(x) for x in raw_choices if str(x).strip()]
            out.append({
                "internal_name": internal_name,
                "title": f.get("Title") or internal_name,
                "type": f.get("TypeAsString") or "",
                "read_only": bool(f.get("ReadOnlyField")),
                "hidden": bool(f.get("Hidden")),
                "required": bool(f.get("Required")),
                "value": value,
                "choices": choices,
            })
        out.sort(key=lambda x: (x["hidden"], x["read_only"], str(x["title"]).lower()))
        return out

    def update_item_fields(self, server_relative_url: str, fields: Dict[str, str], *, is_folder: bool, site_relative_url: Optional[str] = None) -> List[dict]:
        if not server_relative_url.startswith("/"):
            server_relative_url = "/" + server_relative_url
        enc = urllib.parse.quote(server_relative_url, safe="/")
        site_base = self._resolve_site(site_relative_url)
        if is_folder:
            url = f"{site_base}/_api/web/GetFolderByServerRelativeUrl('{enc}')/ListItemAllFields/ValidateUpdateListItem"
        else:
            url = f"{site_base}/_api/web/GetFileByServerRelativeUrl('{enc}')/ListItemAllFields/ValidateUpdateListItem"

        digest = self._ensure_digest(site_relative_url)
        headers = {
            "X-RequestDigest": digest,
            "Content-Type": "application/json;odata=verbose",
            "Accept": "application/json;odata=nometadata",
        }
        form_values = []
        for k, v in (fields or {}).items():
            key = str(k or "").strip()
            if not key:
                continue
            form_values.append({
                "FieldName": key,
                "FieldValue": "" if v is None else str(v),
            })
        body = {"formValues": form_values, "bNewDocumentUpdate": False}
        with self._http() as client:
            resp = client.post(url, headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json()
        results = data.get("value") or data.get("d", {}).get("ValidateUpdateListItem", {}).get("results", []) or data.get("ValidateUpdateListItem", [])
        if isinstance(results, dict):
            results = results.get("results", [])
        normalized: List[dict] = []
        for r in results or []:
            normalized.append({
                "field": r.get("FieldName") or r.get("FieldInternalName") or "",
                "has_exception": bool(r.get("HasException")),
                "error_message": r.get("ErrorMessage") or "",
                "value": r.get("FieldValue") or "",
            })
        return normalized

    def web_url(self, server_relative_url: str, *,
                site_relative_url: Optional[str] = None) -> str:
        site = self._resolve_site(site_relative_url)
        if not server_relative_url.startswith("/"):
            server_relative_url = "/" + server_relative_url
        parsed = urllib.parse.urlparse(site)
        return urllib.parse.urljoin(f"{parsed.scheme}://{parsed.netloc}", server_relative_url)

    def share_link(self, server_relative_url: str, *,
                   site_relative_url: Optional[str] = None) -> str:
        # Basic fallback: return direct browser URL. More advanced link generation can be added later.
        return self.web_url(server_relative_url, site_relative_url=site_relative_url)

    def get_effective_permissions(self, server_relative_url: str, *, is_folder: bool, site_relative_url: Optional[str] = None) -> dict:
        if not server_relative_url.startswith("/"):
            server_relative_url = "/" + server_relative_url
        enc = urllib.parse.quote(server_relative_url, safe="/")
        site_base = self._resolve_site(site_relative_url)
        if is_folder:
            url = (
                f"{site_base}/_api/web/GetFolderByServerRelativeUrl('{enc}')/ListItemAllFields"
                f"?$select=EffectiveBasePermissions"
            )
        else:
            url = (
                f"{site_base}/_api/web/GetFileByServerRelativeUrl('{enc}')/ListItemAllFields"
                f"?$select=EffectiveBasePermissions"
            )
        with self._http() as client:
            resp = client.get(url)
            resp.raise_for_status()
            data = resp.json()
        payload = data.get("d", data) or {}
        perms = payload.get("EffectiveBasePermissions") or {}
        low_raw = perms.get("Low", 0)
        high_raw = perms.get("High", 0)
        try:
            low = int(str(low_raw), 0)
        except Exception:
            try:
                low = int(str(low_raw))
            except Exception:
                low = 0
        try:
            high = int(str(high_raw), 0)
        except Exception:
            try:
                high = int(str(high_raw))
            except Exception:
                high = 0

        # Common SPBasePermissions (low bits)
        view_items = bool(low & 0x00000001)
        add_items = bool(low & 0x00000002)
        edit_items = bool(low & 0x00000004)
        delete_items = bool(low & 0x00000008)
        open_items = bool(low & 0x00000020)
        return {
            "raw_low": low,
            "raw_high": high,
            "can_view": view_items or open_items,
            "can_add": add_items,
            "can_edit": edit_items,
            "can_delete": delete_items,
            "can_open": open_items,
        }

    # New helpers
    def _resolve_site(self, site_relative_url: Optional[str]) -> str:
        if not site_relative_url:
            return self.base_url
        site_relative_url = site_relative_url.lstrip("/")
        return f"{self._resource_base}/{site_relative_url}"

    def _cookie_store_key(self) -> str:
        return self._resource_base

    def _default_cookie_domain(self) -> Optional[str]:
        return urllib.parse.urlparse(self._resource_base).hostname

    def _build_cookie_record(self, name: str, value: str) -> CookieRecord:
        return CookieRecord(
            name=str(name or "").strip(),
            value=str(value or ""),
            domain=self._default_cookie_domain(),
            path="/",
            secure=True,
            http_only=False,
            expires_at=None,
        )

    def _normalize_cookie_records(self, entry: Any) -> List[CookieRecord]:
        records: List[CookieRecord] = []
        if isinstance(entry, dict):
            if isinstance(entry.get("cookies"), list):
                for item in entry.get("cookies") or []:
                    if not isinstance(item, dict):
                        continue
                    try:
                        record = CookieRecord.from_dict(item)
                    except Exception:
                        continue
                    if record.name and record.value and not record.expired():
                        records.append(record)
                return records
            for name, value in entry.items():
                if isinstance(name, str) and isinstance(value, str) and name != "cookies":
                    record = self._build_cookie_record(name, value)
                    if record.name and record.value:
                        records.append(record)
        return records

    def _cookie_records(self) -> List[CookieRecord]:
        key = self._cookie_store_key()
        entry = self._cookies_store.get(key)
        records = self._normalize_cookie_records(entry)
        normalized_entry = {"cookies": [asdict(record) for record in records]}
        if entry != normalized_entry:
            self._cookies_store[key] = normalized_entry
            _save_cookies(self._cookies_store)
        return records

    def _set_cookie_records(self, records: List[CookieRecord]) -> None:
        unique: Dict[tuple[str, str, str], CookieRecord] = {}
        for record in records:
            if not record.name or not record.value or record.expired():
                continue
            domain = record.domain or self._default_cookie_domain() or ""
            path = record.path or "/"
            record.domain = domain or None
            record.path = path
            unique[(record.name, domain, path)] = record
        self._cookies_store[self._cookie_store_key()] = {
            "cookies": [asdict(record) for record in unique.values()]
        }
        _save_cookies(self._cookies_store)

    def _upsert_cookie_record(self, record: CookieRecord) -> None:
        records = self._cookie_records()
        merged: Dict[tuple[str, str, str], CookieRecord] = {}
        for item in records:
            domain = item.domain or ""
            path = item.path or "/"
            merged[(item.name, domain, path)] = item
        domain = record.domain or self._default_cookie_domain() or ""
        path = record.path or "/"
        record.domain = domain or None
        record.path = path
        merged[(record.name, domain, path)] = record
        self._set_cookie_records(list(merged.values()))
