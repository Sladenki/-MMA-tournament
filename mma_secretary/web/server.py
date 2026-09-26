"""Один адрес запуска для run.py и python -m mma_secretary."""

from __future__ import annotations

import threading
import webbrowser

HOST = "127.0.0.1"
PORT = 8765


def serve() -> None:
    import uvicorn

    url = f"http://{HOST}:{PORT}"
    threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    print(f"Секретарь ММА: {url}")
    print("Работает без интернета. Закройте это окно, чтобы остановить.")
    uvicorn.run("mma_secretary.web.app:app", host=HOST, port=PORT, reload=False)
