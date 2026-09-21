"""Запуск секретаря турнира: локальный сервер + браузер."""

from __future__ import annotations

import sys
import threading
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> None:
    import uvicorn

    url = "http://127.0.0.1:8765"
    threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    print(f"Секретарь ММА: {url}")
    print("Работает без интернета. Закройте это окно, чтобы остановить.")
    uvicorn.run("mma_secretary.web.app:app", host="127.0.0.1", port=8765, reload=False)


if __name__ == "__main__":
    main()
