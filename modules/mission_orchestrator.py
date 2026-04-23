#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Orquestrador de missões com checkpoint, retry e fallback para ATENA."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


TaskHandler = Callable[[Dict[str, Any]], Dict[str, Any]]


@dataclass
class TaskNode:
    name: str
    handler: TaskHandler
    retries: int = 0
    retry_delay_seconds: float = 0.0
    continue_on_failure: bool = False
    fallback_handler: Optional[TaskHandler] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class AtenaMissionOrchestrator:
    """Executa missões em etapas com persistência de estado."""

    def __init__(self, root_path: str | Path):
        self.root_path = Path(root_path)
        self.tasks: List[TaskNode] = []
        self.runs_dir = self.root_path / "atena_evolution" / "orchestrator_runs"
        self.runs_dir.mkdir(parents=True, exist_ok=True)

    def add_task(self, task: TaskNode) -> None:
        self.tasks.append(task)

    def _new_run_id(self) -> str:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        return f"mission_{stamp}"

    def _checkpoint_path(self, run_id: str) -> Path:
        return self.runs_dir / f"{run_id}.json"

    def _write_checkpoint(self, run_id: str, payload: Dict[str, Any]) -> None:
        self._checkpoint_path(run_id).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _read_checkpoint(self, run_id: str) -> Dict[str, Any]:
        path = self._checkpoint_path(run_id)
        if not path.exists():
            raise FileNotFoundError(f"Checkpoint não encontrado para run_id={run_id}")
        return json.loads(path.read_text(encoding="utf-8"))

    def run(
        self,
        initial_context: Optional[Dict[str, Any]] = None,
        run_id: Optional[str] = None,
        resume_from_checkpoint: bool = False,
    ) -> Dict[str, Any]:
        run_id = run_id or self._new_run_id()
        context: Dict[str, Any] = dict(initial_context or {})
        steps: List[Dict[str, Any]] = []
        start_index = 0

        if resume_from_checkpoint:
            checkpoint = self._read_checkpoint(run_id)
            context = dict(checkpoint.get("context", {}))
            steps = list(checkpoint.get("steps", []))
            start_index = len(steps)
            for i, step in enumerate(steps):
                if step.get("status") == "failed":
                    start_index = i
                    steps = steps[:i]
                    break

        status = "ok"
        for idx, task in enumerate(self.tasks[start_index:], start=start_index + 1):
            started = time.perf_counter()
            task_result: Dict[str, Any] = {
                "index": idx,
                "name": task.name,
                "status": "ok",
                "attempts": 0,
                "used_fallback": False,
                "metadata": task.metadata,
            }

            attempts = max(1, task.retries + 1)
            last_error = None
            success_payload: Optional[Dict[str, Any]] = None

            for attempt in range(1, attempts + 1):
                task_result["attempts"] = attempt
                try:
                    success_payload = task.handler(context)
                    break
                except Exception as exc:  # noqa: BLE001
                    last_error = str(exc)
                    if attempt < attempts and task.retry_delay_seconds > 0:
                        time.sleep(task.retry_delay_seconds)

            if success_payload is None and task.fallback_handler is not None:
                try:
                    success_payload = task.fallback_handler(context)
                    task_result["used_fallback"] = True
                    task_result["status"] = "fallback"
                except Exception as exc:  # noqa: BLE001
                    last_error = f"fallback_error: {exc}"

            if success_payload is None:
                task_result["status"] = "failed"
                task_result["error"] = last_error or "unknown_error"
                steps.append(task_result)
                status = "partial"
                checkpoint = {
                    "run_id": run_id,
                    "status": status,
                    "context": context,
                    "steps": steps,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
                self._write_checkpoint(run_id, checkpoint)
                if not task.continue_on_failure:
                    break
                continue

            context.update(success_payload)
            task_result["output_keys"] = sorted(success_payload.keys())
            task_result["duration_ms"] = round((time.perf_counter() - started) * 1000, 2)
            steps.append(task_result)

            checkpoint = {
                "run_id": run_id,
                "status": status,
                "context": context,
                "steps": steps,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            self._write_checkpoint(run_id, checkpoint)

        final = {
            "run_id": run_id,
            "status": status,
            "total_tasks": len(self.tasks),
            "completed_steps": len(steps),
            "remaining_steps": max(0, len(self.tasks) - len(steps)),
            "context": context,
            "steps": steps,
            "resumed": resume_from_checkpoint,
            "checkpoint_path": str(self._checkpoint_path(run_id)),
        }
        self._write_checkpoint(run_id, final)
        return final

    def resume(self, run_id: str) -> Dict[str, Any]:
        """Retoma uma execução a partir do checkpoint existente."""
        return self.run(run_id=run_id, resume_from_checkpoint=True)
