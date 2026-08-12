from datetime import datetime, timezone


class TradeTracker:

    def __init__(self):

        self.active = {}

        self.completed = []

    # ==================================================
    # OPEN TRADE
    # ==================================================

    def open_trade(
        self,
        symbol,
        direction,
        price,
        features
    ):

        symbol = str(
            symbol
        )

        direction = str(
            direction
        ).upper()

        try:
            price = float(price)
        except Exception:
            return None

        if price <= 0:
            return None

        if direction not in {
            "BUY",
            "SELL"
        }:
            return None

        # Don't overwrite an active trade
        if symbol in self.active:
            return self.active[
                symbol
            ]

        trade = {

            "symbol": symbol,

            "direction": direction,

            "entry_price": price,

            "entry_time": (
                datetime.now(
                    timezone.utc
                ).isoformat()
            ),

            "features": dict(
                features or {}
            ),
        }

        self.active[symbol] = trade

        return trade

    # ==================================================
    # CLOSE TRADE
    # ==================================================

    def close_trade(
        self,
        symbol,
        exit_price
    ):

        symbol = str(
            symbol
        )

        try:
            exit_price = float(
                exit_price
            )
        except Exception:
            return None

        if exit_price <= 0:
            return None

        trade = self.active.pop(
            symbol,
            None
        )

        if trade is None:
            return None

        entry_price = float(
            trade["entry_price"]
        )

        direction = trade[
            "direction"
        ]

        # ==================================================
        # PNL
        # ==================================================

        if direction == "BUY":

            pnl = (
                exit_price
                - entry_price
            )

        else:

            pnl = (
                entry_price
                - exit_price
            )

        # ==================================================
        # PNL %
        # ==================================================

        if entry_price > 0:

            pnl_percent = (
                pnl
                / entry_price
            ) * 100.0

        else:

            pnl_percent = 0.0

        # ==================================================
        # LABEL
        #
        # 1 = profitable
        # 0 = losing / breakeven
        # ==================================================

        label = (
            1
            if pnl > 0
            else 0
        )

        trade[
            "exit_price"
        ] = exit_price

        trade[
            "exit_time"
        ] = (
            datetime.now(
                timezone.utc
            ).isoformat()
        )

        trade[
            "pnl"
        ] = float(pnl)

        trade[
            "pnl_percent"
        ] = float(
            pnl_percent
        )

        trade[
            "label"
        ] = label

        self.completed.append(
            trade
        )

        return trade

    # ==================================================
    # GET ACTIVE TRADE
    # ==================================================

    def get_active(
        self,
        symbol
    ):

        return self.active.get(
            str(symbol)
        )

    # ==================================================
    # CHECK ACTIVE
    # ==================================================

    def has_active(
        self,
        symbol
    ):

        return (
            str(symbol)
            in self.active
        )

    # ==================================================
    # ACTIVE COUNT
    # ==================================================

    def active_count(self):

        return len(
            self.active
        )

    # ==================================================
    # COMPLETED COUNT
    # ==================================================

    def completed_count(self):

        return len(
            self.completed
        )

    # ==================================================
    # STATISTICS
    # ==================================================

    def statistics(self):

        if not self.completed:

            return {
                "total": 0,
                "profitable": 0,
                "losing": 0,
                "win_rate": 0.0,
                "total_pnl": 0.0,
            }

        profitable = sum(
            1
            for trade
            in self.completed
            if trade.get(
                "label",
                0
            ) == 1
        )

        losing = (
            len(
                self.completed
            )
            - profitable
        )

        total_pnl = sum(
            float(
                trade.get(
                    "pnl",
                    0
                )
            )
            for trade
            in self.completed
        )

        win_rate = (
            profitable
            / len(
                self.completed
            )
        ) * 100.0

        return {

            "total": len(
                self.completed
            ),

            "profitable": profitable,

            "losing": losing,

            "win_rate": float(
                win_rate
            ),

            "total_pnl": float(
                total_pnl
            ),
        }