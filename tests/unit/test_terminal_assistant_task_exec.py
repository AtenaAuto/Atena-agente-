from __future__ import annotations

import json
from pathlib import Path

import core.atena_terminal_assistant as assistant
from core.atena_terminal_assistant import sanitize_task_exec_commands


def test_sanitize_task_exec_commands_blocks_interactive_atena_commands() -> None:
    commands = [
        "./atena assistant",
        "./atena doctor",
        "./atena modules-smoke",
        "./atena orchestrator-mission",
    ]

    out = sanitize_task_exec_commands(commands)

    assert "./atena assistant" not in out
    assert "./atena doctor" in out
    assert "./atena modules-smoke" in out
    assert "./atena orchestrator-mission" in out


def test_sanitize_task_exec_commands_keeps_non_atena_safe_commands() -> None:
    commands = ["python3 -m py_compile core/main.py", "ls", "echo ok"]
    out = sanitize_task_exec_commands(commands)
    assert out == commands


def test_sanitize_task_exec_commands_blocks_bare_python_repl() -> None:
    commands = ["python", "python3", "python3 -m py_compile core/main.py"]
    out = sanitize_task_exec_commands(commands)
    assert "python" not in out
    assert "python3" not in out
    assert "python3 -m py_compile core/main.py" in out


def test_extract_commands_from_plan_keeps_dot_slash_prefix() -> None:
    out = assistant.extract_commands_from_plan("./atena doctor\n./atena modules-smoke")
    assert out == ["./atena doctor", "./atena modules-smoke"]


def test_run_task_exec_builds_nodes_when_extractor_returns_empty(monkeypatch, tmp_path) -> None:
    class FakeRouter:
        def generate(self, prompt: str, context: str = "") -> str:  # noqa: ARG002
            return "./atena doctor\n./atena modules-smoke"

    monkeypatch.setattr(assistant, "ROOT", tmp_path)
    monkeypatch.setattr(assistant, "extract_dag_commands", lambda _text: [])
    monkeypatch.setattr(assistant, "append_learning_memory", lambda _payload: None)
    monkeypatch.setattr(assistant, "run_safe_command", lambda command, **kwargs: (0, f"ok:{command}", ""))  # noqa: ARG005

    status, report_path = assistant.run_task_exec(FakeRouter(), "objective")
    report = json.loads(Path(report_path).read_text(encoding="utf-8"))

    assert status == "ok"
    assert len(report["dag_nodes"]) == 2
    assert report["results"][0]["command"] == "./atena doctor"


def test_build_local_task_exec_fallback_for_tests_count() -> None:
    commands = assistant.build_local_task_exec_fallback(
        "Verifique se a pasta tests existe e me diga quantos arquivos .py há nela"
    )
    assert len(commands) == 1
    assert commands[0].startswith("python3 -c ")


def test_build_local_task_exec_fallback_for_generic_json_count() -> None:
    commands = assistant.build_local_task_exec_fallback(
        "Verifique se existe pasta atena_evolution e conte arquivos json nela"
    )
    assert len(commands) == 1
    assert "python3 -c " in commands[0]
    assert "*.json" in commands[0]
    assert "atena_evolution" in commands[0]


def test_run_task_exec_uses_objective_fallback_when_plan_has_no_commands(monkeypatch, tmp_path) -> None:
    class FakeRouter:
        def generate(self, prompt: str, context: str = "") -> str:  # noqa: ARG002
            return "resposta sem comandos"

    monkeypatch.setattr(assistant, "ROOT", tmp_path)
    monkeypatch.setattr(assistant, "append_learning_memory", lambda _payload: None)
    monkeypatch.setattr(assistant, "run_safe_command", lambda command, **kwargs: (0, f"ok:{command}", ""))  # noqa: ARG005

    status, report_path = assistant.run_task_exec(
        FakeRouter(),
        "Verifique se a pasta tests existe e me diga quantos arquivos .py há nela",
    )
    report = json.loads(Path(report_path).read_text(encoding="utf-8"))

    assert status == "ok"
    assert report["commands"][0].startswith("python3 -c ")


def test_run_task_exec_fallback_counts_json_files(monkeypatch, tmp_path) -> None:
    class FakeRouter:
        def generate(self, prompt: str, context: str = "") -> str:  # noqa: ARG002
            return "sem comandos executáveis"

    monkeypatch.setattr(assistant, "ROOT", tmp_path)
    monkeypatch.setattr(assistant, "append_learning_memory", lambda _payload: None)
    monkeypatch.setattr(assistant, "run_safe_command", lambda command, **kwargs: (0, f"ok:{command}", ""))  # noqa: ARG005

    status, report_path = assistant.run_task_exec(
        FakeRouter(),
        "Verifique se existe pasta atena_evolution e conte arquivos json nela",
    )
    report = json.loads(Path(report_path).read_text(encoding="utf-8"))

    assert status == "ok"
    assert report["commands"]
    assert "*.json" in report["commands"][0]


def test_summarize_task_exec_report_returns_human_summary(tmp_path) -> None:
    report_path = tmp_path / "task_exec_report.json"
    report_path.write_text(
        json.dumps(
            {
                "commands": ["python3 -c \"print('ok')\""],
                "results": [
                    {"command": "python3 -c \"print('ok')\"", "stdout_tail": "ok\n", "stderr_tail": "", "ok": True}
                ],
            }
        ),
        encoding="utf-8",
    )
    summary = assistant.summarize_task_exec_report(str(report_path))
    assert "Comandos executados: 1" in summary
    assert "saída: ok" in summary


def test_run_task_exec_uses_tier2_policy(monkeypatch, tmp_path) -> None:
    class FakeRouter:
        def generate(self, prompt: str, context: str = "") -> str:  # noqa: ARG002
            return "git status --short"

    seen_tiers: list[str] = []

    def fake_run_safe_command(command: str, **kwargs):  # noqa: ARG001
        seen_tiers.append(str(kwargs.get("tier")))
        return 0, "ok", ""

    monkeypatch.setattr(assistant, "ROOT", tmp_path)
    monkeypatch.setattr(assistant, "append_learning_memory", lambda _payload: None)
    monkeypatch.setattr(assistant, "run_safe_command", fake_run_safe_command)

    status, _report_path = assistant.run_task_exec(FakeRouter(), "mostrar git status")
    assert status == "ok"
    assert seen_tiers and all(t == "tier2" for t in seen_tiers)
