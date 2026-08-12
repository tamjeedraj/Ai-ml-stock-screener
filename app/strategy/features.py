import math


def _safe_float(
    value,
    default=0.0
):

    try:

        value = float(value)

        if not math.isfinite(value):
            return default

        return value

    except Exception:

        return default


def _safe_int(
    value,
    default=0
):

    try:

        value = int(
            float(value)
        )

        return value

    except Exception:

        return default


def build_features(
    current,
    metrics
):

    if not isinstance(
        current,
        dict
    ):
        current = {}

    if not isinstance(
        metrics,
        dict
    ):
        metrics = {}

    # ==================================================
    # CURRENT MARKET VALUES
    # ==================================================

    smma20 = _safe_float(
        current.get(
            "smma20",
            0
        )
    )

    smma120 = _safe_float(
        current.get(
            "smma120",
            0
        )
    )

    ltp = _safe_float(
        current.get(
            "ltp",
            0
        )
    )

    bid_qty = _safe_int(
        current.get(
            "bid_qty",
            0
        )
    )

    ask_qty = _safe_int(
        current.get(
            "ask_qty",
            0
        )
    )

    # ==================================================
    # SMMA DISTANCE
    # ==================================================

    if smma120 != 0:

        smma_distance = (
            smma20 - smma120
        ) / abs(
            smma120
        )

    else:

        smma_distance = 0.0

    # ==================================================
    # TRADE QUANTITY RATIO
    # ==================================================

    avg_ltq_2m = _safe_float(
        metrics.get(
            "avg_ltq_2m",
            0
        )
    )

    avg_ltq_5m = _safe_float(
        metrics.get(
            "avg_ltq_5m",
            0
        )
    )

    if avg_ltq_5m > 0:

        ltq_ratio = (
            avg_ltq_2m
            / avg_ltq_5m
        )

    else:

        ltq_ratio = 0.0

    # ==================================================
    # ETQ
    # ==================================================

    etq_5m = _safe_float(
        metrics.get(
            "etq_5m",
            0
        )
    )

    etq_20m = _safe_float(
        metrics.get(
            "etq_20m",
            0
        )
    )

    etq_60m = _safe_float(
        metrics.get(
            "etq_60m",
            0
        )
    )

    # ==================================================
    # ORDER IMBALANCE
    # ==================================================

    total_depth = (
        bid_qty
        + ask_qty
    )

    if total_depth > 0:

        order_imbalance = (
            bid_qty - ask_qty
        ) / total_depth

    else:

        order_imbalance = 0.0

    # ==================================================
    # LIMIT EXTREME VALUES
    # ==================================================

    ltq_ratio = max(
        -10.0,
        min(
            10.0,
            ltq_ratio
        )
    )

    smma_distance = max(
        -1.0,
        min(
            1.0,
            smma_distance
        )
    )

    order_imbalance = max(
        -1.0,
        min(
            1.0,
            order_imbalance
        )
    )

    # ==================================================
    # FINAL ML FEATURES
    # ==================================================

    return {

        "ltq_ratio": float(
            ltq_ratio
        ),

        "etq_5m": float(
            etq_5m
        ),

        "etq_20m": float(
            etq_20m
        ),

        "etq_60m": float(
            etq_60m
        ),

        "smma_distance": float(
            smma_distance
        ),

        "order_imbalance": float(
            order_imbalance
        ),

        "ltp": float(
            max(
                0.0,
                ltp
            )
        ),

        "bid_qty": float(
            max(
                0,
                bid_qty
            )
        ),

        "ask_qty": float(
            max(
                0,
                ask_qty
            )
        ),
    }