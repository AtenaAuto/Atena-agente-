from pathlib import Path

from examples.atena_windows_guest_demo import (
    run_atena_windows_guest_in_vm,
    run_atena_windows_stress_in_vm,
)


def test_atena_windows_guest_demo_runs_with_pe_loader_and_win32_api_calls():
    report = run_atena_windows_guest_in_vm()
    logs = "\n".join(report["result"]["kernel_log"])
    self_logs = "\n".join(report["atena_self_result"]["kernel_log"])

    assert report["pe_name"] == "notepad.exe"
    assert report["installed_programs"] == ["atena_self.exe", "notepad.exe"]
    assert report["install_path"].endswith("/notepad.exe.apkg")
    assert report["atena_self_install_path"].endswith("/atena_self.exe.apkg")
    assert report["package_url"].endswith("/packages/notepad.exe.apkg")
    assert len(report["published_urls"]) == 2
    assert report["autocomplete_remote"] == ["remote-install", "remove"]
    assert report["login_result"] == {"ok": True, "user": "admin", "home": "/home/admin"}
    assert report["whoami_result"] == {"ok": True, "user": "admin"}
    assert report["info_result"]["ok"] is True
    assert report["info_result"]["info"]["metadata"]["author"] == "ATENA Core"
    assert report["search_result"]["ok"] is True
    assert report["export_result"] == {"ok": True, "program": "atena_self.exe", "output": "/vm/exports/atena_self.apkg"}
    assert report["local_install_result"]["ok"] is True
    assert report["self_update_result"]["ok"] is True
    assert report["snapshot_save_result"] == {"ok": True, "snapshot": "base"}
    assert report["snapshot_load_result"] == {"ok": True, "snapshot": "base"}
    assert report["remove_result"] == {"ok": True, "program": "notepad.exe"}
    assert report["update_result"]["ok"] is True
    assert report["stress_result"]["ok"] is True
    assert report["stress_result"]["runs"] == 2
    assert report["web_publish_result"]["ok"] is True
    assert report["web_publish_result"]["provider"] == "ngrok"
    assert report["web_publish_result"]["tunnel_command"] == "ngrok http 8765"
    assert report["web_publish_result"]["page"]["index_html"].endswith("index.html")
    assert report["logs_result"]["ok"] is True
    assert report["shell_history"] == [
        "login admin atena",
        "remote-install http://atena.local/packages/notepad.exe.apkg",
        "run notepad.exe",
        "remote-install http://atena.local/packages/atena_self.exe.apkg",
        "run atena_self.exe",
        "info atena_self.exe",
        "search atena",
        "export atena_self.exe --output /vm/exports/atena_self.apkg",
        "install --local /vm/exports/atena_self.apkg",
        "self-update http://atena.local/packages/atena_self.exe.apkg",
        "snapshot save base",
        "remove notepad.exe",
        "snapshot load base",
        "update atena_self.exe",
        "stress --progs 1 --duration 2",
        "web-publish --provider ngrok --port 8765",
        "whoami",
        "logs",
        "list-programs",
    ]
    assert report["history_reloaded"] == report["shell_history"]
    assert report["list_programs_result"]["ok"] is True
    assert report["list_programs_result"]["programs"] == ["atena_self.exe", "notepad.exe"]
    assert report["result"]["mapped_sections"] == [".data", ".rdata", ".text"]
    assert report["result"]["imports"] == ["CreateWindowA", "DefWindowProc", "DispatchMessage"]
    assert "InstallProgram -> notepad.exe" in logs
    assert "remote-install notepad.exe" in logs
    assert "InstallProgram -> atena_self.exe" in self_logs
    assert "ExportProgram -> atena_self.exe to /vm/exports/atena_self.apkg" in "\n".join(report["logs_result"]["logs"])
    html = Path(report["web_publish_result"]["page"]["index_html"]).read_text(encoding="utf-8")
    assert "xterm.js" in html
    assert "WebSocket" in html
    assert "CreateWindowA" in logs
    assert "WM_CLOSE" in logs


def test_atena_windows_stress_demo_runs_with_high_event_volume():
    report = run_atena_windows_stress_in_vm()
    logs = "\n".join(report["result"]["kernel_log"])

    assert report["pe_name"] == "windows_stress.exe"
    assert report["installed_programs"] == ["windows_stress.exe"]
    assert report["install_path"].endswith("/windows_stress.exe.apkg")
    assert report["dispatch_count"] >= 20
    assert report["stress_ok"] is True
    assert "Notepad-A" in report["open_windows"]
    assert "WM_CLOSE" in logs
