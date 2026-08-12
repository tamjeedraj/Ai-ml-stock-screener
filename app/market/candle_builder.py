from datetime import datetime, timezone


class CandleBuilder:

    def __init__(self):
        self.current = {}

    # ==================================================
    # TIMESTAMP
    # ==================================================

    def _get_timestamp(self, tick):

        raw_timestamp = tick.get("timestamp")

        if raw_timestamp is None:
            return datetime.now(timezone.utc)

        try:

            # Already datetime
            if isinstance(
                raw_timestamp,
                datetime
            ):

                if raw_timestamp.tzinfo is None:
                    return raw_timestamp.replace(
                        tzinfo=timezone.utc
                    )

                return raw_timestamp

            # Numeric timestamp
            timestamp = float(
                raw_timestamp
            )

            # Angel One normally sends milliseconds.
            # Also support seconds safely.
            if timestamp > 10_000_000_000:
                timestamp = timestamp / 1000.0

            return datetime.fromtimestamp(
                timestamp,
                tz=timezone.utc
            )

        except Exception:

            return datetime.now(
                timezone.utc
            )

    # ==================================================
    # CREATE CANDLE
    # ==================================================

    def _create_candle(
        self,
        symbol,
        minute,
        price,
        volume
    ):

        return {
            "symbol": symbol,
            "timestamp": minute,
            "open": price,
            "high": price,
            "low": price,
            "close": price,
            "volume": volume,
        }

    # ==================================================
    # UPDATE
    # ==================================================

    def update(self, tick):

        if not isinstance(tick, dict):
            return None

        symbol = tick.get("symbol")

        if not symbol:
            return None

        try:

            price = float(
                tick.get(
                    "ltp",
                    0
                ) or 0
            )

        except Exception:

            return None

        if price <= 0:
            return None

        try:

            volume = int(
                float(
                    tick.get(
                        "ltq",
                        0
                    ) or 0
                )
            )

        except Exception:

            volume = 0

        timestamp = self._get_timestamp(
            tick
        )

        minute = timestamp.replace(
            second=0,
            microsecond=0
        )

        current = self.current.get(
            symbol
        )

        # ==================================================
        # FIRST LIVE CANDLE
        # ==================================================

        if current is None:

            self.current[symbol] = (
                self._create_candle(
                    symbol,
                    minute,
                    price,
                    volume
                )
            )

            return None

        # ==================================================
        # SAME MINUTE
        # ==================================================

        if current["timestamp"] == minute:

            current["high"] = max(
                current["high"],
                price
            )

            current["low"] = min(
                current["low"],
                price
            )

            current["close"] = price

            current["volume"] += volume

            return None

        # ==================================================
        # NEW MINUTE
        # ==================================================

        completed = {
            "symbol": current["symbol"],
            "timestamp": current["timestamp"],
            "open": float(
                current["open"]
            ),
            "high": float(
                current["high"]
            ),
            "low": float(
                current["low"]
            ),
            "close": float(
                current["close"]
            ),
            "volume": int(
                current["volume"]
            ),
        }

        # ==================================================
        # START NEW CANDLE
        # ==================================================

        self.current[symbol] = (
            self._create_candle(
                symbol,
                minute,
                price,
                volume
            )
        )

        return completed

    # ==================================================
    # GET CURRENT CANDLE
    # ==================================================

    def get_current(self, symbol):

        candle = self.current.get(
            symbol
        )

        if candle is None:
            return None

        return dict(candle)

    # ==================================================
    # GET ALL CURRENT CANDLES
    # ==================================================

    def get_all_current(self):

        return {
            symbol: dict(candle)
            for symbol, candle
            in self.current.items()
        }

    # ==================================================
    # CLEAR
    # ==================================================

    def clear(self, symbol=None):

        if symbol is None:

            self.current.clear()

            return

        self.current.pop(
            symbol,
            None
        )