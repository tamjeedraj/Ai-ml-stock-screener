import pandas as pd


class TickAggregator:

    # ==================================================
    # CONVERT TICKS TO DATAFRAME
    # ==================================================

    @staticmethod
    def dataframe(ticks):

        if not ticks:
            return pd.DataFrame()

        try:

            df = pd.DataFrame(ticks)

        except Exception:
            return pd.DataFrame()

        if df.empty:
            return df

        # ----------------------------------------------
        # Required columns
        # ----------------------------------------------

        required_columns = [
            "timestamp",
            "ltp",
            "ltq",
            "bid_qty",
            "ask_qty",
        ]

        for column in required_columns:

            if column not in df.columns:

                if column == "timestamp":
                    return pd.DataFrame()

                df[column] = 0

        # ----------------------------------------------
        # Numeric conversion
        # ----------------------------------------------

        df["ltp"] = pd.to_numeric(
            df["ltp"],
            errors="coerce"
        )

        df["ltq"] = pd.to_numeric(
            df["ltq"],
            errors="coerce"
        ).fillna(0)

        df["bid_qty"] = pd.to_numeric(
            df["bid_qty"],
            errors="coerce"
        ).fillna(0)

        df["ask_qty"] = pd.to_numeric(
            df["ask_qty"],
            errors="coerce"
        ).fillna(0)

        # ----------------------------------------------
        # Timestamp conversion
        # ----------------------------------------------

        try:

            timestamps = pd.to_numeric(
                df["timestamp"],
                errors="coerce"
            )

            # Angel One normally sends milliseconds.
            # Support seconds as well.
            if (
                timestamps.notna().any()
                and timestamps.dropna().median()
                < 10_000_000_000
            ):

                df["timestamp"] = pd.to_datetime(
                    timestamps,
                    unit="s",
                    errors="coerce",
                    utc=True
                )

            else:

                df["timestamp"] = pd.to_datetime(
                    timestamps,
                    unit="ms",
                    errors="coerce",
                    utc=True
                )

        except Exception:

            df["timestamp"] = pd.to_datetime(
                df["timestamp"],
                errors="coerce",
                utc=True
            )

        df = df.dropna(
            subset=[
                "timestamp",
                "ltp"
            ]
        ).copy()

        if df.empty:
            return df

        return df.sort_values(
            "timestamp"
        ).reset_index(
            drop=True
        )

    # ==================================================
    # TIME WINDOW
    # ==================================================

    @staticmethod
    def _window(
        df,
        now,
        minutes
    ):

        if df.empty:
            return df

        start = (
            now
            - pd.Timedelta(
                minutes=minutes
            )
        )

        return df[
            df["timestamp"] >= start
        ]

    # ==================================================
    # METRICS
    # ==================================================

    @classmethod
    def metrics(cls, ticks):

        df = cls.dataframe(
            ticks
        )

        if df.empty:

            return {
                "etq_5m": 0.0,
                "etq_20m": 0.0,
                "etq_60m": 0.0,
                "avg_ltp_20m": None,
                "avg_ltp_60m": None,
                "avg_ltq_2m": 0.0,
                "avg_ltq_5m": 0.0,
                "ltq_latest": 0.0,
                "bid_qty_latest": 0.0,
                "ask_qty_latest": 0.0,
                "order_imbalance": 0.0,
                "tick_count": 0,
            }

        now = df["timestamp"].max()

        d2 = cls._window(
            df,
            now,
            2
        )

        d5 = cls._window(
            df,
            now,
            5
        )

        d20 = cls._window(
            df,
            now,
            20
        )

        d60 = cls._window(
            df,
            now,
            60
        )

        latest = df.iloc[-1]

        # ==================================================
        # ETQ
        # ==================================================

        etq_5m = float(
            d5["ltq"].sum()
        )

        etq_20m = float(
            d20["ltq"].sum()
        )

        etq_60m = float(
            d60["ltq"].sum()
        )

        # ==================================================
        # AVERAGE LTP
        # ==================================================

        avg_ltp_20m = (
            float(
                d20["ltp"].mean()
            )
            if not d20.empty
            else None
        )

        avg_ltp_60m = (
            float(
                d60["ltp"].mean()
            )
            if not d60.empty
            else None
        )

        # ==================================================
        # LTQ
        # ==================================================

        avg_ltq_2m = (
            float(
                d2["ltq"].mean()
            )
            if not d2.empty
            else 0.0
        )

        avg_ltq_5m = (
            float(
                d5["ltq"].mean()
            )
            if not d5.empty
            else 0.0
        )

        ltq_latest = float(
            latest["ltq"]
        )

        # ==================================================
        # LIVE DEPTH
        # ==================================================

        bid_qty_latest = float(
            latest.get(
                "bid_qty",
                0
            ) or 0
        )

        ask_qty_latest = float(
            latest.get(
                "ask_qty",
                0
            ) or 0
        )

        # ==================================================
        # ORDER IMBALANCE
        #
        # Range approximately:
        # -1 = completely sell-side
        #  0 = balanced
        # +1 = completely buy-side
        # ==================================================

        total_depth = (
            bid_qty_latest
            + ask_qty_latest
        )

        if total_depth > 0:

            order_imbalance = (
                bid_qty_latest
                - ask_qty_latest
            ) / total_depth

        else:

            order_imbalance = 0.0

        return {

            "etq_5m": etq_5m,

            "etq_20m": etq_20m,

            "etq_60m": etq_60m,

            "avg_ltp_20m": avg_ltp_20m,

            "avg_ltp_60m": avg_ltp_60m,

            "avg_ltq_2m": avg_ltq_2m,

            "avg_ltq_5m": avg_ltq_5m,

            "ltq_latest": ltq_latest,

            "bid_qty_latest": bid_qty_latest,

            "ask_qty_latest": ask_qty_latest,

            "order_imbalance": float(
                order_imbalance
            ),

            "tick_count": int(
                len(df)
            ),
        }