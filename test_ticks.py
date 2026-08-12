from app.broker.angel_one import AngelOneClient
from app.broker.websocket import AngelWebSocket
from app.market.universe import NSEUniverse
from app.market.tick_normalizer import normalize_tick
from app.market.tick_store import TickStore
import app.config as cfg
import threading
import time

store = TickStore()

def on_tick(data):
    print("RAW_TICK=", data)

    tick = normalize_tick(data)
    store.add(tick["symbol"], tick)

    print("NORMALIZED=", tick)
    print("STORE_COUNT=", len(store.data[tick["symbol"]]))


client = AngelOneClient()
client.login()

universe = NSEUniverse()

tokens = [
    str(x["token"])
    for x in universe.get_tokens()
    if x["symbol"] in ("RELIANCE-EQ", "TCS-EQ")
]

print("TOKENS=", tokens)

ws = AngelWebSocket(
    client.auth_token,
    client.smart_api.api_key,
    cfg.settings.ANGEL_CLIENT_CODE,
    client.feed_token,
    on_tick
)

thread = threading.Thread(
    target=ws.connect,
    daemon=True
)

thread.start()

time.sleep(3)

ws.subscribe(tokens)

print("SUBSCRIBED")
print("WAITING FOR TICKS...")

time.sleep(30)