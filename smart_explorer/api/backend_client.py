from __future__ import annotations

from typing import Optional, Dict
import httpx


class BackendClient:
    def __init__(self, base_url: str = "http://127.0.0.1:5001") -> None:
        self.base_url = base_url.rstrip("/")

    def get(self, path: str, params: Optional[dict] = None) -> dict:
        with httpx.Client(timeout=15.0) as c:
            r = c.get(self.base_url + path, params=params)
            r.raise_for_status()
            return r.json()

    def post(self, path: str, json: Optional[dict] = None) -> dict:
        with httpx.Client(timeout=15.0) as c:
            r = c.post(self.base_url + path, json=json)
            r.raise_for_status()
            return r.json()

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

    def sp_rename(self, server_relative_url: str, new_name: str, is_folder: bool) -> dict:
        return self.post(
            "/api/sp/rename",
            json={
                "server_relative_url": server_relative_url,
                "new_name": new_name,
                "is_folder": is_folder,
            },
        )

    def sp_default_doclib(self) -> dict:
        return self.get("/api/sp/default_doclib")
