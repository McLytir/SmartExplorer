from __future__ import annotations

from typing import Optional, Dict
import httpx
import os


class BackendClient:
    def __init__(self, base_url: str = "http://127.0.0.1:5001") -> None:
        try:
            env_url = os.getenv("SMX_BACKEND_URL") or os.getenv("SMART_EXPLORER_BACKEND_URL")
            if env_url and base_url == "http://127.0.0.1:5001":
                base_url = env_url
        except Exception:
            pass
        self.base_url = base_url.rstrip("/")

    def get(self, path: str, params: Optional[dict] = None) -> dict:
        with httpx.Client(timeout=15.0) as c:
            r = c.get(self.base_url + path, params=params)
            r.raise_for_status()
            return r.json()

    def post(self, path: str, json: Optional[dict] = None) -> dict:
        with httpx.Client(timeout=60.0) as c:
            r = c.post(self.base_url + path, json=json)
            r.raise_for_status()
            if r.headers.get("content-type", "").startswith("application/json"):
                return r.json()
            return {}

    def get_settings(self) -> dict:
        return self.get("/api/settings")

    def update_settings(self, **kwargs) -> dict:
        return self.post("/api/settings", json=kwargs)

    def set_sp_cookies(self, base_url: str, cookies: Optional[Dict[str, str]] = None, cookie_header: Optional[str] = None) -> dict:
        payload = {"base_url": base_url}
        if cookies:
            payload["cookies"] = cookies
        if cookie_header:
            payload["cookie_header"] = cookie_header
        return self.post("/api/sp/cookies", json=payload)

    def sp_list(self, site_relative_url: str, folder_server_relative_url: str) -> dict:
        params = {
            "site_relative_url": site_relative_url,
            "folder_server_relative_url": folder_server_relative_url,
        }
        return self.get("/api/sp/list", params=params)

    def sp_rename(self, server_relative_url: str, new_name: str, is_folder: bool, *, site_relative_url: Optional[str] = None) -> dict:
        return self.post(
            "/api/sp/rename",
            json={
                "server_relative_url": server_relative_url,
                "new_name": new_name,
                "is_folder": is_folder,
                "site_relative_url": site_relative_url,
            },
        )

    def sp_default_doclib(self) -> dict:
        return self.get("/api/sp/default_doclib")

    def sp_sites(self) -> dict:
        return self.get("/api/sp/sites")

    def sp_libraries(self, site_relative_url: Optional[str] = None) -> dict:
        params = {"site_relative_url": site_relative_url} if site_relative_url else None
        return self.get("/api/sp/libraries", params=params)

    def sp_copy(self, source: str, target: str, *, is_folder: bool, overwrite: bool = False, site_relative_url: Optional[str] = None) -> dict:
        payload = {
            "source_server_relative_url": source,
            "target_server_relative_url": target,
            "is_folder": is_folder,
            "overwrite": overwrite,
            "site_relative_url": site_relative_url,
        }
        return self.post("/api/sp/copy", json=payload)

    def sp_move(self, source: str, target: str, *, is_folder: bool, overwrite: bool = False, site_relative_url: Optional[str] = None) -> dict:
        payload = {
            "source_server_relative_url": source,
            "target_server_relative_url": target,
            "is_folder": is_folder,
            "overwrite": overwrite,
            "site_relative_url": site_relative_url,
        }
        return self.post("/api/sp/move", json=payload)

    def sp_delete(self, server_relative_url: str, *, is_folder: bool, site_relative_url: Optional[str] = None, recycle: bool = True) -> dict:
        payload = {
            "server_relative_url": server_relative_url,
            "is_folder": is_folder,
            "site_relative_url": site_relative_url,
            "recycle": recycle,
        }
        return self.post("/api/sp/delete", json=payload)

    def sp_create_folder(self, parent_server_relative_url: str, name: str, *, site_relative_url: Optional[str] = None) -> dict:
        payload = {
            "parent_server_relative_url": parent_server_relative_url,
            "name": name,
            "site_relative_url": site_relative_url,
        }
        return self.post("/api/sp/folder", json=payload)

    def sp_upload(self, parent_server_relative_url: str, name: str, content_base64: str, *, site_relative_url: Optional[str] = None, overwrite: bool = True) -> dict:
        payload = {
            "parent_server_relative_url": parent_server_relative_url,
            "name": name,
            "content_base64": content_base64,
            "site_relative_url": site_relative_url,
            "overwrite": overwrite,
        }
        return self.post("/api/sp/upload", json=payload)

    def sp_share_link(self, server_relative_url: str, *, site_relative_url: Optional[str] = None) -> dict:
        payload = {
            "server_relative_url": server_relative_url,
            "site_relative_url": site_relative_url,
        }
        return self.post("/api/sp/share-link", json=payload)

    def sp_properties(self, server_relative_url: str, *, is_folder: bool, site_relative_url: Optional[str] = None) -> dict:
        payload = {
            "server_relative_url": server_relative_url,
            "is_folder": is_folder,
            "site_relative_url": site_relative_url,
        }
        return self.post("/api/sp/properties", json=payload)

    def sp_download(self, server_relative_url: str, *, site_relative_url: Optional[str] = None) -> bytes:
        params = {
            "server_relative_url": server_relative_url,
        }
        if site_relative_url:
            params["site_relative_url"] = site_relative_url
        with httpx.Client(timeout=60.0) as c:
            r = c.get(self.base_url + "/api/sp/download", params=params)
            r.raise_for_status()
            return r.content

    # Check-out / Check-in / Versions
    def sp_checkout(self, server_relative_url: str, *, site_relative_url: Optional[str] = None) -> dict:
        payload = {"server_relative_url": server_relative_url, "site_relative_url": site_relative_url}
        return self.post("/api/sp/checkout", json=payload)

    def sp_checkin(self, server_relative_url: str, *, comment: str = "", checkin_type: int = 1, site_relative_url: Optional[str] = None) -> dict:
        payload = {
            "server_relative_url": server_relative_url,
            "comment": comment,
            "checkin_type": checkin_type,
            "site_relative_url": site_relative_url,
        }
        return self.post("/api/sp/checkin", json=payload)

    def sp_undo_checkout(self, server_relative_url: str, *, site_relative_url: Optional[str] = None) -> dict:
        payload = {"server_relative_url": server_relative_url, "site_relative_url": site_relative_url}
        return self.post("/api/sp/undo-checkout", json=payload)

    def sp_versions(self, server_relative_url: str, *, site_relative_url: Optional[str] = None) -> dict:
        params = {"server_relative_url": server_relative_url}
        if site_relative_url:
            params["site_relative_url"] = site_relative_url
        return self.get("/api/sp/versions", params=params)

    def sp_restore_version(self, server_relative_url: str, label: str, *, site_relative_url: Optional[str] = None) -> dict:
        payload = {"server_relative_url": server_relative_url, "label": label, "site_relative_url": site_relative_url}
        return self.post("/api/sp/restore-version", json=payload)

    def sp_download_version(self, server_relative_url: str, label: str, *, site_relative_url: Optional[str] = None) -> bytes:
        params = {"server_relative_url": server_relative_url, "label": label}
        if site_relative_url:
            params["site_relative_url"] = site_relative_url
        with httpx.Client(timeout=60.0) as c:
            r = c.get(self.base_url + "/api/sp/download-version", params=params)
            r.raise_for_status()
            return r.content
