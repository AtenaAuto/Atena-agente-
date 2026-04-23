#!/usr/bin/env python3
"""Demo recursiva: mini-SO + CPU/VM + servidor HTTP virtual + execução de código ATENA na VM.

Como executar:
  python examples/recursive_vm_atena_demo.py
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Deque

PAGE_SIZE = 4096


class PagedMemory:
    def __init__(self) -> None:
        self.pages: dict[int, bytearray] = {}
        self.page_faults = 0

    def _page(self, addr: int) -> tuple[int, int]:
        return addr // PAGE_SIZE, addr % PAGE_SIZE

    def write_bytes(self, addr: int, data: bytes) -> None:
        for i, b in enumerate(data):
            pno, off = self._page(addr + i)
            if pno not in self.pages:
                self.pages[pno] = bytearray(PAGE_SIZE)
                self.page_faults += 1
            self.pages[pno][off] = b

    def read_bytes(self, addr: int, size: int) -> bytes:
        out = bytearray()
        for i in range(size):
            pno, off = self._page(addr + i)
            if pno not in self.pages:
                self.pages[pno] = bytearray(PAGE_SIZE)
                self.page_faults += 1
            out.append(self.pages[pno][off])
        return bytes(out)


class VirtualNetPipe:
    """Dispositivo de rede virtual (pipe host<->VM)."""

    def __init__(self) -> None:
        self.host_to_vm: Deque[str] = deque()
        self.vm_to_host: Deque[str] = deque()

    def host_send(self, req: str) -> None:
        self.host_to_vm.append(req)

    def host_recv(self) -> str | None:
        return self.vm_to_host.popleft() if self.vm_to_host else None


class TinyAsmCPU:
    """CPU minimalista com assembly próprio para loop HTTP."""

    def __init__(self, mem: PagedMemory, net: VirtualNetPipe) -> None:
        self.mem = mem
        self.net = net
        self.reg: dict[str, int] = {f"R{i}": 0 for i in range(8)}
        self.pc = 0
        self.labels: dict[str, int] = {}
        self.program: list[tuple[str, list[str]]] = []
        self.text_regs: dict[str, str] = {}
        self.last_msg = ""
        self.running = False

    def load(self, asm: str) -> None:
        self.program.clear()
        self.labels.clear()
        for raw in asm.splitlines():
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            if line.endswith(":"):
                self.labels[line[:-1]] = len(self.program)
                continue
            op, *rest = line.split(maxsplit=1)
            args = []
            if rest:
                args = [a.strip() for a in rest[0].split(",")]
            self.program.append((op.upper(), args))
        self.pc = 0

    def step(self) -> None:
        if not (0 <= self.pc < len(self.program)):
            self.running = False
            return
        op, a = self.program[self.pc]
        self.pc += 1

        if op == "JMP":
            self.pc = self.labels[a[0]]
        elif op == "JZ":
            if self.reg[a[0]] == 0:
                self.pc = self.labels[a[1]]
        elif op == "RECV":
            max_len = int(a[1])
            msg = self.net.host_to_vm.popleft() if self.net.host_to_vm else ""
            self.last_msg = msg[:max_len]
            raw = self.last_msg.encode("utf-8")
            self.mem.write_bytes(0, raw)
            self.reg[a[0]] = len(raw)
        elif op == "MATCH":
            reg_out, prefix = a[0], a[1].strip('"')
            self.reg[reg_out] = 1 if self.last_msg.startswith(prefix) else 0
        elif op == "LOADS":
            reg, txt = a[0], a[1].strip('"')
            self.text_regs[reg] = txt
            self.reg[reg] = len(txt)
        elif op == "SEND":
            self.net.vm_to_host.append(self.text_regs.get(a[0], ""))
        elif op == "HALT":
            self.running = False

    def run_steps(self, n: int = 64) -> None:
        self.running = True
        for _ in range(n):
            if not self.running:
                break
            self.step()


@dataclass
class Process:
    pid: int
    name: str
    fn: Callable[["MiniOS", int], None]
    alive: bool = True


@dataclass
class MiniOS:
    memory: PagedMemory = field(default_factory=PagedMemory)
    net: VirtualNetPipe = field(default_factory=VirtualNetPipe)
    fs: dict[str, str] = field(default_factory=dict)
    queue: Deque[Process] = field(default_factory=deque)
    pid_seq: int = 100
    logs: list[str] = field(default_factory=list)
    killed_pids: set[int] = field(default_factory=set)

    def spawn(self, name: str, fn: Callable[["MiniOS", int], None]) -> int:
        pid = self.pid_seq
        self.pid_seq += 1
        self.queue.append(Process(pid, name, fn))
        return pid

    def schedule(self, ticks: int = 16) -> None:
        for _ in range(ticks):
            if not self.queue:
                return
            p = self.queue.popleft()
            if (not p.alive) or (p.pid in self.killed_pids):
                continue
            p.fn(self, p.pid)
            if p.alive and p.pid not in self.killed_pids:
                self.queue.append(p)

    def kill(self, pid: int) -> None:
        self.killed_pids.add(pid)
        for p in self.queue:
            if p.pid == pid:
                p.alive = False


def vm_web_server_process(cpu: TinyAsmCPU) -> Callable[[MiniOS, int], None]:
    def _run(_os: MiniOS, _pid: int) -> None:
        cpu.run_steps(8)
    return _run


def atena_guest_process(osys: MiniOS, _pid: int) -> None:
    """Executa código da ATENA copiado para o FS da VM e responde comando do shell."""
    code = osys.fs.get("/vm/atena/production_contracts.py", "")
    ns: dict[str, object] = {}
    exec(code, ns, ns)
    validate_contract = ns["validate_contract"]
    missing = validate_contract("subagent-solve", {"status": "ok"})
    osys.logs.append(f"ATENA_VM validate_contract -> {missing[:2]} ... total_missing={len(missing)}")
    osys.kill(_pid)


def shell_demo(osys: MiniOS) -> None:
    # 1) Copia código real da ATENA para FS da VM
    atena_src = Path("core/production_contracts.py").read_text(encoding="utf-8")
    osys.fs["/vm/atena/production_contracts.py"] = atena_src
    osys.logs.append("shell> copy core/production_contracts.py /vm/atena/production_contracts.py")

    # 2) Monta VM CPU + assembly do web server
    cpu = TinyAsmCPU(osys.memory, osys.net)
    cpu.load(
        """
START:
RECV R1, 2048
JZ R1, START
MATCH R2, "GET / HTTP/1.1"
JZ R2, NOTFOUND
LOADS R3, "HTTP/1.1 200 OK\\r\\nContent-Length: 15\\r\\n\\r\\nATENA VM ONLINE"
SEND R3
JMP START
NOTFOUND:
LOADS R3, "HTTP/1.1 404 Not Found\\r\\nContent-Length: 9\\r\\n\\r\\nnot found"
SEND R3
JMP START
"""
    )

    # 3) Spawn processos no mini-SO
    web_pid = osys.spawn("vm-web", vm_web_server_process(cpu))
    atena_pid = osys.spawn("atena-vm", atena_guest_process)
    osys.logs.append(f"shell> spawn vm-web pid={web_pid}")
    osys.logs.append(f"shell> spawn atena-vm pid={atena_pid}")

    # 4) Host envia request HTTP para rede virtual da VM
    osys.net.host_send("GET / HTTP/1.1\\r\\nHost: vm\\r\\n\\r\\n")
    osys.logs.append("shell> host_net_send GET /")

    # 5) Scheduler roda e depois host coleta resposta da VM
    osys.schedule(ticks=20)
    resp = osys.net.host_recv() or ""
    osys.logs.append(f"host<vm_http {resp.splitlines()[0] if resp else 'EMPTY'}")


def run_recursive_demo() -> dict[str, object]:
    osys = MiniOS()
    shell_demo(osys)
    return {
        "page_faults": osys.memory.page_faults,
        "vm_files": sorted(osys.fs.keys()),
        "logs": osys.logs,
    }


def main() -> None:
    report = run_recursive_demo()
    print("=== RECURSIVE VM REPORT ===")
    print(f"page_faults={report['page_faults']}")
    print("vm_files:")
    for p in report["vm_files"]:
        print(" -", p)
    print("logs:")
    for line in report["logs"]:
        print(" *", line)


if __name__ == "__main__":
    main()
