import pandas as pd


# ==================================================
# SMMA / SMMA (WILDER'S MOVING AVERAGE)
# ==================================================

def smma(
    series: pd.Series,
    period: int
) -> pd.Series:

    if period <= 0:

        raise ValueError(
            "SMMA period must be greater than 0"
        )

    values = pd.to_numeric(
        series,
        errors="coerce"
    )

    result = pd.Series(
        float("nan"),
        index=values.index,
        dtype=float
    )

    if len(values) < period:
        return result

    # ----------------------------------------------
    # Initial SMMA = SMA
    # ----------------------------------------------

    first_values = values.iloc[
        :period
    ]

    if first_values.isna().all():
        return result

    initial = first_values.mean()

    if pd.isna(initial):
        return result

    result.iloc[
        period - 1
    ] = float(initial)

    # ----------------------------------------------
    # Wilder SMMA
    # ----------------------------------------------

    for i in range(
        period,
        len(values)
    ):

        previous = result.iloc[
            i - 1
        ]

        current = values.iloc[
            i
        ]

        if pd.isna(current):

            result.iloc[i] = previous

            continue

        if pd.isna(previous):

            result.iloc[i] = float(
                current
            )

            continue

        result.iloc[i] = (
            (
                previous
                * (period - 1)
            )
            + current
        ) / period

    return result


# ==================================================
# ADD SMMA INDICATORS
# ==================================================

def add_smma(df):

    if df is None:
        return pd.DataFrame()

    if df.empty:
        return df.copy()

    df = df.copy()

    # ----------------------------------------------
    # Ensure close is numeric
    # ----------------------------------------------

    df["close"] = pd.to_numeric(
        df["close"],
        errors="coerce"
    )

    # ----------------------------------------------
    # Remove invalid close rows
    # ----------------------------------------------

    df = df.dropna(
        subset=["close"]
    ).copy()

    if df.empty:

        df["smma20"] = pd.Series(
            dtype=float
        )

        df["smma120"] = pd.Series(
            dtype=float
        )

        return df

    # ----------------------------------------------
    # Sort historical candles
    # ----------------------------------------------

    if "timestamp" in df.columns:

        df["timestamp"] = pd.to_datetime(
            df["timestamp"],
            errors="coerce",
            utc=True
        )

        df = df.dropna(
            subset=["timestamp"]
        ).copy()

        df = df.sort_values(
            "timestamp"
        )

        # Remove duplicate candles
        df = df.drop_duplicates(
            subset=["timestamp"],
            keep="last"
        )

        df = df.reset_index(
            drop=True
        )

    # ----------------------------------------------
    # SMMA 20
    # ----------------------------------------------

    df["smma20"] = smma(
        df["close"],
        20
    )

    # ----------------------------------------------
    # SMMA 120
    # ----------------------------------------------

    df["smma120"] = smma(
        df["close"],
        120
    )

    return df