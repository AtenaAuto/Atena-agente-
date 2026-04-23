#!/usr/bin/env python3
"""ATENA-Windows guest OS demo running inside the existing MiniOS VM.

Run:
  python examples/atena_windows_guest_demo.py
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any, Callable, Deque
from urllib.parse import urlparse
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from examples.recursive_vm_atena_demo import MiniOS, TinyAsmCPU


# -----------------------------
# ATENA-Windows kernel + Win32-like API
# -----------------------------


@dataclass
class Message:
    hwnd: int
    msg: str
    wparam: Any = None
    lparam: Any = None


@dataclass
class Window:
    hwnd: int
    title: str
    x: int
    y: int
    w: int
    h: int
    text: str = ""
    z: int = 0
    closed: bool = False


class WindowManager:
    def __init__(self) -> None:
        self.windows: dict[int, Window] = {}
        self.next_hwnd = 1
        self.z_counter = 0

    def create(self, title: str, x: int, y: int, w: int, h: int) -> int:
        hwnd = self.next_hwnd
        self.next_hwnd += 1
        self.z_counter += 1
        self.windows[hwnd] = Window(hwnd=hwnd, title=title, x=x, y=y, w=w, h=h, z=self.z_counter)
        return hwnd

    def bring_to_front(self, hwnd: int) -> None:
        if hwnd in self.windows and not self.windows[hwnd].closed:
            self.z_counter += 1
            self.windows[hwnd].z = self.z_counter

    def resize(self, hwnd: int, w: int, h: int) -> None:
        if hwnd in self.windows and not self.windows[hwnd].closed:
            self.windows[hwnd].w = max(10, w)
            self.windows[hwnd].h = max(4, h)

    def close(self, hwnd: int) -> None:
        if hwnd in self.windows:
            self.windows[hwnd].closed = True

    def set_text(self, hwnd: int, text: str) -> None:
        if hwnd in self.windows and not self.windows[hwnd].closed:
            self.windows[hwnd].text = text

    def stacking(self) -> list[Window]:
        return sorted([w for w in self.windows.values() if not w.closed], key=lambda w: w.z)


class AtenaWindowsKernel:
    def __init__(self) -> None:
        self.wm = WindowManager()
        self.queue: Deque[Message] = deque()
        self.log: list[str] = []
        self.installed_programs: dict[str, dict[str, Any]] = {}

    # Win32-like API (simplified)
    def CreateWindowA(self, title: str, x: int, y: int, w: int, h: int) -> int:
        hwnd = self.wm.create(title, x, y, w, h)
        self.log.append(f"CreateWindowA -> hwnd={hwnd} title={title}")
        self.queue.append(Message(hwnd, "WM_CREATE"))
        return hwnd

    def DefWindowProc(self, msg: Message) -> int:
        self.log.append(f"DefWindowProc hwnd={msg.hwnd} msg={msg.msg}")
        return 0

    def DispatchMessage(self, msg: Message) -> int:
        self.log.append(f"DispatchMessage hwnd={msg.hwnd} msg={msg.msg}")
        self.wm.bring_to_front(msg.hwnd)
        if msg.msg == "WM_CLOSE":
            self.wm.close(msg.hwnd)
        return self.DefWindowProc(msg)

    def post(self, hwnd: int, msg: str, wparam: Any = None, lparam: Any = None) -> None:
        self.queue.append(Message(hwnd, msg, wparam, lparam))

    def pump_messages(self, budget: int = 16) -> None:
        for _ in range(budget):
            if not self.queue:
                return
            self.DispatchMessage(self.queue.popleft())

    def draw_desktop_ascii(self) -> str:
        lines = [
            "+--------------------- ATENA-Windows Desktop ---------------------+",
            "| [N] Notepad   [C] Calculator   [R] Recycle Bin                 |",
            "+-----------------------------------------------------------------+",
        ]
        for w in self.wm.stacking():
            lines.append(f"| Window#{w.hwnd} '{w.title}' pos=({w.x},{w.y}) size={w.w}x{w.h} |")
            lines.append(f"| text: {w.text[:58]:58} |")
            lines.append("+-----------------------------------------------------------------+")
        return "\n".join(lines)

    def register_program(
        self,
        program_name: str,
        package_path: str,
        metadata: dict[str, Any] | None = None,
        source_url: str | None = None,
    ) -> None:
        self.installed_programs[program_name] = {
            "path": package_path,
            "metadata": metadata or {},
            "source_url": source_url,
            "installed_at": datetime.now(timezone.utc).isoformat(),
        }
        self.log.append(f"InstallProgram -> {program_name} at {package_path}")

    def list_programs(self) -> list[str]:
        return sorted(self.installed_programs.keys())

    def remove_program(self, program_name: str) -> bool:
        if program_name not in self.installed_programs:
            return False
        self.installed_programs.pop(program_name, None)
        self.log.append(f"RemoveProgram -> {program_name}")
        return True

    def program_info(self, program_name: str) -> dict[str, Any] | None:
        return self.installed_programs.get(program_name)


# -----------------------------
# Minimal PE loader for VM guest
# -----------------------------


@dataclass
class PESection:
    name: str
    data: Any


@dataclass
class PortableExecutable:
    name: str
    entry: str
    sections: dict[str, PESection]
    imports: list[str]
    metadata: dict[str, Any] = field(default_factory=dict)


class PELoader:
    def __init__(self, kernel: AtenaWindowsKernel) -> None:
        self.kernel = kernel
        self.import_table: dict[str, Callable[..., Any]] = {
            "CreateWindowA": kernel.CreateWindowA,
            "DispatchMessage": kernel.DispatchMessage,
            "DefWindowProc": kernel.DefWindowProc,
        }

    def map_sections(self, pe: PortableExecutable) -> dict[str, Any]:
        mapped: dict[str, Any] = {}
        for sec_name in (".text", ".data", ".rdata"):
            if sec_name in pe.sections:
                mapped[sec_name] = pe.sections[sec_name].data
        return mapped

    def resolve_imports(self, pe: PortableExecutable) -> dict[str, Callable[..., Any]]:
        resolved: dict[str, Callable[..., Any]] = {}
        for imp in pe.imports:
            if imp not in self.import_table:
                raise RuntimeError(f"import não resolvido: {imp}")
            resolved[imp] = self.import_table[imp]
        return resolved


# -----------------------------
# "Assembly" program + compiler to minimal PE
# -----------------------------


def compile_vm_asm_to_pe(name: str, asm_lines: list[str]) -> PortableExecutable:
    # Minimal compiler: stores executable pseudo-op stream in .text
    text_ops = [line.strip() for line in asm_lines if line.strip() and not line.strip().startswith(";")]
    pe = PortableExecutable(
        name=name,
        entry="main",
        sections={
            ".text": PESection(".text", text_ops),
            ".data": PESection(".data", {"buffer": ""}),
            ".rdata": PESection(".rdata", {"app_name": name}),
        },
        imports=["CreateWindowA", "DispatchMessage", "DefWindowProc"],
        metadata={
            "version": "1.0.0",
            "author": "ATENA",
            "dependencies": [],
        },
    )
    return pe


class GuestProcessRunner:
    def __init__(self, kernel: AtenaWindowsKernel, pe_loader: PELoader) -> None:
        self.kernel = kernel
        self.loader = pe_loader

    def run_pe(self, pe: PortableExecutable) -> dict[str, Any]:
        mapped = self.loader.map_sections(pe)
        imports = self.loader.resolve_imports(pe)
        text_ops: list[str] = mapped[".text"]

        hwnd = 0
        handles_by_alias: dict[str, int] = {}
        for op in text_ops:
            # Opcodes pseudo-assembly for ATENA-Windows guest
            if op.startswith("WIN_CREATE"):
                _, title, x, y, w, h = op.split("|", 5)
                hwnd = imports["CreateWindowA"](title, int(x), int(y), int(w), int(h))
                handles_by_alias[title] = hwnd
            elif op.startswith("WIN_TEXT"):
                _, txt = op.split("|", 1)
                self.kernel.wm.set_text(hwnd, txt)
                self.kernel.post(hwnd, "WM_PAINT")
            elif op.startswith("WIN_RESIZE"):
                _, w, h = op.split("|", 2)
                self.kernel.wm.resize(hwnd, int(w), int(h))
                self.kernel.post(hwnd, "WM_SIZE", w, h)
            elif op == "WIN_CLOSE":
                self.kernel.post(hwnd, "WM_CLOSE")
            elif op.startswith("WIN_FOCUS"):
                _, title = op.split("|", 1)
                target = handles_by_alias.get(title)
                if target is not None:
                    self.kernel.post(target, "WM_FOCUS")
            elif op.startswith("WIN_BURST"):
                _, count = op.split("|", 1)
                for _ in range(max(0, int(count))):
                    self.kernel.post(hwnd, "WM_PAINT")
            elif op == "DISPATCH":
                self.kernel.pump_messages(8)

        return {
            "mapped_sections": sorted(mapped.keys()),
            "imports": sorted(imports.keys()),
            "desktop": self.kernel.draw_desktop_ascii(),
            "kernel_log": list(self.kernel.log),
        }

    def run_installed(self, vm: MiniOS, program_name: str) -> dict[str, Any]:
        pkg = self.kernel.installed_programs.get(program_name)
        if not pkg:
            raise RuntimeError(f"programa não instalado: {program_name}")
        package_path = pkg["path"]
        raw_package = vm.fs.get(package_path)
        if not raw_package:
            raise RuntimeError(f"pacote ausente no filesystem da VM: {package_path}")
        pe = _deserialize_pe(raw_package)
        return self.run_pe(pe)


def _serialize_pe(pe: PortableExecutable) -> str:
    payload = {
        "name": pe.name,
        "entry": pe.entry,
        "imports": list(pe.imports),
        "metadata": pe.metadata,
        "sections": {name: section.data for name, section in pe.sections.items()},
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _deserialize_pe(raw: str) -> PortableExecutable:
    payload = json.loads(raw)
    sections = {
        name: PESection(name=name, data=data)
        for name, data in payload.get("sections", {}).items()
    }
    return PortableExecutable(
        name=payload["name"],
        entry=payload["entry"],
        sections=sections,
        imports=list(payload.get("imports", [])),
        metadata=dict(payload.get("metadata", {})),
    )


def install_program_to_vm(
    vm: MiniOS,
    kernel: AtenaWindowsKernel,
    pe: PortableExecutable,
    source_url: str | None = None,
) -> str:
    package_dir = "/vm/ATENA-Windows/ProgramFiles"
    package_path = f"{package_dir}/{pe.name}.apkg"
    vm.fs[package_path] = _serialize_pe(pe)
    kernel.register_program(pe.name, package_path, metadata=pe.metadata, source_url=source_url)
    return package_path


class AtenaPackageRepository:
    """Repositório centralizado de programas servidos via HTTP na rede virtual."""

    def __init__(self, vm: MiniOS, base_url: str = "http://atena.local") -> None:
        self.vm = vm
        self.base_url = base_url.rstrip("/")
        self._packages_by_path: dict[str, str] = {}
        self._catalog: dict[str, list[dict[str, Any]]] = {}

    def publish(self, pe: PortableExecutable) -> str:
        path = f"/packages/{pe.name}.apkg"
        self._packages_by_path[path] = _serialize_pe(pe)
        url = f"{self.base_url}{path}"
        self._catalog.setdefault(pe.name, []).append(
            {
                "name": pe.name,
                "version": pe.metadata.get("version", "0.0.0"),
                "author": pe.metadata.get("author", "unknown"),
                "dependencies": pe.metadata.get("dependencies", []),
                "url": url,
            }
        )
        return url

    def handle_once(self) -> bool:
        req = self.vm.net.host_to_vm.popleft() if self.vm.net.host_to_vm else ""
        if not req:
            return False
        request_line = req.splitlines()[0] if req.splitlines() else ""
        parts = request_line.split()
        path = parts[1] if len(parts) >= 2 else "/"
        if path not in self._packages_by_path:
            body = "not found"
            resp = (
                "HTTP/1.1 404 Not Found\r\n"
                f"Content-Length: {len(body)}\r\n"
                "Content-Type: text/plain\r\n\r\n"
                f"{body}"
            )
            self.vm.net.vm_to_host.append(resp)
            return True
        body = self._packages_by_path[path]
        resp = (
            "HTTP/1.1 200 OK\r\n"
            f"Content-Length: {len(body)}\r\n"
            "Content-Type: application/x-atena-package\r\n\r\n"
            f"{body}"
        )
        self.vm.net.vm_to_host.append(resp)
        return True

    def fetch(self, url: str) -> str:
        parsed = urlparse(url)
        if parsed.netloc and parsed.netloc != "atena.local":
            with urlopen(url, timeout=5) as resp:  # nosec B310 - demo utility
                return resp.read().decode("utf-8")
        path = parsed.path or "/"
        self.vm.net.host_send(f"GET {path} HTTP/1.1\r\nHost: atena.local\r\n\r\n")
        self.handle_once()
        raw = self.vm.net.host_recv() or ""
        if not raw.startswith("HTTP/1.1 200"):
            raise RuntimeError(f"download falhou: {url}")
        return raw.split("\r\n\r\n", 1)[1]

    def search(self, term: str) -> list[dict[str, Any]]:
        t = term.lower()
        out: list[dict[str, Any]] = []
        for name, versions in self._catalog.items():
            if t in name.lower():
                out.extend(versions)
        return out

    def latest_url(self, program_name: str) -> str | None:
        entries = self._catalog.get(program_name, [])
        if not entries:
            return None
        latest = sorted(entries, key=lambda x: x.get("version", "0.0.0"))[-1]
        return latest["url"]


class AtenaWindowsDesktopShell:
    """Shell textual da área de trabalho com comando remote-install."""

    def __init__(
        self,
        vm: MiniOS,
        kernel: AtenaWindowsKernel,
        runner: GuestProcessRunner,
        repo: AtenaPackageRepository,
        history_path: str = "/tmp/atena_windows_shell_history.txt",
        users: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self.vm = vm
        self.kernel = kernel
        self.runner = runner
        self.repo = repo
        self.history_path = history_path
        self.history: list[str] = self._load_history()
        self.users = users or {
            "admin": {"password": "atena", "quota": 1000, "home": "/home/admin"},
        }
        self.current_user: str | None = None
        self.snapshots: dict[str, dict[str, Any]] = {}

    def _load_history(self) -> list[str]:
        p = Path(self.history_path)
        if not p.exists():
            return []
        return [line.rstrip("\n") for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]

    def _append_history(self, cmd: str) -> None:
        p = Path(self.history_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            fh.write(cmd + "\n")

    def execute(self, cmd: str) -> dict[str, Any]:
        self.history.append(cmd)
        self._append_history(cmd)
        parts = cmd.strip().split()
        if not parts:
            return {"ok": False, "error": "empty command"}

        if parts[0] == "login" and len(parts) >= 3:
            username, password = parts[1], parts[2]
            user = self.users.get(username)
            if not user or user["password"] != password:
                return {"ok": False, "error": "invalid credentials"}
            self.current_user = username
            self.kernel.log.append(f"Login -> {username}")
            return {"ok": True, "user": username, "home": user["home"]}

        if parts[0] == "whoami":
            return {"ok": True, "user": self.current_user}

        if self.current_user is None:
            return {"ok": False, "error": "not authenticated"}

        quota = self.users[self.current_user]["quota"]
        if len(self.history) > quota:
            return {"ok": False, "error": "quota exceeded"}

        if parts[0] == "list-programs":
            return {"ok": True, "programs": self.kernel.list_programs()}

        if parts[0] == "snapshot" and len(parts) >= 3 and parts[1] in {"save", "load"}:
            action, name = parts[1], parts[2]
            if action == "save":
                self.snapshots[name] = {
                    "fs": dict(self.vm.fs),
                    "installed": dict(self.kernel.installed_programs),
                }
                self.kernel.log.append(f"SnapshotSave -> {name}")
                return {"ok": True, "snapshot": name}
            snap = self.snapshots.get(name)
            if not snap:
                return {"ok": False, "error": f"snapshot not found: {name}"}
            self.vm.fs = dict(snap["fs"])
            self.kernel.installed_programs = dict(snap["installed"])
            self.kernel.log.append(f"SnapshotLoad -> {name}")
            return {"ok": True, "snapshot": name}

        if parts[0] == "logs":
            return {"ok": True, "logs": list(self.kernel.log)}

        if parts[0] == "search" and len(parts) >= 2:
            term = " ".join(parts[1:])
            return {"ok": True, "results": self.repo.search(term)}

        if parts[0] == "info" and len(parts) >= 2:
            program_name = parts[1]
            info = self.kernel.program_info(program_name)
            if not info:
                return {"ok": False, "error": f"program not installed: {program_name}"}
            return {"ok": True, "program": program_name, "info": info}

        if parts[0] == "remote-install" and len(parts) >= 2:
            package_url = parts[1]
            install_path = remote_install_program(self.vm, self.kernel, self.repo, package_url)
            return {
                "ok": True,
                "installed": package_url,
                "install_path": install_path,
                "programs": self.kernel.list_programs(),
            }

        if parts[0] == "install" and len(parts) >= 3 and parts[1] == "--local":
            local_path = parts[2]
            raw_pkg = self.vm.fs.get(local_path)
            if raw_pkg is None:
                return {"ok": False, "error": f"local package not found: {local_path}"}
            pe = _deserialize_pe(raw_pkg)
            install_path = install_program_to_vm(self.vm, self.kernel, pe, source_url=f"local:{local_path}")
            self.kernel.log.append(f"local-install {pe.name} from {local_path}")
            return {"ok": True, "program": pe.name, "install_path": install_path}

        if parts[0] == "remove" and len(parts) >= 2:
            program_name = parts[1]
            removed = self.kernel.remove_program(program_name)
            return {"ok": removed, "program": program_name}

        if parts[0] == "update" and len(parts) >= 2:
            program_name = parts[1]
            latest = self.repo.latest_url(program_name)
            if not latest:
                return {"ok": False, "error": f"program not found in repo: {program_name}"}
            install_path = remote_install_program(self.vm, self.kernel, self.repo, latest)
            return {"ok": True, "program": program_name, "install_path": install_path, "url": latest}

        if parts[0] == "self-update" and len(parts) >= 2:
            update_url = parts[1]
            install_path = remote_install_program(self.vm, self.kernel, self.repo, update_url)
            self.kernel.log.append(f"SelfUpdate -> {update_url}")
            return {"ok": True, "install_path": install_path, "restarted": True}

        if parts[0] == "run" and len(parts) >= 2:
            program_name = parts[1]
            result = self.runner.run_installed(self.vm, program_name)
            return {"ok": True, "program": program_name, "result": result}

        if parts[0] == "export" and len(parts) >= 4 and parts[2] == "--output":
            program_name = parts[1]
            output = parts[3]
            info = self.kernel.program_info(program_name)
            if not info:
                return {"ok": False, "error": f"program not installed: {program_name}"}
            payload = self.vm.fs.get(info["path"])
            if payload is None:
                return {"ok": False, "error": f"package data missing: {info['path']}"}
            self.vm.fs[output] = payload
            self.kernel.log.append(f"ExportProgram -> {program_name} to {output}")
            return {"ok": True, "program": program_name, "output": output}

        if parts[0] == "stress":
            n = 3
            duration = 10
            if "--progs" in parts:
                n = max(1, int(parts[parts.index("--progs") + 1]))
            if "--duration" in parts:
                duration = max(1, int(parts[parts.index("--duration") + 1]))
            progs = self.kernel.list_programs()[:n]
            runs = 0
            for _ in range(min(duration, 25)):
                for p in progs:
                    self.runner.run_installed(self.vm, p)
                    runs += 1
            self.kernel.log.append(f"Stress -> progs={len(progs)} duration={duration} runs={runs}")
            return {"ok": True, "programs": progs, "runs": runs}

        if parts[0] == "web-publish":
            provider = "cloudflare"
            port = 8765
            if "--provider" in parts:
                provider = parts[parts.index("--provider") + 1]
            if "--port" in parts:
                port = int(parts[parts.index("--port") + 1])
            page = create_xterm_web_page(ws_url=f"ws://127.0.0.1:{port}/ws")
            if provider == "ngrok":
                tunnel_cmd = f"ngrok http {port}"
            else:
                tunnel_cmd = f"cloudflared tunnel --url http://127.0.0.1:{port}"
            self.kernel.log.append(f"WebPublish -> provider={provider} port={port}")
            return {
                "ok": True,
                "provider": provider,
                "port": port,
                "page": page,
                "tunnel_command": tunnel_cmd,
            }

        return {"ok": False, "error": f"unknown command: {cmd}"}

    def complete(self, prefix: str) -> list[str]:
        commands = [
            "login",
            "whoami",
            "remote-install",
            "install",
            "run",
            "list-programs",
            "logs",
            "search",
            "info",
            "remove",
            "update",
            "self-update",
            "export",
            "snapshot",
            "stress",
            "web-publish",
        ]
        return sorted([c for c in commands if c.startswith(prefix)])


def shell_execute_bridge(shell: AtenaWindowsDesktopShell, cmd: str) -> dict[str, Any]:
    """Ponto de integração ATENA real -> shell da VM."""
    return shell.execute(cmd)


def create_xterm_web_page(output_dir: str = "/tmp/atena_windows_web", ws_url: str = "ws://127.0.0.1:8765/ws") -> dict[str, str]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    index = out / "index.html"
    index.write_text(
        f"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8"/>
    <title>ATENA-Windows Web Terminal</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/xterm/css/xterm.css"/>
    <style>html,body,#terminal{{height:100%;margin:0;background:#111;color:#eee}}</style>
  </head>
  <body>
    <div id="terminal"></div>
    <script src="https://cdn.jsdelivr.net/npm/xterm/lib/xterm.js"></script>
    <script>
      const term = new Terminal({{cursorBlink:true}});
      term.open(document.getElementById('terminal'));
      term.writeln('ATENA-Windows Web Terminal');
      const ws = new WebSocket('{ws_url}');
      ws.onopen = () => term.writeln('connected');
      ws.onmessage = (ev) => term.writeln(ev.data);
      term.onData((data) => ws.send(data));
    </script>
  </body>
</html>""",
        encoding="utf-8",
    )
    return {"index_html": str(index), "ws_url": ws_url}


def remote_install_program(
    vm: MiniOS,
    kernel: AtenaWindowsKernel,
    repo: AtenaPackageRepository,
    package_url: str,
) -> str:
    raw_pkg = repo.fetch(package_url)
    pe = _deserialize_pe(raw_pkg)
    package_path = install_program_to_vm(vm, kernel, pe, source_url=package_url)
    kernel.log.append(f"remote-install {pe.name} from {package_url}")
    return package_path


def build_self_hosted_atena_package() -> PortableExecutable:
    atena_src = Path("core/atena_subagent_solver.py").read_text(encoding="utf-8")
    asm = [
        "WIN_CREATE|ATENA Self|1|1|72|10",
        "WIN_TEXT|ATENA rodando dentro do ATENA-Windows.",
        "DISPATCH",
    ]
    pe = compile_vm_asm_to_pe("atena_self.exe", asm)
    pe.sections[".rdata"] = PESection(
        ".rdata",
        {
            "app_name": "atena_self.exe",
            "embedded_source": atena_src[:2000],
        },
    )
    return pe


# -----------------------------
# Integration into existing VM/MiniOS
# -----------------------------


def run_atena_windows_guest_in_vm() -> dict[str, Any]:
    vm = MiniOS()
    # TinyAsmCPU instantiation proves guest still runs inside existing VM model.
    _cpu = TinyAsmCPU(vm.memory, vm.net)

    kernel = AtenaWindowsKernel()
    loader = PELoader(kernel)
    runner = GuestProcessRunner(kernel, loader)
    repo = AtenaPackageRepository(vm)
    history_path = "/tmp/atena_windows_shell_history_demo.txt"
    hist_file = Path(history_path)
    if hist_file.exists():
        hist_file.unlink()
    shell = AtenaWindowsDesktopShell(vm, kernel, runner, repo, history_path=history_path)
    login_result = shell.execute("login admin atena")

    notepad_asm = [
        "WIN_CREATE|Bloco de Notas|2|2|60|10",
        "WIN_TEXT|ATENA-Windows em execução dentro da VM.",
        "WIN_RESIZE|70|12",
        "DISPATCH",
        "WIN_CLOSE",
        "DISPATCH",
    ]

    pe = compile_vm_asm_to_pe("notepad.exe", notepad_asm)
    package_url = repo.publish(pe)
    shell_install = shell_execute_bridge(shell, f"remote-install {package_url}")
    package_path = shell_install["install_path"]
    result = shell_execute_bridge(shell, "run notepad.exe")["result"]

    atena_self_pe = build_self_hosted_atena_package()
    atena_self_pe.metadata.update({"version": "1.0.0", "author": "ATENA Core"})
    atena_self_url = repo.publish(atena_self_pe)
    atena_self_path = shell_execute_bridge(shell, f"remote-install {atena_self_url}")["install_path"]
    atena_self_result = shell_execute_bridge(shell, "run atena_self.exe")["result"]
    info_result = shell_execute_bridge(shell, "info atena_self.exe")
    search_result = shell_execute_bridge(shell, "search atena")
    export_result = shell_execute_bridge(shell, "export atena_self.exe --output /vm/exports/atena_self.apkg")
    local_install_result = shell_execute_bridge(shell, "install --local /vm/exports/atena_self.apkg")
    self_update_result = shell_execute_bridge(shell, f"self-update {atena_self_url}")
    snapshot_save_result = shell_execute_bridge(shell, "snapshot save base")
    remove_result = shell_execute_bridge(shell, "remove notepad.exe")
    snapshot_load_result = shell_execute_bridge(shell, "snapshot load base")
    update_result = shell_execute_bridge(shell, "update atena_self.exe")
    stress_result = shell_execute_bridge(shell, "stress --progs 1 --duration 2")
    web_publish_result = shell_execute_bridge(shell, "web-publish --provider ngrok --port 8765")
    whoami_result = shell_execute_bridge(shell, "whoami")
    logs_result = shell_execute_bridge(shell, "logs")
    list_programs_result = shell_execute_bridge(shell, "list-programs")
    shell_reloaded = AtenaWindowsDesktopShell(vm, kernel, runner, repo, history_path=history_path)

    return {
        "vm_page_faults": vm.memory.page_faults,
        "pe_name": pe.name,
        "installed_programs": kernel.list_programs(),
        "install_path": package_path,
        "package_url": package_url,
        "atena_self_install_path": atena_self_path,
        "atena_self_result": atena_self_result,
        "published_urls": [package_url, atena_self_url],
        "shell_history": shell.history,
        "history_path": history_path,
        "history_reloaded": shell_reloaded.history,
        "login_result": login_result,
        "autocomplete_remote": shell.complete("re"),
        "info_result": info_result,
        "logs_result": logs_result,
        "search_result": search_result,
        "export_result": export_result,
        "local_install_result": local_install_result,
        "self_update_result": self_update_result,
        "snapshot_save_result": snapshot_save_result,
        "snapshot_load_result": snapshot_load_result,
        "remove_result": remove_result,
        "update_result": update_result,
        "stress_result": stress_result,
        "web_publish_result": web_publish_result,
        "whoami_result": whoami_result,
        "list_programs_result": list_programs_result,
        "result": result,
    }


def run_atena_windows_stress_in_vm() -> dict[str, Any]:
    """Stress scenario with multiple guest apps and high event volume."""
    vm = MiniOS()
    _cpu = TinyAsmCPU(vm.memory, vm.net)

    kernel = AtenaWindowsKernel()
    loader = PELoader(kernel)
    runner = GuestProcessRunner(kernel, loader)

    multi_app_asm = [
        "WIN_CREATE|Notepad-A|2|2|60|10",
        "WIN_TEXT|Editor A inicializado",
        "WIN_BURST|10",
        "WIN_CREATE|Calculator-B|6|4|40|8",
        "WIN_TEXT|2+2=4",
        "WIN_RESIZE|44|10",
        "WIN_BURST|10",
        "WIN_FOCUS|Notepad-A",
        "DISPATCH",
        "DISPATCH",
        "DISPATCH",
        "WIN_CLOSE",
        "DISPATCH",
        "DISPATCH",
        "DISPATCH",
    ]

    pe = compile_vm_asm_to_pe("windows_stress.exe", multi_app_asm)
    package_path = install_program_to_vm(vm, kernel, pe)
    result = runner.run_installed(vm, "windows_stress.exe")
    open_titles = [w.title for w in kernel.wm.stacking()]
    dispatch_count = sum(1 for line in result["kernel_log"] if line.startswith("DispatchMessage"))
    report = {
        "vm_page_faults": vm.memory.page_faults,
        "pe_name": pe.name,
        "install_path": package_path,
        "installed_programs": kernel.list_programs(),
        "result": result,
        "open_windows": open_titles,
        "dispatch_count": dispatch_count,
        "log_size": len(result["kernel_log"]),
        "stress_ok": (
            dispatch_count >= 20
            and any("WM_CLOSE" in line for line in result["kernel_log"])
            and "Notepad-A" in open_titles
        ),
    }
    return report


def main() -> None:
    report = run_atena_windows_guest_in_vm()
    print("=== ATENA-Windows Guest Report ===")
    print("pe:", report["pe_name"])
    print("vm_page_faults:", report["vm_page_faults"])
    print("mapped_sections:", report["result"]["mapped_sections"])
    print("imports:", report["result"]["imports"])
    print("--- desktop ---")
    print(report["result"]["desktop"])
    print("--- kernel log ---")
    for line in report["result"]["kernel_log"]:
        print("*", line)
    stress = run_atena_windows_stress_in_vm()
    print("\n=== ATENA-Windows Stress Report ===")
    print("pe:", stress["pe_name"])
    print("dispatch_count:", stress["dispatch_count"])
    print("open_windows:", stress["open_windows"])
    print("stress_ok:", stress["stress_ok"])


if __name__ == "__main__":
    main()
