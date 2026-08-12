def normalize_tick(data):

    if not isinstance(data, dict):
        return {}

    raw_ltp = data.get(
        "last_traded_price",
        0
    )

    try:
        ltp = float(raw_ltp) / 100.0
    except Exception:
        ltp = 0.0

    buys = (
        data.get(
            "best_5_buy_data",
            []
        )
        or []
    )

    sells = (
        data.get(
            "best_5_sell_data",
            []
        )
        or []
    )

    best_bid = 0.0
    bid_qty = 0

    best_ask = 0.0
    ask_qty = 0

    if buys:

        try:

            best_bid = (
                float(
                    buys[0].get(
                        "price",
                        0
                    )
                )
                / 100.0
            )

            bid_qty = int(
                buys[0].get(
                    "quantity",
                    0
                )
            )

        except Exception:
            pass

    if sells:

        try:

            best_ask = (
                float(
                    sells[0].get(
                        "price",
                        0
                    )
                )
                / 100.0
            )

            ask_qty = int(
                sells[0].get(
                    "quantity",
                    0
                )
            )

        except Exception:
            pass

    total_buy = float(
        data.get(
            "total_buy_quantity",
            0
        )
        or 0
    )

    total_sell = float(
        data.get(
            "total_sell_quantity",
            0
        )
        or 0
    )

    return {

        "symbol": str(
            data.get(
                "token",
                ""
            )
        ),

        "timestamp": data.get(
            "exchange_timestamp"
        ),

        "ltp": ltp,

        "ltq": int(
            data.get(
                "last_traded_quantity",
                0
            )
            or 0
        ),

        "volume": int(
            data.get(
                "volume_trade_for_the_day",
                0
            )
            or 0
        ),

        "total_buy_quantity": total_buy,

        "total_sell_quantity": total_sell,

        "best_5_buy": buys,

        "best_5_sell": sells,

        "bid_price": best_bid,

        "bid_qty": bid_qty,

        "ask_price": best_ask,

        "ask_qty": ask_qty,
    }

# def normalize_tick(data):
#     tick = {
#         "symbol": data.get("token"),
#         "timestamp": data.get("exchange_timestamp"),
#         "ltp": data.get("last_traded_price", 0) / 100,
#         "ltq": data.get("last_traded_quantity", 0),
#         "volume": data.get("volume_trade_for_the_day", 0),
#         "total_buy_quantity": data.get("total_buy_quantity", 0),
#         "total_sell_quantity": data.get("total_sell_quantity", 0),
#         "best_5_buy": data.get("best_5_buy_data", []),
#         "best_5_sell": data.get("best_5_sell_data", []),
#     }

#     buys = tick["best_5_buy"]
#     sells = tick["best_5_sell"]

#     best_bid = 0
#     bid_qty = 0
#     best_ask = 0
#     ask_qty = 0

#     if buys:
#         best_bid = buys[0].get("price", 0) / 100
#         bid_qty = buys[0].get("quantity", 0)

#     if sells:
#         best_ask = sells[0].get("price", 0) / 100
#         ask_qty = sells[0].get("quantity", 0)

#     tick.update({
#         "bid_price": best_bid,
#         "bid_qty": bid_qty,
#         "ask_price": best_ask,
#         "ask_qty": ask_qty,
#     })

#     return tick