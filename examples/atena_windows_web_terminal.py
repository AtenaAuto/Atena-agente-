#!/usr/bin/env python3
"""ATENA-Windows web terminal bridge (xterm.js + websocket).

Run:
  python examples/atena_windows_web_terminal.py --provider ngrok --port 8765 --http-port 8088
"""

from __future__ import annotations

import argparse
import asyncio
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading

from examples.atena_windows_guest_demo import (
    AtenaPackageRepository,
    AtenaWindowsDesktopShell,
    AtenaWindowsKernel,
    GuestProcessRunner,
    MiniOS,
    PELoader,
    TinyAsmCPU,
    create_xterm_web_page,
    shell_execute_bridge,
)


def _start_static_server(directory: Path, port: int) -> ThreadingHTTPServer:
    handler = lambda *a, **k: SimpleHTTPRequestHandler(*a, directory=str(directory), **k)
    httpd = ThreadingHTTPServer(("0.0.0.0", port), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd


async def _serve_ws(shell: AtenaWindowsDesktopShell, host: str, port: int) -> None:
    try:
        import websockets
    except ImportError as exc:  # pragma: no cover
        raise SystemExit("Missing dependency: pip install websockets") from exc

    async def _handler(ws):
        await ws.send("ATENA shell online. Use commands like: list-programs")
        async for message in ws:
            cmd = message.strip()
            if not cmd:
                continue
            result = shell_execute_bridge(shell, cmd)
            await ws.send(json.dumps(result, ensure_ascii=False))

    async with websockets.serve(_handler, host, port):
        await asyncio.Future()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", choices=["ngrok", "cloudflare"], default="ngrok")
    ap.add_argument("--port", type=int, default=8765, help="WebSocket port")
    ap.add_argument("--http-port", type=int, default=8088, help="Static web port")
    args = ap.parse_args()

    vm = MiniOS()
    _cpu = TinyAsmCPU(vm.memory, vm.net)
    kernel = AtenaWindowsKernel()
    loader = PELoader(kernel)
    runner = GuestProcessRunner(kernel, loader)
    repo = AtenaPackageRepository(vm)
    shell = AtenaWindowsDesktopShell(vm, kernel, runner, repo, history_path="/tmp/atena_webterm_history.txt")
    shell_execute_bridge(shell, "login admin atena")

    page = create_xterm_web_page(output_dir="/tmp/atena_windows_web", ws_url=f"ws://127.0.0.1:{args.port}/ws")
    static_dir = Path(page["index_html"]).parent
    _start_static_server(static_dir, args.http_port)

    if args.provider == "ngrok":
        tunnel_cmd = f"ngrok http {args.http_port}"
    else:
        tunnel_cmd = f"cloudflared tunnel --url http://127.0.0.1:{args.http_port}"

    print(f"[ATENA] Static page: http://127.0.0.1:{args.http_port}/index.html")
    print(f"[ATENA] WS endpoint: ws://127.0.0.1:{args.port}/ws")
    print(f"[ATENA] Tunnel command: {tunnel_cmd}")
    asyncio.run(_serve_ws(shell, "0.0.0.0", args.port))


if __name__ == "__main__":
    main()

