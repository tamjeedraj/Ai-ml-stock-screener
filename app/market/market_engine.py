import asyncio
import csv
import os
import time
import threading

from collections import defaultdict, deque
from datetime import datetime, timedelta

import pandas as pd

from app.broker.angel_one import AngelOneClient
from app.broker.websocket import AngelWebSocket

from app.market.tick_normalizer import normalize_tick
from app.market.tick_store import TickStore
from app.market.candle_builder import CandleBuilder
from app.market.indicators import add_smma
from app.market.aggregator import TickAggregator
from app.market.universe import NSEUniverse

from app.strategy.crossover import detect_crossover
from app.strategy.features import build_features
from app.strategy.trade_tracker import TradeTracker

from app.ml.predictor import MLPredictor
from app.ml.trainer import train_model

from app.api.routes import broadcast
from app.config import settings


class MarketEngine:

    FEATURES = [
        "ltq_ratio",
        "etq_5m",
        "etq_20m",
        "etq_60m",
        "smma_distance",
        "order_imbalance",
        "ltp",
        "bid_qty",
        "ask_qty",
    ]

    TRAINING_DATASET = "data/training_dataset.csv"

    # ==================================================
    # SCREENING
    # ==================================================

    MIN_LTP = 30.0
    MAX_LTP = 500.0

    MIN_BID_QTY = 1_000_001
    MIN_ASK_QTY = 1_000_001

    MIN_TOTAL_DEPTH = 200_000

    USE_SOFT_DEPTH_FILTER = True

    # 120 is intentional. Change to 0 for all eligible stocks.
    MAX_LIVE_STOCKS = 120

    QUOTE_BATCH_SIZE = 50
    QUOTE_DELAY = 1.15
    HISTORY_DELAY = 1.20

    # Historical retry configuration
    HISTORY_RETRIES = 3
    HISTORY_DAYS = 10

    # ==================================================
    # INIT
    # ==================================================

    def __init__(self):

        self.client = AngelOneClient()
        self.universe = NSEUniverse()

        self.store = TickStore()
        self.candles = CandleBuilder()

        self.ws = None

        # IMPORTANT:
        # This must be the FastAPI/uvicorn event loop.
        self.loop = None

        self.websocket_thread_id = None

        self.candle_history = defaultdict(
            lambda: deque(maxlen=500)
        )

        self.previous_indicator = {}

        self.trade_tracker = TradeTracker()

        self.predictor = MLPredictor(
            settings.MODEL_PATH
        )

        self.last_training_rows = 0

        self.token_symbols = {}
        self.eligible_tokens = set()
        self.screened_rows = {}

        self.last_tick_time = {}
        self.tick_count = defaultdict(int)

        self._ensure_training_dataset()

    # ==================================================
    # EVENT LOOP
    # ==================================================

    def set_loop(self, loop=None):
        """
        Call this from the FastAPI startup code.

        Example:

            market_engine.set_loop(asyncio.get_running_loop())
        """

        if loop is not None:
            self.loop = loop

            print(
                "MarketEngine event loop attached."
            )

    def _get_loop(self):

        if self.loop is not None:
            return self.loop

        try:
            loop = asyncio.get_running_loop()
            self.loop = loop
            return loop
        except RuntimeError:
            pass

        try:
            loop = asyncio.get_event_loop()

            if loop.is_running():
                self.loop = loop
                return loop

        except Exception:
            pass

        return None

    # ==================================================
    # DATASET
    # ==================================================

    def _ensure_training_dataset(self):

        directory = os.path.dirname(
            self.TRAINING_DATASET
        )

        if directory:
            os.makedirs(
                directory,
                exist_ok=True
            )

        if not os.path.exists(
            self.TRAINING_DATASET
        ):

            with open(
                self.TRAINING_DATASET,
                "w",
                newline="",
                encoding="utf-8"
            ) as file:

                writer = csv.DictWriter(
                    file,
                    fieldnames=self.FEATURES + ["label"]
                )

                writer.writeheader()

    def _save_completed_trade(self, trade):

        row = {}

        for feature in self.FEATURES:

            try:

                row[feature] = float(
                    trade["features"].get(
                        feature,
                        0
                    )
                )

            except Exception:

                row[feature] = 0.0

        row["label"] = int(
            trade["label"]
        )

        with open(
            self.TRAINING_DATASET,
            "a",
            newline="",
            encoding="utf-8"
        ) as file:

            writer = csv.DictWriter(
                file,
                fieldnames=self.FEATURES + ["label"]
            )

            writer.writerow(row)

    # ==================================================
    # ML
    # ==================================================

    def _train_if_ready(self):

        if not os.path.exists(
            self.TRAINING_DATASET
        ):
            return

        try:

            df = pd.read_csv(
                self.TRAINING_DATASET
            )

        except Exception as error:

            print(
                "Dataset error:",
                error
            )

            return

        if len(df) < 20:

            print(
                f"ML samples: {len(df)}/20"
            )

            return

        if "label" not in df.columns:
            return

        labels = set(
            df["label"]
            .dropna()
            .astype(int)
            .unique()
        )

        if not {0, 1}.issubset(labels):

            print(
                "ML waiting for both "
                "profitable and losing trades."
            )

            return

        if len(df) == self.last_training_rows:
            return

        try:

            model, accuracy = train_model(
                df,
                settings.MODEL_PATH
            )

            self.predictor = MLPredictor(
                settings.MODEL_PATH
            )

            self.last_training_rows = len(df)

            print("================================")
            print("ML MODEL READY")
            print(
                "MODEL:",
                settings.MODEL_PATH
            )
            print(
                "ACCURACY:",
                round(accuracy, 4)
            )
            print(
                "SAMPLES:",
                len(df)
            )
            print("================================")

        except Exception as error:

            print(
                "ML training error:",
                error
            )

    # ==================================================
    # SAFE NUMBER
    # ==================================================

    @staticmethod
    def _safe_float(value, default=0.0):

        try:

            if value is None:
                return default

            return float(value)

        except Exception:

            return default

    @staticmethod
    def _safe_int(value, default=0):

        try:

            if value is None:
                return default

            return int(
                float(value)
            )

        except Exception:

            return default

    # ==================================================
    # DEPTH
    # ==================================================

    def _extract_depth(self, quote):

        bid_qty = self._safe_int(
            quote.get(
                "totalBuyQuantity"
            )
        )

        ask_qty = self._safe_int(
            quote.get(
                "totalSellQuantity"
            )
        )

        if bid_qty <= 0:

            bid_qty = self._safe_int(
                quote.get(
                    "total_buy_quantity"
                )
            )

        if ask_qty <= 0:

            ask_qty = self._safe_int(
                quote.get(
                    "total_sell_quantity"
                )
            )

        buy_data = (
            quote.get(
                "best_5_buy_data"
            )
            or []
        )

        sell_data = (
            quote.get(
                "best_5_sell_data"
            )
            or []
        )

        if bid_qty <= 0:

            for level in buy_data:

                if not isinstance(
                    level,
                    dict
                ):
                    continue

                bid_qty += self._safe_int(
                    level.get(
                        "quantity"
                    )
                )

        if ask_qty <= 0:

            for level in sell_data:

                if not isinstance(
                    level,
                    dict
                ):
                    continue

                ask_qty += self._safe_int(
                    level.get(
                        "quantity"
                    )
                )

        bid_price = 0.0
        ask_price = 0.0

        if buy_data:

            try:

                bid_price = self._safe_float(
                    buy_data[0].get(
                        "price"
                    )
                )

            except Exception:

                bid_price = 0.0

        if sell_data:

            try:

                ask_price = self._safe_float(
                    sell_data[0].get(
                        "price"
                    )
                )

            except Exception:

                ask_price = 0.0

        if bid_price > 10000:
            bid_price /= 100.0

        if ask_price > 10000:
            ask_price /= 100.0

        return (
            bid_qty,
            ask_qty,
            bid_price,
            ask_price
        )

    # ==================================================
    # STOCK SCREENING
    # ==================================================

    def _screen_nse_stocks(self):

        instruments = self.universe.get_tokens()

        if not instruments:

            print(
                "ERROR: NSE universe is empty."
            )

            return []

        self.token_symbols = {
            str(row["token"]): str(row["symbol"])
            for row in instruments
            if row.get("token")
        }

        tokens = list(
            self.token_symbols.keys()
        )

        print(
            "NSE universe:",
            len(tokens)
        )

        ltp_candidates = []
        preferred_depth_candidates = []

        total_batches = (
            len(tokens)
            + self.QUOTE_BATCH_SIZE
            - 1
        ) // self.QUOTE_BATCH_SIZE

        for batch_no, start in enumerate(
            range(
                0,
                len(tokens),
                self.QUOTE_BATCH_SIZE
            ),
            start=1
        ):

            batch = tokens[
                start:
                start + self.QUOTE_BATCH_SIZE
            ]

            try:

                response = self.client.market_quote(
                    batch,
                    mode="FULL"
                )

            except Exception as error:

                print(
                    f"Quote batch "
                    f"{batch_no}/{total_batches} error:",
                    error
                )

                time.sleep(
                    self.QUOTE_DELAY * 2
                )

                continue

            if not isinstance(
                response,
                dict
            ):

                print(
                    f"Quote batch "
                    f"{batch_no}/{total_batches}: "
                    "invalid response"
                )

                time.sleep(
                    self.QUOTE_DELAY
                )

                continue

            fetched = (
                response.get(
                    "fetched",
                    []
                )
                or []
            )

            ltp_pass = 0
            depth_pass = 0
            depth_available = 0

            for quote in fetched:

                try:

                    if not isinstance(
                        quote,
                        dict
                    ):
                        continue

                    token = str(
                        quote.get(
                            "symbolToken",
                            ""
                        )
                    )

                    if not token:
                        continue

                    symbol = (
                        self.token_symbols.get(
                            token,
                            quote.get(
                                "tradingSymbol",
                                token
                            )
                        )
                    )

                    ltp = self._safe_float(
                        quote.get(
                            "ltp"
                        )
                    )

                    if not (
                        self.MIN_LTP
                        <= ltp
                        <= self.MAX_LTP
                    ):
                        continue

                    ltp_pass += 1

                    (
                        bid_qty,
                        ask_qty,
                        bid_price,
                        ask_price
                    ) = self._extract_depth(
                        quote
                    )

                    total_depth = (
                        bid_qty
                        + ask_qty
                    )

                    if total_depth > 0:
                        depth_available += 1

                    depth_score = (
                        min(
                            bid_qty,
                            self.MIN_BID_QTY
                        )
                        +
                        min(
                            ask_qty,
                            self.MIN_ASK_QTY
                        )
                    )

                    self.screened_rows[
                        token
                    ] = {

                        "symbol": symbol,

                        "ltp": ltp,

                        "bid_price": bid_price,

                        "bid_qty": bid_qty,

                        "ask_price": ask_price,

                        "ask_qty": ask_qty,

                        "total_depth": total_depth,

                        "depth_score": depth_score,
                    }

                    ltp_candidates.append(
                        token
                    )

                    if (
                        bid_qty >= self.MIN_BID_QTY
                        and
                        ask_qty >= self.MIN_ASK_QTY
                    ):

                        preferred_depth_candidates.append(
                            token
                        )

                        depth_pass += 1

                except Exception as error:

                    print(
                        "Quote parse error:",
                        error
                    )

            print(
                f"Screening "
                f"{batch_no}/{total_batches} | "
                f"checked "
                f"{min(start + len(batch), len(tokens))}/"
                f"{len(tokens)} | "
                f"LTP pass: {ltp_pass} | "
                f"Depth pass: {depth_pass} | "
                f"Depth data: {depth_available}"
            )

            time.sleep(
                self.QUOTE_DELAY
            )

        unique_ltp = list(
            dict.fromkeys(
                ltp_candidates
            )
        )

        unique_depth = list(
            dict.fromkeys(
                preferred_depth_candidates
            )
        )

        if (
            self.USE_SOFT_DEPTH_FILTER
            and len(unique_depth) >= 10
        ):

            final_candidates = unique_depth

            selection_mode = (
                "LTP + FULL DEPTH"
            )

        else:

            final_candidates = unique_ltp

            final_candidates.sort(
                key=lambda token: (
                    self.screened_rows.get(
                        token,
                        {}
                    ).get(
                        "total_depth",
                        0
                    ),

                    min(
                        self.screened_rows.get(
                            token,
                            {}
                        ).get(
                            "bid_qty",
                            0
                        ),

                        self.screened_rows.get(
                            token,
                            {}
                        ).get(
                            "ask_qty",
                            0
                        )
                    ),

                    self.screened_rows.get(
                        token,
                        {}
                    ).get(
                        "ltp",
                        0
                    )
                ),
                reverse=True
            )

            selection_mode = (
                "LTP + LIQUIDITY RANKING"
            )

        if (
            self.MAX_LIVE_STOCKS > 0
            and
            len(final_candidates)
            > self.MAX_LIVE_STOCKS
        ):

            final_candidates = (
                final_candidates[
                    :self.MAX_LIVE_STOCKS
                ]
            )

        self.eligible_tokens = set(
            final_candidates
        )

        print("================================")
        print("SCREENING COMPLETE")
        print("================================")
        print(
            "Universe:",
            len(tokens)
        )
        print(
            "LTP candidates:",
            len(unique_ltp)
        )
        print(
            "Full depth candidates:",
            len(unique_depth)
        )
        print(
            "Selection mode:",
            selection_mode
        )
        print(
            "Live stocks selected:",
            len(self.eligible_tokens)
        )
        print(
            "================================"
        )

        for token in final_candidates:

            row = self.screened_rows.get(
                token,
                {}
            )

            print(
                f"{row.get('symbol', token)} | "
                f"LTP={row.get('ltp', 0):.2f} | "
                f"BID={row.get('bid_qty', 0)} | "
                f"ASK={row.get('ask_qty', 0)} | "
                f"DEPTH={row.get('total_depth', 0)}"
            )

        print("================================")

        return list(
            self.eligible_tokens
        )

    # ==================================================
    # HISTORICAL DATA
    # ==================================================

    def _parse_history_response(self, response):

        if not isinstance(
            response,
            dict
        ):
            return []

        data = (
            response.get(
                "data",
                []
            )
            or []
        )

        if not isinstance(
            data,
            list
        ):
            return []

        history = []

        for row in data:

            try:

                if not isinstance(
                    row,
                    (list, tuple)
                ):
                    continue

                if len(row) < 6:
                    continue

                timestamp = pd.Timestamp(
                    row[0]
                )

                candle = {

                    "symbol": None,

                    "timestamp": timestamp,

                    "open": float(
                        row[1]
                    ),

                    "high": float(
                        row[2]
                    ),

                    "low": float(
                        row[3]
                    ),

                    "close": float(
                        row[4]
                    ),

                    "volume": int(
                        float(
                            row[5]
                        )
                    ),
                }

                history.append(
                    candle
                )

            except Exception as error:

                print(
                    "History row parse error:",
                    error
                )

        history.sort(
            key=lambda x: x["timestamp"]
        )

        return history

    def _load_history(self, token):

        symbol = self.token_symbols.get(
            token,
            token
        )

        print(
            f"[HISTORY] Loading {symbol} "
            f"token={token}"
        )

        for attempt in range(
            1,
            self.HISTORY_RETRIES + 1
        ):

            try:

                to_date = datetime.now()

                from_date = (
                    to_date
                    - timedelta(
                        days=self.HISTORY_DAYS
                    )
                )

                response = self.client.historical_data(
                    "NSE",
                    str(token),
                    "ONE_MINUTE",
                    from_date.strftime(
                        "%Y-%m-%d %H:%M"
                    ),
                    to_date.strftime(
                        "%Y-%m-%d %H:%M"
                    )
                )

                if not isinstance(
                    response,
                    dict
                ):

                    print(
                        f"[HISTORY] {symbol} "
                        f"attempt={attempt} "
                        f"invalid response: "
                        f"{type(response)}"
                    )

                    time.sleep(2)

                    continue

                history = (
                    self._parse_history_response(
                        response
                    )
                )

                if not history:

                    print(
                        f"[HISTORY] {symbol} "
                        f"attempt={attempt} "
                        f"NO DATA"
                    )

                    print(
                        "[HISTORY] API response keys:",
                        list(response.keys())
                    )

                    if response.get("message"):
                        print(
                            "[HISTORY] message:",
                            response.get("message")
                        )

                    if response.get("errorcode"):
                        print(
                            "[HISTORY] errorcode:",
                            response.get("errorcode")
                        )

                    time.sleep(2)

                    continue

                for candle in history[-500:]:

                    candle["symbol"] = token

                    self.candle_history[
                        token
                    ].append(
                        candle
                    )

                count = len(
                    self.candle_history[
                        token
                    ]
                )

                print(
                    f"[HISTORY] SUCCESS | "
                    f"{symbol} | "
                    f"candles={count}"
                )

                return count

            except Exception as error:

                print(
                    f"[HISTORY] ERROR | "
                    f"{symbol} | "
                    f"attempt={attempt}/"
                    f"{self.HISTORY_RETRIES} | "
                    f"{error}"
                )

                time.sleep(2)

        print(
            f"[HISTORY] FAILED | "
            f"{symbol} | "
            f"0 candles"
        )

        return 0

    def _load_historical_data(self, tokens):

        print("==========================")
        print(
            "HISTORICAL INITIALIZATION STARTED"
        )
        print(
            "Stocks:",
            len(tokens)
        )
        print("==========================")

        success = 0
        failed = 0

        for index, token in enumerate(
            tokens,
            start=1
        ):

            try:

                count = len(
                    self.candle_history[
                        token
                    ]
                )

                if count < 120:

                    count = self._load_history(
                        token
                    )

                if count >= 120:
                    success += 1
                else:
                    failed += 1

                print(
                    f"[HISTORY PROGRESS] "
                    f"{index}/{len(tokens)} | "
                    f"{self.token_symbols.get(token, token)} | "
                    f"{count}/120"
                )

            except Exception as error:

                failed += 1

                print(
                    "[HISTORY LOADER ERROR]:",
                    token,
                    error
                )

            time.sleep(
                self.HISTORY_DELAY
            )

        print("================================")
        print(
            "HISTORICAL INITIALIZATION FINISHED"
        )
        print(
            "SUCCESS:",
            success
        )
        print(
            "FAILED:",
            failed
        )
        print("================================")

    # ==================================================
    # PREDICTION
    # ==================================================

    def _build_prediction(self, tick):

        token = str(
            tick["symbol"]
        )

        history = list(
            self.candle_history[
                token
            ]
        )

        if len(history) < 120:

            return {

                "smma20": None,

                "smma120": None,

                "etq_5m": None,

                "etq_20m": None,

                "etq_60m": None,

                "avg_ltp_20m": None,

                "avg_ltp_60m": None,

                "crossover": "-",

                "decision": "WAITING",

                "probability": None,

                "reason": (
                    f"Collecting historical candles "
                    f"{len(history)}/120"
                )
            }

        df = pd.DataFrame(
            history
        )

        df = add_smma(
            df
        )

        current_row = df.iloc[-1]

        current = {

            "smma20": current_row[
                "smma20"
            ],

            "smma120": current_row[
                "smma120"
            ],

            "ltp": self._safe_float(
                tick.get(
                    "ltp"
                )
            ),

            "bid_qty": self._safe_int(
                tick.get(
                    "bid_qty"
                )
            ),

            "ask_qty": self._safe_int(
                tick.get(
                    "ask_qty"
                )
            ),
        }

        if (
            pd.isna(
                current["smma20"]
            )
            or
            pd.isna(
                current["smma120"]
            )
        ):

            return {

                "smma20": None,

                "smma120": None,

                "etq_5m": None,

                "etq_20m": None,

                "etq_60m": None,

                "avg_ltp_20m": None,

                "avg_ltp_60m": None,

                "crossover": "-",

                "decision": "WAITING",

                "probability": None,

                "reason": "SMMA pending"
            }

        previous = (
            self.previous_indicator.get(
                token
            )
        )

        crossover = detect_crossover(
            previous,
            current
        )

        self.previous_indicator[
            token
        ] = {

            "smma20": float(
                current["smma20"]
            ),

            "smma120": float(
                current["smma120"]
            )
        }

        ticks = self.store.get_recent(
            token,
            60
        )

        metrics = TickAggregator.metrics(
            ticks
        )

        features = build_features(
            current,
            metrics
        )

        if crossover:

            active = (
                self.trade_tracker.active.get(
                    token
                )
            )

            if active:

                if (
                    active["direction"]
                    != crossover
                ):

                    closed = (
                        self.trade_tracker.close_trade(
                            token,
                            float(
                                tick["ltp"]
                            )
                        )
                    )

                    if closed:

                        self._save_completed_trade(
                            closed
                        )

                        self._train_if_ready()

            if (
                token
                not in self.trade_tracker.active
            ):

                self.trade_tracker.open_trade(
                    token,
                    crossover,
                    float(
                        tick["ltp"]
                    ),
                    features
                )

        try:

            prediction = (
                self.predictor.predict(
                    features
                )
            )

        except Exception as error:

            print(
                "Prediction error:",
                token,
                error
            )

            prediction = {

                "decision": "MODEL_NOT_READY",

                "probability": None,

                "reason": "Prediction error"
            }

        return {

            "smma20": float(
                current["smma20"]
            ),

            "smma120": float(
                current["smma120"]
            ),

            "etq_5m": metrics.get(
                "etq_5m",
                0
            ),

            "etq_20m": metrics.get(
                "etq_20m",
                0
            ),

            "etq_60m": metrics.get(
                "etq_60m",
                0
            ),

            "avg_ltp_20m": metrics.get(
                "avg_ltp_20m",
                0
            ),

            "avg_ltp_60m": metrics.get(
                "avg_ltp_60m",
                0
            ),

            "crossover": (
                crossover
                or "-"
            ),

            "decision": prediction.get(
                "decision",
                "MODEL_NOT_READY"
            ),

            "probability": prediction.get(
                "probability"
            ),

            "reason": prediction.get(
                "reason",
                "Waiting for ML analysis"
            )
        }

    # ==================================================
    # BROADCAST
    # ==================================================

    def _broadcast_from_tick(self, result):

        loop = self._get_loop()

        if loop is None:

            print(
                "[BROADCAST] Event loop not available"
            )

            return

        if not loop.is_running():

            print(
                "[BROADCAST] Event loop is not running"
            )

            return

        try:

            future = (
                asyncio.run_coroutine_threadsafe(
                    broadcast(result),
                    loop
                )
            )

            # Do not block tick thread.
            future.add_done_callback(
                self._broadcast_done
            )

        except Exception as error:

            print(
                "[BROADCAST ERROR]:",
                error
            )

    @staticmethod
    def _broadcast_done(future):

        try:
            future.result()

        except Exception as error:

            print(
                "[BROADCAST TASK ERROR]:",
                error
            )

    # ==================================================
    # LIVE TICK
    # ==================================================

    def on_tick(self, raw_tick):

        try:

            self.websocket_thread_id = (
                threading.get_ident()
            )

            tick = normalize_tick(
                raw_tick
            )

            if not isinstance(
                tick,
                dict
            ):
                return

            token = tick.get(
                "symbol"
            )

            if token is None:
                return

            token = str(token)

            if (
                self.eligible_tokens
                and
                token not in self.eligible_tokens
            ):
                return

            symbol = self.token_symbols.get(
                token,
                token
            )

            self.tick_count[
                token
            ] += 1

            self.last_tick_time[
                token
            ] = time.time()

            # ------------------------------------------
            # STORE LIVE TICK
            # ------------------------------------------

            self.store.add(
                token,
                tick
            )

            # ------------------------------------------
            # UPDATE CANDLE
            # ------------------------------------------

            completed = self.candles.update(
                tick
            )

            if completed:

                completed["symbol"] = token

                self.candle_history[
                    token
                ].append(
                    completed
                )

            # ------------------------------------------
            # SCREENING FALLBACK
            # ------------------------------------------

            screening = self.screened_rows.get(
                token,
                {}
            )

            result = {

                "symbol": symbol,

                "token": token,

                "ltp": tick.get(
                    "ltp",
                    screening.get(
                        "ltp",
                        0
                    )
                ),

                "bid_price": tick.get(
                    "bid_price",
                    screening.get(
                        "bid_price",
                        0
                    )
                ),

                "bid_qty": tick.get(
                    "bid_qty",
                    screening.get(
                        "bid_qty",
                        0
                    )
                ),

                "ask_price": tick.get(
                    "ask_price",
                    screening.get(
                        "ask_price",
                        0
                    )
                ),

                "ask_qty": tick.get(
                    "ask_qty",
                    screening.get(
                        "ask_qty",
                        0
                    )
                ),

                "ltq": tick.get(
                    "ltq",
                    0
                ),

                "smma20": None,

                "smma120": None,

                "etq_5m": None,

                "etq_20m": None,

                "etq_60m": None,

                "avg_ltp_20m": None,

                "avg_ltp_60m": None,

                "crossover": "-",

                "decision": "WAITING",

                "probability": None,

                "reason": (
                    "Loading historical candles..."
                )
            }

            # ------------------------------------------
            # PREDICTION ON EVERY LIVE TICK
            # ------------------------------------------

            history_count = len(
                self.candle_history[
                    token
                ]
            )

            if history_count >= 120:

                prediction = (
                    self._build_prediction(
                        tick
                    )
                )

                result.update(
                    prediction
                )

            else:

                result["reason"] = (
                    f"Collecting historical candles "
                    f"{history_count}/120"
                )

            # ------------------------------------------
            # BROADCAST LIVE RESULT
            # ------------------------------------------

            self._broadcast_from_tick(
                result
            )

            # ------------------------------------------
            # TERMINAL LIVE DEBUG
            # ------------------------------------------

            if (
                self.tick_count[token] == 1
                or
                self.tick_count[token] % 100 == 0
            ):

                print(
                    f"[LIVE] "
                    f"{symbol} | "
                    f"LTP={result.get('ltp', 0)} | "
                    f"ticks={self.tick_count[token]} | "
                    f"history={history_count}/120"
                )

        except Exception as error:

            print(
                "Tick processing error:",
                error
            )

    # ==================================================
    # WEBSOCKET HEALTH MONITOR
    # ==================================================

    def _websocket_monitor(self):

        print(
            "[WS MONITOR] Started"
        )

        while True:

            try:

                time.sleep(10)

                if not self.ws:
                    continue

                now = time.time()

                active = 0

                for token in self.eligible_tokens:

                    last = self.last_tick_time.get(
                        token
                    )

                    if last and (
                        now - last < 30
                    ):

                        active += 1

                print(
                    f"[WS MONITOR] "
                    f"selected={len(self.eligible_tokens)} | "
                    f"active_ticks={active} | "
                    f"total_ticks="
                    f"{sum(self.tick_count.values())}"
                )

            except Exception as error:

                print(
                    "[WS MONITOR ERROR]:",
                    error
                )

    # ==================================================
    # START MARKET
    # ==================================================

    def start_market_scan(self):

        try:

            print("================================")
            print("STARTING MARKET ENGINE")
            print("================================")

            # ------------------------------------------
            # IMPORTANT:
            # Capture currently running event loop
            # if start_market_scan is called from async
            # FastAPI code.
            # ------------------------------------------

            self._get_loop()

            if self.loop:

                print(
                    "Event loop:",
                    self.loop
                )

            else:

                print(
                    "WARNING: "
                    "Event loop not attached yet."
                )

            # ------------------------------------------
            # LOGIN
            # ------------------------------------------

            session = self.client.login()

            if not session:

                raise RuntimeError(
                    "Angel One login returned empty session"
                )

            print(
                "Angel One login successful"
            )

            # ------------------------------------------
            # SCREEN
            # ------------------------------------------

            eligible = (
                self._screen_nse_stocks()
            )

            if not eligible:

                print("================================")
                print(
                    "NO STOCKS PASSED SCREENING"
                )
                print("================================")

                return

            print(
                "LIVE ELIGIBLE STOCKS:",
                len(eligible)
            )

            # ------------------------------------------
            # WEBSOCKET
            # ------------------------------------------

            self.ws = AngelWebSocket(

                auth_token=session[
                    "auth_token"
                ],

                api_key=(
                    self.client.smart_api.api_key
                ),

                client_code=(
                    settings.ANGEL_CLIENT_CODE
                ),

                feed_token=session[
                    "feed_token"
                ],

                on_tick=self.on_tick
            )

            print(
                "Subscribing WebSocket tokens..."
            )

            self.ws.subscribe(
                eligible
            )

            print(
                "Eligible WebSocket tokens:",
                len(eligible)
            )

            # ------------------------------------------
            # HISTORICAL DATA
            #
            # Run in parallel so WebSocket can become
            # live immediately.
            # ------------------------------------------

            history_thread = threading.Thread(

                target=self._load_historical_data,

                args=(eligible,),

                daemon=True,

                name="historical-loader"
            )

            history_thread.start()

            print(
                "Historical loader started."
            )

            # ------------------------------------------
            # WEBSOCKET MONITOR
            # ------------------------------------------

            monitor_thread = threading.Thread(

                target=self._websocket_monitor,

                daemon=True,

                name="websocket-monitor"
            )

            monitor_thread.start()

            # ------------------------------------------
            # CONNECT
            # ------------------------------------------

            print(
                "================================"
            )

            print(
                "CONNECTING WEBSOCKET..."
            )

            print(
                "================================"
            )

            self.ws.connect()

        except Exception as error:

            print("================================")
            print(
                "MARKET STARTUP ERROR:",
                error
            )
            print("================================")

            raise