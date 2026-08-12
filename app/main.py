import asyncio
import threading

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.market.market_engine import MarketEngine


app = FastAPI(
    title="AI/ML NSE Stock Screener"
)

app.mount(
    "/static",
    StaticFiles(directory="frontend"),
    name="static"
)

app.include_router(router)

market_engine = MarketEngine()


@app.on_event("startup")
def start_market():

    market_engine.loop = asyncio.get_running_loop()

    thread = threading.Thread(
        target=market_engine.start_market_scan,
        daemon=True
    )

    thread.start()


@app.get(
    "/",
    response_class=HTMLResponse
)
def dashboard():

    with open(
        "frontend/index.html",
        "r",
        encoding="utf-8"
    ) as file:
        return file.read()


@app.get("/health")
def health():

    return {
        "status": "ok"
    }