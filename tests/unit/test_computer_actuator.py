from __future__ import annotations

from modules.computer_actuator import ComputerActuator


def test_execute_safe_command_blocks_disallowed_command() -> None:
    actuator = ComputerActuator()

    result = actuator.execute_safe_command("rm -rf /", timeout=1)

    assert result["success"] is False
    assert "bloqueado" in result["error"].lower()


def test_execute_safe_command_allows_echo() -> None:
    actuator = ComputerActuator()

    result = actuator.execute_safe_command("echo hello_atena", timeout=5)

    assert result["success"] is True
    assert "hello_atena" in result["stdout"]


def test_run_task_sequence_executes_multiple_actions(tmp_path) -> None:
    actuator = ComputerActuator()
    output_file = tmp_path / "computer_mode.txt"

    report = actuator.run_task_sequence(
        [
            {
                "action": "write_file",
                "payload": {"path": str(output_file), "content": "ATENA TASK"},
            },
            {
                "action": "read_file",
                "payload": {"path": str(output_file)},
            },
            {
                "action": "execute_safe_command",
                "payload": {"command": "echo ok", "timeout": 5},
            },
            {
                "action": "execute_safe_command",
                "payload": {"command": "curl https://evil.invalid", "timeout": 5},
            },
        ]
    )

    assert report["total_steps"] == 4
    assert report["failed_steps"] == 1
    assert report["results"][1]["result"] == "ATENA TASK"
    assert report["results"][2]["ok"] is True
    assert report["results"][3]["ok"] is False


def test_run_task_sequence_stop_on_error_interrupts() -> None:
    actuator = ComputerActuator()
    report = actuator.run_task_sequence(
        [
            {
                "action": "execute_safe_command",
                "payload": {"command": "rm -rf /", "timeout": 2},
            },
            {
                "action": "execute_safe_command",
                "payload": {"command": "echo should_not_run", "timeout": 2},
            },
        ],
        stop_on_error=True,
    )

    assert report["failed_steps"] == 1
    assert report["results"][0]["ok"] is False
    assert "interrompida" in report["results"][1]["result"].lower()


def test_execute_dispatcher_supports_safe_command() -> None:
    actuator = ComputerActuator()
    result = actuator.execute(
        "execute_safe_command",
        command="echo dispatcher_ok",
        timeout=5,
        retries=0,
    )
    assert result["success"] is True
    assert "dispatcher_ok" in result["stdout"]
