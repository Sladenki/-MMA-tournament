from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from mma_secretary import __version__
from mma_secretary.web.deps import PHOTOS, STATIC
from mma_secretary.web.routes import routers

app = FastAPI(title="Секретарь ММА", version=__version__)
app.mount("/static", StaticFiles(directory=STATIC), name="static")
if PHOTOS.exists():
    app.mount("/photos", StaticFiles(directory=PHOTOS), name="photos")

for router in routers:
    app.include_router(router)
