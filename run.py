"""Запуск секретаря турнира: локальный сервер + браузер."""

from __future__ import annotations

import sys
import threading
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _free_port(port: int = 8765) -> None:
    import subprocess

    try:
        out = subprocess.check_output(["netstat", "-ano"], text=True, errors="ignore")
    except Exception:
        return
    pids = set()
    for line in out.splitlines():
        if f":{port}" in line and "LISTENING" in line:
            parts = line.split()
            if parts and parts[-1].isdigit():
                pids.add(parts[-1])
    for pid in pids:
        subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True)


def main() -> None:
    import uvicorn

    _free_port(8765)
    url = "http://127.0.0.1:8765"
    threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    print(f"Секретарь ММА: {url}")
    print("Работает без интернета. Закройте это окно, чтобы остановить.")
    uvicorn.run("mma_secretary.web.app:app", host="127.0.0.1", port=8765, reload=False)


if __name__ == "__main__":
    main()
