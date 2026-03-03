from __future__ import annotations

import csv
import json
import os
import urllib.parse
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import List, Optional


LOG_FILENAME = "smart_explorer_link_migrations.json"


@dataclass
class LinkMigrationRecord:
    id: str
    timestamp: str
    operation_type: str
    item_type: str
    source_site_url: Optional[str]
    target_site_url: Optional[str]
    source_site_relative_url: Optional[str]
    target_site_relative_url: Optional[str]
    old_server_relative_url: str
    new_server_relative_url: str
    old_web_url: Optional[str]
    new_web_url: Optional[str]
    old_display_name: Optional[str]
    new_display_name: Optional[str]
    workspace_id: Optional[str]
    initiated_by: Optional[str]
    status: str
    notes: Optional[str] = None

    @staticmethod
    def from_dict(data: dict) -> "LinkMigrationRecord":
        return LinkMigrationRecord(
            id=str(data.get("id") or f"mig-{uuid.uuid4().hex[:8]}"),
            timestamp=str(data.get("timestamp") or datetime.now(timezone.utc).isoformat()),
            operation_type=str(data.get("operation_type") or "move"),
            item_type=str(data.get("item_type") or "file"),
            source_site_url=data.get("source_site_url"),
            target_site_url=data.get("target_site_url"),
            source_site_relative_url=data.get("source_site_relative_url"),
            target_site_relative_url=data.get("target_site_relative_url"),
            old_server_relative_url=str(data.get("old_server_relative_url") or ""),
            new_server_relative_url=str(data.get("new_server_relative_url") or ""),
            old_web_url=data.get("old_web_url"),
            new_web_url=data.get("new_web_url"),
            old_display_name=data.get("old_display_name"),
            new_display_name=data.get("new_display_name"),
            workspace_id=data.get("workspace_id"),
            initiated_by=data.get("initiated_by"),
            status=str(data.get("status") or "completed"),
            notes=data.get("notes"),
        )


class LinkMigrationLog:
    def __init__(self, path: Optional[str] = None) -> None:
        self.path = os.path.abspath(path or LOG_FILENAME)
        self._records: List[LinkMigrationRecord] = []
        self._load()

    def all(self) -> List[LinkMigrationRecord]:
        return list(self._records)

    def reload(self) -> None:
        self._load()

    def add(self, record: LinkMigrationRecord) -> LinkMigrationRecord:
        self._records.append(record)
        self._save()
        return record

    def delete(self, record_id: str) -> bool:
        before = len(self._records)
        self._records = [record for record in self._records if record.id != str(record_id or "")]
        changed = len(self._records) != before
        if changed:
            self._save()
        return changed

    def clear(self) -> int:
        removed = len(self._records)
        if not removed:
            return 0
        self._records = []
        self._save()
        return removed

    def import_json(self, path: str) -> int:
        return self.import_json_report(path)["added"]

    def import_json_report(self, path: str) -> dict:
        try:
            with open(path, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
        except Exception:
            return {"added": 0, "duplicates": 0, "conflicts": 0, "conflict_records": []}
        return self.merge_records_report(raw)

    def merge_records(self, rows: object) -> int:
        return self.merge_records_report(rows)["added"]

    def merge_records_report(self, rows: object) -> dict:
        if not isinstance(rows, list):
            return {"added": 0, "duplicates": 0, "conflicts": 0, "conflict_records": []}
        existing_keys = {
            self._record_key(record)
            for record in self._records
        }
        existing_sources: dict[tuple[str, str, str], set[tuple[str, str]]] = {}
        for record in self._records:
            source_key = self._source_key(record)
            target_key = self._target_key(record)
            existing_sources.setdefault(source_key, set()).add(target_key)

        added = 0
        duplicates = 0
        conflicts = 0
        conflict_records: list[dict] = []
        for item in rows:
            if not isinstance(item, dict):
                continue
            try:
                record = LinkMigrationRecord.from_dict(item)
            except Exception:
                continue
            key = self._record_key(record)
            if key in existing_keys:
                duplicates += 1
                continue
            source_key = self._source_key(record)
            target_key = self._target_key(record)
            prior_targets = existing_sources.setdefault(source_key, set())
            conflict_target = next((value for value in prior_targets if value != target_key), None)
            if conflict_target is not None:
                conflicts += 1
                conflict_records.append(
                    {
                        "source_site_relative_url": source_key[1],
                        "old_server_relative_url": source_key[2],
                        "operation_type": source_key[0],
                        "existing_target_site_relative_url": conflict_target[0],
                        "existing_new_server_relative_url": conflict_target[1],
                        "incoming_target_site_relative_url": target_key[0],
                        "incoming_new_server_relative_url": target_key[1],
                    }
                )
            self._records.append(record)
            existing_keys.add(key)
            prior_targets.add(target_key)
            added += 1
        if added:
            self._save()
        return {
            "added": added,
            "duplicates": duplicates,
            "conflicts": conflicts,
            "conflict_records": conflict_records,
        }

    def record(
        self,
        *,
        operation_type: str,
        item_type: str,
        old_server_relative_url: str,
        new_server_relative_url: str,
        source_site_relative_url: Optional[str] = None,
        target_site_relative_url: Optional[str] = None,
        source_site_url: Optional[str] = None,
        target_site_url: Optional[str] = None,
        old_web_url: Optional[str] = None,
        new_web_url: Optional[str] = None,
        old_display_name: Optional[str] = None,
        new_display_name: Optional[str] = None,
        workspace_id: Optional[str] = None,
        initiated_by: Optional[str] = None,
        status: str = "completed",
        notes: Optional[str] = None,
    ) -> LinkMigrationRecord:
        record = LinkMigrationRecord(
            id=f"mig-{uuid.uuid4().hex[:8]}",
            timestamp=datetime.now(timezone.utc).isoformat(),
            operation_type=operation_type,
            item_type=item_type,
            source_site_url=source_site_url,
            target_site_url=target_site_url,
            source_site_relative_url=source_site_relative_url,
            target_site_relative_url=target_site_relative_url,
            old_server_relative_url=self._normalize_path(old_server_relative_url),
            new_server_relative_url=self._normalize_path(new_server_relative_url),
            old_web_url=old_web_url,
            new_web_url=new_web_url,
            old_display_name=old_display_name,
            new_display_name=new_display_name,
            workspace_id=workspace_id,
            initiated_by=initiated_by,
            status=status,
            notes=notes,
        )
        return self.add(record)

    def resolve_path(self, server_relative_url: str, *, site_relative_url: Optional[str] = None) -> Optional[str]:
        resolved = self.resolve_target(server_relative_url, site_relative_url=site_relative_url)
        return resolved["server_relative_url"] if resolved else None

    def resolve_target(self, server_relative_url: str, *, site_relative_url: Optional[str] = None) -> Optional[dict]:
        path = self._normalize_path(server_relative_url)
        if not path:
            return None
        current = path
        current_site = (site_relative_url or "").strip() or None
        changed = False
        for _ in range(20):
            replacement = self._resolve_once(current, site_relative_url=current_site)
            if not replacement or replacement["server_relative_url"] == current:
                break
            current = replacement["server_relative_url"]
            current_site = replacement.get("site_relative_url") or current_site
            changed = True
        if not changed:
            return None
        return {
            "server_relative_url": current,
            "site_relative_url": current_site,
        }

    def export_csv(self, path: str) -> None:
        rows = [asdict(item) for item in self._records]
        if not rows:
            headers = [
                "timestamp",
                "operation_type",
                "item_type",
                "old_server_relative_url",
                "new_server_relative_url",
                "old_web_url",
                "new_web_url",
                "status",
            ]
        else:
            headers = list(rows[0].keys())
        with open(path, "w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=headers)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)

    def export_json(self, path: str) -> None:
        payload = [asdict(item) for item in self._records]
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)

    def build_web_url(self, base_url: Optional[str], server_relative_url: Optional[str]) -> Optional[str]:
        base = (base_url or "").strip()
        path = self._normalize_path(server_relative_url or "")
        if not base or not path:
            return None
        parsed = urllib.parse.urlparse(base)
        if not parsed.scheme or not parsed.netloc:
            return None
        return urllib.parse.urljoin(f"{parsed.scheme}://{parsed.netloc}", path)

    def _resolve_once(self, server_relative_url: str, *, site_relative_url: Optional[str]) -> Optional[dict]:
        path = self._normalize_path(server_relative_url)
        site_rel = (site_relative_url or "").strip() or None
        for record in reversed(self._records):
            if str(record.status or "").lower() != "completed":
                continue
            src_site = (record.source_site_relative_url or "").strip() or None
            if site_rel and src_site and site_rel != src_site:
                continue
            old_path = self._normalize_path(record.old_server_relative_url)
            new_path = self._normalize_path(record.new_server_relative_url)
            if not old_path or not new_path:
                continue
            if path == old_path:
                return {
                    "server_relative_url": new_path,
                    "site_relative_url": (record.target_site_relative_url or "").strip() or site_rel,
                }
            if path.startswith(old_path.rstrip("/") + "/"):
                suffix = path[len(old_path):]
                return {
                    "server_relative_url": new_path.rstrip("/") + suffix,
                    "site_relative_url": (record.target_site_relative_url or "").strip() or site_rel,
                }
        return None

    def _load(self) -> None:
        self._records = []
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
        except Exception:
            return
        if not isinstance(raw, list):
            return
        for item in raw:
            if not isinstance(item, dict):
                continue
            try:
                record = LinkMigrationRecord.from_dict(item)
            except Exception:
                continue
            self._records.append(record)

    def _save(self) -> None:
        tmp_path = self.path + ".tmp"
        payload = [asdict(item) for item in self._records]
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
        os.replace(tmp_path, self.path)

    @staticmethod
    def _record_key(record: LinkMigrationRecord) -> tuple[str, str, str, str, str]:
        return (
            str(record.operation_type or ""),
            str(record.source_site_relative_url or ""),
            LinkMigrationLog._normalize_path(record.old_server_relative_url),
            str(record.target_site_relative_url or ""),
            LinkMigrationLog._normalize_path(record.new_server_relative_url),
        )

    @staticmethod
    def _source_key(record: LinkMigrationRecord) -> tuple[str, str, str]:
        return (
            str(record.operation_type or ""),
            str(record.source_site_relative_url or ""),
            LinkMigrationLog._normalize_path(record.old_server_relative_url),
        )

    @staticmethod
    def _target_key(record: LinkMigrationRecord) -> tuple[str, str]:
        return (
            str(record.target_site_relative_url or ""),
            LinkMigrationLog._normalize_path(record.new_server_relative_url),
        )

    @staticmethod
    def _normalize_path(path: str) -> str:
        value = str(path or "").strip()
        if not value:
            return ""
        if not value.startswith("/"):
            value = "/" + value
        return value.rstrip("/") or "/"
