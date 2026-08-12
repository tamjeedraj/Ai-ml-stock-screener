from collections import defaultdict, deque
from datetime import datetime
import threading


class TickStore:

    def __init__(self):

        self.data = defaultdict(
            lambda: deque(maxlen=50000)
        )

        self.lock = threading.RLock()

    def add(self, symbol, tick):

        with self.lock:
            self.data[symbol].append(tick)

    def get_recent(
        self,
        symbol,
        minutes
    ):

        cutoff = (
            datetime.now().timestamp() - (minutes * 60)
        ) * 1000

        with self.lock:

            return [
                x
                for x in self.data[symbol]
                if x["timestamp"] >= cutoff
            ]