#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Controle de acesso multi-tenant para ATENA."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class AccessRole(str, Enum):
    ADMIN = "admin"
    DEV = "dev"
    VIEWER = "viewer"


@dataclass(frozen=True)
class Tenant:
    tenant_id: str
    name: str


@dataclass(frozen=True)
class Workspace:
    workspace_id: str
    tenant_id: str
    name: str


@dataclass(frozen=True)
class UserIdentity:
    user_id: str
    tenant_id: str
    role: AccessRole
    workspaces: set[str] = field(default_factory=set)


class AccessManager:
    """Validação de isolamento entre tenant/workspace."""

    @staticmethod
    def can_access_workspace(user: UserIdentity, workspace: Workspace) -> bool:
        if user.tenant_id != workspace.tenant_id:
            return False
        if user.role == AccessRole.ADMIN:
            return True
        return workspace.workspace_id in user.workspaces


@dataclass(frozen=True)
class TenantQuota:
    requests_per_minute: int
    max_parallel_jobs: int
    max_storage_mb: int


class QuotaManager:
    @staticmethod
    def evaluate_usage(quota: TenantQuota, *, requests_per_minute: int, parallel_jobs: int, storage_mb: int) -> dict[str, object]:
        checks = {
            "requests_per_minute": requests_per_minute <= quota.requests_per_minute,
            "parallel_jobs": parallel_jobs <= quota.max_parallel_jobs,
            "storage_mb": storage_mb <= quota.max_storage_mb,
        }
        return {
            "quota": {
                "requests_per_minute": quota.requests_per_minute,
                "max_parallel_jobs": quota.max_parallel_jobs,
                "max_storage_mb": quota.max_storage_mb,
            },
            "usage": {
                "requests_per_minute": requests_per_minute,
                "parallel_jobs": parallel_jobs,
                "storage_mb": storage_mb,
            },
            "checks": checks,
            "status": "ok" if all(checks.values()) else "exceeded",
        }
