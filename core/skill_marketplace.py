#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Catálogo interno de skills/plugins com curadoria."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class SkillRecord:
    skill_id: str
    version: str
    risk_level: str
    cost_class: str
    compatible_with: str
    approved: bool = False
    active: bool = False
    sandbox_passed: bool = True
    contract_passed: bool = True
    security_passed: bool = True
    validation_enforced: bool = False


class SkillMarketplace:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> list[dict]:
        if not self.path.exists():
            return []
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _save(self, records: list[dict]) -> None:
        self.path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")

    def register(self, record: SkillRecord) -> None:
        records = self._load()
        exists = any(r.get("skill_id") == record.skill_id and r.get("version") == record.version for r in records)
        if exists:
            return
        same_skill = [r for r in records if r.get("skill_id") == record.skill_id]
        payload = asdict(record)
        if not same_skill:
            payload["active"] = True
        records.append(payload)
        self._save(records)

    def approve(self, skill_id: str, version: str | None = None) -> bool:
        records = self._load()
        updated = False
        for r in records:
            if r.get("skill_id") != skill_id:
                continue
            if version and r.get("version") != version:
                continue
            r["approved"] = True
            updated = True
        if updated:
            self._save(records)
        return updated

    def promote(self, skill_id: str, version: str) -> bool:
        records = self._load()
        found = False
        approved = False
        validated = False
        for r in records:
            if r.get("skill_id") != skill_id:
                continue
            if r.get("version") == version:
                found = True
                approved = bool(r.get("approved", False))
                if bool(r.get("validation_enforced", False)):
                    validated = all(
                        bool(r.get(k, False))
                        for k in ("sandbox_passed", "contract_passed", "security_passed")
                    )
                else:
                    validated = True
        if not found or not approved or not validated:
            return False
        for r in records:
            if r.get("skill_id") == skill_id:
                r["active"] = r.get("version") == version
        self._save(records)
        return True

    def rollback(self, skill_id: str, to_version: str) -> bool:
        return self.promote(skill_id, to_version)

    def validate(self, skill_id: str, version: str, sandbox_passed: bool, contract_passed: bool, security_passed: bool) -> bool:
        records = self._load()
        updated = False
        for r in records:
            if r.get("skill_id") == skill_id and r.get("version") == version:
                r["sandbox_passed"] = bool(sandbox_passed)
                r["contract_passed"] = bool(contract_passed)
                r["security_passed"] = bool(security_passed)
                r["validation_enforced"] = True
                updated = True
        if updated:
            self._save(records)
        return updated

    def list_records(self) -> list[dict]:
        return self._load()

    def active_version(self, skill_id: str) -> str | None:
        for record in self._load():
            if record.get("skill_id") == skill_id and record.get("active") is True:
                return str(record.get("version"))
        return None
