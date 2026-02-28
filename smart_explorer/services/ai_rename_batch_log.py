from __future__ import annotations

import csv
import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import List, Optional


LOG_FILENAME = "smart_explorer_ai_rename_batches.json"


@dataclass
class AIRenameBatchOperation:
    source_path: str
    target_path: str
    action: str
    reason: str
    is_dir: bool = False
    status: str = "planned"
    error: Optional[str] = None


@dataclass
class AIRenameBatchRecord:
    id: str
    timestamp: str
    kind: str
    site_relative_url: Optional[str]
    root_path: str
    instruction: str
    recursive: bool
    summary: str
    warnings: List[str] = field(default_factory=list)
    operations: List[AIRenameBatchOperation] = field(default_factory=list)

    @staticmethod
    def from_dict(data: dict) -> "AIRenameBatchRecord":
        return AIRenameBatchRecord(
            id=str(data.get("id") or f"ai-batch-{uuid.uuid4().hex[:8]}"),
            timestamp=str(data.get("timestamp") or datetime.now(timezone.utc).isoformat()),
            kind=str(data.get("kind") or "local"),
            site_relative_url=data.get("site_relative_url"),
            root_path=str(data.get("root_path") or ""),
            instruction=str(data.get("instruction") or ""),
            recursive=bool(data.get("recursive")),
            summary=str(data.get("summary") or ""),
            warnings=[str(value) for value in (data.get("warnings") or []) if str(value).strip()],
            operations=[
                AIRenameBatchOperation(
                    source_path=str(op.get("source_path") or ""),
                    target_path=str(op.get("target_path") or ""),
                    action=str(op.get("action") or ""),
                    reason=str(op.get("reason") or ""),
                    is_dir=bool(op.get("is_dir")),
                    status=str(op.get("status") or "planned"),
                    error=(str(op.get("error")) if op.get("error") is not None else None),
                )
                for op in (data.get("operations") or [])
                if isinstance(op, dict)
            ],
        )


class AIRenameBatchLog:
    def __init__(self, path: Optional[str] = None) -> None:
        self.path = os.path.abspath(path or LOG_FILENAME)
        self._records: List[AIRenameBatchRecord] = []
        self._load()

    def all(self) -> List[AIRenameBatchRecord]:
        return list(self._records)

    def reload(self) -> None:
        self._load()

    def record(
        self,
        *,
        kind: str,
        root_path: str,
        instruction: str,
        recursive: bool,
        summary: str,
        site_relative_url: Optional[str] = None,
        warnings: Optional[List[str]] = None,
        operations: Optional[List[dict]] = None,
    ) -> AIRenameBatchRecord:
        record = AIRenameBatchRecord(
            id=f"ai-batch-{uuid.uuid4().hex[:8]}",
            timestamp=datetime.now(timezone.utc).isoformat(),
            kind=str(kind or "local"),
            site_relative_url=site_relative_url,
            root_path=str(root_path or ""),
            instruction=str(instruction or ""),
            recursive=bool(recursive),
            summary=str(summary or ""),
            warnings=[str(value) for value in (warnings or []) if str(value).strip()],
            operations=[
                AIRenameBatchOperation(
                    source_path=str(op.get("source_path") or ""),
                    target_path=str(op.get("target_path") or ""),
                    action=str(op.get("action") or ""),
                    reason=str(op.get("reason") or ""),
                    is_dir=bool(op.get("is_dir")),
                    status=str(op.get("status") or "planned"),
                    error=(str(op.get("error")) if op.get("error") is not None else None),
                )
                for op in (operations or [])
                if isinstance(op, dict)
            ],
        )
        self._records.append(record)
        self._save()
        return record

    def export_json(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump([self._serialize(record) for record in self._records], fh, indent=2)

    def export_csv(self, path: str) -> None:
        rows: list[dict] = []
        for record in self._records:
            for op in record.operations:
                rows.append(
                    {
                        "batch_id": record.id,
                        "timestamp": record.timestamp,
                        "kind": record.kind,
                        "site_relative_url": record.site_relative_url or "",
                        "root_path": record.root_path,
                        "recursive": record.recursive,
                        "summary": record.summary,
                        "instruction": record.instruction,
                        "source_path": op.source_path,
                        "target_path": op.target_path,
                        "action": op.action,
                        "reason": op.reason,
                        "is_dir": op.is_dir,
                        "status": op.status,
                        "error": op.error or "",
                    }
                )
        headers = [
            "batch_id",
            "timestamp",
            "kind",
            "site_relative_url",
            "root_path",
            "recursive",
            "summary",
            "instruction",
            "source_path",
            "target_path",
            "action",
            "reason",
            "is_dir",
            "status",
            "error",
        ]
        with open(path, "w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=headers)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)

    def _serialize(self, record: AIRenameBatchRecord) -> dict:
        data = asdict(record)
        return data

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
                self._records.append(AIRenameBatchRecord.from_dict(item))
            except Exception:
                continue

    def _save(self) -> None:
        tmp_path = self.path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump([self._serialize(record) for record in self._records], fh, indent=2)
        os.replace(tmp_path, self.path)


__all__ = ["AIRenameBatchLog", "AIRenameBatchRecord", "AIRenameBatchOperation"]
